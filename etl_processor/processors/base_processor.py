# processors/base_processor.py

import logging
from typing import Optional
from sqlalchemy.orm import Session
from ..cli.display import DisplayBase

class BaseProcessor:
    """Base class for all processors"""
    
    def __init__(self, is_cron: bool = False):
        """
        Initialize base processor
        
        Args:
            is_cron: Whether running in cron mode
        """
        self.logger = logging.getLogger(__name__)
        self.display: Optional[DisplayBase] = None
        self.is_cron = is_cron

    def update_progress(self, stage: str, status: str = 'working', 
                       progress: Optional[int] = None, details: Optional[str] = None):
        """
        Update progress display if available
        
        Args:
            stage: Current processing stage
            status: Current status ('working', 'done', 'error', etc.)
            progress: Optional progress percentage (0-100)
            details: Optional status details
        """
        if self.display:
            self.display.update(stage, status, progress, details)

    def handle_error(self, message: str, error: Exception, session: Optional[Session] = None):
        """
        Handle errors consistently
        
        Args:
            message: Error message
            error: Exception that occurred
            session: Optional database session to rollback
        """
        # Log error unless in cron mode
        if not self.is_cron:
            self.logger.error(f"{message}: {str(error)}", exc_info=True)
        
        # Rollback database session if provided
        if session:
            session.rollback()
            
        # Update display if available
        if self.display:
            self.display.error(message)
            
        # Return error for propagation if needed
        return error

    def handle_warning(self, message: str):
        """
        Handle warnings consistently
        
        Args:
            message: Warning message
        """
        if not self.is_cron:
            self.logger.warning(message)
        if self.display:
            self.display.warning(message)

    def handle_success(self, message: str):
        """
        Handle success messages consistently
        
        Args:
            message: Success message
        """
        if not self.is_cron:
            self.logger.info(message)
        if self.display:
            self.display.success(message)

    def set_display(self, display: DisplayBase):
        """
        Set the display handler
        
        Args:
            display: Display handler instance
        """
        self.display = display