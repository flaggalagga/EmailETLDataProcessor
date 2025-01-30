#!/usr/bin/env python3

import os
import sys
import asyncio
import argparse
import logging
import textwrap
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
import tempfile

from .processors.email_processor import EmailProcessor
from .processors.reference_processor import ReferenceProcessor
from .config.config_loader import ConfigLoader
from .cli.display import create_display
from .utils.db_session import get_db_session


def setup_logging(debug: bool = False):
    """Setup logging configuration"""
    # Create logs directory in app root
    app_root = '/var/www/html'
    logs_dir = os.path.join(app_root, 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    # Create log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(logs_dir, f'import_{timestamp}.log')

    # Configure logging
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler() if not debug else logging.NullHandler()
        ]
    )

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generic Import Processor for BSM and CRS data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''
            Examples:
              %(prog)s --interactive --import-type bsm
                Process BSM imports interactively with default settings
                
              %(prog)s --interactive --import-type crs --days 14 --folder INBOX
                Process CRS imports from last 14 days in INBOX only
                
              %(prog)s --cron --import-type bsm
                Run BSM import in cron mode
                
              %(prog)s --interactive --import-type crs --folder "INBOX.Archive" --force
                Force process CRS imports from Archive folder
            
            Import Types:
              bsm    BSM Mountain Accidents
              crs    CRS Montagne Reports
        '''))
    
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--cron',
        action='store_true',
        help='Run in cron mode with minimal output'
    )
    mode_group.add_argument(
        '--interactive',
        action='store_true',
        help='Run in interactive mode with full UI'
    )
    
    parser.add_argument(
        '--import-type',
        type=str,
        choices=['bsm', 'crs'],
        help='Type of import to process (required)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        help='Number of days to look back (overrides config default)'
    )
    
    parser.add_argument(
        '--folder',
        type=str,
        action='append',
        metavar='FOLDER',
        help='IMAP folder to scan (can be specified multiple times)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force processing of files regardless of hash status'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Additional validation
    if not args.cron and not args.import_type:
        parser.error("--import-type is required in interactive mode")
    
    return args

async def process_email(email_msg, import_type: str, temp_dir: str, display, force: bool = False):
    """Process a single email message"""
    try:
        # Create database session
        session = get_db_session()

        # Initialize processors
        email_processor = EmailProcessor()
        reference_processor = ReferenceProcessor(force_process=force)
        
        # Set display handlers
        email_processor.set_display(display)
        reference_processor.set_display(display)
        
        # Extract and validate attachments
        display.update('extract', 'working')
        extract_dir, extracted_files = await email_processor.extract_attachment(
            email_msg, 
            import_type,
            temp_dir
        )
        display.update('extract', 'done', details=f"{len(extracted_files)} files extracted")
        
        # Process reference data
        display.update('process', 'working')
        processed_files, skipped_files = await reference_processor.process_reference_files(
            extract_dir,
            import_type,
            session
        )
        
        summary = f"Processed {len(processed_files)}, skipped {len(skipped_files)} files"
        display.update('process', 'done', details=summary)
        
        return {
            'processed_files': processed_files,
            'skipped_files': skipped_files
        }
        
    except Exception as e:
        # Rollback the session in case of any error
        if 'session' in locals():
            session.rollback()
        display.error(f"Error processing email: {str(e)}")
        raise
    finally:
        # Ensure session is closed
        if 'session' in locals():
            session.close()

async def run_cron():
    """Run processor in cron mode"""
    with create_display(is_cron=True) as display:
        try:
            # Initialize processor
            email_processor = EmailProcessor()
            email_processor.set_display(display)
            
            # List available emails
            display.update('init', 'working')
            emails = await email_processor.list_sender_emails(all_folders=False)
            
            if not emails:
                display.update('init', 'done', details='No emails to process')
                return
            
            # Process first valid email
            with tempfile.TemporaryDirectory() as temp_dir:
                for email in emails:
                    try:
                        # Get and process email
                        msg = await email_processor.get_email_message(
                            email['uid'],
                            email['folder'],
                            email['import_type']
                        )
                        
                        display.update('init', 'done', 
                            details=f"Processing email from {email['date']}")
                        
                        await process_email(msg, email['import_type'], temp_dir, display)
                        break
                        
                    except Exception as e:
                        display.error(f"Error processing email: {str(e)}")
                        continue
            
        except Exception as e:
            display.error(f"Error in cron mode: {str(e)}")
            raise

async def run_interactive(days: Optional[int] = None, import_type: Optional[str] = None, force: bool = False, folders: Optional[list[str]] = None):
    """Run processor in interactive mode"""
    with create_display() as display:
        try:
            # Initialize processor
            email_processor = EmailProcessor()
            email_processor.set_display(display)
            
            # List available emails
            display.update('init', 'working')
            emails = await email_processor.list_sender_emails(
                days=days,
                folders=folders,
                import_type=import_type
            )
            
            if not emails:
                display.update('init', 'done', details='No emails found')
                return
            
            # Show email selection
            await display.show_email_selection(emails)
            selected = await display.get_email_selection(emails)
            
            if selected:
                display.update('init', 'done', 
                    details=f"Processing email from {selected['date']}")
                
                # Get and process selected email
                msg = await email_processor.get_email_message(
                    selected['uid'],
                    selected['folder'],
                    selected['import_type']
                )
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    await process_email(msg, selected['import_type'], temp_dir, display, force)
            else:
                display.update('init', 'done', details='No email selected')
            
        except Exception as e:
            display.error(f"Error in interactive mode: {str(e)}")
            raise

async def main():
    """Main entry point"""
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Setup logging
        setup_logging(args.debug)
        logger = logging.getLogger(__name__)
        
        # Load environment variables
        env_path = '/var/www/html/.env'
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.debug(f".env file loaded from {env_path}")
        else:
            logger.warning(f"No .env file found at {env_path}")
        
        # Log startup information
        logger.debug(f"Starting import processor with args: {args}")
        
        # Run in appropriate mode
        if args.cron:
            await run_cron()
        else:
            await run_interactive(
                days=args.days,
                import_type=args.import_type,
                force=args.force,
                folders=args.folder
            )
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception("Fatal error")
        print(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())