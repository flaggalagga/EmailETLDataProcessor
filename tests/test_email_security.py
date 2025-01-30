import pytest
import dns.resolver
from unittest.mock import Mock, patch
from etl_processor.security.email_security import EmailSecurityProcessor

@pytest.fixture
def email_security():
    return EmailSecurityProcessor()

@pytest.fixture
def mock_email_msg():
    email = Mock()
    email.from_ = "sender@gendarmerie.interieur.gouv.fr"
    email.headers = {"Received": "from [192.168.1.1]"}
    email.obj.as_bytes.return_value = b"test email content"
    email.attachments = []
    return email

class TestEmailSecurityProcessor:
    
    @pytest.mark.asyncio
    async def test_verify_email_security_all_pass(self, email_security, mock_email_msg):
        # Mock all security checks to pass
        with patch.multiple(email_security,
                          _verify_sender_domain=Mock(return_value=True),
                          _check_spf=Mock(return_value=True),
                          _verify_dkim=Mock(return_value=True),
                          _check_dmarc=Mock(return_value=True),
                          _scan_attachments=Mock(return_value=True)):
            
            results = await email_security.verify_email_security(mock_email_msg)
            
            assert all(results.values())
            assert set(results.keys()) == {
                'sender_verified',
                'spf_pass',
                'dkim_pass',
                'dmarc_pass',
                'malware_scan_pass'
            }

    @pytest.mark.asyncio
    async def test_verify_email_security_all_fail(self, email_security, mock_email_msg):
        # Mock all security checks to fail
        with patch.multiple(email_security,
                          _verify_sender_domain=Mock(return_value=False),
                          _check_spf=Mock(return_value=False),
                          _verify_dkim=Mock(return_value=False),
                          _check_dmarc=Mock(return_value=False),
                          _scan_attachments=Mock(return_value=False)):
            
            results = await email_security.verify_email_security(mock_email_msg)
            
            assert not any(results.values())

    def test_verify_sender_domain_valid(self, email_security):
        with patch('dns.resolver.resolve') as mock_resolve:
            mock_resolve.return_value = [Mock()]  # Simulate MX records exist
            assert email_security._verify_sender_domain('gendarmerie.interieur.gouv.fr')

    def test_verify_sender_domain_invalid(self, email_security):
        with patch('dns.resolver.resolve') as mock_resolve:
            mock_resolve.side_effect = dns.resolver.NXDOMAIN()
            assert not email_security._verify_sender_domain('invalid-domain.com')

    def test_check_spf_valid(self, email_security, mock_email_msg):
        with patch('dns.resolver.resolve') as mock_resolve:
            mock_resolve.return_value = [
                Mock(strings=[b'v=spf1 ip4:192.168.1.1 -all'])
            ]
            assert email_security._check_spf(mock_email_msg)

    def test_verify_dkim_valid(self, email_security, mock_email_msg):
        with patch('dkim.verify', return_value=True):
            assert email_security._verify_dkim(mock_email_msg)

    def test_check_dmarc_valid(self, email_security):
        with patch('dns.resolver.resolve') as mock_resolve:
            mock_resolve.return_value = [
                Mock(strings=[b'v=DMARC1; p=reject; rua=mailto:dmarc@example.com'])
            ]
            assert email_security._check_dmarc('gendarmerie.interieur.gouv.fr')

    @pytest.mark.asyncio
    async def test_scan_attachments_clean(self, email_security, mock_email_msg):
        with patch('clamd.ClamdUnixSocket') as mock_clamd:
            instance = mock_clamd.return_value
            instance.instream.return_value = {'stream': ['OK', '']}
            assert await email_security._scan_attachments(mock_email_msg)

    @pytest.mark.asyncio
    async def test_scan_attachments_infected(self, email_security, mock_email_msg):
        mock_email_msg.attachments = [Mock(payload=b'test content')]
        with patch('clamd.ClamdUnixSocket') as mock_clamd:
            instance = mock_clamd.return_value
            instance.instream.return_value = {'stream': ['FOUND', 'malware']}
            assert not await email_security._scan_attachments(mock_email_msg)

    @pytest.mark.asyncio
    async def test_verify_email_security_exception_handling(self, email_security, mock_email_msg):
        with patch.object(email_security, '_verify_sender_domain', side_effect=Exception('Test error')):
            with pytest.raises(Exception):
                await email_security.verify_email_security(mock_email_msg)
