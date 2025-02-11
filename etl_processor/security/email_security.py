import os
import logging
import magic
from typing import Dict, Optional
import dns.resolver
import re
from imap_tools import MailBox
from ..config.config_loader import ConfigLoader

class EmailSecurityProcessor:
    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """Initialize the email security processor"""
        self.logger = logging.getLogger(__name__)
        self.config_loader = config_loader


    async def verify_email_security(self, email_msg, import_type: str) -> Dict[str, bool]:
            """
            Verify email security based on import-specific configuration
            """
            # Setup logging
            self.logger.info(f"\nStarting email security verification for {import_type}")
            self.logger.info(f"From: {email_msg.from_}")
            self.logger.info(f"Subject: {email_msg.subject}")

            if not self.config_loader:
                self.logger.warning("No config loader provided - using default security settings")
                return {'all_checks': True}

            # Get security configuration
            security_config = self.config_loader.get_security_rules(import_type)
            required_checks = security_config.get('email_checks', [])
            
            self.logger.info(f"\nSecurity Configuration:")
            self.logger.info(f"Required checks: {required_checks}")
            self.logger.info(f"Allowed domains: {security_config.get('allowed_sender_domains', [])}")
            self.logger.info(f"Allowed attachment types: {security_config.get('allowed_attachment_types', [])}")
            self.logger.info(f"Max attachment size: {security_config.get('max_attachment_size', '50MB')}")

            # Initialize results only for required checks
            results = {
                'sender_verified': False,
                'attachment_valid': False  # Always check attachments
            }
            
            # Add optional checks only if required
            if 'spf' in required_checks:
                results['spf_pass'] = False
            if 'dkim' in required_checks:
                results['dkim_pass'] = False
            if 'dmarc' in required_checks:
                results['dmarc_pass'] = False

            self.logger.info(f"\nInitialized checks: {list(results.keys())}")

            try:
                # Verify sender domain
                sender_domain = self._extract_domain(email_msg.from_)
                allowed_domains = security_config.get('allowed_sender_domains', [])
                results['sender_verified'] = sender_domain in allowed_domains
                self.logger.info(f"\nSender verification:")
                self.logger.info(f"Domain: {sender_domain}")
                self.logger.info(f"Allowed: {results['sender_verified']}")

                # Perform configured email checks
                if 'spf' in required_checks:
                    self.logger.info("\nChecking SPF...")
                    results['spf_pass'] = self._verify_spf(email_msg)
                    self.logger.info(f"SPF result: {results['spf_pass']}")
                else:
                    self.logger.info("SPF check not required")
                
                if 'dkim' in required_checks:
                    self.logger.info("\nChecking DKIM...")
                    results['dkim_pass'] = self._verify_dkim(email_msg)
                    self.logger.info(f"DKIM result: {results['dkim_pass']}")
                else:
                    self.logger.info("DKIM check not required")
                
                if 'dmarc' in required_checks:
                    self.logger.info("\nChecking DMARC...")
                    results['dmarc_pass'] = self._verify_dmarc(email_msg)
                    self.logger.info(f"DMARC result: {results['dmarc_pass']}")
                else:
                    self.logger.info("DMARC check not required")

                # Check attachments
                self.logger.info("\nChecking attachments...")
                for attachment in email_msg.attachments:
                    self.logger.info(f"Found attachment: {attachment.filename}")
                    self.logger.info(f"Size: {len(attachment.payload)} bytes")

                results['attachment_valid'] = self._validate_attachments(
                    email_msg,
                    security_config.get('allowed_attachment_types', []),
                    security_config.get('max_attachment_size', '50MB'),
                    import_type
                )
                self.logger.info(f"Attachment validation result: {results['attachment_valid']}")

                # Final results
                self.logger.info("\nFinal security check results:")
                for check, result in results.items():
                    self.logger.info(f"{check}: {result}")

                failed_checks = [k for k, v in results.items() if not v]
                if failed_checks:
                    self.logger.warning(f"Failed checks: {', '.join(failed_checks)}")
                else:
                    self.logger.info("All checks passed successfully")

                return results

            except Exception as e:
                self.logger.error(f"Error in email security verification: {str(e)}", exc_info=True)
                raise

    def _extract_domain(self, email_address: str) -> str:
        """Extract domain from email address"""
        match = re.search(r'@([\w.-]+)', email_address)
        if match:
            return match.group(1).strip('>')
            return ''
        
    def _verify_spf(self, email_msg) -> bool:
        """Verify SPF record"""
        try:
            # Check Received-SPF header
            spf_headers = email_msg.headers.get('received-spf', [])
            if isinstance(spf_headers, str):
                spf_headers = [spf_headers]
                
            for header in spf_headers:
                if header and 'pass' in header.lower():
                    self.logger.debug(f"SPF pass found in header: {header}")
                    return True

            # Check Authentication-Results header
            auth_results = email_msg.headers.get('authentication-results', [])
            if isinstance(auth_results, str):
                auth_results = [auth_results]
                
            for result in auth_results:
                if result and 'spf=pass' in result.lower():
                    self.logger.debug(f"SPF pass found in auth results: {result}")
                    return True

            self.logger.warning("No valid SPF pass found in headers")
            return False

        except Exception as e:
            self.logger.error(f"SPF verification error: {str(e)}")
            return False

    def _verify_dkim(self, email_msg) -> bool:
        """Verify DKIM signature"""
        try:
            auth_results = email_msg.headers.get('authentication-results', [])
            if isinstance(auth_results, str):
                auth_results = [auth_results]
                
            for result in auth_results:
                if not result:
                    continue
                    
                # Look for DKIM pass in authentication results
                if 'dkim=pass' in result.lower():
                    self.logger.debug(f"DKIM pass found: {result}")
                    return True
                    
                # Check for specific DKIM signature verification
                dkim_parts = re.findall(r'dkim=(\w+)', result.lower())
                if dkim_parts and 'pass' in dkim_parts:
                    self.logger.debug(f"DKIM pass found in parts: {dkim_parts}")
                    return True

            self.logger.warning("No valid DKIM signature found")
            return False

        except Exception as e:
            self.logger.error(f"DKIM verification error: {str(e)}")
            return False

    def _verify_dmarc(self, email_msg) -> bool:
        """Verify DMARC policy"""
        try:
            # Check Authentication-Results header
            auth_results = email_msg.headers.get('authentication-results', [])
            if isinstance(auth_results, str):
                auth_results = [auth_results]
                
            for result in auth_results:
                if not result:
                    continue
                    
                # Look for DMARC pass
                if 'dmarc=pass' in result.lower():
                    self.logger.debug(f"DMARC pass found: {result}")
                    return True
                
                # Check for action=none which can indicate pass
                if 'dmarc=none' in result.lower() or 'action=none' in result.lower():
                    self.logger.debug("DMARC none/action none found - considered valid")
                    return True

            self.logger.warning("No valid DMARC result found")
            return False

        except Exception as e:
            self.logger.error(f"DMARC verification error: {str(e)}")
            return False

    def _check_spam_score(self, email_msg, threshold: float) -> bool:
        """Check if email passes spam threshold"""
        try:
            # Check X-Spam-Score header if present
            spam_score = email_msg.headers.get('x-spam-score', ['0'])[0]
            try:
                score = float(spam_score)
                return score <= threshold
            except ValueError:
                pass

            # Check alternative spam headers
            spam_status = email_msg.headers.get('x-spam-status', [''])[0].lower()
            if 'yes' in spam_status:
                return False

            # If no clear spam indicators, consider it passed
            return True

        except Exception as e:
            self.logger.error(f"Spam check error: {str(e)}")
            return False

    def _validate_attachments(self, email_msg, allowed_types: list, max_size: str, import_type: str) -> bool:
            """
            Validate attachment types and sizes
            
            Args:
                email_msg: Email message
                allowed_types: List of allowed MIME types
                max_size: Maximum size (e.g., '50MB')
            """
            try:
                if not self.config_loader:
                    self.logger.error("No config loader available")
                    return False
                    
                attachment_name = self.config_loader.get_primary_attachment_filename(import_type)
                if not attachment_name:
                    self.logger.error(f"No primary attachment configured for {import_type}")
                    return False
                    
                primary_attachment = next(
                    (att for att in email_msg.attachments if att.filename == attachment_name),
                    None
                )
                if not primary_attachment:
                    self.logger.warning(f"Primary attachment {attachment_name} not found")
                    return False
                
                # Convert max_size to bytes
                size_map = {'KB': 1024, 'MB': 1024*1024, 'GB': 1024*1024*1024}
                size_unit = max_size[-2:]
                max_bytes = int(max_size[:-2]) * size_map.get(size_unit, 1)

                # Get primary attachment name from config
                # Get primary attachment name from config for THIS import type
                attachment_name = self.config_loader.get_primary_attachment_filename(import_type)

                primary_attachment = None
                # Find primary attachment
                for attachment in email_msg.attachments:
                    if attachment.filename == attachment_name:
                        primary_attachment = attachment
                        break

                if not primary_attachment:
                    self.logger.warning(f"Primary attachment {attachment_name} not found")
                    return False

                # Only validate the primary attachment
                # Check size
                if len(primary_attachment.payload) > max_bytes:
                    self.logger.warning(f"Primary attachment exceeds max size")
                    return False

                # Check type using python-magic
                mime_type = magic.from_buffer(primary_attachment.payload, mime=True)
                self.logger.debug(f"Primary attachment MIME type: {mime_type}")
                
                if mime_type not in allowed_types:
                    self.logger.warning(
                        f"Primary attachment has invalid type: {mime_type}. "
                        f"Allowed types: {allowed_types}"
                    )
                    return False

                return True

            except Exception as e:
                self.logger.error(f"Attachment validation error: {str(e)}")
                return False