# tests/test_data_converter.py

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, date
from etl_processor.utils.data_converter import convert_field, convert_to_sql_value

def test_error_handling():
    """Test error handling in conversion"""
    with patch('etl_processor.utils.data_converter.logger') as mock_logger:
        # Test integer conversion error
        result = convert_field("abc", "integer")
        assert result is None
        mock_logger.error.assert_called_with(
            "Error converting 'abc' to integer: invalid literal"
        )
        mock_logger.reset_mock()
        
        # Test float conversion error
        result = convert_field("not a float", "float")
        assert result is None
        mock_logger.error.assert_called_with(
            "Error converting 'not a float' to float: could not convert string to float: 'not a float'"
        )
        mock_logger.reset_mock()
        
        # Test date conversion error
        result = convert_field("invalid date", "date")
        assert result is None
        assert mock_logger.error.called
        assert "Error converting 'invalid date' to date" in mock_logger.error.call_args[0][0]
        mock_logger.reset_mock()
        
        # Test datetime conversion error
        result = convert_field("invalid time", "datetime")
        assert result is None
        assert mock_logger.error.called
        assert "Error converting 'invalid time' to datetime" in mock_logger.error.call_args[0][0]
        mock_logger.reset_mock()
        
        # Test unknown type warning
        result = convert_field("test", "unknown_type")
        assert result == "test"
        mock_logger.warning.assert_called_with("Unknown field type: unknown_type")