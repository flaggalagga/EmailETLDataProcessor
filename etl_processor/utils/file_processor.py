import os
import logging
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Optional
from ..core.constants import REFERENCE_ORDER

class FileProcessor:
    def __init__(self, reference_order: Optional[List[str]] = None):
        """
        Initialize FileProcessor with optional reference file processing order
        
        :param reference_order: List of XML files to process in a specific order
        """
        self.logger = logging.getLogger(__name__)
        
        # Use provided reference order or default from constants
        self.reference_order = reference_order or REFERENCE_ORDER

    def extract_zip(self, zip_path: str, extract_dir: str) -> None:
        """
        Extract ZIP file to specified directory
        
        :param zip_path: Path to the ZIP file
        :param extract_dir: Directory to extract files to
        :raises ValueError: If ZIP file is invalid
        """
        try:
            with zipfile.ZipFile(zip_path) as zip_ref:
                # Log all files in the ZIP
                file_list = zip_ref.namelist()
                self.logger.info(f"Files in ZIP: {file_list}")
                
                # Extract each file
                zip_ref.extractall(extract_dir)
        except zipfile.BadZipFile as e:
            self.logger.error(f"Invalid ZIP file: {e}")
            raise ValueError(f"Invalid ZIP file: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error extracting ZIP: {e}")
            raise

    def get_xml_files(self, directory: str) -> List[str]:
        """
        Get list of XML files in the directory, sorted by reference order
        
        :param directory: Directory to search for XML files
        :return: List of XML file paths
        """
        # First, get all XML files in the directory
        xml_files = [
            os.path.join(directory, f) 
            for f in os.listdir(directory) 
            if f.upper().endswith('.XML')
        ]
        
        # Sort files based on reference_order
        sorted_files = []
        
        # First, add files in the predefined reference order
        for ref_file in self.reference_order:
            matching_files = [
                f for f in xml_files 
                if os.path.basename(f).upper() == ref_file.upper()
            ]
            sorted_files.extend(matching_files)
        
        # Then add any remaining XML files not in reference_order
        remaining_files = [
            f for f in xml_files 
            if f not in sorted_files
        ]
        sorted_files.extend(remaining_files)
        
        return sorted_files

    def parse_xml(self, file_path: str):
        """
        Parse XML file
        
        :param file_path: Path to XML file
        :return: Parsed XML tree
        """
        try:
            # Log file details before parsing
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                self.logger.info(f"Parsing XML file: {file_path} (Size: {file_size} bytes)")
            else:
                self.logger.error(f"XML file does not exist: {file_path}")
                raise FileNotFoundError(f"XML file not found: {file_path}")
            
            return ET.parse(file_path)
        except ET.ParseError as e:
            self.logger.error(f"Error parsing XML file {file_path}: {e}")
            raise
        except FileNotFoundError as e:
            self.logger.error(f"File not found error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error parsing XML: {e}")
            raise
