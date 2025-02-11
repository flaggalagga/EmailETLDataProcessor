# tests/test_base_processor.py

import pytest
from unittest.mock import MagicMock, patch
from etl_processor.processors.base_processor import BaseProcessor

@pytest.fixture
def mock_logger():
    with patch('etl_processor.processors.base_processor.logging') as mock_log:
        yield mock_log.getLogger.return_value

@pytest.fixture
def mock_display():
    display = MagicMock()
    return display

@pytest.fixture
def processor(mock_logger):
    return BaseProcessor(is_cron=False)

def test_init_default():
    """Test default initialization"""
    processor = BaseProcessor()
    assert processor.is_cron is False
    assert processor.display is None

def test_init_cron():
    """Test cron mode initialization"""
    processor = BaseProcessor(is_cron=True)
    assert processor.is_cron is True

def test_update_progress_with_display(processor, mock_display):
    """Test progress updates with display"""
    processor.display = mock_display
    processor.update_progress("test_stage", "working", 50, "Testing")
    mock_display.update.assert_called_once_with("test_stage", "working", 50, "Testing")

def test_update_progress_without_display(processor):
    """Test progress updates without display"""
    processor.update_progress("test_stage", "working", 50, "Testing")
    # Should not raise any errors

def test_handle_error_with_session(processor, mock_display):
    """Test error handling with database session"""
    mock_session = MagicMock()
    error = Exception("Test error")
    processor.display = mock_display

    result = processor.handle_error("Test message", error, mock_session)

    mock_session.rollback.assert_called_once()
    mock_display.error.assert_called_once_with("Test message")
    assert result == error

def test_handle_error_cron_mode():
    """Test error handling in cron mode"""
    processor = BaseProcessor(is_cron=True)
    error = Exception("Test error")
    
    result = processor.handle_error("Test message", error)
    assert result == error

def test_handle_warning(processor, mock_display):
    """Test warning handling"""
    processor.display = mock_display
    processor.handle_warning("Test warning")
    mock_display.warning.assert_called_once_with("Test warning")

def test_handle_warning_cron_mode():
    """Test warning handling in cron mode"""
    processor = BaseProcessor(is_cron=True)
    processor.handle_warning("Test warning")  # Should not raise errors

def test_handle_success(processor, mock_display):
    """Test success handling"""
    processor.display = mock_display
    processor.handle_success("Test success")
    mock_display.success.assert_called_once_with("Test success")

def test_handle_success_cron_mode():
    """Test success handling in cron mode"""
    processor = BaseProcessor(is_cron=True)
    processor.handle_success("Test success")  # Should not raise errors

def test_set_display(processor, mock_display):
    """Test display setter"""
    processor.set_display(mock_display)
    assert processor.display == mock_display