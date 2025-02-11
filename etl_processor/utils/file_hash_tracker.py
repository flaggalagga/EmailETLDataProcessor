import os
import json
import hashlib
import logging
from typing import Dict, Optional
from pathlib import Path

def get_app_root():
    """Get the application root directory"""
    return '/var/www/html'

class FileHashTracker:
    """Manages hash tracking for reference data files.
    
    This class is specifically designed for tracking changes in reference/lookup data files.
    It should NOT be used for main data files (like accidents or incidents) which need
    to be processed on every import regardless of content changes.
    
    The hash tracking helps prevent unnecessary reprocessing of unchanged reference data,
    while ensuring that main data files are always processed for audit and data consistency.
    """
    
    REFERENCE_FILE_PATTERNS = [
        'reference_*.xml',
        'ref_*.xml',
        '*_reference.xml',
        'reference_*.json',
        'ref_*.json',
        '*_reference.json'
    ]
    
    def __init__(self, is_cron: bool = False):
        """Initialize FileHashTracker"""
        self.logger = logging.getLogger(__name__)
        self.is_cron = is_cron
        
        # Use logs directory in app root
        app_root = '/var/www/html'
        logs_dir = os.path.join(app_root, 'logs')
        if not os.path.exists(logs_dir):
            try:
                os.makedirs(logs_dir)
            except PermissionError:
                self.logger.error("Cannot create logs directory. Check permissions.")
                raise
        cache_path = os.path.join(logs_dir, 'reference_file_hashes.json')
        
        self.cache_path = cache_path
        self.file_hashes = self._load_hashes()
        
        # Only log in non-cron mode
        if not self.is_cron:
            self.logger.info(f"Loaded {len(self.file_hashes)} reference file hashes from cache")
            self.logger.info(f"Initialized hash cache at: {self.cache_path}")

    def _load_hashes(self) -> Dict[str, str]:
        """Load existing file hashes from cache"""
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Could not load hash cache: {e}")
        
        return {}

    def _save_hashes(self):
        """Save current file hashes to cache"""
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            
            with open(self.cache_path, 'w') as f:
                json.dump(self.file_hashes, f, indent=2)
            self.logger.debug(f"Saved hashes: {self.file_hashes}")
        except IOError as e:
            self.logger.error(f"Could not save hash cache: {e}")

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file contents"""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
                return file_hash
        except IOError as e:
            self.logger.error(f"Could not read file {file_path}: {e}")
            return ''

    def is_reference_file(self, file_path: str) -> bool:
        """Check if a file is a reference data file based on naming patterns"""
        filename = Path(file_path).name
        return any(Path(filename).match(pattern) for pattern in self.REFERENCE_FILE_PATTERNS)

    def needs_processing(self, file_path: str) -> bool:
        """Check if a reference file needs processing based on its hash.
        
        Args:
            file_path: Path to the reference file to check
            
        Returns:
            bool: True if file needs processing, False otherwise
            
        Raises:
            ValueError: If file_path is not a reference data file
        """
        if not self.is_reference_file(file_path):
            self.logger.warning(
                f"Hash tracking attempted on non-reference file: {file_path}. "
                "Hash tracking should only be used for reference data files."
            )
            # Return True to ensure non-reference files are always processed
            return True
            
        filename = os.path.basename(file_path)
        current_hash = self.calculate_file_hash(file_path)
        
        # Check if file is new or hash has changed
        needs_proc = filename not in self.file_hashes or self.file_hashes[filename] != current_hash
        self.logger.info(
            f"Reference file {filename} needs processing: {needs_proc} "
            f"(Current hash: {current_hash}, Cached hash: {self.file_hashes.get(filename, 'none')})"
        )
        return needs_proc

    def mark_processed(self, file_path: str):
        """Mark a reference file as processed by storing its hash.
        
        Args:
            file_path: Path to the reference file
            
        Raises:
            ValueError: If file_path is not a reference data file
        """
        if not self.is_reference_file(file_path):
            self.logger.warning(
                f"Attempted to mark non-reference file as processed: {file_path}. "
                "Hash tracking should only be used for reference data files."
            )
            return
            
        filename = os.path.basename(file_path)
        current_hash = self.calculate_file_hash(file_path)
        self.file_hashes[filename] = current_hash
        self._save_hashes()
        self.logger.info(f"Marked reference file {filename} as processed with hash {current_hash}")

    def clear_cache(self):
        """Clear the hash cache"""
        self.file_hashes = {}
        self._save_hashes()
        self.logger.info("Cleared hash cache")