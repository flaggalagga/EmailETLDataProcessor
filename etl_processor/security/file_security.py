import os
import magic
import zipfile
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path
import defusedxml.ElementTree as ET
from xml.etree.ElementTree import Element
import clamd
from ..config.config_loader import ConfigLoader

class SecureFileProcessor:
    """Handles secure file processing with import-specific validation"""
    
    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """Initialize the file security processor"""
        self.logger = logging.getLogger(__name__)
        self.config_loader = config_loader
        self.clamd = None
        try:
            self.clamd = clamd.ClamdUnixSocket()
        except Exception as e:
            self.logger.warning(f"Could not initialize ClamAV: {e}")

    def validate_file(self, file_path: str, import_type: str) -> bool:
        """
        Validate file according to import-specific rules
        
        Args:
            file_path: Path to file to validate
            import_type: Type of import
        """
        try:
            if not self.config_loader:
                self.logger.warning("No config loader provided - using default validation")
                return True

            security_config = self.config_loader.get_security_rules(import_type)
            file_validation = security_config.get('file_validation', {})
            
            # Get file info
            file_size = os.path.getsize(file_path)
            mime_type = magic.from_file(file_path, mime=True)
            file_ext = Path(file_path).suffix.lower()
            
            # Convert max_size to bytes
            max_size = self._parse_size(file_validation.get('max_size', '50MB'))
            
            # Check file size
            if file_size > max_size:
                raise ValueError(f"File exceeds maximum size of {file_validation['max_size']}")
            
            # Explicitly validate ZIP file
            if file_ext == '.zip':
                if mime_type not in ['application/zip', 'application/x-zip-compressed']:
                    raise ValueError(f"Invalid ZIP file MIME type: {mime_type}")
            
            # Rest of the validation remains the same
            return True
                
        except Exception as e:
            self.logger.error(f"File validation error: {str(e)}")
            raise


    def secure_extract_zip(self, zip_path: str, extract_dir: str, import_type: str) -> List[str]:
            """
            Securely extract ZIP file according to import-specific rules
            
            Args:
                zip_path: Path to ZIP file
                extract_dir: Directory to extract to
                import_type: Type of import
                
            Returns:
                List of extracted file paths
            """
            try:
                security_config = self.config_loader.get_security_rules(import_type)
                zip_config = security_config.get('file_validation', {}).get('zip_extraction', {})
                
                # Log ZIP configuration
                self.logger.debug(f"ZIP validation config for {import_type}:")
                self.logger.debug(f"Max ratio: {zip_config.get('max_ratio', 15)}")
                self.logger.debug(f"Max files: {zip_config.get('max_files', 200)}")
                self.logger.debug(f"Max file size: {zip_config.get('max_file_size', '50MB')}")
                
                with zipfile.ZipFile(zip_path) as zip_ref:
                    # Check number of files
                    num_files = len(zip_ref.namelist())
                    max_files = zip_config.get('max_files', 200)
                    self.logger.debug(f"Number of files in ZIP: {num_files}")
                    if num_files > max_files:
                        raise ValueError(f"ZIP contains too many files (max {max_files})")
                    
                    # Check compression ratio
                    uncompressed_size = sum(info.file_size for info in zip_ref.filelist)
                    compressed_size = os.path.getsize(zip_path)
                    max_ratio = zip_config.get('max_ratio', 15)
                    
                    self.logger.info(f"ZIP stats for {os.path.basename(zip_path)}:")
                    self.logger.info(f"Compressed size: {compressed_size:,} bytes")
                    self.logger.info(f"Uncompressed size: {uncompressed_size:,} bytes")
                    
                    if compressed_size > 0:  # Avoid division by zero
                        ratio = uncompressed_size / compressed_size
                        self.logger.info(f"Compression ratio: {ratio:.2f}")
                        if ratio > max_ratio:
                            raise ValueError(f"Compression ratio too high: {ratio:.2f} (max {max_ratio})")
            
                    
                    # Check individual file sizes
                    max_file_size = self._parse_size(zip_config['max_file_size'])
                    for info in zip_ref.filelist:
                        if info.file_size > max_file_size:
                            raise ValueError(
                                f"File {info.filename} exceeds maximum size of {zip_config['max_file_size']}"
                            )
                    
                    # Check for directory traversal
                    for file_path in zip_ref.namelist():
                        if file_path.startswith('/') or '..' in file_path:
                            raise ValueError(f"Potential directory traversal attack in {file_path}")
                        
                        # Check file extensions
                        if not any(file_path.lower().endswith(ext) for ext in zip_config['allowed_types']):
                            raise ValueError(f"Invalid file type in ZIP: {file_path}")
                    
                    # Extract and validate each file
                    extracted_files = []
                    for file_path in zip_ref.namelist():
                        # Make the extraction path safe
                        safe_path = os.path.join(extract_dir, os.path.basename(file_path))
                        
                        # Extract file
                        zip_ref.extract(file_path, extract_dir)
                        extracted_path = os.path.join(extract_dir, file_path)
                        
                        if os.path.isfile(extracted_path):
                            # Validate extracted file
                            self.validate_file(extracted_path, import_type)
                            extracted_files.append(extracted_path)
                    
                    return extracted_files
                    
            except Exception as e:
                self.logger.error(f"ZIP extraction error: {str(e)}")
                raise

    def _validate_xml(self, file_path: str, xml_config: Dict) -> bool:
        """
        Validate XML file
        
        Args:
            file_path: Path to XML file
            xml_config: XML validation configuration
        """
        try:
            # Configure parser security options
            if xml_config.get('disable_entities', True):
                ET.set_disable_entities()
            if xml_config.get('disable_dtd', True):
                ET.set_disable_dtd()
                
            # Parse XML
            tree = ET.parse(file_path)
            
            # Check depth
            max_depth = xml_config.get('max_depth', 100)
            depth = self._get_xml_depth(tree.getroot())
            
            if depth > max_depth:
                raise ValueError(f"XML depth exceeds maximum of {max_depth}")
            
            # Get validation rules
            rules = xml_config.get('validation_rules', {})
            
            # Validate against rules
            if rules:
                self._validate_xml_rules(tree.getroot(), rules)
            
            return True
            
        except Exception as e:
            self.logger.error(f"XML validation error: {str(e)}")
            raise

    def _validate_json(self, file_path: str, json_config: Dict) -> bool:
        """
        Validate JSON file
        
        Args:
            file_path: Path to JSON file
            json_config: JSON validation configuration
        """
        try:
            with open(file_path) as f:
                content = f.read()
                
            # Check string length
            max_string = json_config.get('max_string_length', 10000)
            if len(content) > max_string:
                raise ValueError(f"JSON content exceeds maximum length of {max_string}")
            
            # Parse JSON
            data = json.loads(content)
            
            # Check depth
            max_depth = json_config.get('max_depth', 50)
            depth = self._get_json_depth(data)
            
            if depth > max_depth:
                raise ValueError(f"JSON depth exceeds maximum of {max_depth}")
            
            # Validate arrays
            max_array = json_config.get('max_array_length', 1000)
            self._check_array_lengths(data, max_array)
            
            return True
            
        except Exception as e:
            self.logger.error(f"JSON validation error: {str(e)}")
            raise

    def _validate_xml_rules(self, element: Element, rules: Dict):
        """Validate XML against rules"""
        tag = element.tag
        
        # Check tag rules
        if tag in rules:
            tag_rules = rules[tag]
            
            # Check required attributes
            required_attrs = tag_rules.get('required_attributes', [])
            for attr in required_attrs:
                if attr not in element.attrib:
                    raise ValueError(f"Missing required attribute {attr} in {tag}")
            
            # Check attribute values
            attr_values = tag_rules.get('attribute_values', {})
            for attr, values in attr_values.items():
                if attr in element.attrib and element.attrib[attr] not in values:
                    raise ValueError(
                        f"Invalid value for attribute {attr} in {tag}: {element.attrib[attr]}")

            # Check text content
            text_rules = tag_rules.get('text_content', {})
            if text_rules:
                text = element.text or ''
                
                # Check max length
                max_length = text_rules.get('max_length')
                if max_length and len(text) > max_length:
                    raise ValueError(f"Text content too long in {tag}")
                
                # Check pattern
                pattern = text_rules.get('pattern')
                if pattern and not re.match(pattern, text):
                    raise ValueError(f"Invalid text content format in {tag}")

        # Recursively validate children
        for child in element:
            self._validate_xml_rules(child, rules)

    def _check_array_lengths(self, data: any, max_length: int):
        """Recursively check array lengths in JSON data"""
        if isinstance(data, list):
            if len(data) > max_length:
                raise ValueError(f"Array length exceeds maximum of {max_length}")
            for item in data:
                self._check_array_lengths(item, max_length)
        elif isinstance(data, dict):
            for value in data.values():
                self._check_array_lengths(value, max_length)

    def _get_xml_depth(self, element: Element, current_depth: int = 1) -> int:
        """Get maximum depth of XML tree"""
        child_depths = [
            self._get_xml_depth(child, current_depth + 1)
            for child in element
        ]
        return max([current_depth] + child_depths)

    def _get_json_depth(self, data: any, current_depth: int = 1) -> int:
        """Get maximum depth of JSON data"""
        if isinstance(data, dict):
            if not data:
                return current_depth
            return max(
                self._get_json_depth(value, current_depth + 1)
                for value in data.values()
            )
        elif isinstance(data, list):
            if not data:
                return current_depth
            return max(
                self._get_json_depth(item, current_depth + 1)
                for item in data
            )
        return current_depth

    def _scan_file(self, file_path: str) -> bool:
        """
        Scan file for malware using ClamAV
        
        Args:
            file_path: Path to file to scan
            
        Returns:
            True if file is clean, False if malware detected
        """
        try:
            if not self.clamd:
                self.logger.warning("ClamAV not available - skipping malware scan")
                return True
                
            # Scan file
            with open(file_path, 'rb') as f:
                scan_result = self.clamd.instream(f)
            
            # Check result
            status = scan_result['stream'][0]
            return status == 'OK'
            
        except Exception as e:
            self.logger.error(f"Malware scan error: {str(e)}")
            return False

    def _parse_size(self, size_str: str) -> int:
        """
        Convert size string (e.g., '50MB') to bytes
        
        Args:
            size_str: Size string with unit
            
        Returns:
            Size in bytes
        """
        # Handle empty/none
        if not size_str:
            return 0
            
        # Strip whitespace and convert to uppercase
        size_str = size_str.strip().upper()
        
        # Define size units
        units = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 * 1024,
            'GB': 1024 * 1024 * 1024,
            'TB': 1024 * 1024 * 1024 * 1024
        }
        
        # Find unit in string
        unit = None
        number = None
        for u in sorted(units.keys(), key=len, reverse=True):
            if size_str.endswith(u):
                unit = u
                number = size_str[:-len(u)]
                break
        
        if unit is None:
            # Assume bytes if no unit specified
            try:
                return int(size_str)
            except ValueError:
                raise ValueError(f"Invalid size format: {size_str}")
        
        try:
            # Convert size to bytes
            return int(float(number) * units[unit])
        except ValueError:
            raise ValueError(f"Invalid size format: {size_str}")

    def _validate_zip(self, file_path: str, zip_config: Dict) -> bool:
        """
        Validate ZIP file structure
        
        Args:
            file_path: Path to ZIP file
            zip_config: ZIP validation configuration
        """
        try:
            with zipfile.ZipFile(file_path) as zip_ref:
                # Check CRC
                if zip_config.get('check_crc', True):
                    test_result = zip_ref.testzip()
                    if test_result is not None:
                        raise ValueError(f"CRC check failed for {test_result}")
                
                # Validate structure
                file_list = zip_ref.namelist()
                
                # Check number of files
                max_files = zip_config.get('max_files', 100)
                if len(file_list) > max_files:
                    raise ValueError(f"Too many files in ZIP: {len(file_list)} (max {max_files})")
                
                # Check for required files
                required_files = zip_config.get('required_files', [])
                for required in required_files:
                    if not any(f.endswith(required) for f in file_list):
                        raise ValueError(f"Required file missing: {required}")
                
                # Check for allowed file types
                allowed_types = zip_config.get('allowed_types', [])
                if allowed_types:
                    for file_name in file_list:
                        ext = Path(file_name).suffix.lower()
                        if ext not in allowed_types:
                            raise ValueError(f"Invalid file type in ZIP: {ext}")
                
                # Validate individual file sizes
                max_file_size = self._parse_size(zip_config.get('max_file_size', '10MB'))
                for info in zip_ref.filelist:
                    if info.file_size > max_file_size:
                        raise ValueError(
                            f"File {info.filename} exceeds maximum size of {max_file_size} bytes"
                        )
                
                return True
                
        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid ZIP file: {str(e)}")
        except Exception as e:
            raise ValueError(f"ZIP validation error: {str(e)}")