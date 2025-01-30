import pytest
import os
import zipfile
import magic
from unittest.mock import Mock, patch
from etl_processor.security.file_security import SecureFileProcessor

@pytest.fixture
def file_processor():
    return SecureFileProcessor()

@pytest.fixture
def temp_dir(tmp_path):
    return str(tmp_path)

@pytest.fixture
def create_test_file(temp_dir):
    def _create_file(content: bytes, name: str):
        file_path = os.path.join(temp_dir, name)
        with open(file_path, 'wb') as f:
            f.write(content)
        return file_path
    return _create_file

@pytest.fixture
def create_test_zip(temp_dir, create_test_file):
    def _create_zip(files: dict):
        zip_path = os.path.join(temp_dir, 'test.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for name, content in files.items():
                file_path = create_test_file(content, name)
                zf.write(file_path, name)
        return zip_path
    return _create_zip

class TestSecureFileProcessor:

    def test_validate_file_size_limit(self, file_processor, create_test_file):
        # Create file larger than max_file_size
        large_content = b'x' * (file_processor.max_file_size + 1)
        large_file = create_test_file(large_content, 'large.xml')
        
        with pytest.raises(ValueError, match="File exceeds maximum size"):
            file_processor.validate_file(large_file)

    def test_validate_file_type_allowed(self, file_processor, create_test_file):
        xml_content = b'<?xml version="1.0"?><root></root>'
        xml_file = create_test_file(xml_content, 'test.xml')
        
        with patch('magic.Magic') as mock_magic:
            mock_magic.return_value.from_file.return_value = 'application/xml'
            assert file_processor.validate_file(xml_file)

    def test_validate_file_type_not_allowed(self, file_processor, create_test_file):
        exe_content = b'MZ\x90\x00'  # DOS MZ executable header
        exe_file = create_test_file(exe_content, 'test.exe')
        
        with patch('magic.Magic') as mock_magic:
            mock_magic.return_value.from_file.return_value = 'application/x-dosexec'
            with pytest.raises(ValueError, match="Invalid file type"):
                file_processor.validate_file(exe_file)

    def test_secure_extract_zip_valid(self, file_processor, create_test_zip, temp_dir):
        # Create a valid ZIP with XML files
        valid_files = {
            'test1.xml': b'<?xml version="1.0"?><root></root>',
            'test2.xml': b'<?xml version="1.0"?><data></data>'
        }
        zip_path = create_test_zip(valid_files)
        
        with patch('magic.Magic') as mock_magic:
            mock_magic.return_value.from_buffer.return_value = 'application/xml'
            mock_magic.return_value.from_file.return_value = 'application/zip'
            
            extract_dir = os.path.join(temp_dir, 'extract')
            os.makedirs(extract_dir, exist_ok=True)
            
            file_processor.secure_extract_zip(zip_path, extract_dir)
            
            # Verify files were extracted
            assert os.path.exists(os.path.join(extract_dir, 'test1.xml'))
            assert os.path.exists(os.path.join(extract_dir, 'test2.xml'))

    def test_secure_extract_zip_bomb(self, file_processor, create_test_zip, temp_dir):
        # Create a zip with a very large decompressed size
        large_content = b'0' * (file_processor.max_file_size + 1)
        bomb_files = {'large.xml': large_content}
        zip_path = create_test_zip(bomb_files)
        
        with patch('magic.Magic') as mock_magic:
            mock_magic.return_value.from_file.return_value = 'application/zip'
            mock_magic.return_value.from_buffer.return_value = 'application/xml'
            
            with pytest.raises(ValueError, match="Potential zip bomb detected"):
                file_processor.secure_extract_zip(zip_path, temp_dir)

    def test_secure_extract_zip_directory_traversal(self, file_processor, temp_dir):
        # Create a zip file with directory traversal attempt
        zip_path = os.path.join(temp_dir, 'malicious.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('../outside.txt', 'malicious content')
        
        with patch('magic.Magic') as mock_magic:
            mock_magic.return_value.from_file.return_value = 'application/zip'
            
            with pytest.raises(ValueError, match="Potential directory traversal attack"):
                file_processor.secure_extract_zip(zip_path, temp_dir)

    def test_validate_xml_valid(self, file_processor, create_test_file):
        valid_xml = b'<?xml version="1.0"?><root><item>test</item></root>'
        xml_file = create_test_file(valid_xml, 'valid.xml')
        
        with patch('magic.Magic') as mock_magic:
            mock_magic.return_value.from_file.return_value = 'application/xml'
            assert file_processor.validate_xml(xml_file)

    def test_validate_xml_invalid(self, file_processor, create_test_file):
        invalid_xml = b'<?xml version="1.0"?><root><unclosed>'
        xml_file = create_test_file(invalid_xml, 'invalid.xml')
        
        with patch('magic.Magic') as mock_magic:
            mock_magic.return_value.from_file.return_value = 'application/xml'
            with pytest.raises(Exception):
                file_processor.validate_xml(xml_file)

    def test_validate_xml_xxe(self, file_processor, create_test_file):
        # XML with XXE attack attempt
        xxe_xml = b'''<?xml version="1.0"?>
        <!DOCTYPE root [
            <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <root>&xxe;</root>'''
        xml_file = create_test_file(xxe_xml, 'xxe.xml')
        
        with patch('magic.Magic') as mock_magic:
            mock_magic.return_value.from_file.return_value = 'application/xml'
            with pytest.raises(Exception):
                file_processor.validate_xml(xml_file)
