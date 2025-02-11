# tests/test_config_loader.py

import pytest
import os
import yaml
from unittest.mock import patch, mock_open
from etl_processor.config.config_loader import ConfigLoader

@pytest.fixture
def sample_config():
    return {
        'imports': {
            'test_import': {
                'name': 'Test Import',
                'sender_email': 'test@example.com',
                'primary_attachment': 'test.zip',
                'days_lookback': 30,
                'inboxes': ['INBOX', 'Archive'],
                'security': {
                    'email_checks': ['spf', 'dkim'],
                    'file_validation': {
                        'max_size': '50MB',
                        'allowed_types': ['.xml', '.json']
                    }
                },
                'reference_order': ['ref1.xml', 'ref2.xml'],
                'mappings': {
                    'test.xml': {
                        'table': 'test_table',
                        'fields': {
                            'id': {'db_field': 'id', 'type': 'integer'},
                            'name': {'db_field': 'name', 'type': 'string'}
                        }
                    }
                }
            }
        }
    }

@pytest.fixture
def config_file(tmp_path, sample_config):
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(sample_config, f)
    return str(config_path)

@pytest.fixture
def mock_logger():
    with patch('etl_processor.config.config_loader.logging') as mock_log:
        yield mock_log.getLogger.return_value

def test_init_with_config_path(config_file, sample_config):
    """Test initialization with specific config path"""
    loader = ConfigLoader(config_file)
    assert loader.config_path == config_file
    assert loader.config == sample_config

def test_init_without_config_path():
    """Test initialization without config path"""
    with pytest.raises(FileNotFoundError):
        ConfigLoader('nonexistent.yaml')

def test_get_import_types(config_file):
    """Test getting import types"""
    loader = ConfigLoader(config_file)
    types = loader.get_import_types()
    assert types == ['test_import']

def test_get_import_config(config_file):
    """Test getting specific import configuration"""
    loader = ConfigLoader(config_file)
    config = loader.get_import_config('test_import')
    assert config['name'] == 'Test Import'
    assert config['sender_email'] == 'test@example.com'

def test_get_import_config_invalid(config_file):
    """Test getting invalid import type"""
    loader = ConfigLoader(config_file)
    with pytest.raises(ValueError, match="No configuration found for import type"):
        loader.get_import_config('invalid_type')

def test_get_security_rules(config_file):
    """Test getting security rules"""
    loader = ConfigLoader(config_file)
    rules = loader.get_security_rules('test_import')
    assert rules['email_checks'] == ['spf', 'dkim']
    assert 'file_validation' in rules

def test_get_reference_order(config_file):
    """Test getting reference order"""
    loader = ConfigLoader(config_file)
    order = loader.get_reference_order('test_import')
    assert order == ['ref1.xml', 'ref2.xml']

def test_get_mappings(config_file):
    """Test getting mappings"""
    loader = ConfigLoader(config_file)
    mappings = loader.get_mappings('test_import')
    assert 'test.xml' in mappings
    assert mappings['test.xml']['table'] == 'test_table'

def test_get_field_mapping(config_file):
    """Test getting field mapping for specific file"""
    loader = ConfigLoader(config_file)
    mapping = loader.get_field_mapping('test_import', 'test.xml')
    assert mapping['table'] == 'test_table'
    assert 'fields' in mapping

def test_get_field_mapping_invalid_file(config_file):
    """Test getting mapping for invalid file"""
    loader = ConfigLoader(config_file)
    with pytest.raises(ValueError):
        loader.get_field_mapping('test_import', 'nonexistent.xml')

def test_reload_config(config_file, sample_config):
    """Test config reloading"""
    loader = ConfigLoader(config_file)
    
    # Modify config and save
    modified_config = dict(sample_config)
    modified_config['imports']['test_import']['name'] = 'Modified Test'
    with open(config_file, 'w') as f:
        yaml.dump(modified_config, f)
    
    # Reload and verify
    loader.reload_config()
    assert loader.config['imports']['test_import']['name'] == 'Modified Test'