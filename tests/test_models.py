"""
Unit tests for data models and validation.
"""

import pytest
from datetime import datetime
from decimal import Decimal

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))

from app.models.trade import Trade, TradeSide, TradeStatus, WinLoss
from app.models.position import Position, PositionSide, PositionStatus
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.models.custom_fields import CustomFieldConfig, FieldType
from app.utils.validators import ValidationError


class TestTradeModel:
    """Test cases for Trade model."""
    
    def test_valid_trade_creation(self):
        """Test creating a valid trade."""
        trade = Trade(
            id='test-123',
            exchange='bitunix',
            symbol='BTCUSDT',
            side=TradeSide.LONG,
            entry_price=Decimal('50000.00'),
            quantity=Decimal('0.1'),
            entry_time=datetime.now(),
            status=TradeStatus.OPEN
        )
        
        assert trade.id == 'test-123'
        assert trade.exchange == 'bitunix'
        assert trade.symbol == 'BTCUSDT'
        assert trade.side == TradeSide.LONG
        assert trade.entry_price == Decimal('50000.00')
        assert trade.quantity == Decimal('0.1')
        assert trade.status == TradeStatus.OPEN
        assert trade.confluences == []
        assert trade.custom_fields == {}
    
    def test_trade_validation_errors(self):
        """Test trade validation errors."""
        # Test empty ID
        with pytest.raises(ValueError, match="Trade ID must be a non-empty string"):
            Trade(
                id='',
                exchange='bitunix',
                symbol='BTCUSDT',
                side=TradeSide.LONG,
                entry_price=Decimal('50000.00'),
                quantity=Decimal('0.1'),
                entry_time=datetime.now(),
                status=TradeStatus.OPEN
            )
        
        # Test negative price
        with pytest.raises(ValueError, match="Entry price must be a positive Decimal"):
            Trade(
                id='test-123',
                exchange='bitunix',
                symbol='BTCUSDT',
                side=TradeSide.LONG,
                entry_price=Decimal('-50000.00'),
                quantity=Decimal('0.1'),
                entry_time=datetime.now(),
                status=TradeStatus.OPEN
            )
    
    def test_trade_pnl_calculation(self):
        """Test PnL calculation for trades."""
        # Long trade
        long_trade = Trade(
            id='long-123',
            exchange='bitunix',
            symbol='BTCUSDT',
            side=TradeSide.LONG,
            entry_price=Decimal('50000.00'),
            quantity=Decimal('0.1'),
            entry_time=datetime.now(),
            status=TradeStatus.OPEN
        )
        
        pnl = long_trade.calculate_pnl(Decimal('55000.00'))
        assert pnl == Decimal('500.00')  # (55000 - 50000) * 0.1
        
        # Short trade
        short_trade = Trade(
            id='short-123',
            exchange='bitunix',
            symbol='BTCUSDT',
            side=TradeSide.SHORT,
            entry_price=Decimal('50000.00'),
            quantity=Decimal('0.1'),
            entry_time=datetime.now(),
            status=TradeStatus.OPEN
        )
        
        pnl = short_trade.calculate_pnl(Decimal('45000.00'))
        assert pnl == Decimal('500.00')  # (50000 - 45000) * 0.1
    
    def test_trade_confluence_management(self):
        """Test confluence management methods."""
        trade = Trade(
            id='test-123',
            exchange='bitunix',
            symbol='BTCUSDT',
            side=TradeSide.LONG,
            entry_price=Decimal('50000.00'),
            quantity=Decimal('0.1'),
            entry_time=datetime.now(),
            status=TradeStatus.OPEN
        )
        
        # Add confluence
        trade.add_confluence('Support/Resistance')
        assert 'Support/Resistance' in trade.confluences
        
        # Add duplicate confluence (should not duplicate)
        trade.add_confluence('Support/Resistance')
        assert trade.confluences.count('Support/Resistance') == 1
        
        # Remove confluence
        trade.remove_confluence('Support/Resistance')
        assert 'Support/Resistance' not in trade.confluences


