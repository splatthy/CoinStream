"""
Tests for the configuration page functionality.
"""

import pytest
from unittest.mock import Mock, patch

from app.pages.config import (
    add_exchange_configuration,
    update_exchange_api_key,
    test_exchange_connection,
    toggle_exchange_status,
    delete_exchange_config,
    add_custom_field_configuration,
    update_custom_field_configuration,
    add_custom_field_option,
    remove_custom_field_option,
    delete_custom_field_config
)
from app.services.config_service import ConfigService
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.models.custom_fields import CustomFieldConfig, FieldType


class TestConfigPageHelpers:
    """Test helper functions for the configuration page."""
    
    @pytest.fixture
    def mock_config_service(self):
        """Create a mock config service."""
        return Mock(spec=ConfigService)
    
    @pytest.fixture
    def mock_notification_manager(self):
        """Create a mock notification manager."""
        with patch('app.pages.config.get_notification_manager') as mock:
            notification_manager = Mock()
            mock.return_value = notification_manager
            yield notification_manager
    
    @pytest.fixture
    def sample_exchange_config(self):
        """Create a sample exchange configuration."""
        return ExchangeConfig(
            name="bitunix",
            api_key_encrypted="encrypted_key_123",
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
    
    @pytest.fixture
    def sample_custom_field_config(self):
        """Create a sample custom field configuration."""
        return CustomFieldConfig(
            field_name="test_field",
            field_type=FieldType.MULTISELECT,
            options=["option1", "option2", "option3"],
            is_required=False,
            description="Test field description"
        )
    
    def test_add_exchange_configuration_success(self, mock_config_service, mock_notification_manager):
        """Test successful addition of exchange configuration."""
        # Setup
        mock_config_service.get_exchange_config.return_value = None
        mock_config_service.create_exchange_config_with_validation.return_value = ExchangeConfig(
            name="bitunix",
            api_key_encrypted="encrypted_key",
            connection_status=ConnectionStatus.CONNECTED
        )
        
        with patch('streamlit.rerun'):
            # Execute
            add_exchange_configuration(mock_config_service, "bitunix", "test_api_key", True)
        
        # Verify
        mock_config_service.get_exchange_config.assert_called_once_with("bitunix")
        mock_config_service.create_exchange_config_with_validation.assert_called_once_with(
            "bitunix", "test_api_key", True
        )
        mock_notification_manager.success.assert_called_once()
    
    def test_add_exchange_configuration_already_exists(self, mock_config_service, mock_notification_manager, sample_exchange_config):
        """Test adding exchange configuration when it already exists."""
        # Setup
        mock_config_service.get_exchange_config.return_value = sample_exchange_config
        
        # Execute
        add_exchange_configuration(mock_config_service, "bitunix", "test_api_key", True)
        
        # Verify
        mock_config_service.create_exchange_config_with_validation.assert_not_called()
        mock_notification_manager.error.assert_called_once_with("Exchange bitunix is already configured")
    
    def test_add_exchange_configuration_empty_api_key(self, mock_config_service, mock_notification_manager):
        """Test adding exchange configuration with empty API key."""
        # Execute
        add_exchange_configuration(mock_config_service, "bitunix", "", True)
        
        # Verify
        mock_config_service.get_exchange_config.assert_not_called()
        mock_notification_manager.error.assert_called_once_with("API key is required")
    
    def test_update_exchange_api_key_success(self, mock_config_service, mock_notification_manager, sample_exchange_config):
        """Test successful API key update."""
        # Setup
        mock_config_service.update_exchange_api_key.return_value = True
        mock_config_service.get_exchange_config.return_value = sample_exchange_config
        
        with patch('streamlit.rerun'):
            # Execute
            update_exchange_api_key(mock_config_service, "bitunix", "new_api_key", save=True)
        
        # Verify
        mock_config_service.update_exchange_api_key.assert_called_once_with("bitunix", "new_api_key", test_connection=True)
        mock_notification_manager.success.assert_called_once()
    
    def test_test_exchange_connection_success(self, mock_config_service, mock_notification_manager):
        """Test successful exchange connection test."""
        # Setup
        mock_config_service.test_exchange_connection.return_value = True
        
        with patch('streamlit.rerun'):
            # Execute
            test_exchange_connection(mock_config_service, "bitunix")
        
        # Verify
        mock_config_service.update_exchange_connection_status.assert_any_call("bitunix", ConnectionStatus.TESTING)
        mock_config_service.update_exchange_connection_status.assert_any_call("bitunix", ConnectionStatus.CONNECTED)
        mock_notification_manager.success.assert_called_once_with("Connection test passed for bitunix")
    
    def test_toggle_exchange_status_activate(self, mock_config_service, mock_notification_manager, sample_exchange_config):
        """Test activating an exchange."""
        # Setup
        sample_exchange_config.is_active = False
        mock_config_service.get_exchange_config.return_value = sample_exchange_config
        
        with patch('streamlit.rerun'):
            # Execute
            toggle_exchange_status(mock_config_service, "bitunix", True)
        
        # Verify
        assert sample_exchange_config.is_active is True
        mock_config_service.save_exchange_config.assert_called_once_with(sample_exchange_config)
        mock_notification_manager.success.assert_called_once_with("Exchange bitunix activated")
    
    def test_delete_exchange_config_success(self, mock_config_service, mock_notification_manager):
        """Test successful exchange configuration deletion."""
        # Setup
        mock_config_service.delete_exchange_config.return_value = True
        
        with patch('streamlit.rerun'):
            # Execute
            delete_exchange_config(mock_config_service, "bitunix")
        
        # Verify
        mock_config_service.delete_exchange_config.assert_called_once_with("bitunix")
        mock_notification_manager.success.assert_called_once_with("Exchange bitunix deleted successfully")
    
    def test_add_custom_field_configuration_success(self, mock_config_service, mock_notification_manager):
        """Test successful addition of custom field configuration."""
        # Setup
        mock_config_service.get_custom_field_config.return_value = None
        
        with patch('streamlit.rerun'):
            # Execute
            add_custom_field_configuration(
                mock_config_service, "test_field", "multiselect", 
                ["option1", "option2"], False, "Test description"
            )
        
        # Verify
        mock_config_service.get_custom_field_config.assert_called_once_with("test_field")
        mock_config_service.save_custom_field_config.assert_called_once()
        mock_notification_manager.success.assert_called_once_with("Custom field test_field added successfully")
    
    def test_add_custom_field_configuration_already_exists(self, mock_config_service, mock_notification_manager, sample_custom_field_config):
        """Test adding custom field configuration when it already exists."""
        # Setup
        mock_config_service.get_custom_field_config.return_value = sample_custom_field_config
        
        # Execute
        add_custom_field_configuration(
            mock_config_service, "test_field", "multiselect", 
            ["option1", "option2"], False, "Test description"
        )
        
        # Verify
        mock_config_service.save_custom_field_config.assert_not_called()
        mock_notification_manager.error.assert_called_once_with("Custom field test_field already exists")
    
    def test_add_custom_field_option_success(self, mock_config_service, mock_notification_manager, sample_custom_field_config):
        """Test successful addition of custom field option."""
        # Setup
        mock_config_service.get_custom_field_config.return_value = sample_custom_field_config
        
        with patch('streamlit.rerun'):
            # Execute
            add_custom_field_option(mock_config_service, "test_field", "new_option")
        
        # Verify
        mock_config_service.get_custom_field_config.assert_called_once_with("test_field")
        mock_config_service.save_custom_field_config.assert_called_once_with(sample_custom_field_config)
        mock_notification_manager.success.assert_called_once_with("Option 'new_option' added to test_field")
    
    def test_remove_custom_field_option_success(self, mock_config_service, mock_notification_manager, sample_custom_field_config):
        """Test successful removal of custom field option."""
        # Setup
        mock_config_service.get_custom_field_config.return_value = sample_custom_field_config
        
        with patch('streamlit.rerun'):
            # Execute
            remove_custom_field_option(mock_config_service, "test_field", "option1")
        
        # Verify
        mock_config_service.get_custom_field_config.assert_called_once_with("test_field")
        mock_config_service.save_custom_field_config.assert_called_once_with(sample_custom_field_config)
        mock_notification_manager.success.assert_called_once_with("Option 'option1' removed from test_field")
    
    def test_update_custom_field_configuration_success(self, mock_config_service, mock_notification_manager, sample_custom_field_config):
        """Test successful update of custom field configuration."""
        # Setup
        mock_config_service.get_custom_field_config.return_value = sample_custom_field_config
        
        with patch('streamlit.rerun'):
            # Execute
            update_custom_field_configuration(
                mock_config_service, "test_field", True, "Updated description"
            )
        
        # Verify
        assert sample_custom_field_config.is_required is True
        assert sample_custom_field_config.description == "Updated description"
        mock_config_service.save_custom_field_config.assert_called_once_with(sample_custom_field_config)
        mock_notification_manager.success.assert_called_once_with("Custom field test_field updated successfully")
    
    def test_delete_custom_field_config_success(self, mock_config_service, mock_notification_manager):
        """Test successful custom field configuration deletion."""
        # Setup
        mock_config_service.delete_custom_field_config.return_value = True
        
        with patch('streamlit.rerun'):
            # Execute
            delete_custom_field_config(mock_config_service, "test_field")
        
        # Verify
        mock_config_service.delete_custom_field_config.assert_called_once_with("test_field")
        mock_notification_manager.success.assert_called_once_with("Custom field test_field deleted successfully")