"""
Unit tests for validation and sanitization utilities.
"""

import pytest
from app.utils.validators import (
    DataValidator, 
    ValidationError, 
    ErrorHandler, 
    InputSanitizer
)


class TestDataValidatorEnhanced:
    """Test cases for enhanced DataValidator functionality."""
    
    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        # Normal input
        result = DataValidator.sanitize_input("Hello World")
        assert result == "Hello World"
        
        # Input with control characters
        result = DataValidator.sanitize_input("Hello\x00\x01World")
        assert result == "HelloWorld"
        
        # Input with HTML tags
        result = DataValidator.sanitize_input("<script>alert('xss')</script>Hello")
        assert result == "alert(xss)Hello"  # Tags removed, content preserved
        
        # Long input
        long_input = "a" * 2000
        result = DataValidator.sanitize_input(long_input, max_length=100)
        assert len(result) == 100
    
    def test_sanitize_input_with_html_allowed(self):
        """Test input sanitization with HTML allowed."""
        html_input = "<p>Hello <strong>World</strong></p>"
        result = DataValidator.sanitize_input(html_input, allow_html=True)
        assert "<p>" in result
        assert "<strong>" in result
        
        # Should still remove dangerous SQL injection patterns
        sql_input = "Hello'; DROP TABLE users; --"
        result = DataValidator.sanitize_input(sql_input, allow_html=True)
        assert "'" not in result  # Single quotes removed
        assert ";" not in result  # Semicolons removed
        assert "--" not in result  # SQL comments removed
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
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
        
        # Very long filename
        long_name = "a" * 300 + ".txt"
        result = DataValidator.sanitize_filename(long_name)
        assert len(result) <= 255
    
    def test_validate_url(self):
        """Test URL validation."""
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
            "",
            123  # Non-string
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                DataValidator.validate_url(url)
        
        # Custom allowed schemes
        result = DataValidator.validate_url("ftp://example.com", allowed_schemes=["ftp"])
        assert result == "ftp://example.com"
    
    def test_validate_email(self):
        """Test email validation."""
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
            "",
            123  # Non-string
        ]
        
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                DataValidator.validate_email(email)
        
        # Email too long
        long_email = "a" * 250 + "@example.com"
        with pytest.raises(ValidationError, match="Email address too long"):
            DataValidator.validate_email(long_email)
    
    def test_validate_json_string(self):
        """Test JSON string validation."""
        # Valid JSON
        valid_json = '{"key": "value", "number": 123}'
        result = DataValidator.validate_json_string(valid_json)
        assert result == {"key": "value", "number": 123}
        
        # Valid JSON array
        valid_json_array = '[1, 2, 3]'
        result = DataValidator.validate_json_string(valid_json_array)
        assert result == [1, 2, 3]
        
        # Invalid JSON
        with pytest.raises(ValidationError, match="Invalid JSON format"):
            DataValidator.validate_json_string('{"invalid": json}')
        
        # Empty string
        with pytest.raises(ValidationError, match="JSON string cannot be empty"):
            DataValidator.validate_json_string("")
        
        # Non-string input
        with pytest.raises(ValidationError, match="JSON input must be a string"):
            DataValidator.validate_json_string(123)
    
    def test_validate_numeric_string(self):
        """Test numeric string validation."""
        # Valid numbers
        assert DataValidator.validate_numeric_string("123.45") == 123.45
        assert DataValidator.validate_numeric_string("-10") == -10.0
        assert DataValidator.validate_numeric_string("0") == 0.0
        assert DataValidator.validate_numeric_string("1e5") == 100000.0
        
        # With range validation
        assert DataValidator.validate_numeric_string("50", min_value=0, max_value=100) == 50.0
        
        # Invalid numbers
        with pytest.raises(ValidationError, match="Invalid numeric format"):
            DataValidator.validate_numeric_string("not_a_number")
        
        # Empty string
        with pytest.raises(ValidationError, match="Numeric value cannot be empty"):
            DataValidator.validate_numeric_string("")
        
        # Non-string input
        with pytest.raises(ValidationError, match="Numeric value must be a string"):
            DataValidator.validate_numeric_string(123)
        
        # Out of range
        with pytest.raises(ValidationError, match="Value must be at most 100"):
            DataValidator.validate_numeric_string("150", min_value=0, max_value=100)
        
        with pytest.raises(ValidationError, match="Value must be at least 0"):
            DataValidator.validate_numeric_string("-10", min_value=0, max_value=100)
    
    def test_validate_ip_address(self):
        """Test IP address validation."""
        # Valid IPv4 addresses
        valid_ipv4 = [
            "192.168.1.1",
            "10.0.0.1",
            "255.255.255.255",
            "0.0.0.0",
            "127.0.0.1"
        ]
        
        for ip in valid_ipv4:
            result = DataValidator.validate_ip_address(ip)
            assert result == ip
        
        # Valid IPv6 addresses
        valid_ipv6 = [
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "::1",
            "::"
        ]
        
        for ip in valid_ipv6:
            result = DataValidator.validate_ip_address(ip)
            assert result == ip
        
        # Invalid IP addresses
        invalid_ips = [
            "256.256.256.256",
            "192.168.1",
            "192.168.1.1.1",
            "not_an_ip",
            "",
            123  # Non-string
        ]
        
        for ip in invalid_ips:
            with pytest.raises(ValidationError):
                DataValidator.validate_ip_address(ip)