class TestPositionModel:
    """Test cases for Position model."""
    
    def test_valid_position_creation(self):
        """Test creating a valid position."""
        position = Position(
            position_id='pos-456',
            symbol='ETHUSDT',
            side=PositionSide.LONG,
            size=Decimal('1.5'),
            entry_price=Decimal('3000.00'),
            mark_price=Decimal('3100.00'),
            unrealized_pnl=Decimal('150.00'),
            realized_pnl=Decimal('0.00'),
            status=PositionStatus.OPEN,
            open_time=datetime.now()
        )
        
        assert position.position_id == 'pos-456'
        assert position.symbol == 'ETHUSDT'
        assert position.side == PositionSide.LONG
        assert position.size == Decimal('1.5')
        assert position.get_total_pnl() == Decimal('150.00')
        assert position.is_profitable() == True
    
    def test_position_pnl_calculation(self):
        """Test position PnL calculations."""
        position = Position(
            position_id='pos-456',
            symbol='ETHUSDT',
            side=PositionSide.LONG,
            size=Decimal('1.0'),
            entry_price=Decimal('3000.00'),
            mark_price=Decimal('3100.00'),
            unrealized_pnl=Decimal('100.00'),
            realized_pnl=Decimal('50.00'),
            status=PositionStatus.OPEN,
            open_time=datetime.now()
        )
        
        # Test total PnL
        assert position.get_total_pnl() == Decimal('150.00')
        
        # Test unrealized PnL calculation
        calculated_unrealized = position.calculate_unrealized_pnl()
        assert calculated_unrealized == Decimal('100.00')  # (3100 - 3000) * 1.0


class TestExchangeConfigModel:
    """Test cases for ExchangeConfig model."""
    
    def test_valid_exchange_config_creation(self):
        """Test creating a valid exchange config."""
        config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_key_123',
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        
        assert config.name == 'bitunix'
        assert config.api_key_encrypted == 'encrypted_key_123'
        assert config.is_active == True
        assert config.is_connected() == True
        assert '🟢' in config.get_display_name()
    
    def test_exchange_config_status_management(self):
        """Test exchange config status management."""
        config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_key_123'
        )
        
        # Test activation/deactivation
        config.deactivate()
        assert config.is_active == False
        
        config.activate()
        assert config.is_active == True
        
        # Test connection status update
        config.update_connection_status(ConnectionStatus.ERROR)
        assert config.connection_status == ConnectionStatus.ERROR
        assert not config.is_connected()


class TestCustomFieldConfigModel:
    """Test cases for CustomFieldConfig model."""
    
    def test_valid_custom_field_creation(self):
        """Test creating a valid custom field config."""
        field_config = CustomFieldConfig(
            field_name='confluences',
            field_type=FieldType.MULTISELECT,
            options=['Support/Resistance', 'Moving Average', 'RSI'],
            is_required=False
        )
        
        assert field_config.field_name == 'confluences'
        assert field_config.field_type == FieldType.MULTISELECT
        assert len(field_config.options) == 3
        assert field_config.get_display_name() == 'Confluences'
    
    def test_custom_field_validation(self):
        """Test custom field value validation."""
        field_config = CustomFieldConfig(
            field_name='confluences',
            field_type=FieldType.MULTISELECT,
            options=['Support/Resistance', 'Moving Average', 'RSI']
        )
        
        # Valid multiselect value
        assert field_config.validate_value(['Support/Resistance', 'RSI']) == True
        
        # Invalid value (not in options)
        assert field_config.validate_value(['Invalid Option']) == False
        
        # Invalid type
        assert field_config.validate_value('Not a list') == False
    
    def test_custom_field_options_management(self):
        """Test custom field options management."""
        field_config = CustomFieldConfig(
            field_name='confluences',
            field_type=FieldType.MULTISELECT,
            options=['Support/Resistance']
        )
        
        # Add option
        field_config.add_option('Moving Average')
        assert 'Moving Average' in field_config.options
        
        # Remove option
        field_config.remove_option('Support/Resistance')
        assert 'Support/Resistance' not in field_config.options
        
        # Update all options
        new_options = ['RSI', 'MACD', 'Volume']
        field_config.update_options(new_options)
        assert field_config.options == new_options


if __name__ == '__main__':
    pytest.main([__file__])


