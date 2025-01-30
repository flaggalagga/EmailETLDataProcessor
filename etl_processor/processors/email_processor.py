import os
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from imap_tools import MailBox, AND

from .base_processor import BaseProcessor
from ..security.email_security import EmailSecurityProcessor
from ..security.file_security import SecureFileProcessor
from ..config.config_loader import ConfigLoader

class EmailProcessor(BaseProcessor):
    def __init__(self, is_cron: bool = False):
        """Initialize the email processor"""
        super().__init__(is_cron=is_cron)
        self.config_loader = ConfigLoader()
        self.email_security = EmailSecurityProcessor(self.config_loader)
        self.file_security = SecureFileProcessor(self.config_loader)

    async def list_sender_emails(
        self, 
        days: Optional[int] = None, 
        folders: Optional[list[str]] = None,
        import_type: Optional[str] = None
    ) -> List[Dict]:
        """
        List emails from configured senders with security checks
        
        Args:
            days: Number of days to look back
            folders: List of folders to scan
            import_type: Specific import type to process
        """
        host = os.getenv('IMAP_HOST')
        username = os.getenv('IMAP_USERNAME')
        password = os.getenv('IMAP_PASSWORD')
        emails = []

        try:
            # Get configuration for import type
            if import_type:
                config = self.config_loader.get_import_config(import_type)
                days = days or config.get('days_lookback', 90)
                folders = folders or config.get('inboxes', ['INBOX'])
                self.logger.debug(f"Using lookback period of {days} days for {import_type}")
                self.logger.debug(f"Scanning folders: {folders}")
            else:
                days = days or 90
                folders = folders or ['INBOX']

            # Calculate date range
            date_from = (datetime.now() - timedelta(days=days)).date()
            self.logger.debug(f"Looking for emails from {date_from}")

            with MailBox(host).login(username, password) as mailbox:
                for folder in folders:
                    try:
                        self.logger.debug(f"Scanning folder: {folder}")
                        mailbox.folder.set(folder)
                        
                        # Get import types to process
                        import_types = [import_type] if import_type else self.config_loader.get_import_types()
                        
                        for imp_type in import_types:
                            sender_email = self.config_loader.get_sender_email(imp_type)
                            attachment_name = self.config_loader.get_primary_attachment_filename(imp_type)
                            
                            criteria = AND(
                                from_=sender_email,
                                date_gte=date_from
                            )
                            
                            for msg in mailbox.fetch(criteria):
                                security_results = await self.email_security.verify_email_security(msg, imp_type)
                                
                                if all(security_results.values()):
                                    emails.append({
                                        'uid': msg.uid,
                                        'folder': folder,
                                        'date': msg.date,
                                        'subject': msg.subject,
                                        'import_type': imp_type,
                                        'has_attachment': any(
                                            att.filename == attachment_name 
                                            for att in msg.attachments
                                        ),
                                        'security_verified': True
                                    })
                                else:
                                    failed_checks = [k for k, v in security_results.items() if not v]
                                    self.logger.warning(
                                        f"Email security checks failed for {imp_type} message {msg.uid} in {folder}:\n"
                                        f"Failed checks: {', '.join(failed_checks)}"
                                    )
                    except Exception as e:
                        self.logger.error(f"Error accessing folder {folder}: {str(e)}")
                        continue
            
            return sorted(emails, key=lambda x: x['date'], reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error listing emails: {str(e)}")
            raise

    async def get_email_message(self, uid: str, folder: str, import_type: str):
        """Get specific email message with security verification"""
        host = os.getenv('IMAP_HOST')
        username = os.getenv('IMAP_USERNAME')
        password = os.getenv('IMAP_PASSWORD')
        
        try:
            with MailBox(host).login(username, password) as mailbox:
                mailbox.folder.set(folder)
                messages = mailbox.fetch(AND(uid=uid))
                msg = next(messages, None)
                
                if not msg:
                    raise ValueError(f"Email with UID {uid} not found in folder {folder}")
                
                # Verify email security for this import type
                security_results = await self.email_security.verify_email_security(msg, import_type)
                
                if not all(security_results.values()):
                    failed_checks = [k for k, v in security_results.items() if not v]
                    raise ValueError(
                        f"Email security checks failed for {import_type}: {', '.join(failed_checks)}"
                    )
                
                return msg
                
        except Exception as e:
            raise self.handle_error(f"Error getting email from {folder}", e)

    async def extract_attachment(self, email_msg, import_type: str, temp_dir: str) -> str:
        """Extract and validate primary attachment"""
        try:
            attachment_name = self.config_loader.get_primary_attachment_filename(import_type)
            attachment = next(
                (att for att in email_msg.attachments if att.filename == attachment_name),
                None
            )
            
            if not attachment:
                raise ValueError(f"Primary attachment {attachment_name} not found")
            
            # Save attachment
            zip_path = os.path.join(temp_dir, attachment_name)
            with open(zip_path, 'wb') as f:
                f.write(attachment.payload)
            
            # Validate file
            self.file_security.validate_file(zip_path, import_type)
            
            # Extract contents
            extract_dir = os.path.join(temp_dir, 'extracted')
            os.makedirs(extract_dir, exist_ok=True)
            
            extracted_files = self.file_security.secure_extract_zip(
                zip_path, 
                extract_dir, 
                import_type
            )
            
            return extract_dir, extracted_files
            
        except Exception as e:
            raise self.handle_error("Error extracting attachment", e)