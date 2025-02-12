# tests/test_enhanced_date_conversion.py

import pytest
from datetime import datetime, date
from etl_processor.utils.data_converter import convert_field

def test_flexible_date_conversion():
    """Test various date format conversions"""
    test_cases = [
        # ISO Format
        ('2025-02-04', 'date', None, date(2025, 2, 4)),
        ('2025-02-04', 'datetime', None, datetime(2025, 2, 4)),
        
        # Day-Month-Year
        ('04-02-2025', 'date', None, date(2025, 2, 4)),
        ('04-02-2025', 'datetime', None, datetime(2025, 2, 4)),
        
        # Month-Day-Year
        ('02-04-2025', 'date', None, date(2025, 2, 4)),
        ('02-04-2025', 'datetime', None, datetime(2025, 2, 4)),
        
        # With different separators
        ('04/02/2025', 'date', None, date(2025, 2, 4)),
        ('04.02.2025', 'date', None, date(2025, 2, 4)),
        
        # With time
        ('04-02-2025 15:30:45', 'datetime', None, datetime(2025, 2, 4, 15, 30, 45)),
        ('2025-02-04 15:30:45', 'datetime', None, datetime(2025, 2, 4, 15, 30, 45)),
        
        # Specific format override
        ('04/02/2025', 'date', '%d/%m/%Y', date(2025, 2, 4)),
        ('04-02-2025', 'date', '%d-%m-%Y', date(2025, 2, 4)),
    ]
    
    for input_val, field_type, field_format, expected in test_cases:
        result = convert_field(input_val, field_type, field_format)
        assert result == expected, f"Failed for {input_val} ({field_type})"

def test_invalid_date_conversion():
    """Test handling of invalid date formats"""
    invalid_cases = [
        ('invalid-date', 'date'),
        ('99-99-9999', 'date'),
        ('2025-13-32', 'date')
    ]
    
    for input_val, field_type in invalid_cases:
        result = convert_field(input_val, field_type)
        assert result is None, f"Should return None for invalid date: {input_val}"

def test_date_conversion_with_specific_format():
    """Test date conversion with specific format"""
    # Formats that might be ambiguous without specification
    test_cases = [
        # Ambiguous format
        ('02/04/2025', 'date', '%m/%d/%Y', date(2025, 2, 4)),  # Month/Day/Year
        ('02/04/2025', 'date', '%d/%m/%Y', date(2025, 4, 2)),  # Day/Month/Year
        
        # Time formats
        ('04-02-2025 15:30', 'datetime', '%d-%m-%Y %H:%M', datetime(2025, 2, 4, 15, 30)),
        ('2025-02-04 15:30', 'datetime', '%Y-%m-%d %H:%M', datetime(2025, 2, 4, 15, 30))
    ]
    
    for input_val, field_type, field_format, expected in test_cases:
        result = convert_field(input_val, field_type, field_format)
        assert result == expected, f"Failed for {input_val} with format {field_format}"