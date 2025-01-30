# cli/display.py

import sys
import time
import threading
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional, Dict, List, Any
from tabulate import tabulate
import logging
from colorama import init, Fore, Back, Style

# Initialize colorama
init()

class LiveTimer(threading.Thread):
    """Live timer thread for showing elapsed time"""
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.start_time = time.time()
        self.current_time = "00:00:00"
        self._lock = threading.Lock()
        self.daemon = True
        
    def run(self):
        while self.running:
            elapsed = int(time.time() - self.start_time)
            with self._lock:
                self.current_time = str(timedelta(seconds=elapsed))
            time.sleep(0.2)
            
    def stop(self):
        self.running = False
        
    def get_time(self) -> str:
        with self._lock:
            return self.current_time

class MultiProgress:
    """Multi-stage progress display"""
    
    STAGES = {
        'pending': '⋯',
        'working': '⚙️',
        'done': '✓',
        'error': '❌',
        'download': '📥',
        'extract': '📦',
        'process': '🔄',
        'parse': '🔍',
        'save': '💾',
    }
    
    def __init__(self):
        self.timer = LiveTimer()
        self.timer.start()
        self.stages = {}
        self.last_lines = 0
        self.current_stage = None
        self.finished = False
        
    def add_stage(self, name: str, description: str, status: str = 'pending'):
        """Add a new stage to track"""
        self.stages[name] = {
            'description': description,
            'status': status,
            'progress': 0,
            'details': ''
        }
        
    def update_stage(self, name: str, status: str, progress: int = None, details: str = None):
        """Update stage status"""
        if self.finished:
            return
            
        if name in self.stages:
            self.stages[name]['status'] = status
            if progress is not None:
                self.stages[name]['progress'] = progress
            if details is not None:
                self.stages[name]['details'] = details
            self.current_stage = name
            self._draw()
            
    def _get_progress_bar(self, progress: int, width: int = 30) -> str:
        """Generate progress bar string"""
        filled = int(width * progress / 100)
        return f"[{Fore.GREEN}{'=' * filled}{Fore.WHITE}{' ' * (width - filled)}]"
    
    def _clear_display(self):
        """Clear previous display"""
        if self.last_lines > 0:
            for _ in range(self.last_lines + 1):
                sys.stdout.write('\033[F')
                sys.stdout.write('\033[K')
    
    def _draw(self):
        """Draw current progress state"""
        if self.finished:
            return
            
        self._clear_display()
        
        lines = []
        elapsed = self.timer.get_time()
        lines.append(f"{Fore.CYAN}⏱ Elapsed Time: {Style.BRIGHT}{elapsed}{Style.RESET_ALL}")
        
        for name, stage in self.stages.items():
            icon = self.STAGES.get(stage['status'], self.STAGES['pending'])
            color = Fore.GREEN if stage['status'] == 'done' else \
                   Fore.YELLOW if stage['status'] == 'working' else \
                   Fore.RED if stage['status'] == 'error' else \
                   Fore.WHITE
            
            if stage['status'] == 'working' and stage['progress'] is not None:
                progress_bar = self._get_progress_bar(stage['progress'])
                status_str = f"{progress_bar} {stage['progress']}%"
            else:
                status_str = stage['status'].upper()
            
            line = f"{icon} {color}{stage['description']}{Style.RESET_ALL}: {status_str}"
            if stage['details']:
                line += f" ({stage['details']})"
            
            if name == self.current_stage:
                line = f"{Style.BRIGHT}{line}{Style.RESET_ALL}"
            
            lines.append(line)
        
        lines.append("")
        
        output = '\n'.join(lines)
        sys.stdout.write(output)
        sys.stdout.flush()
        self.last_lines = len(lines)
        
    def finish(self):
        """Finish progress display"""
        if self.finished:
            return
            
        self.finished = True
        self.timer.stop()
        self._clear_display()
        
        lines = []
        total_time = self.timer.get_time()
        lines.append(f"{Fore.CYAN}⏱ Total Time: {Style.BRIGHT}{total_time}{Style.RESET_ALL}")
        
        for name, stage in self.stages.items():
            icon = self.STAGES.get(stage['status'], self.STAGES['pending'])
            color = Fore.GREEN if stage['status'] == 'done' else \
                   Fore.RED if stage['status'] == 'error' else \
                   Fore.WHITE
            
            line = f"{icon} {color}{stage['description']}{Style.RESET_ALL}: {stage['status'].upper()}"
            if stage['details']:
                line += f" ({stage['details']})"
            
            lines.append(line)
            
        lines.append("")
        output = '\n'.join(lines)
        sys.stdout.write(output)
        sys.stdout.flush()

