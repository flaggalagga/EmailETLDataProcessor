# README.md

# Generic ETL Processor

A configuration-driven ETL processor designed to handle various types of email-based data imports. The system is built to be completely generic, allowing new import types to be added through configuration without code changes.

## Features

- Fully configuration-driven import processing
- Support for multiple data formats (XML, JSON)
- Interactive CLI with real-time progress visualization
- Comprehensive security checks:
  - Email security (SPF, DKIM, DMARC)
  - File validation
  - Malware scanning with ClamAV
  - ZIP bomb protection
  - XML entity expansion protection
  - JSON depth and size limits
- Interactive and cron modes
- Detailed progress visualization
- Robust error handling with transaction management
- Complete logging system
- Support for both MySQL and MariaDB

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd etl_processor
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

3. Install ClamAV (optional, for malware scanning):
```bash
# Ubuntu/Debian
sudo apt-get install clamav clamav-daemon

# CentOS/RHEL
sudo yum install clamav clamd
```

## Configuration

### Environment Variables

Create a `.env` file with the following required variables:
```ini
# Email settings
IMAP_HOST=imap.example.com
IMAP_USERNAME=your_username
IMAP_PASSWORD=your_password
IMAP_FOLDER=INBOX

# Database settings
MYSQL_HOST=localhost
MYSQL_PORT_INTERNAL=3306
MYSQL_DATABASE=your_database
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password

# Email notification settings
MAILJET_SMTP=smtp.mailjet.com
MAILJET_SMTP_USER=user
MAILJET_SMTP_PASS=pass
MAILJET_SMTP_PORT=587
EMAIL_FROM=notifications@example.com
EMAIL_IMPORTS=admin@example.com

# Security settings
CLAMD_SOCKET=/var/run/clamav/clamd.ctl
```

### Import Configuration

Create or modify `config/config.yaml` to define your import types. Example configuration:
```yaml
imports:
  custom_import:
    name: "Custom Data Import"
    sender_email: "authorized@example.com"
    primary_attachment: "data.zip"
    days_lookback: 90
    inboxes:
      - INBOX
      - INBOX.Archive
    security:
      email_checks:
        - sender_domain
        - spf
        - dkim
        - dmarc
      malware_scan: true
      allowed_sender_domains:
        - example.com
      file_validation:
        max_size: "50MB"
        allowed_types:
          - application/xml
          - application/json
    # ... additional configuration as needed
```

## Usage

### Interactive Mode

Run the processor interactively with progress visualization:
```bash
python -m etl_processor.run_import --interactive
```

Options:
- `--months N`: Look back N months for emails (default: 3)
- `--import-type TYPE`: Process specific import type only
- `--debug`: Enable debug logging

Example interactive output:
```
⏱ Elapsed Time: 00:01:23
📥 Loading Email Attachment: [==========] 100%
📦 Extracting Files: [=========>] 95%
🔄 Processing Files: [=====>    ] 52%
```

### Cron Mode

Run the processor in automated mode:
```bash
python -m etl_processor.run_import --cron
```

Add to crontab:
```crontab
0 * * * * /path/to/venv/bin/python -m etl_processor.run_import --cron
```

## Project Structure

```
etl_processor/
├── config/
│   ├── __init__.py
│   ├── config.yaml               # Import configurations
│   └── config_loader.py          # Configuration management
├── security/
│   ├── __init__.py
│   ├── email_security.py         # Email security checks
│   └── file_security.py          # File validation
├── processors/
│   ├── __init__.py
│   ├── base_processor.py         # Base processor class
│   ├── email_processor.py        # Email processing
│   └── reference_processor.py    # Reference data processing
├── utils/
│   ├── __init__.py
│   ├── data_converter.py         # Data type conversion
│   ├── file_hash_tracker.py      # File tracking
│   ├── email_utils.py            # Email utilities
│   └── db_session.py            # Database session management
└── cli/
    ├── __init__.py
    ├── display.py               # CLI interface
    └── progress.py              # Progress visualization
```

## Error Handling

The system provides comprehensive error handling:

1. Security Errors:
   - Invalid email signatures
   - Failed malware scans
   - ZIP extraction issues

2. Data Errors:
   - XML/JSON parsing failures
   - Data type conversion errors
   - Validation failures

3. Database Errors:
   - Transaction failures
   - Foreign key violations
   - Connection issues

All errors are:
- Logged to file
- Displayed in CLI (interactive mode)
- Sent via email (cron mode)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the Development Standards in TECHNICAL.md
4. Write tests for new features
5. Create a Pull Request

## License

[Your License Here]