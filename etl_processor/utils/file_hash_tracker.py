import os
import json
import hashlib
import logging
from typing import Dict, Optional

def get_app_root():
    """Get the application root directory"""
    return '/var/www/html'

class FileHashTracker:
    """Manages file hash tracking to determine if files have changed"""
    
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
        cache_path = os.path.join(logs_dir, 'bsm_file_hashes.json')
        
        self.cache_path = cache_path
        self.file_hashes = self._load_hashes()
        
        # Only log in non-cron mode
        if not self.is_cron:
            self.logger.info(f"Loaded {len(self.file_hashes)} file hashes from cache")
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

    def needs_processing(self, file_path: str) -> bool:
        """Check if a file needs processing based on its hash"""
        filename = os.path.basename(file_path)
        current_hash = self.calculate_file_hash(file_path)
        
        # Check if file is new or hash has changed
        needs_proc = filename not in self.file_hashes or self.file_hashes[filename] != current_hash
        self.logger.info(f"File {filename} needs processing: {needs_proc} (Current hash: {current_hash}, Cached hash: {self.file_hashes.get(filename, 'none')})")
        return needs_proc

    def mark_processed(self, file_path: str):
        """Explicitly mark a file as processed"""
        filename = os.path.basename(file_path)
        current_hash = self.calculate_file_hash(file_path)
        self.file_hashes[filename] = current_hash
        self._save_hashes()
        self.logger.info(f"Marked {filename} as processed with hash {current_hash}")

    def clear_cache(self):
        """Clear the hash cache"""
        self.file_hashes = {}
        self._save_hashes()
        self.logger.info("Cleared hash cache")