class TestErrorHandler:
    """Test cases for error handling utilities."""
    
    def test_format_validation_error(self):
        """Test validation error formatting."""
        error = ValidationError("Field is required")
        
        # Without field name
        result = ErrorHandler.format_validation_error(error)
        assert result == "Validation error: Field is required"
        
        # With field name
        result = ErrorHandler.format_validation_error(error, "username")
        assert result == "Validation error in 'username': Field is required"
    
    def test_format_api_error(self):
        """Test API error formatting."""
        error = ConnectionError("Connection failed")
        
        # Without operation
        result = ErrorHandler.format_api_error(error)
        assert "ConnectionError" in result
        assert "Connection failed" in result
        
        # With operation
        result = ErrorHandler.format_api_error(error, "fetching user data")
        assert "API error during fetching user data" in result
    
    def test_format_file_error(self):
        """Test file error formatting."""
        error = FileNotFoundError("File not found")
        
        # Basic error
        result = ErrorHandler.format_file_error(error)
        assert "File error" in result
        assert "FileNotFoundError" in result
        
        # With file path
        result = ErrorHandler.format_file_error(error, "/path/to/file.txt")
        assert "with file '/path/to/file.txt'" in result
        
        # With operation
        result = ErrorHandler.format_file_error(error, operation="reading")
        assert "during reading" in result
        
        # With both
        result = ErrorHandler.format_file_error(error, "/path/to/file.txt", "writing")
        assert "during writing" in result
        assert "with file '/path/to/file.txt'" in result
    
    def test_get_user_friendly_message(self):
        """Test user-friendly error message generation."""
        # Connection error
        error = ConnectionError("Failed to connect")
        result = ErrorHandler.get_user_friendly_message(error)
        assert "connect to the service" in result
        
        # Permission error
        error = PermissionError("Access denied")
        result = ErrorHandler.get_user_friendly_message(error)
        assert "Permission denied" in result
        
        # Timeout error
        error = TimeoutError("Operation timed out")
        result = ErrorHandler.get_user_friendly_message(error)
        assert "took too long" in result
        
        # Unknown error
        error = ValueError("Some unknown error")
        result = ErrorHandler.get_user_friendly_message(error)
        assert "unexpected error occurred" in result
    
    def test_log_error(self):
        """Test error logging functionality."""
        import logging
        from unittest.mock import Mock
        
        # Mock logger
        mock_logger = Mock()
        
        error = ValueError("Test error")
        context = {"user_id": 123, "action": "test_action"}
        
        ErrorHandler.log_error(error, context, mock_logger)
        
        # Verify logger was called
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "ValueError" in call_args
        assert "Test error" in call_args


