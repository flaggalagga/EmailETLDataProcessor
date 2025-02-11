# etl_processor/utils/email_utils.py

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from typing import List, Optional, Tuple
from imap_tools import MailBox

logger = logging.getLogger(__name__)

class EmailUtils:
    def __init__(self):
        # Get SMTP settings
        self.logger = logging.getLogger(__name__)
        self.logger.info("Email configuration:")
        
        self.smtp_host = os.getenv('MAILJET_SMTP')
        self.logger.info(f"SMTP Host: {self.smtp_host}")
        
        self.smtp_user = os.getenv('MAILJET_SMTP_USER')
        self.logger.info(f"SMTP User: {self.smtp_user}")
        
        self.smtp_pass = os.getenv('MAILJET_SMTP_PASS')
        
        try:
            self.smtp_port = int(os.getenv('MAILJET_SMTP_PORT', '587'))
            self.logger.info(f"SMTP Port: {self.smtp_port}")
        except (TypeError, ValueError):
            self.logger.warning("Invalid SMTP port value, using default 587")
            self.smtp_port = 587
            self.logger.info(f"SMTP Port: {self.smtp_port}")
        
        # Get IMAP settings
        self.imap_host = os.getenv('IMAP_HOST')
        self.imap_user = os.getenv('IMAP_USERNAME')
        self.imap_pass = os.getenv('IMAP_PASSWORD')
        
        self.logger.info("Email configuration initialized")

    def _format_email_addresses(self, addresses_str: str) -> Tuple[str, List[str]]:
        """
        Format email addresses for header and SMTP
        
        Args:
            addresses_str: Comma-separated email addresses
            
        Returns:
            Tuple of (header string, list of SMTP addresses)
        """
        if not addresses_str:
            return '', []
        
        # Split and clean addresses
        addresses = [addr.strip() for addr in addresses_str.split(',') if addr.strip()]
        
        # For headers, keep addresses as-is
        header_str = ', '.join(addresses)
        
        # For SMTP, extract pure email if in "Name <email>" format
        smtp_addrs = [
            addr.split('<')[1].rstrip('>') if '<' in addr else addr 
            for addr in addresses
        ]
        
        return header_str, smtp_addrs

    def send_import_notification(self, 
                               processed_files: List[str], 
                               skipped_files: List[str], 
                               total_accidents: int,
                               total_victims: int,
                               email_date: datetime,
                               error: Optional[str] = None) -> bool:
        """
        Send email notification about import results
        
        Args:
            processed_files: List of processed file names
            skipped_files: List of skipped file names
            total_accidents: Total number of accidents processed
            total_victims: Total number of victims processed
            email_date: Date of the processed email
            error: Optional error message
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            msg = MIMEMultipart()
            msg['Subject'] = f"BSM Import Report - {email_date.strftime('%Y-%m-%d %H:%M')}"
            msg['From'] = os.getenv('EMAIL_FROM', 'SNOSM <rapport_snosm@ensm.si>')

            # Format email addresses
            to_header, to_addrs = self._format_email_addresses(os.getenv('EMAIL_IMPORTS', ''))
            msg['To'] = to_header
            
            self.logger.debug(f"Sending to: {to_header}")
            
            # Create email body
            body = [
                "BSM Import Processing Report",
                "=========================",
                "",
                f"Import Date: {email_date.strftime('%Y-%m-%d %H:%M')}",
                "",
                "Reference Files:",
                "---------------",
                f"Processed: {len(processed_files)}",
                f"Skipped: {len(skipped_files)}",
                "",
                "Processed Files:",
                "---------------",
                *[f"- {file}" for file in processed_files],
                "",
                "Skipped Files:",
                "-------------",
                *[f"- {file}" for file in skipped_files],
                "",
                "Accidents Data:",
                "--------------",
                f"Total Accidents: {total_accidents}",
                f"Total Victims: {total_victims}",
                ""
            ]
            
            if error:
                body.extend([
                    "Errors:",
                    "-------",
                    error,
                    ""
                ])
            
            body.append("---")
            body.append("This is an automated message from the BSM Import System")
            
            msg.attach(MIMEText('\n'.join(body), 'plain'))
            
            self.logger.info("Attempting to send email...")
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                self.logger.debug("Connected to SMTP server")
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                
                if msg['From'] and to_addrs:
                    from_addr = msg['From'].split('<')[1].rstrip('>') if '<' in msg['From'] else msg['From']
                    server.send_message(msg, from_addr=from_addr, to_addrs=to_addrs)
                    self.logger.info("Email sent successfully")
                    return True
                else:
                    self.logger.error("Missing From or To addresses")
                    return False
            
        except Exception as e:
            self.logger.error(f"Failed to send import notification: {str(e)}", exc_info=True)
            return False

    async def move_to_archive(self, email_msg, source_folder: str) -> bool:
        """
        Move email to Archive BSM folder
        
        Args:
            email_msg: Email message to archive
            source_folder: Source folder name
            
        Returns:
            True if moved successfully, False otherwise
        """
        try:
            # Early validation
            if not all([self.imap_host, self.imap_user, self.imap_pass]):
                self.logger.error("Missing IMAP configuration")
                return False

            archive_folder = 'INBOX.Archive BSM'
            
            with MailBox(self.imap_host).login(self.imap_user, self.imap_pass) as mailbox:
                # Check if archive folder exists
                folders = [f.name for f in mailbox.folder.list()]
                if archive_folder not in folders:
                    self.logger.error(f"Archive folder {archive_folder} not found")
                    return False
                
                try:
                    # Set source folder and move message
                    mailbox.folder.set(source_folder)
                    mailbox.move(email_msg.uid, archive_folder)
                    self.logger.info(f"Email {email_msg.uid} moved to {archive_folder}")
                    return True
                    
                except Exception as move_error:
                    self.logger.error(f"Failed to move email: {str(move_error)}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to move email to archive: {str(e)}")
            return False