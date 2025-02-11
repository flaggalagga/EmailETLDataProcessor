import pytest
import os
import json
import tempfile
import logging
from pathlib import Path
from etl_processor.utils.file_hash_tracker import FileHashTracker

# Add this fixture to control logging during tests
@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging to suppress output during tests"""
    logging.getLogger().setLevel(logging.CRITICAL)
    yield
    logging.getLogger().setLevel(logging.INFO)

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing"""
    # Create reference files
    ref_files = [
        'reference_data.xml',
        'ref_codes.xml',
        'types_reference.json'
    ]
    
    # Create non-reference files
    other_files = [
        'data.xml',
        'main.json',
        'config.yaml'
    ]
    
    # Create all files with some content
    for filename in ref_files + other_files:
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, 'w') as f:
            f.write(f"Test content for {filename}")
            
    return {
        'ref_files': [os.path.join(temp_dir, f) for f in ref_files],
        'other_files': [os.path.join(temp_dir, f) for f in other_files]
    }

def test_init_with_nonexistent_cache(temp_dir):
    """Test initializing with nonexistent cache directory"""
    cache_path = os.path.join(temp_dir, 'logs', 'test_hashes.json')
    tracker = FileHashTracker()
    assert os.path.exists(os.path.dirname(tracker.cache_path))
    assert isinstance(tracker.file_hashes, dict)
    assert len(tracker.file_hashes) == 0

def test_is_reference_file(sample_files):
    """Test reference file detection"""
    tracker = FileHashTracker()
    
    # Check reference files
    for ref_file in sample_files['ref_files']:
        assert tracker.is_reference_file(ref_file)
        
    # Check non-reference files
    for other_file in sample_files['other_files']:
        assert not tracker.is_reference_file(other_file)

def test_calculate_file_hash(temp_dir):
    """Test hash calculation"""
    # Create two files with same content
    file1_path = os.path.join(temp_dir, 'file1.txt')
    file2_path = os.path.join(temp_dir, 'file2.txt')
    
    content = "Test content"
    with open(file1_path, 'w') as f1, open(file2_path, 'w') as f2:
        f1.write(content)
        f2.write(content)
    
    tracker = FileHashTracker()
    hash1 = tracker.calculate_file_hash(file1_path)
    hash2 = tracker.calculate_file_hash(file2_path)
    
    # Same content should produce same hash
    assert hash1 == hash2
    # Hash should be a non-empty string
    assert isinstance(hash1, str)
    assert len(hash1) > 0

def test_needs_processing_for_reference_files(sample_files):
    """Test needs_processing for reference files"""
    tracker = FileHashTracker()
    ref_file = sample_files['ref_files'][0]
    
    # First check should indicate processing needed
    assert tracker.needs_processing(ref_file)
    
    # Mark as processed
    tracker.mark_processed(ref_file)
    
    # Second check should indicate no processing needed
    assert not tracker.needs_processing(ref_file)
    
    # Modify file content
    with open(ref_file, 'a') as f:
        f.write("Modified content")
    
    # Check should now indicate processing needed
    assert tracker.needs_processing(ref_file)

def test_needs_processing_for_non_reference_files(sample_files):
    """Test needs_processing for non-reference files"""
    tracker = FileHashTracker()
    non_ref_file = sample_files['other_files'][0]
    
    # Non-reference files should always need processing
    assert tracker.needs_processing(non_ref_file)
    
    # Even after marking as processed
    tracker.mark_processed(non_ref_file)
    assert tracker.needs_processing(non_ref_file)

def test_mark_processed(temp_dir):
    """Test marking files as processed"""
    tracker = FileHashTracker()
    
    # Create a reference file
    ref_file = os.path.join(temp_dir, 'reference_test.xml')
    with open(ref_file, 'w') as f:
        f.write("Test content")
    
    # Mark as processed
    tracker.mark_processed(ref_file)
    
    # Verify hash was saved
    filename = os.path.basename(ref_file)
    assert filename in tracker.file_hashes
    assert isinstance(tracker.file_hashes[filename], str)
    
    # Verify hash was written to cache file
    with open(tracker.cache_path, 'r') as f:
        cache_data = json.load(f)
        assert filename in cache_data
        assert cache_data[filename] == tracker.file_hashes[filename]

def test_clear_cache(temp_dir):
    """Test clearing the hash cache"""
    tracker = FileHashTracker()
    
    # Create and process a reference file
    ref_file = os.path.join(temp_dir, 'reference_test.xml')
    with open(ref_file, 'w') as f:
        f.write("Test content")
    
    tracker.mark_processed(ref_file)
    assert len(tracker.file_hashes) > 0
    
    # Clear cache
    tracker.clear_cache()
    
    # Verify cache is empty
    assert len(tracker.file_hashes) == 0
    with open(tracker.cache_path, 'r') as f:
        assert json.load(f) == {}