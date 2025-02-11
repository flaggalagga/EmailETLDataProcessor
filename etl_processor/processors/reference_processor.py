import os
import logging
from typing import List, Dict, Tuple
from datetime import datetime
from sqlalchemy import text, Column, Integer
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import defusedxml.ElementTree as ET
import json
from pathlib import Path

from .base_processor import BaseProcessor
from ..config.config_loader import ConfigLoader
from ..utils.data_converter import convert_field
from ..utils.file_hash_tracker import FileHashTracker

class ReferenceProcessor(BaseProcessor):
    """Handles processing of reference data files"""

    def __init__(self, is_cron: bool = False, force_process: bool = False):
        """Initialize reference processor"""
        super().__init__(is_cron=is_cron)
        self.config_loader = ConfigLoader()
        self.file_hash_tracker = FileHashTracker(is_cron=is_cron)
        self.force_process = force_process
        self._lookup_cache = {}

    async def process_reference_files(self, temp_dir: str, import_type: str, session: Session) -> Tuple[List[str], List[str]]:
            """Process all reference files for an import type"""
            self.update_progress('process', 'working')
            processed_files = []
            skipped_files = []
            
            try:
                reference_order = self.config_loader.get_reference_order(import_type)
                total_refs = len(reference_order)
                processed = 0
                
                for ref_file in reference_order:
                    file_path = os.path.join(temp_dir, ref_file)
                    
                    if os.path.exists(file_path):
                        try:
                            # Process file
                            self._process_file(file_path, import_type, session)
                            
                            # Explicitly commit after each file
                            session.commit()
                            
                            processed_files.append(ref_file)
                            processed += 1
                            progress = int((processed / total_refs) * 100)
                            self.update_progress('process', 'working', progress)
                            
                        except Exception as e:
                            session.rollback()  # Rollback on error
                            self.logger.error(f"Error processing {ref_file}: {str(e)}")
                            raise
                    else:
                        self.logger.warning(f"File not found: {file_path}")
                        skipped_files.append(ref_file)
                
                return processed_files, skipped_files
                    
            except Exception as e:
                raise self.handle_error("Reference processing failed", e, session)

    def _perform_lookup(self, session: Session, table: str, query: str, value: str) -> any:
        """Perform database lookup with NULL fallback"""
        try:
            # Check cache first
            cache_key = f"{table}:{value}"
            if cache_key in self._lookup_cache:
                self.logger.debug(f"Cache hit for {cache_key}")
                return self._lookup_cache[cache_key]
            
            # Format the query with the table name
            formatted_query = query.format(table=table)
            self.logger.debug(f"Executing lookup query: {formatted_query} with value: {value}")
            
            # Execute lookup query
            result = session.execute(text(formatted_query), {'value': value}).scalar()
            self.logger.debug(f"Lookup {value} in {table} returned: {result}")
            
            # Cache result (even if None)
            self._lookup_cache[cache_key] = result
            return result
            
        except Exception as e:
            self.logger.error(f"Lookup error for value {value} in {table}: {str(e)}")
            return None

    def _process_file(self, file_path: str, import_type: str, session: Session):
        """Process a single reference file"""
        # Get file info
        file_name = os.path.basename(file_path)
        file_ext = Path(file_path).suffix.lower()
        
        try:
            # Get mapping for this file
            mapping = self.config_loader.get_field_mapping(import_type, file_name)
            
            # Process based on file type
            if file_ext == '.xml':
                self._process_xml_file(file_path, mapping, session)
            elif file_ext == '.json':
                self._process_json_file(file_path, mapping, session)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
                
        except Exception as e:
            raise self.handle_error(f"Error processing {file_name}", e, session)

    def _process_xml_file(self, file_path: str, mapping: Dict, session: Session):
        """Process XML reference file"""
        try:
            self.logger.info(f"Processing XML file: {file_path}")
            
            # Parse XML safely
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Get table configurations
            table_configs = mapping.get('tables', [])
            if not table_configs:
                table_configs = [{'name': mapping['table'], 'fields': mapping['fields']}]
            
            self.logger.info(f"Processing {len(table_configs)} table configurations")
            
            # Process each table configuration
            for table_config in table_configs:
                table_name = table_config['name']
                root_element = table_config.get('root_element', '')
                
                self.logger.info(f"Processing table: {table_name}")
                self.logger.info(f"Root element: '{root_element}'")
                
                # Find elements to process
                elements = root.findall(f".//{root_element}") if root_element else [root]
                self.logger.info(f"Found {len(elements)} elements to process")
                
                processed = 0
                for elem in elements:
                    data = {}
                    
                    # Process fields according to mapping
                    for xml_key, field_config in table_config['fields'].items():
                        field_elem = elem.find(f".//{xml_key}")
                        if field_elem is not None and field_elem.text:
                            value = field_elem.text.strip()
                            
                            # Handle lookup fields
                            if 'lookup' in field_config:
                                lookup_config = field_config['lookup']
                                lookup_value = self._perform_lookup(
                                    session,
                                    lookup_config['table'],
                                    lookup_config['query'],
                                    value
                                )
                                # Set value to None if lookup fails (instead of raising error)
                                data[field_config['db_field']] = lookup_value
                                if lookup_value is None:
                                    self.logger.warning(
                                        f"No matching record found in {lookup_config['table']} "
                                        f"for value: {value} - setting to NULL"
                                    )
                            else:
                                # Regular field conversion
                                converted = convert_field(
                                    value,
                                    field_config['type'],
                                    field_config.get('format')
                                )
                                if converted is not None:
                                    data[field_config['db_field']] = converted
                    
                    # Add timestamps
                    now = datetime.utcnow()
                    if 'created' not in data:
                        data['created'] = now
                    if 'modified' not in data:
                        data['modified'] = now
                    
                    # Save to database
                    if data:
                        self._save_record(table_name, data, session)
                        processed += 1
                        if processed % 100 == 0:
                            self.logger.info(f"Processed {processed} records for {table_name}")
                
                self.logger.info(f"Total records processed for {table_name}: {processed}")
                
        except Exception as e:
            self.logger.error("Error processing XML file", exc_info=True)
            raise

    def _process_json_file(self, file_path: str, mapping: Dict, session: Session):
        """Process JSON reference file"""
        try:
            self.logger.info(f"Processing JSON file: {file_path}")
            
            # Read JSON file
            with open(file_path) as f:
                records = json.load(f)
            
            # Handle both single record and array
            if not isinstance(records, list):
                records = [records]
            
            self.logger.info(f"Processing {len(records)} records")
            
            # Process each record
            for record in records:
                data = {}
                
                # Process fields according to mapping
                for json_key, field_config in mapping['fields'].items():
                    value = record.get(json_key)
                    if value is not None:
                        if 'lookup' in field_config:
                            lookup_config = field_config['lookup']
                            lookup_value = self._perform_lookup(
                                session,
                                lookup_config['table'],
                                lookup_config['query'],
                                str(value)
                            )
                            if lookup_value is not None:
                                data[field_config['db_field']] = lookup_value
                        else:
                            converted = convert_field(
                                value,
                                field_config['type'],
                                field_config.get('format')
                            )
                            if converted is not None:
                                data[field_config['db_field']] = converted
                
                # Add timestamps
                now = datetime.utcnow()
                if 'created' not in data:
                    data['created'] = now
                if 'modified' not in data:
                    data['modified'] = now
                
                # Save to database
                if data:
                    self._save_record(mapping['table'], data, session)
                
        except Exception as e:
            self.logger.error("Error processing JSON file", exc_info=True)
            raise

    def _save_record(self, table_name: str, data: Dict, session: Session):
        """Save or update database record"""
        try:
            # Get primary key
            primary_key = data.get('id') or data.get('code')
            
            if primary_key is not None:
                # Build column list excluding NULL values
                columns = [k for k, v in data.items() if v is not None]
                values = {k: v for k, v in data.items() if v is not None}
                
                # Construct base query
                query = f"""
                    INSERT INTO {table_name} ({', '.join(columns)})
                    VALUES ({', '.join([':' + col for col in columns])})
                """
                
                # Add ON DUPLICATE KEY UPDATE clause
                update_cols = [col for col in columns if col not in ('id', 'code')]
                if update_cols:
                    updates = [f"{col} = VALUES({col})" for col in update_cols]
                    query += f" ON DUPLICATE KEY UPDATE {', '.join(updates)}"
                
                # Execute query
                session.execute(text(query), values)
                session.flush()
                
        except IntegrityError as e:
            self.logger.warning(f"Integrity error in {table_name}: {str(e)}")
            session.rollback()
        except Exception as e:
            self.logger.error(f"Error saving to {table_name}: {str(e)}")
            raise

    def clear_lookup_cache(self):
        """Clear the lookup cache"""
        self._lookup_cache.clear()