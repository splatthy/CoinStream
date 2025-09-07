"""
Validation utilities for data integrity checks across the application.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, List, Dict, Optional, Union
from app.models.trade import Trade, TradeSide, TradeStatus, WinLoss
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.models.custom_fields import CustomFieldConfig, FieldType


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class DataValidator:
    """Utility class for data validation operations."""
    
    @staticmethod
    def validate_string(value: Any, field_name: str, min_length: int = 1, max_length: Optional[int] = None) -> str:
        """Validate string field with length constraints."""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string, got {type(value)}")
        
        if len(value) < min_length:
            raise ValidationError(f"{field_name} must be at least {min_length} characters long")
        
        if max_length and len(value) > max_length:
            raise ValidationError(f"{field_name} must be at most {max_length} characters long")
        
        return value.strip()

    @staticmethod
    def validate_decimal(value: Any, field_name: str, min_value: Optional[Decimal] = None, 
                        max_value: Optional[Decimal] = None) -> Decimal:
        """Validate decimal field with range constraints."""
        if isinstance(value, (int, float, str)):
            try:
                value = Decimal(str(value))
            except InvalidOperation:
                raise ValidationError(f"{field_name} cannot be converted to Decimal")
        
        if not isinstance(value, Decimal):
            raise ValidationError(f"{field_name} must be a Decimal, got {type(value)}")
        
        if min_value is not None and value < min_value:
            raise ValidationError(f"{field_name} must be at least {min_value}")
        
        if max_value is not None and value > max_value:
            raise ValidationError(f"{field_name} must be at most {max_value}")
        
        return value

    @staticmethod
    def validate_datetime(value: Any, field_name: str) -> datetime:
        """Validate datetime field."""
        if value is None:
            raise ValidationError(f"{field_name} cannot be None")
            
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationError(f"{field_name} string is not in valid ISO format")
        
        if not isinstance(value, datetime):
            raise ValidationError(f"{field_name} must be a datetime object, got {type(value)}")
        
        return value

    @staticmethod
    def validate_enum(value: Any, enum_class: type, field_name: str):
        """Validate enum field."""
        if isinstance(value, str):
            try:
                return enum_class(value)
            except ValueError:
                valid_values = [e.value for e in enum_class]
                raise ValidationError(f"{field_name} must be one of {valid_values}, got '{value}'")
        
        if not isinstance(value, enum_class):
            valid_values = [e.value for e in enum_class]
            raise ValidationError(f"{field_name} must be one of {valid_values}, got {type(value)}")
        
        return value

    @staticmethod
    def validate_list(value: Any, field_name: str, item_type: Optional[type] = None) -> List:
        """Validate list field with optional item type checking."""
        if not isinstance(value, list):
            raise ValidationError(f"{field_name} must be a list, got {type(value)}")
        
        if item_type:
            for i, item in enumerate(value):
                if not isinstance(item, item_type):
                    raise ValidationError(f"{field_name}[{i}] must be {item_type.__name__}, got {type(item)}")
        
        return value

    @staticmethod
    def validate_dict(value: Any, field_name: str) -> Dict:
        """Validate dictionary field."""
        if not isinstance(value, dict):
            raise ValidationError(f"{field_name} must be a dictionary, got {type(value)}")
        
        return value

    @staticmethod
    def validate_symbol_format(symbol: str) -> str:
        """Validate trading symbol format (e.g., BTCUSDT, ETH-USD)."""
        if not isinstance(symbol, str):
            raise ValidationError("Symbol must be a string")
        
        symbol = symbol.upper().strip()
        
        # Allow alphanumeric characters, hyphens, and underscores
        if not re.match(r'^[A-Z0-9_-]+$', symbol):
            raise ValidationError("Symbol must contain only uppercase letters, numbers, hyphens, and underscores")
        
        if len(symbol) < 3:
            raise ValidationError("Symbol must be at least 3 characters long")
        
        if len(symbol) > 20:
            raise ValidationError("Symbol must be at most 20 characters long")
        
        return symbol

    @staticmethod
    def validate_exchange_name(name: str) -> str:
        """Validate exchange name format."""
        if not isinstance(name, str):
            raise ValidationError("Exchange name must be a string")
        
        name = name.lower().strip()
        
        # Allow alphanumeric characters and hyphens
        if not re.match(r'^[a-z0-9-]+$', name):
            raise ValidationError("Exchange name must contain only lowercase letters, numbers, and hyphens")
        
        if len(name) < 2:
            raise ValidationError("Exchange name must be at least 2 characters long")
        
        if len(name) > 50:
            raise ValidationError("Exchange name must be at most 50 characters long")
        
        return name

    @staticmethod
    def validate_api_key_format(api_key: str) -> str:
        """Validate API key format (basic format checking)."""
        if not isinstance(api_key, str):
            raise ValidationError("API key must be a string")
        
        api_key = api_key.strip()
        
        if len(api_key) < 10:
            raise ValidationError("API key must be at least 10 characters long")
        
        if len(api_key) > 500:
            raise ValidationError("API key must be at most 500 characters long")
        
        # Check for basic format (alphanumeric and common special characters)
        if not re.match(r'^[A-Za-z0-9+/=_-]+$', api_key):
            raise ValidationError("API key contains invalid characters")
        
        return api_key

    @staticmethod
    def validate_trade_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trade data dictionary before creating Trade object."""
        validated = {}
        
        # Required fields
        validated['id'] = DataValidator.validate_string(data.get('id'), 'id')
        validated['exchange'] = DataValidator.validate_exchange_name(data.get('exchange'))
        validated['symbol'] = DataValidator.validate_symbol_format(data.get('symbol'))
        validated['side'] = DataValidator.validate_enum(data.get('side'), TradeSide, 'side')
        validated['entry_price'] = DataValidator.validate_decimal(data.get('entry_price'), 'entry_price', Decimal('0'))
        validated['quantity'] = DataValidator.validate_decimal(data.get('quantity'), 'quantity', Decimal('0'))
        validated['entry_time'] = DataValidator.validate_datetime(data.get('entry_time'), 'entry_time')
        validated['status'] = DataValidator.validate_enum(data.get('status'), TradeStatus, 'status')
        
        # Optional fields
        if 'exit_price' in data and data['exit_price'] is not None:
            validated['exit_price'] = DataValidator.validate_decimal(data['exit_price'], 'exit_price', Decimal('0'))
        
        if 'exit_time' in data and data['exit_time'] is not None:
            validated['exit_time'] = DataValidator.validate_datetime(data['exit_time'], 'exit_time')
        
        if 'pnl' in data and data['pnl'] is not None:
            validated['pnl'] = DataValidator.validate_decimal(data['pnl'], 'pnl')
        
        if 'win_loss' in data and data['win_loss'] is not None:
            validated['win_loss'] = DataValidator.validate_enum(data['win_loss'], WinLoss, 'win_loss')
        
        validated['confluences'] = DataValidator.validate_list(
            data.get('confluences', []), 'confluences', str
        )
        
        validated['custom_fields'] = DataValidator.validate_dict(
            data.get('custom_fields', {}), 'custom_fields'
        )
        
        if 'created_at' in data and data['created_at'] is not None:
            validated['created_at'] = DataValidator.validate_datetime(data['created_at'], 'created_at')
        
        if 'updated_at' in data and data['updated_at'] is not None:
            validated['updated_at'] = DataValidator.validate_datetime(data['updated_at'], 'updated_at')
        
        return validated

    @staticmethod
    # Removed: validate_position_data is not used in CSV-only POC

    @staticmethod
    def validate_custom_field_value(value: Any, field_config: CustomFieldConfig) -> Any:
        """Validate a value against a custom field configuration."""
        if not field_config.validate_value(value):
            field_type = field_config.field_type.value
            if field_config.field_type in [FieldType.SELECT, FieldType.MULTISELECT]:
                raise ValidationError(
                    f"Value for {field_config.field_name} must be valid {field_type} "
                    f"from options: {field_config.options}"
                )
            else:
                raise ValidationError(
                    f"Value for {field_config.field_name} must be of type {field_type}"
                )
        
        return value

    @staticmethod
    def sanitize_input(value: str, max_length: int = 1000, allow_html: bool = False) -> str:
        """
        Sanitize user input to prevent injection attacks.
        
        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML tags (default: False)
            
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return str(value)
        
        # Remove null bytes and control characters (except tab, newline, carriage return)
        sanitized = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')
        
        import re
        
        # Remove HTML tags if not allowed
        if not allow_html:
            # Remove HTML/XML tags
            sanitized = re.sub(r'<[^>]*>', '', sanitized)
        
        # Always remove potentially dangerous characters for SQL injection
        dangerous_chars = ['\'', '"', ';', '--', '/*', '*/', 'xp_', 'sp_']
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent directory traversal and invalid characters.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        if not isinstance(filename, str):
            filename = str(filename)
        
        # Remove directory traversal attempts
        filename = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Remove or replace invalid filename characters
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove control characters
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # Limit length and ensure it's not empty
        filename = filename.strip()[:255]
        if not filename:
            filename = 'unnamed_file'
        
        return filename
    
    @staticmethod
    def validate_url(url: str, allowed_schemes: List[str] = None) -> str:
        """
        Validate and sanitize URL.
        
        Args:
            url: URL to validate
            allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])
            
        Returns:
            Validated URL
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not isinstance(url, str):
            raise ValidationError("URL must be a string")
        
        url = url.strip()
        if not url:
            raise ValidationError("URL cannot be empty")
        
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        # Check scheme first
        if '://' not in url:
            raise ValidationError("Invalid URL format - missing scheme")
        
        scheme = url.split('://')[0].lower()
        if scheme not in allowed_schemes:
            raise ValidationError(f"URL scheme must be one of {allowed_schemes}")
        
        # Basic URL format validation (more flexible)
        import re
        url_pattern = re.compile(
            r'^[a-zA-Z][a-zA-Z0-9+.-]*://'  # scheme://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)?$', re.IGNORECASE)  # optional path
        
        if not url_pattern.match(url):
            raise ValidationError("Invalid URL format")
        
        return url
    
    @staticmethod
    def validate_email(email: str) -> str:
        """
        Validate email address format.
        
        Args:
            email: Email address to validate
            
        Returns:
            Validated email address
            
        Raises:
            ValidationError: If email is invalid
        """
        if not isinstance(email, str):
            raise ValidationError("Email must be a string")
        
        email = email.strip().lower()
        if not email:
            raise ValidationError("Email cannot be empty")
        
        # Basic email validation
        import re
        email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        
        if not email_pattern.match(email):
            raise ValidationError("Invalid email format")
        
        if len(email) > 254:  # RFC 5321 limit
            raise ValidationError("Email address too long")
        
        return email
    
    @staticmethod
    def validate_json_string(json_str: str) -> dict:
        """
        Validate and parse JSON string.
        
        Args:
            json_str: JSON string to validate
            
        Returns:
            Parsed JSON object
            
        Raises:
            ValidationError: If JSON is invalid
        """
        if not isinstance(json_str, str):
            raise ValidationError("JSON input must be a string")
        
        json_str = json_str.strip()
        if not json_str:
            raise ValidationError("JSON string cannot be empty")
        
        try:
            import json
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format: {str(e)}")
    
    @staticmethod
    def validate_numeric_string(value: str, min_value: Optional[float] = None, 
                               max_value: Optional[float] = None) -> float:
        """
        Validate numeric string and convert to float.
        
        Args:
            value: String representation of number
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            
        Returns:
            Validated numeric value
            
        Raises:
            ValidationError: If value is not a valid number or out of range
        """
        if not isinstance(value, str):
            raise ValidationError("Numeric value must be a string")
        
        value = value.strip()
        if not value:
            raise ValidationError("Numeric value cannot be empty")
        
        try:
            numeric_value = float(value)
        except ValueError:
            raise ValidationError("Invalid numeric format")
        
        if min_value is not None and numeric_value < min_value:
            raise ValidationError(f"Value must be at least {min_value}")
        
        if max_value is not None and numeric_value > max_value:
            raise ValidationError(f"Value must be at most {max_value}")
        
        return numeric_value
    
    @staticmethod
    def validate_ip_address(ip: str) -> str:
        """
        Validate IP address format.
        
        Args:
            ip: IP address to validate
            
        Returns:
            Validated IP address
            
        Raises:
            ValidationError: If IP address is invalid
        """
        if not isinstance(ip, str):
            raise ValidationError("IP address must be a string")
        
        ip = ip.strip()
        if not ip:
            raise ValidationError("IP address cannot be empty")
        
        import re
        
        # IPv4 pattern
        ipv4_pattern = re.compile(
            r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        )
        
        # IPv6 pattern (simplified)
        ipv6_pattern = re.compile(
            r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|'
            r'^::1$|^::$'
        )
        
        if not (ipv4_pattern.match(ip) or ipv6_pattern.match(ip)):
            raise ValidationError("Invalid IP address format")
        
        return ip

    @staticmethod
    def validate_date_range(start_date: datetime, end_date: datetime) -> tuple:
        """Validate date range ensuring start is before end."""
        if not isinstance(start_date, datetime):
            raise ValidationError("Start date must be a datetime object")
        
        if not isinstance(end_date, datetime):
            raise ValidationError("End date must be a datetime object")
        
        if start_date >= end_date:
            raise ValidationError("Start date must be before end date")
        
        return start_date, end_date


class ErrorHandler:
    """Utility class for handling and formatting errors with user-friendly messages."""
    
    @staticmethod
    def format_validation_error(error: ValidationError, field_name: str = None) -> str:
        """
        Format validation error with user-friendly message.
        
        Args:
            error: ValidationError instance
            field_name: Name of the field that failed validation
            
        Returns:
            Formatted error message
        """
        base_message = str(error)
        
        if field_name:
            return f"Validation error in '{field_name}': {base_message}"
        
        return f"Validation error: {base_message}"
    
    @staticmethod
    def format_api_error(error: Exception, operation: str = None) -> str:
        """
        Format API error with user-friendly message.
        
        Args:
            error: Exception instance
            operation: Description of the operation that failed
            
        Returns:
            Formatted error message
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        if operation:
            return f"API error during {operation}: {error_type} - {error_message}"
        
        return f"API error: {error_type} - {error_message}"
    
    @staticmethod
    def format_file_error(error: Exception, file_path: str = None, operation: str = None) -> str:
        """
        Format file operation error with user-friendly message.
        
        Args:
            error: Exception instance
            file_path: Path to the file that caused the error
            operation: Description of the file operation
            
        Returns:
            Formatted error message
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        parts = ["File error"]
        
        if operation:
            parts.append(f"during {operation}")
        
        if file_path:
            parts.append(f"with file '{file_path}'")
        
        parts.append(f": {error_type} - {error_message}")
        
        return " ".join(parts)
    
    @staticmethod
    def get_user_friendly_message(error: Exception) -> str:
        """
        Convert technical error to user-friendly message.
        
        Args:
            error: Exception instance
            
        Returns:
            User-friendly error message
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Common error patterns and their user-friendly messages
        friendly_messages = {
            'connectionerror': "Unable to connect to the service. Please check your internet connection.",
            'timeout': "The operation took too long to complete. Please try again.",
            'permission': "Permission denied. Please check file permissions or contact support.",
            'not found': "The requested resource was not found.",
            'invalid': "The provided data is invalid. Please check your input.",
            'authentication': "Authentication failed. Please check your credentials.",
            'authorization': "You don't have permission to perform this action.",
            'rate limit': "Too many requests. Please wait a moment before trying again.",
            'server error': "Server error occurred. Please try again later.",
            'network': "Network error occurred. Please check your connection.",
        }
        
        # Check for known error patterns
        for pattern, friendly_msg in friendly_messages.items():
            if pattern in error_message or pattern in error_type.lower():
                return friendly_msg
        
        # Default message for unknown errors
        return f"An unexpected error occurred: {error_message}"
    
    @staticmethod
    def log_error(error: Exception, context: dict = None, logger=None) -> None:
        """
        Log error with context information.
        
        Args:
            error: Exception instance
            context: Additional context information
            logger: Logger instance (optional)
        """
        import logging
        
        if logger is None:
            logger = logging.getLogger(__name__)
        
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {}
        }
        
        logger.error(f"Error occurred: {error_info}")


class InputSanitizer:
    """Advanced input sanitization utilities."""
    
    @staticmethod
    def sanitize_for_display(text: str, max_length: int = 500) -> str:
        """
        Sanitize text for safe display in UI.
        
        Args:
            text: Text to sanitize
            max_length: Maximum display length
            
        Returns:
            Sanitized text safe for display
        """
        if not isinstance(text, str):
            text = str(text)
        
        # Remove control characters except newlines and tabs
        sanitized = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."
        
        return sanitized
    
    @staticmethod
    def sanitize_for_logging(text: str, max_length: int = 200) -> str:
        """
        Sanitize text for safe logging (removes sensitive patterns).
        
        Args:
            text: Text to sanitize
            max_length: Maximum log length
            
        Returns:
            Sanitized text safe for logging
        """
        if not isinstance(text, str):
            text = str(text)
        
        import re
        
        # Patterns that might contain sensitive information
        sensitive_patterns = [
            (r'api[_\s-]*key["\s]*[:=]["\s]*["\']?[a-zA-Z0-9+/=]{10,}["\']?', '[API_KEY_REDACTED]'),
            (r'password["\s]*[:=]["\s]*["\']?\S+["\']?', '[PASSWORD_REDACTED]'),
            (r'token["\s]*[:=]["\s]*["\']?[a-zA-Z0-9+/=_-]{10,}["\']?', '[TOKEN_REDACTED]'),
            (r'secret["\s]*[:=]["\s]*["\']?\S+["\']?', '[SECRET_REDACTED]'),
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
        ]
        
        sanitized = text
        for pattern, replacement in sensitive_patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        # Remove control characters
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in '\n\t')
        
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."
        
        return sanitized
    
    @staticmethod
    def sanitize_api_response(response_data: dict, sensitive_keys: List[str] = None) -> dict:
        """
        Sanitize API response data by removing or masking sensitive information.
        
        Args:
            response_data: API response dictionary
            sensitive_keys: List of keys to mask (default: common sensitive keys)
            
        Returns:
            Sanitized response data
        """
        if not isinstance(response_data, dict):
            return response_data
        
        if sensitive_keys is None:
            sensitive_keys = [
                'api_key', 'apikey', 'api-key',
                'password', 'passwd', 'pwd',
                'token', 'access_token', 'refresh_token',
                'secret', 'client_secret',
                'private_key', 'privatekey'
            ]
        
        sanitized = response_data.copy()
        
        def mask_sensitive_data(obj, keys_to_mask):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key.lower() in [k.lower() for k in keys_to_mask]:
                        obj[key] = '[REDACTED]'
                    elif isinstance(value, (dict, list)):
                        mask_sensitive_data(value, keys_to_mask)
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, (dict, list)):
                        mask_sensitive_data(item, keys_to_mask)
        
        mask_sensitive_data(sanitized, sensitive_keys)
        return sanitized
    
    @staticmethod
    def validate_and_sanitize_user_input(data: dict, field_configs: dict) -> dict:
        """
        Validate and sanitize user input based on field configurations.
        
        Args:
            data: Input data dictionary
            field_configs: Configuration for each field
                Format: {
                    'field_name': {
                        'type': 'string|number|email|url',
                        'required': True|False,
                        'max_length': int,
                        'min_value': float,
                        'max_value': float,
                        'sanitize': True|False
                    }
                }
        
        Returns:
            Validated and sanitized data
            
        Raises:
            ValidationError: If validation fails
        """
        validated_data = {}
        
        for field_name, config in field_configs.items():
            value = data.get(field_name)
            
            # Check required fields
            if config.get('required', False) and (value is None or value == ''):
                raise ValidationError(f"Field '{field_name}' is required")
            
            # Skip validation for optional empty fields
            if value is None or value == '':
                validated_data[field_name] = value
                continue
            
            field_type = config.get('type', 'string')
            
            try:
                if field_type == 'string':
                    if config.get('sanitize', True):
                        value = DataValidator.sanitize_input(
                            str(value), 
                            max_length=config.get('max_length', 1000),
                            allow_html=config.get('allow_html', False)
                        )
                    validated_data[field_name] = DataValidator.validate_string(
                        value, field_name, 
                        max_length=config.get('max_length')
                    )
                
                elif field_type == 'number':
                    validated_data[field_name] = DataValidator.validate_numeric_string(
                        str(value),
                        min_value=config.get('min_value'),
                        max_value=config.get('max_value')
                    )
                
                elif field_type == 'email':
                    validated_data[field_name] = DataValidator.validate_email(str(value))
                
                elif field_type == 'url':
                    validated_data[field_name] = DataValidator.validate_url(str(value))
                
                else:
                    # Default to string validation
                    validated_data[field_name] = str(value)
            
            except ValidationError as e:
                raise ValidationError(f"Field '{field_name}': {str(e)}")
        
        return validated_data
