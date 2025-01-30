# utils/data_converter.py

from datetime import datetime
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

def convert_field(value: Any, field_type: str, field_format: Optional[str] = None) -> any:
    """
    Convert field value based on configuration
    
    Args:
        value: Value to convert
        field_type: Target data type
        field_format: Optional format string for dates/times
        
    Returns:
        Converted value
    """
    if value is None:
        return None
        
    try:
        # Always strip string values first
        if isinstance(value, str):
            value = value.strip()
            
        # Handle different data types
        if field_type == 'string':
            return str(value).strip() if value else None
            
        elif field_type == 'integer':
            if isinstance(value, str) and not value.isdigit():
                # If it's a string containing non-digits (like '2B147'), 
                # return as is for lookup processing
                return value
            return int(str(value).strip())
            
        elif field_type == 'float':
            return float(str(value).strip())
            
        elif field_type == 'boolean':
            return _convert_boolean(value)
            
        elif field_type == 'date':
            return _convert_date(value, field_format)
            
        elif field_type == 'datetime':
            return _convert_datetime(value, field_format)
            
        elif field_type == 'array':
            return _convert_array(value)
            
        else:
            logger.warning(f"Unknown field type: {field_type}")
            return value
            
    except Exception as e:
        logger.error(f"Error converting value '{value}' to {field_type}: {str(e)}")
        return None

def _convert_boolean(value: Any) -> bool:
    """Convert value to boolean"""
    if isinstance(value, bool):
        return value
        
    if isinstance(value, str):
        value = value.strip().lower()
        if value in ('true', '1', 'yes', 'y'):
            return True
        if value in ('false', '0', 'no', 'n'):
            return False
            
    if isinstance(value, (int, float)):
        return bool(value)
        
    return False

def _convert_date(value: Any, date_format: Optional[str] = None) -> Optional[datetime]:
    """Convert value to date"""
    if isinstance(value, datetime):
        return value.date()
        
    if not isinstance(value, str):
        return None
        
    value = value.strip()
    
    # Try specified format first
    if date_format:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            pass
    
    # Try common formats
    formats = [
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%d/%m/%Y',
        '%Y/%m/%d',
        '%d.%m.%Y',
        '%Y.%m.%d'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
            
    return None

def _convert_datetime(value: Any, datetime_format: Optional[str] = None) -> Optional[datetime]:
    """Convert value to datetime"""
    if isinstance(value, datetime):
        return value
        
    if not isinstance(value, str):
        return None
        
    value = value.strip()
    
    # Try specified format first
    if datetime_format:
        try:
            return datetime.strptime(value, datetime_format)
        except ValueError:
            pass
    
    # Try common formats
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%d-%m-%Y %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
        '%Y/%m/%d %H:%M:%S'
    ]
    
    # Also try with milliseconds
    formats.extend([f + '.%f' for f in formats])
    
    # Try with timezone
    formats.extend([f + '%z' for f in formats])
    
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
            
    return None

def _convert_array(value: Any) -> list:
    """Convert value to array"""
    if isinstance(value, list):
        return value
        
    if isinstance(value, str):
        # Handle comma-separated string
        return [item.strip() for item in value.split(',') if item.strip()]
        
    if isinstance(value, (int, float, bool)):
        return [value]
        
    return []

def convert_to_sql_value(value: Any) -> str:
    """
    Convert value to SQL-safe string
    
    Args:
        value: Value to convert
        
    Returns:
        SQL-safe string representation
    """
    if value is None:
        return 'NULL'
        
    if isinstance(value, bool):
        return '1' if value else '0'
        
    if isinstance(value, (int, float)):
        return str(value)
        
    if isinstance(value, datetime):
        return f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'"
        
    if isinstance(value, list):
        # Convert array to comma-separated string
        return f"'{','.join(str(x) for x in value)}'"
        
    # Escape string value
    escaped_value = str(value).replace("'", "''")
    return f"'{escaped_value}'"