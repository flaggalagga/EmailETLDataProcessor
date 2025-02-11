# tests/test_file_security.py

import pytest
import os
import zipfile
import json
import magic
from unittest.mock import patch, MagicMock
from pathlib import Path
from etl_processor.security.file_security import SecureFileProcessor

@pytest.fixture
def mock_logger():
    with patch('etl_processor.security.file_security.logging') as mock_log:
        yield mock_log.getLogger.return_value

@pytest.fixture
def sample_config():
    return {
        'security': {
            'file_validation': {
                'max_size': '50MB',
                'zip_extraction': {
                    'max_ratio': 15,
                    'max_files': 100,
                    'max_file_size': '10MB',
                    'allowed_types': ['.xml', '.json']
                }
            }
        }
    }

@pytest.fixture
def config_loader(sample_config):
    mock_loader = MagicMock()
    mock_loader.get_security_rules.return_value = sample_config['security']
    return mock_loader

@pytest.fixture
def processor(config_loader):
    return SecureFileProcessor(config_loader)

@pytest.fixture
def temp_zip(tmp_path):
    """Create a test ZIP file"""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('test1.xml', 'test content 1')
        zf.writestr('test2.xml', 'test content 2')
    return str(zip_path)

def test_validate_file_size(processor, tmp_path):
    """Test file size validation"""
    test_file = tmp_path / "test.txt"
    with open(test_file, 'wb') as f:
        f.write(b'x' * 1024)  # 1KB file
    
    assert processor.validate_file(str(test_file), 'test_import')

def test_validate_file_too_large(processor, tmp_path):
    """Test file size validation failure"""
    test_file = tmp_path / "large.txt"
    with open(test_file, 'wb') as f:
        f.write(b'x' * (51 * 1024 * 1024))  # 51MB file
    
    with pytest.raises(ValueError, match="exceeds maximum size"):
        processor.validate_file(str(test_file), 'test_import')

def test_validate_zip_file(processor, temp_zip):
    """Test ZIP file validation"""
    assert processor.validate_file(temp_zip, 'test_import')

def test_secure_extract_zip(processor, temp_zip, tmp_path):
    """Test secure ZIP extraction"""
    extract_dir = str(tmp_path / "extracted")
    os.makedirs(extract_dir)
    
    extracted_files = processor.secure_extract_zip(temp_zip, extract_dir, 'test_import')
    assert len(extracted_files) == 2
    assert all(Path(f).exists() for f in extracted_files)

def test_extract_zip_too_many_files(processor, tmp_path):
    """Test ZIP extraction with too many files"""
    zip_path = tmp_path / "many_files.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for i in range(101):  # Exceeds max_files of 100
            zf.writestr(f'test{i}.xml', 'content')
    
    extract_dir = str(tmp_path / "extracted")
    os.makedirs(extract_dir)
    
    with pytest.raises(ValueError, match="too many files"):
        processor.secure_extract_zip(str(zip_path), extract_dir, 'test_import')

def test_extract_zip_bad_extension(processor, tmp_path):
    """Test ZIP extraction with invalid file type"""
    zip_path = tmp_path / "bad_types.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('test.exe', 'bad content')
    
    extract_dir = str(tmp_path / "extracted")
    os.makedirs(extract_dir)
    
    with pytest.raises(ValueError, match="Invalid file type"):
        processor.secure_extract_zip(str(zip_path), extract_dir, 'test_import')

def test_extract_zip_high_ratio(processor, tmp_path):
    """Test ZIP extraction with high compression ratio"""
    zip_path = tmp_path / "high_ratio.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('test.xml', 'a' * 1000000)  # Highly compressible data
    
    extract_dir = str(tmp_path / "extracted")
    os.makedirs(extract_dir)
    
    with pytest.raises(ValueError, match="Compression ratio too high"):
        processor.secure_extract_zip(str(zip_path), extract_dir, 'test_import')

# tests/test_file_security.py

def test_scan_file_no_clamav(processor, tmp_path):
    """Test file scanning without ClamAV"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # Set clamd to None explicitly to simulate no ClamAV
    processor.clamd = None
    processor.logger = MagicMock()  # Mock logger to avoid warnings
    
    assert processor._scan_file(str(test_file)) is True

@patch('clamd.ClamdUnixSocket')
def test_scan_file_with_clamav(mock_clamd, processor, tmp_path):
    """Test file scanning with ClamAV"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # Mock ClamAV response
    mock_scanner = MagicMock()
    mock_scanner.instream.return_value = {'stream': ['OK']}
    mock_clamd.return_value = mock_scanner
    
    # Set up the processor with mocked ClamAV
    processor.clamd = mock_scanner
    result = processor._scan_file(str(test_file))
    assert result is True
    mock_scanner.instream.assert_called_once()

@patch('clamd.ClamdUnixSocket')
def test_scan_file_virus_found(mock_clamd, processor, tmp_path):
    """Test file scanning with virus detection"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # Mock ClamAV response for virus detection
    mock_scanner = MagicMock()
    mock_scanner.instream.return_value = {'stream': ['FOUND']}
    mock_clamd.return_value = mock_scanner
    
    # Set up the processor with mocked ClamAV
    processor.clamd = mock_scanner
    result = processor._scan_file(str(test_file))
    assert result is False
    mock_scanner.instream.assert_called_once()

@patch('clamd.ClamdUnixSocket')
def test_scan_file_error(mock_clamd, processor, tmp_path):
    """Test file scanning with ClamAV error"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # Mock ClamAV to raise an error
    mock_scanner = MagicMock()
    mock_scanner.instream.side_effect = Exception("ClamAV error")
    mock_clamd.return_value = mock_scanner
    
    # Set up the processor with mocked ClamAV
    processor.clamd = mock_scanner
    result = processor._scan_file(str(test_file))
    assert result is False
    mock_scanner.instream.assert_called_once()