import os
import yaml
from typing import Dict, Any, List, Optional
import logging
from pathlib import Path

class ConfigLoader:
    """Handles loading and parsing of import configuration"""
    
    POTENTIAL_PATHS = [
        '/var/www/html/config/import_config.yaml',
        os.path.join(os.path.dirname(__file__), 'config.yaml'),
        os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml'),
        '/etc/etl_processor/config.yaml'
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the configuration loader"""
        self.logger = logging.getLogger(__name__)
        
        # Default to standard locations if no path provided
        if config_path is None:
            config_path = next(
                (path for path in self.POTENTIAL_PATHS if os.path.exists(path)), 
                None
            )
        
        if not config_path or not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Configuration file not found. Checked paths: {self.POTENTIAL_PATHS}"
            )
        
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as config_file:
                return yaml.safe_load(config_file)
                
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise

    def get_import_types(self) -> List[str]:
        """Get list of configured import types"""
        return list(self.config.get('imports', {}).keys())

    def get_import_config(self, import_type: str) -> Dict[str, Any]:
        """Get configuration for specific import type"""
        try:
            imports = self.config.get('imports', {})
            import_config = imports.get(import_type)
            
            if not import_config:
                raise ValueError(f"No configuration found for import type: {import_type}")
            
            return import_config
            
        except Exception as e:
            self.logger.error(f"Error retrieving import configuration: {e}")
            raise

    def get_reference_order(self, import_type: str) -> List[str]:
        """Get reference file processing order for import type"""
        import_config = self.get_import_config(import_type)
        return import_config.get('reference_order', [])

    def get_mappings(self, import_type: str) -> Dict[str, Any]:
        """Get field mappings for import type"""
        import_config = self.get_import_config(import_type)
        return import_config.get('mappings', {})

    def get_sender_email(self, import_type: str) -> str:
        """Get sender email for import type"""
        import_config = self.get_import_config(import_type)
        return import_config.get('sender_email')

    def get_primary_attachment_filename(self, import_type: str) -> str:
        """Get primary attachment filename for import type"""
        import_config = self.get_import_config(import_type)
        return import_config.get('primary_attachment')

    def get_security_rules(self, import_type: str) -> Dict[str, Any]:
        """Get security rules for import type"""
        import_config = self.get_import_config(import_type)
        return import_config.get('security', {})

    def get_file_validation_rules(self, import_type: str) -> Dict[str, Any]:
        """Get file validation rules for import type"""
        security_config = self.get_security_rules(import_type)
        return security_config.get('file_validation', {})

    def get_field_mapping(self, import_type: str, file_name: str) -> Dict[str, Any]:
        """Get field mapping for specific file in import type"""
        mappings = self.get_mappings(import_type)
        mapping = mappings.get(file_name)
        
        if not mapping:
            raise ValueError(f"No mapping found for file {file_name} in {import_type}")
            
        return mapping

    def get_database_config(self, import_type: str) -> Dict[str, Any]:
        """Get database configuration for import type"""
        import_config = self.get_import_config(import_type)
        return import_config.get('database', {})

    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()