class TestInputSanitizer:
    """Test cases for input sanitization utilities."""
    
    def test_sanitize_for_display(self):
        """Test display sanitization."""
        # Normal text
        result = InputSanitizer.sanitize_for_display("Hello World")
        assert result == "Hello World"
        
        # Text with control characters
        result = InputSanitizer.sanitize_for_display("Hello\x00\x01World")
        assert result == "HelloWorld"
        
        # Text with tabs and newlines (should be preserved)
        result = InputSanitizer.sanitize_for_display("Hello\tWorld\nNext line")
        assert "\t" in result
        assert "\n" in result
        
        # Long text
        long_text = "a" * 1000
        result = InputSanitizer.sanitize_for_display(long_text, max_length=100)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")
        
        # Non-string input
        result = InputSanitizer.sanitize_for_display(123)
        assert result == "123"
    
    def test_sanitize_for_logging(self):
        """Test logging sanitization."""
        # Text with API key
        text = 'API key: "abc123def456ghi789"'
        result = InputSanitizer.sanitize_for_logging(text)
        assert "[API_KEY_REDACTED]" in result
        assert "abc123def456ghi789" not in result
        
        # Text with password
        text = 'password: "mypassword123"'
        result = InputSanitizer.sanitize_for_logging(text)
        assert "[PASSWORD_REDACTED]" in result
        assert "mypassword123" not in result
        
        # Text with token
        text = 'token: "bearer_token_12345"'
        result = InputSanitizer.sanitize_for_logging(text)
        assert "[TOKEN_REDACTED]" in result
        assert "bearer_token_12345" not in result
        
        # Text with email
        text = "User email: user@example.com"
        result = InputSanitizer.sanitize_for_logging(text)
        assert "[EMAIL_REDACTED]" in result
        assert "user@example.com" not in result
        
        # Long text
        long_text = "Normal text " * 100
        result = InputSanitizer.sanitize_for_logging(long_text, max_length=50)
        assert len(result) == 53  # 50 + "..."
        assert result.endswith("...")
        
        # Non-string input
        result = InputSanitizer.sanitize_for_logging(123)
        assert result == "123"
    
    def test_sanitize_api_response(self):
        """Test API response sanitization."""
        response = {
            "user_id": 123,
            "username": "testuser",
            "api_key": "secret123",
            "password": "mypassword",
            "data": {
                "token": "access_token_123",
                "public_info": "this is safe"
            },
            "nested": {
                "deep": {
                    "client_secret": "very_secret"
                }
            }
        }
        
        result = InputSanitizer.sanitize_api_response(response)
        
        # Safe data should remain
        assert result["user_id"] == 123
        assert result["username"] == "testuser"
        assert result["data"]["public_info"] == "this is safe"
        
        # Sensitive data should be redacted
        assert result["api_key"] == "[REDACTED]"
        assert result["password"] == "[REDACTED]"
        assert result["data"]["token"] == "[REDACTED]"
        assert result["nested"]["deep"]["client_secret"] == "[REDACTED]"
        
        # Non-dict input should be returned as-is
        result = InputSanitizer.sanitize_api_response("not a dict")
        assert result == "not a dict"
        
        # Custom sensitive keys
        response = {"custom_secret": "secret_value", "safe_data": "safe"}
        result = InputSanitizer.sanitize_api_response(response, ["custom_secret"])
        assert result["custom_secret"] == "[REDACTED]"
        assert result["safe_data"] == "safe"
    
    def test_validate_and_sanitize_user_input(self):
        """Test comprehensive user input validation and sanitization."""
        # Valid input
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": "25",
            "website": "https://johndoe.com",
            "bio": "Software developer"
        }
        
        config = {
            "name": {"type": "string", "required": True, "max_length": 100},
            "email": {"type": "email", "required": True},
            "age": {"type": "number", "required": False, "min_value": 0, "max_value": 150},
            "website": {"type": "url", "required": False},
            "bio": {"type": "string", "required": False, "max_length": 500}
        }
        
        result = InputSanitizer.validate_and_sanitize_user_input(data, config)
        
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"
        assert result["age"] == 25.0
        assert result["website"] == "https://johndoe.com"
        assert result["bio"] == "Software developer"
        
        # Missing required field
        invalid_data = {"name": "John Doe"}  # Missing required email
        
        with pytest.raises(ValidationError, match="Field 'email' is required"):
            InputSanitizer.validate_and_sanitize_user_input(invalid_data, config)
        
        # Invalid field type
        invalid_data = {
            "name": "John Doe",
            "email": "invalid_email",
            "age": "25"
        }
        
        with pytest.raises(ValidationError, match="Field 'email'"):
            InputSanitizer.validate_and_sanitize_user_input(invalid_data, config)
        
        # Optional empty fields
        data_with_empty = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": "",  # Empty optional field
            "website": None  # None optional field
        }
        
        result = InputSanitizer.validate_and_sanitize_user_input(data_with_empty, config)
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"
        assert result["age"] == ""
        assert result["website"] is None
        
        # Input with HTML that gets sanitized
        data_with_html = {
            "name": "John <script>alert('xss')</script> Doe",
            "email": "john@example.com"
        }
        
        result = InputSanitizer.validate_and_sanitize_user_input(data_with_html, config)
        assert "<script>" not in result["name"]
        assert "alert(xss)" in result["name"]  # Script tag removed, content preserved
        assert result["name"].startswith("John")
        assert result["name"].endswith("Doe")