class DisplayBase:
    """Base display handler"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.progress = None
    
    def print(self, message: str):
        print(message)
    
    def update(self, stage: str, status: str = 'working', progress: int = None, details: str = None):
        if self.progress:
            self.progress.update_stage(stage, status, progress, details)
    
    def success(self, message: str):
        print(f"{Fore.GREEN}✨ {message}{Style.RESET_ALL}")
        
    def warning(self, message: str):
        print(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")
        
    def error(self, message: str):
        print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")
        
    def finish(self):
        if self.progress:
            self.progress.finish()

class InteractiveDisplay(DisplayBase):
    """Interactive display handler"""
    
    def __init__(self):
        super().__init__()
        self.progress = MultiProgress()
        self.setup_stages()
        
    def setup_stages(self):
        """Setup default stages"""
        self.progress.add_stage('init', 'Initializing Import')
        self.progress.add_stage('download', 'Loading Email Attachment')
        self.progress.add_stage('extract', 'Extracting Files')
        self.progress.add_stage('process', 'Processing Files')
        self.progress.add_stage('parse', 'Parsing Data')
        self.progress.add_stage('save', 'Saving to Database')
    
    def print(self, message: str):
        """Print message without disrupting progress display"""
        if self.progress:
            sys.stdout.write('\r' + ' ' * 100 + '\r')
        print(message)
        if self.progress:
            self.progress.update_stage(self.progress.current_stage, 'working')

    def success(self, message: str):
        """Show success message and complete progress"""
        if self.progress:
            for stage in self.progress.stages:
                if self.progress.stages[stage]['status'] not in ['error', 'done']:
                    self.progress.update_stage(stage, 'done')
            self.progress.finish()
        print(f"\n{Fore.GREEN}✨ {message}{Style.RESET_ALL}\n")

    def warning(self, message: str):
        """Show warning without disrupting progress"""
        if self.progress:
            sys.stdout.write('\r' + ' ' * 100 + '\r')
        print(f"\n{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")
        if self.progress:
            self.progress.update_stage(self.progress.current_stage, 'working')

    def error(self, message: str):
        """Show error and mark current stage as failed"""
        if self.progress:
            sys.stdout.write('\r' + ' ' * 100 + '\r')
        print(f"\n{Fore.RED}✗ {message}{Style.RESET_ALL}")
        if self.progress:
            self.progress.update_stage(self.progress.current_stage, 'error')

    async def show_email_selection(self, emails: List[Dict]):
        """Show available emails for selection"""
        table_data = []
        for i, email in enumerate(emails, 1):
            date_str = email['date'].strftime('%Y-%m-%d %H:%M')
            has_attachment = f"{Fore.GREEN}✓{Style.RESET_ALL}" if email['has_attachment'] else f"{Fore.RED}✗{Style.RESET_ALL}"
            
            folder = email['folder']
            if 'Non Conforme' in folder:
                folder = f"{Fore.RED}{folder}{Style.RESET_ALL}"
            elif 'Archive' in folder:
                folder = f"{Fore.BLUE}{folder}{Style.RESET_ALL}"
            
            table_data.append([
                f"{Fore.CYAN}{i}{Style.RESET_ALL}",
                date_str,
                folder,
                email['subject'],
                has_attachment,
                email['import_type']
            ])
        
        print(f"\n{Fore.GREEN}Available emails:{Style.RESET_ALL}")
        print(tabulate(
            table_data,
            headers=['#', 'Date', 'Folder', 'Subject', 'Has Attachment', 'Type'],
            tablefmt='fancy_grid'
        ))

    async def get_email_selection(self, emails: List[Dict]) -> Optional[Dict]:
        """Get user's email selection"""
        while True:
            try:
                choice = input(f"\n{Fore.CYAN}Enter email number to process (0 to exit):{Style.RESET_ALL} ").strip()
                if choice == '0':
                    return None
                
                index = int(choice) - 1
                if 0 <= index < len(emails):
                    selected = emails[index]
                    
                    print(f"\n{Fore.GREEN}Selected email details:{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Date:{Style.RESET_ALL} {selected['date']}")
                    print(f"{Fore.CYAN}Folder:{Style.RESET_ALL} {selected['folder']}")
                    print(f"{Fore.CYAN}Subject:{Style.RESET_ALL} {selected['subject']}")
                    print(f"{Fore.CYAN}Import Type:{Style.RESET_ALL} {selected['import_type']}")
                    
                    confirm = input(f"\n{Fore.YELLOW}Process this email? (y/n):{Style.RESET_ALL} ").strip().lower()
                    if confirm == 'y':
                        return selected
                    continue
                    
                self.error("Invalid selection")
            except ValueError:
                self.error("Please enter a valid number")
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
                return None

class CronDisplay(DisplayBase):
    """Minimal display for cron mode"""
    
    def print(self, message: str):
        """Log without printing"""
        self.logger.debug(message)

    def success(self, message: str):
        """Log without printing"""
        self.logger.info(message)

    def warning(self, message: str):
        """Log without printing"""
        self.logger.warning(message)

    def error(self, message: str):
        """Log without printing"""
        self.logger.error(message)

    def update(self, stage: str, status: str = 'working', progress: int = None, details: str = None):
        """Silent update"""
        pass

    async def show_email_selection(self, emails: List[Dict]):
        """No display in cron mode"""
        pass

    async def get_email_selection(self, emails: List[Dict]) -> Optional[Dict]:
        """Auto-select first email in cron mode"""
        return emails[0] if emails else None

@contextmanager
def create_display(is_cron: bool = False):
    """Create appropriate display handler"""
    try:
        display = CronDisplay() if is_cron else InteractiveDisplay()
        yield display
    finally:
        if hasattr(display, 'finish'):
            display.finish()