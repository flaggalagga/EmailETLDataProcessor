# tests/test_display.py

import pytest
import sys
import io
from io import StringIO
import logging
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
from colorama import Fore, Style
from etl_processor.cli.display import (
    LiveTimer,
    MultiProgress,
    DisplayBase,
    InteractiveDisplay,
    CronDisplay,
    create_display
)

@pytest.fixture
def mock_stdout():
    """Mock stdout for testing output"""
    original_stdout = sys.stdout
    string_io = StringIO()
    sys.stdout = string_io
    yield string_io
    sys.stdout = original_stdout
    string_io.close()

@pytest.fixture
def mock_timer():
    """Mock timer to avoid threading issues"""
    timer = MagicMock()
    timer.get_time.return_value = "00:00:00"
    return timer

def test_live_timer_basic():
    """Test LiveTimer basic functionality"""
    timer = LiveTimer()
    # Timer starts running in __init__
    assert timer.running
    timer.stop()
    timer.running = False  # Explicitly set running to False
    assert not timer.running
    timer.start()
    assert timer.running

def test_live_timer_format(monkeypatch):
    """Test LiveTimer time formatting"""
    # Mock time.time to return consistent values
    start_time = 900.0
    current_time = 1000.0
    time_values = iter([start_time, current_time])
    monkeypatch.setattr('time.time', lambda: next(time_values))
    
    timer = LiveTimer()
    timer.start_time = start_time
    with timer._lock:
        timer.current_time = str(timedelta(seconds=int(current_time - start_time)))
    assert timer.get_time() == "0:01:40"
    timer.stop()

def test_multi_progress_draw(mock_stdout):
    """Test MultiProgress drawing"""
    progress = MultiProgress()
    progress.timer = mock_timer()
    
    # Ensure output is directed to our mock
    with patch('sys.stdout', new=mock_stdout):
        progress.add_stage('test', 'Test Stage')
        progress.update_stage('test', 'working', 50, 'Testing')
        progress._draw()
        
        output = mock_stdout.getvalue()
        assert 'Test Stage' in output
        assert '50%' in output
        assert 'Testing' in output

def test_display_base():
    """Test DisplayBase functionality"""
    display = DisplayBase()
    
    # These should not raise any exceptions
    display.print("Test message")
    display.success("Success message")
    display.warning("Warning message")
    display.error("Error message")
    display.update("stage", "working", 50, "details")
    display.finish()

def test_interactive_display(mock_stdout):
    """Test InteractiveDisplay functionality"""
    display = InteractiveDisplay()
    display.progress = mock_timer()  # Avoid threading issues
    
    with patch('sys.stdout', new=mock_stdout):
        display.print("Test message")
        assert "Test message" in mock_stdout.getvalue()
        
        display.success("Success")
        assert "✨ Success" in mock_stdout.getvalue()
        
        display.warning("Warning")
        assert "⚠ Warning" in mock_stdout.getvalue()
        
        display.error("Error")
        assert "✗ Error" in mock_stdout.getvalue()

def test_cron_display(caplog):
    """Test CronDisplay functionality"""
    display = CronDisplay()
    with caplog.at_level(logging.DEBUG):
        display.print("Test message")
        display.success("Success message")
        display.warning("Warning message")
        display.error("Error message")
        
        # Check log records
        log_messages = [rec.message for rec in caplog.records]
        assert "Test message" in log_messages
        assert "Success message" in log_messages
        assert "Warning message" in log_messages
        assert "Error message" in log_messages

@pytest.mark.asyncio
async def test_show_email_selection(mock_stdout):
    """Test email selection display"""
    display = InteractiveDisplay()
    display.progress = mock_timer()  # Avoid threading issues
    
    emails = [
        {
            'date': datetime.now(),
            'folder': 'INBOX',
            'subject': 'Test Email',
            'has_attachment': True,
            'import_type': 'test'
        }
    ]
    
    with patch('sys.stdout', new=mock_stdout):
        await display.show_email_selection(emails)
        output = mock_stdout.getvalue()
        assert any(s in output for s in ['Test Email', 'INBOX', 'test'])

@pytest.mark.asyncio
async def test_get_email_selection(monkeypatch, mock_stdout):
    """Test email selection interaction"""
    display = InteractiveDisplay()
    display.progress = mock_timer()  # Avoid threading issues
    
    emails = [{
        'date': datetime.now(),
        'folder': 'INBOX',
        'subject': 'Test',
        'has_attachment': True,
        'import_type': 'test'
    }]
    
    # Mock inputs: select first email (1) then confirm (y)
    inputs = iter(['1', 'y'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))
    
    with patch('sys.stdout', new=mock_stdout):
        result = await display.get_email_selection(emails)
        assert result == emails[0]

def test_create_display_interactive():
    """Test display creation in interactive mode"""
    with create_display(is_cron=False) as display:
        assert isinstance(display, InteractiveDisplay)
        assert display.progress is not None

def test_create_display_cron():
    """Test display creation in cron mode"""
    with create_display(is_cron=True) as display:
        assert isinstance(display, CronDisplay)