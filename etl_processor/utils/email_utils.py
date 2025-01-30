import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from typing import List, Optional
from imap_tools import MailBox

logger = logging.getLogger(__name__)

class EmailUtils:
    def __init__(self):
        # Get SMTP settings
        self.smtp_host = os.getenv('MAILJET_SMTP')
        self.smtp_user = os.getenv('MAILJET_SMTP_USER')
        self.smtp_pass = os.getenv('MAILJET_SMTP_PASS')
        self.smtp_port = int(os.getenv('MAILJET_SMTP_PORT', '587'))
        
        # Log configuration
        logger.info(f"Email configuration:")
        logger.info(f"SMTP Host: {self.smtp_host}")
        logger.info(f"SMTP User: {self.smtp_user}")
        logger.info(f"SMTP Port: {self.smtp_port}")

    def send_import_notification(self, 
                               processed_files: List[str], 
                               skipped_files: List[str], 
                               total_accidents: int,
                               total_victims: int,
                               email_date: datetime,
                               error: Optional[str] = None) -> bool:
        """Send email notification about import results"""
        try:
            msg = MIMEMultipart()
            msg['Subject'] = f"BSM Import Report - {email_date.strftime('%Y-%m-%d %H:%M')}"
            msg['From'] = os.getenv('EMAIL_FROM', 'SNOSM <rapport_snosm@ensm.si>')

            # Fix for the To header - ensure it ends with >
            to_addresses = [addr.strip() for addr in os.getenv('EMAIL_IMPORTS', '').split(',')]
            msg['To'] = ', '.join(addr if addr.endswith('>') else addr + '>' for addr in to_addresses)
            
            logger.debug(f"Sending to: {msg['To']}")
            
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
            
            # Send email with detailed logging
            logger.info("Attempting to send email...")
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                logger.debug("Connected to SMTP server")
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                
                # Get clean email addresses for SMTP
                to_list = [addr.split('<')[1].rstrip('>') if '<' in addr else addr 
                          for addr in to_addresses]
                
                server.send_message(msg, 
                                  from_addr=msg['From'].split('<')[1].rstrip('>'),
                                  to_addrs=to_list)
                
                logger.info("Email sent successfully")
                return True
            
        except Exception as e:
            logger.error(f"Failed to send import notification: {str(e)}", exc_info=True)
            return False

    async def move_to_archive(self, email_msg, source_folder: str) -> bool:
        """Move email to Archive BSM folder"""
        try:
            host = os.getenv('IMAP_HOST')
            username = os.getenv('IMAP_USERNAME')
            password = os.getenv('IMAP_PASSWORD')
            archive_folder = 'INBOX.Archive BSM'
            
            with MailBox(host).login(username, password) as mailbox:
                # First check if archive folder exists
                folders = [f.name for f in mailbox.folder.list()]
                if archive_folder not in folders:
                    logger.warning(f"Archive folder {archive_folder} not found")
                    return False
                
                # Set source folder and move message
                mailbox.folder.set(source_folder)
                mailbox.move(email_msg.uid, archive_folder)
                
                logger.info(f"Email moved to {archive_folder}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to move email to archive: {str(e)}")
            return False
