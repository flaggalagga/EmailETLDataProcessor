# tests/test_email_security.py

import pytest
from unittest.mock import patch, MagicMock
import dns.resolver
from imap_tools import MailBox
from etl_processor.security.email_security import EmailSecurityProcessor

@pytest.fixture
def mock_logger():
    with patch('etl_processor.security.email_security.logging') as mock_log:
        yield mock_log.getLogger.return_value

@pytest.fixture
def sample_config():
    return {
        'security': {
            'email_checks': ['spf', 'dkim', 'dmarc'],
            'allowed_sender_domains': ['trusted-domain.com'],
            'spam_threshold': 5.0
        }
    }

@pytest.fixture
def mock_email_msg():
    msg = MagicMock()
    msg.from_ = 'Sender <sender@trusted-domain.com>'
    msg.subject = 'Test Subject'
    msg.headers = {
        'received-spf': ['pass (sender IP is 1.2.3.4)'],
        'authentication-results': ['dkim=pass header.d=trusted-domain.com'],
        'dmarc-result': ['pass'],
        'x-spam-score': ['2.0']
    }
    return msg

@pytest.fixture
def config_loader(sample_config):
    mock_loader = MagicMock()
    mock_loader.get_security_rules.return_value = sample_config['security']
    return mock_loader

@pytest.fixture
def processor(config_loader):
    return EmailSecurityProcessor(config_loader)

async def test_verify_email_security_success(processor, mock_email_msg):
    """Test successful email security verification"""
    # Setup security configuration using test email domain
    security_config = {
        'email_checks': ['spf', 'dkim', 'dmarc'],
        'allowed_sender_domains': ['trusted-domain.com'],
        'file_validation': {
            'allowed_types': ['application/zip'],
            'max_attachment_size': '50MB',
            'zip_extraction': {
                'max_ratio': 15,
                'max_files': 100,
                'max_file_size': '50MB',
                'allowed_types': ['.zip', '.xml']
            }
        }
    }
    
    # Configure processor with mocked config
    processor.config_loader = MagicMock()
    processor.config_loader.get_security_rules.return_value = security_config
    processor.config_loader.get_primary_attachment_filename.return_value = 'test.zip'
    
    # Mock get_primary_attachment_filename method
    processor.get_primary_attachment_filename = MagicMock(return_value='test.zip')
    
    # Setup attachment with proper mock
    attachment = MagicMock()
    attachment.filename = 'test.zip'
    attachment.payload = b'test content'
    mock_email_msg.attachments = [attachment]
    
    # Add required DMARC result to existing headers
    mock_email_msg.headers['authentication-results'] = [
        'dkim=pass header.d=trusted-domain.com;' +
        'spf=pass;dmarc=pass action=none'
    ]
    
    # Mock magic file type check
    with patch('magic.from_buffer', return_value='application/zip'):
        results = await processor.verify_email_security(mock_email_msg, 'test_import')
        
        # Check individual results for easier debugging
        for check, result in results.items():
            assert result, f"Check failed: {check}"
        
        # Verify all checks passed
        assert all(results.values())

async def test_verify_email_security_invalid_sender(processor, mock_email_msg):
    """Test security check with invalid sender domain"""
    mock_email_msg.from_ = 'sender@untrusted-domain.com'
    results = await processor.verify_email_security(mock_email_msg, 'test_import')
    assert not results['sender_verified']

async def test_verify_spf_pass(processor, mock_email_msg):
    """Test successful SPF verification"""
    result = processor._verify_spf(mock_email_msg)
    assert result is True

async def test_verify_spf_fail(processor, mock_email_msg):
    """Test failed SPF verification"""
    mock_email_msg.headers['received-spf'] = ['fail']
    result = processor._verify_spf(mock_email_msg)
    assert result is False

async def test_verify_dkim_pass(processor, mock_email_msg):
    """Test successful DKIM verification"""
    result = processor._verify_dkim(mock_email_msg)
    assert result is True

async def test_verify_dkim_fail(processor, mock_email_msg):
    """Test failed DKIM verification"""
    mock_email_msg.headers['authentication-results'] = ['dkim=fail']
    result = processor._verify_dkim(mock_email_msg)
    assert result is False

# tests/test_email_security.py

@pytest.mark.asyncio
async def test_verify_dmarc_pass(processor, mock_email_msg):
    """Test successful DMARC verification"""
    # Add DMARC pass header
    mock_email_msg.headers = {
        'authentication-results': ['dmarc=pass']
    }
    result = processor._verify_dmarc(mock_email_msg)
    assert result is True

async def test_verify_dmarc_fail(processor, mock_email_msg):
    """Test failed DMARC verification"""
    mock_email_msg.headers['dmarc-result'] = ['fail']
    result = processor._verify_dmarc(mock_email_msg)
    assert result is False

async def test_check_spam_score_below_threshold(processor, mock_email_msg):
    """Test spam score below threshold"""
    result = processor._check_spam_score(mock_email_msg, 5.0)
    assert result is True

async def test_check_spam_score_above_threshold(processor, mock_email_msg):
    """Test spam score above threshold"""
    mock_email_msg.headers['x-spam-score'] = ['6.0']
    result = processor._check_spam_score(mock_email_msg, 5.0)
    assert result is False

async def test_verify_email_security_no_config(mock_email_msg):
    """Test security verification without config"""
    processor = EmailSecurityProcessor(None)
    results = await processor.verify_email_security(mock_email_msg, 'test_import')
    assert results == {'all_checks': True}

async def test_verify_email_security_missing_headers(processor, mock_email_msg):
    """Test security verification with missing headers"""
    mock_email_msg.headers = {}
    results = await processor.verify_email_security(mock_email_msg, 'test_import')
    assert not all(results.values())