"""
Unit tests for ConfigService class.
"""

import json
import pytest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.config_service import ConfigService
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.models.custom_fields import CustomFieldConfig, FieldType


class TestConfigService:
    """Test cases for ConfigService."""

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

    def test_init_creates_data_directory(self, temp_data_dir):
        """Test that ConfigService creates data directory if it doesn't exist."""
        data_path = Path(temp_data_dir) / "new_dir"
        assert not data_path.exists()
        
        service = ConfigService(data_path=str(data_path))
        assert data_path.exists()

    def test_get_app_config_empty_initially(self, config_service):
        """Test that app config is empty initially."""
        config = config_service.get_app_config()
        assert isinstance(config, dict)
        assert len(config) == 0

    def test_update_app_config(self, config_service):
        """Test updating application configuration."""
        updates = {
            "theme": "dark",
            "auto_sync": True,
            "sync_interval": 12
        }
        
        config_service.update_app_config(updates)
        config = config_service.get_app_config()
        
        assert config["theme"] == "dark"
        assert config["auto_sync"] is True
        assert config["sync_interval"] == 12

    def test_app_config_persistence(self, config_service):
        """Test that app config persists across service instances."""
        updates = {"test_key": "test_value"}
        config_service.update_app_config(updates)
        
        # Create new service instance
        new_service = ConfigService(data_path=config_service.data_path)
        config = new_service.get_app_config()
        
        assert config["test_key"] == "test_value"

    def test_get_exchange_config_not_found(self, config_service):
        """Test getting non-existent exchange config returns None."""
        config = config_service.get_exchange_config("nonexistent")
        assert config is None

    def test_save_and_get_exchange_config(self, config_service):
        """Test saving and retrieving exchange configuration."""
        exchange_config = ExchangeConfig(
            name="bitunix",
            api_key_encrypted="encrypted_key_123",
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        
        config_service.save_exchange_config(exchange_config)
        retrieved_config = config_service.get_exchange_config("bitunix")
        
        assert retrieved_config is not None
        assert retrieved_config.name == "bitunix"
        assert retrieved_config.api_key_encrypted == "encrypted_key_123"
        assert retrieved_config.is_active is True
        assert retrieved_config.connection_status == ConnectionStatus.CONNECTED

    def test_get_all_exchange_configs(self, config_service):
        """Test getting all exchange configurations."""
        config1 = ExchangeConfig(name="exchange1", api_key_encrypted="key1")
        config2 = ExchangeConfig(name="exchange2", api_key_encrypted="key2")
        
        config_service.save_exchange_config(config1)
        config_service.save_exchange_config(config2)
        
        all_configs = config_service.get_all_exchange_configs()
        
        assert len(all_configs) == 2
        assert "exchange1" in all_configs
        assert "exchange2" in all_configs

    def test_delete_exchange_config(self, config_service):
        """Test deleting exchange configuration."""
        config = ExchangeConfig(name="test_exchange", api_key_encrypted="key")
        config_service.save_exchange_config(config)
        
        # Verify it exists
        assert config_service.get_exchange_config("test_exchange") is not None
        
        # Delete it
        result = config_service.delete_exchange_config("test_exchange")
        assert result is True
        
        # Verify it's gone
        assert config_service.get_exchange_config("test_exchange") is None

    def test_delete_nonexistent_exchange_config(self, config_service):
        """Test deleting non-existent exchange config returns False."""
        result = config_service.delete_exchange_config("nonexistent")
        assert result is False

    def test_get_active_exchanges(self, config_service):
        """Test getting only active exchange configurations."""
        active_config = ExchangeConfig(name="active", api_key_encrypted="key1", is_active=True)
        inactive_config = ExchangeConfig(name="inactive", api_key_encrypted="key2", is_active=False)
        
        config_service.save_exchange_config(active_config)
        config_service.save_exchange_config(inactive_config)
        
        active_exchanges = config_service.get_active_exchanges()
        
        assert len(active_exchanges) == 1
        assert active_exchanges[0].name == "active"

    def test_exchange_config_persistence(self, config_service):
        """Test that exchange configs persist across service instances."""
        config = ExchangeConfig(name="persistent", api_key_encrypted="key")
        config_service.save_exchange_config(config)
        
        # Create new service instance
        new_service = ConfigService(data_path=config_service.data_path)
        retrieved_config = new_service.get_exchange_config("persistent")
        
        assert retrieved_config is not None
        assert retrieved_config.name == "persistent"

    def test_get_custom_field_config_not_found(self, config_service):
        """Test getting non-existent custom field config returns None."""
        config = config_service.get_custom_field_config("nonexistent")
        assert config is None

    def test_save_and_get_custom_field_config(self, config_service):
        """Test saving and retrieving custom field configuration."""
        field_config = CustomFieldConfig(
            field_name="test_field",
            field_type=FieldType.MULTISELECT,
            options=["option1", "option2"],
            is_required=True
        )
        
        config_service.save_custom_field_config(field_config)
        retrieved_config = config_service.get_custom_field_config("test_field")
        
        assert retrieved_config is not None
        assert retrieved_config.field_name == "test_field"
        assert retrieved_config.field_type == FieldType.MULTISELECT
        assert retrieved_config.options == ["option1", "option2"]
        assert retrieved_config.is_required is True

    def test_get_all_custom_field_configs(self, config_service):
        """Test getting all custom field configurations."""
        config1 = CustomFieldConfig(field_name="field1", field_type=FieldType.TEXT)
        config2 = CustomFieldConfig(field_name="field2", field_type=FieldType.NUMBER)
        
        config_service.save_custom_field_config(config1)
        config_service.save_custom_field_config(config2)
        
        all_configs = config_service.get_all_custom_field_configs()
        
        assert len(all_configs) == 2
        assert "field1" in all_configs
        assert "field2" in all_configs

    def test_delete_custom_field_config(self, config_service):
        """Test deleting custom field configuration."""
        config = CustomFieldConfig(field_name="test_field", field_type=FieldType.TEXT)
        config_service.save_custom_field_config(config)
        
        # Verify it exists
        assert config_service.get_custom_field_config("test_field") is not None
        
        # Delete it
        result = config_service.delete_custom_field_config("test_field")
        assert result is True
        
        # Verify it's gone
        assert config_service.get_custom_field_config("test_field") is None

    def test_delete_nonexistent_custom_field_config(self, config_service):
        """Test deleting non-existent custom field config returns False."""
        result = config_service.delete_custom_field_config("nonexistent")
        assert result is False

    def test_custom_field_config_persistence(self, config_service):
        """Test that custom field configs persist across service instances."""
        config = CustomFieldConfig(field_name="persistent", field_type=FieldType.TEXT)
        config_service.save_custom_field_config(config)
        
        # Create new service instance
        new_service = ConfigService(data_path=config_service.data_path)
        retrieved_config = new_service.get_custom_field_config("persistent")
        
        assert retrieved_config is not None
        assert retrieved_config.field_name == "persistent"

    def test_get_confluence_options_no_config(self, config_service):
        """Test getting confluence options when no config exists."""
        options = config_service.get_confluence_options()
        assert options == []

    def test_get_confluence_options_with_config(self, config_service):
        """Test getting confluence options from existing config."""
        confluence_config = CustomFieldConfig(
            field_name="confluences",
            field_type=FieldType.MULTISELECT,
            options=["RSI", "Support", "Volume"]
        )
        config_service.save_custom_field_config(confluence_config)
        
        options = config_service.get_confluence_options()
        assert options == ["RSI", "Support", "Volume"]

    def test_update_confluence_options_new_config(self, config_service):
        """Test updating confluence options creates new config if none exists."""
        new_options = ["MA", "Bollinger", "MACD"]
        config_service.update_confluence_options(new_options)
        
        options = config_service.get_confluence_options()
        assert options == new_options

    def test_update_confluence_options_existing_config(self, config_service):
        """Test updating confluence options on existing config."""
        # Create initial config
        initial_config = CustomFieldConfig(
            field_name="confluences",
            field_type=FieldType.MULTISELECT,
            options=["RSI", "Support"]
        )
        config_service.save_custom_field_config(initial_config)
        
        # Update options
        new_options = ["MA", "Bollinger", "MACD"]
        config_service.update_confluence_options(new_options)
        
        options = config_service.get_confluence_options()
        assert options == new_options

    def test_initialize_default_config(self, config_service):
        """Test initializing default configuration."""
        config_service.initialize_default_config()
        
        # Check app config
        app_config = config_service.get_app_config()
        assert app_config["app_name"] == "Crypto Trading Journal"
        assert app_config["version"] == "1.0.0"
        assert "created_at" in app_config
        
        # Check custom fields
        all_fields = config_service.get_all_custom_field_configs()
        assert "confluences" in all_fields
        assert "win_loss" in all_fields
        
        confluences_config = all_fields["confluences"]
        assert confluences_config.field_type == FieldType.MULTISELECT
        assert len(confluences_config.options) > 0
        
        win_loss_config = all_fields["win_loss"]
        assert win_loss_config.field_type == FieldType.SELECT
        assert "win" in win_loss_config.options
        assert "loss" in win_loss_config.options

    def test_config_file_corruption_handling(self, config_service):
        """Test handling of corrupted configuration files."""
        # Create corrupted config file
        config_file = Path(config_service.data_path) / "config.json"
        with open(config_file, 'w') as f:
            f.write("invalid json content")
        
        with pytest.raises(ValueError, match="Failed to load app configuration"):
            config_service.get_app_config()

    def test_exchange_config_file_corruption_handling(self, config_service):
        """Test handling of corrupted exchange configuration files."""
        # Create corrupted exchanges file
        exchanges_file = Path(config_service.data_path) / "exchanges.json"
        with open(exchanges_file, 'w') as f:
            f.write("invalid json content")
        
        with pytest.raises(ValueError, match="Failed to load exchange configurations"):
            config_service.get_all_exchange_configs()

    def test_custom_fields_file_corruption_handling(self, config_service):
        """Test handling of corrupted custom fields configuration files."""
        # Create corrupted custom fields file
        custom_fields_file = Path(config_service.data_path) / "custom_fields.json"
        with open(custom_fields_file, 'w') as f:
            f.write("invalid json content")
        
        with pytest.raises(ValueError, match="Failed to load custom field configurations"):
            config_service.get_all_custom_field_configs()

    @patch('app.services.config_service.CredentialEncryption')
    def test_encryption_manager_initialization(self, mock_encryption_manager, temp_data_dir):
        """Test that CredentialEncryption is properly initialized."""
        # Create service after mock is applied
        config_service = ConfigService(data_path=temp_data_dir)
        mock_encryption_manager.assert_called_once()

    def test_config_updates_timestamp(self, config_service):
        """Test that configuration updates modify timestamps."""
        # Test exchange config timestamp update
        exchange_config = ExchangeConfig(name="test", api_key_encrypted="key")
        original_time = exchange_config.updated_at
        
        config_service.save_exchange_config(exchange_config)
        saved_config = config_service.get_exchange_config("test")
        
        assert saved_config.updated_at >= original_time

        # Test custom field config timestamp update
        field_config = CustomFieldConfig(field_name="test", field_type=FieldType.TEXT)
        original_time = field_config.updated_at
        
        config_service.save_custom_field_config(field_config)
        saved_field_config = config_service.get_custom_field_config("test")
        
        assert saved_field_config.updated_at >= original_time