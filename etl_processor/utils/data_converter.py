# etl_processor/utils/data_converter.py

from datetime import datetime
from typing import Any, Optional
import logging
from dateutil import parser
import re

logger = logging.getLogger(__name__)

def convert_field(value: Any, field_type: str, field_format: Optional[str] = None) -> Any:
    """
    Convert field value based on configuration with enhanced date parsing
    
    Args:
        value: Input value to convert
        field_type: Target type for conversion
        field_format: Optional format specification for parsing
    
    Returns:
        Converted value or None if conversion fails
    """
    if value is None:
        return None
        
    # Clean string input
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    try:
        if field_type == 'string':
            return str(value) if value else None
            
        elif field_type == 'integer':
            if isinstance(value, str):
                try:
                    float_val = float(value)
                    return int(float_val)
                except ValueError:
                    logger.error(f"Error converting '{value}' to integer: invalid literal")
                    return None
            return int(value)
            
        elif field_type == 'float':
            try:
                return float(value)
            except (TypeError, ValueError) as e:
                logger.error(f"Error converting '{value}' to float: {str(e)}")
                return None
            
        elif field_type == 'boolean':
            if isinstance(value, bool):
                return value
            try:
                str_val = str(value).lower().strip()
                return str_val in ('true', 'yes', '1', 't', 'y')
            except ValueError as e:
                logger.error(f"Error converting '{value}' to boolean: {str(e)}")
                return None
            
        elif field_type == 'date':
            try:
                # If specific format is provided, try parsing with that first
                if field_format:
                    try:
                        return datetime.strptime(value, field_format).date()
                    except ValueError:
                        logger.warning(f"Failed to parse date with specified format {field_format}")
                
                # If no format or format parsing fails, use advanced parsing
                return _parse_flexible_date(value)
                
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting '{value}' to date: {str(e)}")
                return None
            
        elif field_type == 'datetime':
            try:
                # If specific format is provided, try parsing with that first
                if field_format:
                    try:
                        return datetime.strptime(value, field_format)
                    except ValueError:
                        logger.warning(f"Failed to parse datetime with specified format {field_format}")
                
                # If no format or format parsing fails, use advanced parsing
                parsed_dt = _parse_flexible_datetime(value)
                return parsed_dt
                
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting '{value}' to datetime: {str(e)}")
                return None
            
        elif field_type == 'array':
            if isinstance(value, list):
                return value
            if not isinstance(value, str) or not value.strip():
                return []
            
            if ',' in value:
                return [item.strip() for item in value.split(',') if item.strip()]
            return [value]
        
        else:
            logger.warning(f"Unknown field type: {field_type}")
            return value
            
    except Exception as e:
        logger.error(f"Error converting '{value}' to {field_type}: {str(e)}")
        return None

def _parse_flexible_date(value: str) -> datetime.date:
    """
    Parse date with multiple potential formats
    
    Supports these formats (among others):
    - YYYY-MM-DD (ISO)
    - DD-MM-YYYY
    - MM-DD-YYYY
    - Various separators (-, /, .)
    """
    # Try dateutil parser first (most flexible)
    try:
        return parser.parse(value).date()
    except Exception:
        # More explicit parsing for additional formats
        formats_to_try = [
            '%Y-%m-%d',     # ISO format
            '%d-%m-%Y',     # Day-Month-Year
            '%m-%d-%Y',     # Month-Day-Year
            '%d/%m/%Y',     # Day/Month/Year
            '%m/%d/%Y',     # Month/Day/Year
            '%d.%m.%Y',     # Day.Month.Year
            '%m.%d.%Y',     # Month.Day.Year
        ]
        
        for fmt in formats_to_try:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse date from '{value}'")

def _parse_flexible_datetime(value: str) -> datetime:
    """
    Parse datetime with multiple potential formats
    
    Supports these formats (among others):
    - ISO format
    - Various date formats with optional time
    """
    # Try dateutil parser first (most flexible)
    try:
        return parser.parse(value)
    except Exception:
        # More explicit parsing for additional formats
        formats_to_try = [
            '%Y-%m-%d %H:%M:%S',   # ISO-like with time
            '%d-%m-%Y %H:%M:%S',   # Day-Month-Year with time
            '%m-%d-%Y %H:%M:%S',   # Month-Day-Year with time
            '%Y-%m-%d %H:%M',      # ISO-like with partial time
            '%d-%m-%Y %H:%M',      # Day-Month-Year with partial time
            '%m-%d-%Y %H:%M',      # Month-Day-Year with partial time
        ]
        
        for fmt in formats_to_try:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse datetime from '{value}'")

def convert_to_sql_value(value: Any) -> str:
    """Convert value to SQL-safe string"""
    if value is None:
        return 'NULL'
        
    if isinstance(value, bool):
        return '1' if value else '0'
        
    if isinstance(value, (int, float)):
        return str(value)
        
    if isinstance(value, datetime):
        return f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'"
        
    if isinstance(value, list):
        return f"'{','.join(str(x) for x in value)}'"
        
    return f"'{str(value).replace(chr(39), chr(39)+chr(39))}'"