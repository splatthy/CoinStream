"""
Integration tests for configuration validation functionality.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.config_service import ConfigService
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.models.custom_fields import CustomFieldConfig, FieldType


class TestConfigValidation:
    """Integration tests for configuration validation."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def config_service(self, temp_data_dir):
        """Create ConfigService instance with temporary data directory."""
        return ConfigService(data_path=temp_data_dir)

    def test_validate_api_key_valid_bitunix(self, config_service):
        """Test API key validation for valid Bitunix keys."""
        valid_keys = [
            "abcd1234efgh5678ijkl9012mnop3456",
            "ABCD1234EFGH5678IJKL9012MNOP3456",
            "abc123-def456_ghi789",
            "1234567890abcdef1234567890abcdef"
        ]
        
        for key in valid_keys:
            assert config_service.validate_api_key("bitunix", key) is True

    def test_validate_api_key_invalid_bitunix(self, config_service):
        """Test API key validation for invalid Bitunix keys."""
        invalid_keys = [
            "",  # Empty
            "   ",  # Whitespace only
            "short",  # Too short
            "a" * 200,  # Too long
            "invalid@key#with$special%chars",  # Invalid characters
            "key with spaces",  # Contains spaces
            None,  # None value
            123,  # Non-string
        ]
        
        for key in invalid_keys:
            assert config_service.validate_api_key("bitunix", key) is False

    def test_validate_api_key_unknown_exchange(self, config_service):
        """Test API key validation for unknown exchange."""
        # Should still do basic validation
        assert config_service.validate_api_key("unknown_exchange", "validkey123") is True
        assert config_service.validate_api_key("unknown_exchange", "") is False

    def test_encrypt_and_decrypt_api_key(self, config_service):
        """Test API key encryption and decryption."""
        original_key = "test_api_key_12345"
        exchange_name = "bitunix"
        
        # Encrypt the key
        encrypted_key = config_service.encrypt_and_store_api_key(exchange_name, original_key)
        assert encrypted_key != original_key
        assert len(encrypted_key) > 0
        
        # Decrypt the key
        decrypted_key = config_service.decrypt_api_key(exchange_name, encrypted_key)
        assert decrypted_key == original_key

    def test_encrypt_api_key_invalid_input(self, config_service):
        """Test API key encryption with invalid input."""
        with pytest.raises(ValueError, match="Failed to encrypt API key"):
            config_service.encrypt_and_store_api_key("bitunix", "")

    def test_decrypt_api_key_invalid_input(self, config_service):
        """Test API key decryption with invalid input."""
        with pytest.raises(ValueError, match="Failed to decrypt API key"):
            config_service.decrypt_api_key("bitunix", "invalid_encrypted_data")

    def test_test_exchange_connection_with_api_key(self, config_service):
        """Test exchange connection testing with provided API key."""
        # Valid API key should return True (basic validation for now)
        result = config_service.test_exchange_connection("bitunix", "valid_api_key_123")
        assert result is True
        
        # Invalid API key should return False
        result = config_service.test_exchange_connection("bitunix", "invalid@key")
        assert result is False

    def test_test_exchange_connection_with_stored_key(self, config_service):
        """Test exchange connection testing with stored API key."""
        # Create exchange config with valid key
        api_key = "valid_api_key_123"
        config = config_service.create_exchange_config_with_validation(
            "bitunix", api_key, test_connection=False
        )
        
        # Test connection using stored key
        result = config_service.test_exchange_connection("bitunix")
        assert result is True

    def test_test_exchange_connection_no_config(self, config_service):
        """Test exchange connection testing with no stored config."""
        result = config_service.test_exchange_connection("nonexistent")
        assert result is False

    def test_test_exchange_connection_unknown_exchange(self, config_service):
        """Test exchange connection testing for unknown exchange."""
        result = config_service.test_exchange_connection("unknown", "some_key")
        assert result is False

    def test_update_exchange_connection_status(self, config_service):
        """Test updating exchange connection status."""
        # Create exchange config
        config = ExchangeConfig(name="test_exchange", api_key_encrypted="encrypted_key")
        config_service.save_exchange_config(config)
        
        # Update status
        config_service.update_exchange_connection_status("test_exchange", ConnectionStatus.CONNECTED)
        
        # Verify status was updated
        updated_config = config_service.get_exchange_config("test_exchange")
        assert updated_config.connection_status == ConnectionStatus.CONNECTED

    def test_update_exchange_connection_status_nonexistent(self, config_service):
        """Test updating connection status for nonexistent exchange."""
        # Should not raise an error
        config_service.update_exchange_connection_status("nonexistent", ConnectionStatus.CONNECTED)

    def test_monitor_exchange_connections(self, config_service):
        """Test monitoring all exchange connections."""
        # Create multiple exchange configs
        config1 = config_service.create_exchange_config_with_validation(
            "bitunix", "valid_key_123", test_connection=False
        )
        config2 = ExchangeConfig(name="inactive", api_key_encrypted="key", is_active=False)
        config_service.save_exchange_config(config2)
        
        # Monitor connections
        status_map = config_service.monitor_exchange_connections()
        
        # Should only monitor active exchanges
        assert "bitunix" in status_map
        assert "inactive" not in status_map
        
        # Status should be updated
        assert status_map["bitunix"] in [ConnectionStatus.CONNECTED, ConnectionStatus.ERROR]

    def test_create_exchange_config_with_validation_success(self, config_service):
        """Test creating exchange config with successful validation."""
        api_key = "valid_api_key_123"
        
        config = config_service.create_exchange_config_with_validation(
            "bitunix", api_key, test_connection=True
        )
        
        assert config.name == "bitunix"
        assert config.is_active is True
        assert config.connection_status == ConnectionStatus.CONNECTED
        
        # Verify it was saved
        saved_config = config_service.get_exchange_config("bitunix")
        assert saved_config is not None
        assert saved_config.name == "bitunix"

    def test_create_exchange_config_with_validation_invalid_key(self, config_service):
        """Test creating exchange config with invalid API key."""
        with pytest.raises(ValueError, match="Invalid API key format"):
            config_service.create_exchange_config_with_validation(
                "bitunix", "invalid@key", test_connection=False
            )

    def test_create_exchange_config_without_connection_test(self, config_service):
        """Test creating exchange config without connection testing."""
        api_key = "valid_api_key_123"
        
        config = config_service.create_exchange_config_with_validation(
            "bitunix", api_key, test_connection=False
        )
        
        assert config.connection_status == ConnectionStatus.UNKNOWN

    def test_update_exchange_api_key_success(self, config_service):
        """Test updating exchange API key successfully."""
        # Create initial config
        old_key = "old_api_key_123"
        config_service.create_exchange_config_with_validation(
            "bitunix", old_key, test_connection=False
        )
        
        # Update API key
        new_key = "new_api_key_456"
        result = config_service.update_exchange_api_key("bitunix", new_key, test_connection=True)
        
        assert result is True
        
        # Verify key was updated
        updated_config = config_service.get_exchange_config("bitunix")
        decrypted_key = config_service.decrypt_api_key("bitunix", updated_config.api_key_encrypted)
        assert decrypted_key == new_key

    def test_update_exchange_api_key_invalid_key(self, config_service):
        """Test updating exchange API key with invalid key."""
        # Create initial config
        config_service.create_exchange_config_with_validation(
            "bitunix", "valid_key_123", test_connection=False
        )
        
        # Try to update with invalid key
        result = config_service.update_exchange_api_key("bitunix", "invalid@key")
        
        assert result is False

    def test_update_exchange_api_key_nonexistent_exchange(self, config_service):
        """Test updating API key for nonexistent exchange."""
        result = config_service.update_exchange_api_key("nonexistent", "valid_key_123")
        assert result is False

    def test_update_exchange_api_key_without_connection_test(self, config_service):
        """Test updating exchange API key without connection testing."""
        # Create initial config
        config_service.create_exchange_config_with_validation(
            "bitunix", "old_key_123", test_connection=False
        )
        
        # Update API key without testing
        result = config_service.update_exchange_api_key(
            "bitunix", "new_key_456", test_connection=False
        )
        
        assert result is True
        
        # Status should be unknown
        updated_config = config_service.get_exchange_config("bitunix")
        assert updated_config.connection_status == ConnectionStatus.UNKNOWN

    def test_get_exchange_connection_summary(self, config_service):
        """Test getting exchange connection summary."""
        # Create multiple configs
        config1 = config_service.create_exchange_config_with_validation(
            "bitunix", "valid_key_123", test_connection=False
        )
        config2 = ExchangeConfig(name="inactive", api_key_encrypted="encrypted_key_data", is_active=False)
        config_service.save_exchange_config(config2)
        
        summary = config_service.get_exchange_connection_summary()
        
        assert len(summary) == 2
        assert "bitunix" in summary
        assert "inactive" in summary
        
        # Check summary structure
        bitunix_summary = summary["bitunix"]
        assert "is_active" in bitunix_summary
        assert "connection_status" in bitunix_summary
        assert "last_sync" in bitunix_summary
        assert "needs_sync" in bitunix_summary
        assert "display_name" in bitunix_summary
        assert "created_at" in bitunix_summary
        assert "updated_at" in bitunix_summary
        
        assert bitunix_summary["is_active"] is True
        assert bitunix_summary["connection_status"] == "unknown"

    def test_get_exchange_connection_summary_empty(self, config_service):
        """Test getting exchange connection summary with no configs."""
        summary = config_service.get_exchange_connection_summary()
        assert summary == {}

    @patch('app.services.config_service.ConfigService.test_exchange_connection')
    def test_monitor_exchange_connections_with_errors(self, mock_test_connection, config_service):
        """Test monitoring exchange connections with connection errors."""
        # Create exchange config
        config_service.create_exchange_config_with_validation(
            "bitunix", "valid_key_123", test_connection=False
        )
        
        # Mock connection test to raise exception
        mock_test_connection.side_effect = Exception("Connection failed")
        
        # Monitor connections
        status_map = config_service.monitor_exchange_connections()
        
        # Should handle exception and set status to ERROR
        assert status_map["bitunix"] == ConnectionStatus.ERROR
        
        # Verify status was saved
        config = config_service.get_exchange_connection_summary()
        assert config["bitunix"]["connection_status"] == "error"

    def test_configuration_persistence_with_encryption(self, config_service):
        """Test that encrypted configurations persist correctly."""
        api_key = "test_persistence_key_123"
        
        # Create config with encryption
        config = config_service.create_exchange_config_with_validation(
            "bitunix", api_key, test_connection=False
        )
        
        # Create new service instance (simulates app restart)
        new_service = ConfigService(data_path=config_service.data_path)
        
        # Retrieve config
        retrieved_config = new_service.get_exchange_config("bitunix")
        assert retrieved_config is not None
        
        # Decrypt and verify API key
        decrypted_key = new_service.decrypt_api_key("bitunix", retrieved_config.api_key_encrypted)
        assert decrypted_key == api_key

    def test_multiple_exchange_configs_validation(self, config_service):
        """Test validation with multiple exchange configurations."""
        # Create multiple exchange configs
        exchanges = [
            ("bitunix", "bitunix_key_123"),
            ("exchange2", "exchange2_key_456"),
            ("exchange3", "exchange3_key_789")
        ]
        
        for exchange_name, api_key in exchanges:
            config = config_service.create_exchange_config_with_validation(
                exchange_name, api_key, test_connection=False
            )
            assert config.name == exchange_name
        
        # Verify all configs exist
        all_configs = config_service.get_all_exchange_configs()
        assert len(all_configs) == 3
        
        for exchange_name, _ in exchanges:
            assert exchange_name in all_configs
        
        # Test connection monitoring for all
        status_map = config_service.monitor_exchange_connections()
        assert len(status_map) == 3