# Additional tests for validation utilities
class TestValidationUtilities:
    """Test cases for enhanced validation utilities."""
    
    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        from app.utils.validators import DataValidator
        
        # Normal input
        result = DataValidator.sanitize_input("Hello World")
        assert result == "Hello World"
        
        # Input with control characters
        result = DataValidator.sanitize_input("Hello\x00\x01World")
        assert result == "HelloWorld"
        
        # Input with HTML tags (removes tags but keeps content, then removes dangerous chars)
        result = DataValidator.sanitize_input("<script>alert('xss')</script>Hello")
        assert result == "alert(xss)Hello"
        
        # Long input
        long_input = "a" * 2000
        result = DataValidator.sanitize_input(long_input, max_length=100)
        assert len(result) == 100
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        from app.utils.validators import DataValidator
        
        # Normal filename
        result = DataValidator.sanitize_filename("document.txt")
        assert result == "document.txt"
        
        # Filename with dangerous characters
        result = DataValidator.sanitize_filename("../../../etc/passwd")
        assert result == "etcpasswd"
        
        # Filename with invalid characters
        result = DataValidator.sanitize_filename("file<>:\"|?*.txt")
        assert result == "file_______.txt"
        
        # Empty filename
        result = DataValidator.sanitize_filename("")
        assert result == "unnamed_file"
    
    def test_validate_url(self):
        """Test URL validation."""
        from app.utils.validators import DataValidator, ValidationError
        
        # Valid URLs
        valid_urls = [
            "https://example.com",
            "http://localhost:8080",
            "https://api.example.com/v1/data",
            "http://192.168.1.1:3000"
        ]
        
        for url in valid_urls:
            result = DataValidator.validate_url(url)
            assert result == url
        
        # Invalid URLs
        invalid_urls = [
            "not_a_url",
            "ftp://example.com",  # Wrong scheme
            "https://",
            ""
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                DataValidator.validate_url(url)
    
    def test_validate_email(self):
        """Test email validation."""
        from app.utils.validators import DataValidator, ValidationError
        
        # Valid emails
        valid_emails = [
            "user@example.com",
            "test.email+tag@domain.co.uk",
            "user123@test-domain.org"
        ]
        
        for email in valid_emails:
            result = DataValidator.validate_email(email)
            assert result == email.lower()
        
        # Invalid emails
        invalid_emails = [
            "not_an_email",
            "@example.com",
            "user@",
            "user@.com",
            ""
        ]
        
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                DataValidator.validate_email(email)
    
    def test_validate_json_string(self):
        """Test JSON string validation."""
        from app.utils.validators import DataValidator, ValidationError
        
        # Valid JSON
        valid_json = '{"key": "value", "number": 123}'
        result = DataValidator.validate_json_string(valid_json)
        assert result == {"key": "value", "number": 123}
        
        # Invalid JSON
        with pytest.raises(ValidationError):
            DataValidator.validate_json_string('{"invalid": json}')
        
        # Empty string
        with pytest.raises(ValidationError):
            DataValidator.validate_json_string("")
    
    def test_validate_numeric_string(self):
        """Test numeric string validation."""
        from app.utils.validators import DataValidator, ValidationError
        
        # Valid numbers
        assert DataValidator.validate_numeric_string("123.45") == 123.45
        assert DataValidator.validate_numeric_string("-10") == -10.0
        assert DataValidator.validate_numeric_string("0") == 0.0
        
        # With range validation
        assert DataValidator.validate_numeric_string("50", min_value=0, max_value=100) == 50.0
        
        # Invalid numbers
        with pytest.raises(ValidationError):
            DataValidator.validate_numeric_string("not_a_number")
        
        # Out of range
        with pytest.raises(ValidationError):
            DataValidator.validate_numeric_string("150", min_value=0, max_value=100)
    
    def test_validate_ip_address(self):
        """Test IP address validation."""
        from app.utils.validators import DataValidator, ValidationError
        
        # Valid IPv4 addresses
        valid_ipv4 = [
            "192.168.1.1",
            "10.0.0.1",
            "255.255.255.255",
            "0.0.0.0"
        ]
        
        for ip in valid_ipv4:
            result = DataValidator.validate_ip_address(ip)
            assert result == ip
        
        # Invalid IP addresses
        invalid_ips = [
            "256.256.256.256",
            "192.168.1",
            "not_an_ip",
            ""
        ]
        
        for ip in invalid_ips:
            with pytest.raises(ValidationError):
                DataValidator.validate_ip_address(ip)


class TestErrorHandler:
    """Test cases for error handling utilities."""
    
    def test_format_validation_error(self):
        """Test validation error formatting."""
        from app.utils.validators import ErrorHandler, ValidationError
        
        error = ValidationError("Field is required")
        
        # Without field name
        result = ErrorHandler.format_validation_error(error)
        assert result == "Validation error: Field is required"
        
        # With field name
        result = ErrorHandler.format_validation_error(error, "username")
        assert result == "Validation error in 'username': Field is required"
    
    def test_format_api_error(self):
        """Test API error formatting."""
        from app.utils.validators import ErrorHandler
        
        error = ConnectionError("Connection failed")
        
        # Without operation
        result = ErrorHandler.format_api_error(error)
        assert "ConnectionError" in result
        assert "Connection failed" in result
        
        # With operation
        result = ErrorHandler.format_api_error(error, "fetching user data")
        assert "API error during fetching user data" in result
    
    def test_get_user_friendly_message(self):
        """Test user-friendly error message generation."""
        from app.utils.validators import ErrorHandler
        
        # Connection error
        error = ConnectionError("Failed to connect")
        result = ErrorHandler.get_user_friendly_message(error)
        assert "connect to the service" in result
        
        # Permission error
        error = PermissionError("Access denied")
        result = ErrorHandler.get_user_friendly_message(error)
        assert "Permission denied" in result
        
        # Unknown error
        error = ValueError("Some unknown error")
        result = ErrorHandler.get_user_friendly_message(error)
        assert "unexpected error occurred" in result


class TestInputSanitizer:
    """Test cases for input sanitization utilities."""
    
    def test_sanitize_for_display(self):
        """Test display sanitization."""
        from app.utils.validators import InputSanitizer
        
        # Normal text
        result = InputSanitizer.sanitize_for_display("Hello World")
        assert result == "Hello World"
        
        # Text with control characters
        result = InputSanitizer.sanitize_for_display("Hello\x00\x01World")
        assert result == "HelloWorld"
        
        # Long text
        long_text = "a" * 1000
        result = InputSanitizer.sanitize_for_display(long_text, max_length=100)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")
    
    def test_sanitize_for_logging(self):
        """Test logging sanitization."""
        from app.utils.validators import InputSanitizer
        
        # Text with API key
        text = 'API key: "abc123def456"'
        result = InputSanitizer.sanitize_for_logging(text)
        assert "[API_KEY_REDACTED]" in result
        assert "abc123def456" not in result
        
        # Text with email
        text = "User email: user@example.com"
        result = InputSanitizer.sanitize_for_logging(text)
        assert "[EMAIL_REDACTED]" in result
        assert "user@example.com" not in result
    
    def test_sanitize_api_response(self):
        """Test API response sanitization."""
        from app.utils.validators import InputSanitizer
        
        response = {
            "user_id": 123,
            "username": "testuser",
            "api_key": "secret123",
            "password": "mypassword",
            "data": {
                "token": "access_token_123"
            }
        }
        
        result = InputSanitizer.sanitize_api_response(response)
        
        assert result["user_id"] == 123
        assert result["username"] == "testuser"
        assert result["api_key"] == "[REDACTED]"
        assert result["password"] == "[REDACTED]"
        assert result["data"]["token"] == "[REDACTED]"
    
    def test_validate_and_sanitize_user_input(self):
        """Test comprehensive user input validation and sanitization."""
        from app.utils.validators import InputSanitizer, ValidationError
        
        # Valid input
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": "25",
            "website": "https://johndoe.com"
        }
        
        config = {
            "name": {"type": "string", "required": True, "max_length": 100},
            "email": {"type": "email", "required": True},
            "age": {"type": "number", "required": False, "min_value": 0, "max_value": 150},
            "website": {"type": "url", "required": False}
        }
        
        result = InputSanitizer.validate_and_sanitize_user_input(data, config)
        
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"
        assert result["age"] == 25.0
        assert result["website"] == "https://johndoe.com"
        
        # Missing required field
        invalid_data = {"name": "John Doe"}  # Missing required email
        
        with pytest.raises(ValidationError, match="Field 'email' is required"):
            InputSanitizer.validate_and_sanitize_user_input(invalid_data, config)