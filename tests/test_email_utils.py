# tests/test_email_utils.py

import pytest
import os
import smtplib
from datetime import datetime
from unittest.mock import patch, MagicMock, call
from imap_tools import MailBox
from etl_processor.utils.email_utils import EmailUtils

@pytest.fixture
def mock_logger():
    with patch('etl_processor.utils.email_utils.logger') as mock_log:
        yield mock_log

@pytest.fixture
def mock_env():
    """Setup test environment variables"""
    env_vars = {
        'MAILJET_SMTP': 'test.smtp',
        'MAILJET_SMTP_USER': 'test_user',
        'MAILJET_SMTP_PASS': 'test_pass',
        'MAILJET_SMTP_PORT': '587',
        'EMAIL_FROM': 'Test <from@test.com>',
        'EMAIL_IMPORTS': 'to@test.com',
        'IMAP_HOST': 'imap.test.com',
        'IMAP_USERNAME': 'imap_user',
        'IMAP_PASSWORD': 'imap_pass'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars

@pytest.fixture
def email_utils(mock_env):
    """Create EmailUtils instance with mocked environment"""
    return EmailUtils()

@pytest.fixture
def test_data():
    """Sample test data"""
    return {
        'processed_files': ['test1.xml', 'test2.xml'],
        'skipped_files': ['skip.xml'],
        'total_accidents': 42,
        'total_victims': 10,
        'email_date': datetime(2024, 1, 1, 12, 0)
    }

def test_constructor(mock_env, mock_logger):
    """Test EmailUtils constructor with all values"""
    utils = EmailUtils()
    assert utils.smtp_host == mock_env['MAILJET_SMTP']
    assert utils.smtp_user == mock_env['MAILJET_SMTP_USER']
    assert utils.smtp_port == 587

def test_format_email_addresses(email_utils):
    """Test email address formatting"""
    # Empty case
    header, addrs = email_utils._format_email_addresses('')
    assert header == ''
    assert addrs == []
    
    # Simple address
    header, addrs = email_utils._format_email_addresses('test@test.com')
    assert header == 'test@test.com'
    assert addrs == ['test@test.com']
    
    # Complex address
    header, addrs = email_utils._format_email_addresses('Test User <test@test.com>')
    assert header == 'Test User <test@test.com>'
    assert addrs == ['test@test.com']

def test_send_notification_success(email_utils, test_data):
    """Test successful email notification"""
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    
    with patch('smtplib.SMTP', return_value=mock_smtp):
        result = email_utils.send_import_notification(**test_data)
        
        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once()
        mock_smtp.send_message.assert_called_once()

def test_send_notification_with_error(email_utils, test_data):
    """Test notification with error message"""
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    test_data['error'] = 'Test error message'
    
    with patch('smtplib.SMTP', return_value=mock_smtp):
        result = email_utils.send_import_notification(**test_data)
        assert result is True
        msg = mock_smtp.send_message.call_args[0][0]
        body = msg.get_payload()[0].get_payload()
        assert 'Test error message' in body

@pytest.mark.asyncio
async def test_move_to_archive_success():
    """Test successful archive operation"""
    # Setup email utils with mocked environment
    env_vars = {
        'IMAP_HOST': 'imap.test.com',
        'IMAP_USERNAME': 'test_user',
        'IMAP_PASSWORD': 'test_pass'
    }
    
    with patch.dict(os.environ, env_vars):
        email_utils = EmailUtils()
        
        # Setup mocks
        mock_msg = MagicMock(uid='123')
        mock_mailbox = MagicMock()
        mock_mailbox.__enter__ = MagicMock(return_value=mock_mailbox)
        mock_mailbox.__exit__ = MagicMock(return_value=None)
        
        # Setup folder list
        folder_mock = MagicMock()
        folder_mock.name = 'INBOX.Archive BSM'
        mock_mailbox.folder.list.return_value = [folder_mock]
        
        with patch('imap_tools.MailBox', return_value=mock_mailbox):
            result = await email_utils.move_to_archive(mock_msg, 'INBOX')
            
            assert result is True
            mock_mailbox.folder.set.assert_called_once_with('INBOX')
            mock_mailbox.move.assert_called_once_with('123', 'INBOX.Archive BSM')

@pytest.mark.asyncio
async def test_move_to_archive_move_error():
    """Test archive with move error"""
    env_vars = {
        'IMAP_HOST': 'imap.test.com',
        'IMAP_USERNAME': 'test_user',
        'IMAP_PASSWORD': 'test_pass'
    }
    
    with patch.dict(os.environ, env_vars):
        email_utils = EmailUtils()
        
        mock_msg = MagicMock(uid='123')
        mock_mailbox = MagicMock()
        mock_mailbox.__enter__ = MagicMock(return_value=mock_mailbox)
        mock_mailbox.__exit__ = MagicMock(return_value=None)
        
        # Setup folder but make move fail
        folder_mock = MagicMock()
        folder_mock.name = 'INBOX.Archive BSM'
        mock_mailbox.folder.list.return_value = [folder_mock]
        mock_mailbox.move.side_effect = Exception("Move failed")
        
        with patch('imap_tools.MailBox', return_value=mock_mailbox):
            result = await email_utils.move_to_archive(mock_msg, 'INBOX')
            assert result is False

@pytest.mark.asyncio
async def test_move_to_archive_connection_error():
    """Test archive with connection error"""
    env_vars = {
        'IMAP_HOST': 'imap.test.com',
        'IMAP_USERNAME': 'test_user',
        'IMAP_PASSWORD': 'test_pass'
    }
    
    with patch.dict(os.environ, env_vars):
        email_utils = EmailUtils()
        mock_msg = MagicMock(uid='123')
        
        with patch('imap_tools.MailBox') as mock_mb:
            mock_mb.side_effect = Exception("Connection failed")
            result = await email_utils.move_to_archive(mock_msg, 'INBOX')
            assert result is False