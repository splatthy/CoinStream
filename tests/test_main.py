"""
Simple unit tests for the main Streamlit application.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Mock the logging setup and other dependencies before importing main
with patch('app.utils.logging_config.setup_application_logging'), \
     patch('streamlit.set_page_config'), \
     patch('streamlit.session_state', {}):
    
    from app.main import (
        AppState, get_app_state, setup_page_config,
        render_sidebar_navigation, render_sync_controls,
        render_connection_status, main
    )


class TestAppState:
    """Test cases for AppState class."""
    
    def test_app_state_initialization(self):
        """Test AppState initialization."""
        with patch('app.main.get_state_manager'), \
             patch('app.main.get_loading_manager'), \
             patch('app.main.get_notification_manager'), \
             patch('app.main.get_data_refresh_manager'):
            
            app_state = AppState()
            
            assert app_state.config_service is None
            assert app_state.data_service is None
            assert app_state.analysis_service is None
            assert app_state.last_refresh is None
            assert app_state.initialization_error is None
    
    def test_initialize_services_success(self):
        """Test successful service initialization."""
        with patch('app.main.get_state_manager'), \
             patch('app.main.get_loading_manager') as mock_loading, \
             patch('app.main.get_notification_manager') as mock_notification, \
             patch('app.main.get_data_refresh_manager'), \
             patch('app.services.config_service.ConfigService') as mock_config, \
             patch('app.services.data_service.DataService') as mock_data, \
             patch('app.services.analysis_service.AnalysisService') as mock_analysis:
            
            # Setup mocks
            mock_loading_manager = Mock()
            mock_loading.return_value = mock_loading_manager
            
            mock_notification_manager = Mock()
            mock_notification.return_value = mock_notification_manager
            
            mock_config_service = Mock()
            mock_config.return_value = mock_config_service
            
            mock_data_service = Mock()
            mock_data.return_value = mock_data_service
            
            mock_analysis_service = Mock()
            mock_analysis.return_value = mock_analysis_service
            
            # Test initialization
            app_state = AppState()
            app_state.initialize_services("/test/data")
            
            # Verify services were created
            assert app_state.config_service == mock_config_service
            assert app_state.data_service == mock_data_service
            assert app_state.analysis_service == mock_analysis_service
            
            # Verify initialization was called
            mock_config_service.initialize_default_config.assert_called_once()
            mock_notification_manager.success.assert_called_once()
    
    def test_initialize_services_error(self):
        """Test service initialization with error."""
        with patch('app.main.get_state_manager'), \
             patch('app.main.get_loading_manager') as mock_loading, \
             patch('app.main.get_notification_manager') as mock_notification, \
             patch('app.main.get_data_refresh_manager'), \
             patch('app.services.config_service.ConfigService', side_effect=Exception("Init failed")):
            
            mock_loading_manager = Mock()
            mock_loading.return_value = mock_loading_manager
            
            mock_notification_manager = Mock()
            mock_notification.return_value = mock_notification_manager
            
            app_state = AppState()
            
            with pytest.raises(Exception, match="Init failed"):
                app_state.initialize_services("/test/data")
            
            assert app_state.initialization_error == "Init failed"
            mock_notification_manager.error.assert_called_once()
    
    def test_refresh_data(self):
        """Test data refresh functionality."""
        with patch('app.main.get_state_manager') as mock_state_manager, \
             patch('app.main.get_loading_manager'), \
             patch('app.main.get_notification_manager') as mock_notification, \
             patch('app.main.get_data_refresh_manager'):
            
            mock_state_mgr = Mock()
            mock_state_manager.return_value = mock_state_mgr
            
            mock_notification_manager = Mock()
            mock_notification.return_value = mock_notification_manager
            
            mock_data_service = Mock()
            
            app_state = AppState()
            app_state.data_service = mock_data_service
            
            app_state.refresh_data()
            
            # Verify data service cache was cleared
            mock_data_service.clear_cache.assert_called_once()
            
            # Verify state was updated
            mock_state_mgr.clear_cache.assert_called_once()
            mock_state_mgr.set.assert_called()
            
            # Verify success notification
            mock_notification_manager.success.assert_called_once()
    
    def test_is_loading_any(self):
        """Test loading state checking."""
        with patch('app.main.get_state_manager'), \
             patch('app.main.get_loading_manager') as mock_loading, \
             patch('app.main.get_notification_manager'), \
             patch('app.main.get_data_refresh_manager'):
            
            mock_loading_manager = Mock()
            mock_loading_manager.get_all_loading_operations.return_value = {"op1": {}}
            mock_loading.return_value = mock_loading_manager
            
            app_state = AppState()
            
            assert app_state.is_loading_any() is True
            
            # Test with no loading operations
            mock_loading_manager.get_all_loading_operations.return_value = {}
            assert app_state.is_loading_any() is False


class TestMainFunctions:
    """Test main application functions."""
    
    @patch('streamlit.set_page_config')
    def test_setup_page_config(self, mock_set_page_config):
        """Test page configuration setup."""
        setup_page_config()
        
        mock_set_page_config.assert_called_once_with(
            page_title="Crypto Trading Journal",
            page_icon="📈",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    @patch('streamlit.session_state', {})
    def test_get_app_state(self):
        """Test getting app state from session."""
        with patch('app.main.AppState') as mock_app_state_class:
            mock_app_state = Mock()
            mock_app_state_class.return_value = mock_app_state
            
            # First call should create new state
            result = get_app_state()
            
            assert result == mock_app_state
            mock_app_state.initialize_services.assert_called_once()
    
    @patch('streamlit.sidebar.title')
    @patch('streamlit.sidebar.selectbox')
    def test_render_sidebar_navigation(self, mock_selectbox, mock_title):
        """Test sidebar navigation rendering."""
        mock_selectbox.return_value = "Trade History"
        
        with patch('app.main.render_sync_controls'), \
             patch('app.main.render_connection_status'):
            
            result = render_sidebar_navigation()
            
            assert result == "trade_history"
            mock_title.assert_called_once_with("📈 Trading Journal")
            mock_selectbox.assert_called_once()
    
    @patch('streamlit.sidebar.subheader')
    @patch('streamlit.sidebar.columns')
    @patch('streamlit.sidebar.button')
    def test_render_sync_controls(self, mock_button, mock_columns, mock_subheader):
        """Test sync controls rendering."""
        mock_columns.return_value = [Mock(), Mock()]
        mock_button.return_value = False
        
        with patch('app.main.get_app_state') as mock_get_state, \
             patch('app.main.render_sync_status'):
            
            mock_app_state = Mock()
            mock_get_state.return_value = mock_app_state
            
            render_sync_controls()
            
            mock_subheader.assert_called_once_with("🔄 Data Sync")
            mock_columns.assert_called_once_with(2)
    
    @patch('streamlit.sidebar.subheader')
    @patch('streamlit.sidebar.caption')
    def test_render_connection_status(self, mock_caption, mock_subheader):
        """Test connection status rendering."""
        with patch('app.main.get_app_state') as mock_get_state:
            mock_app_state = Mock()
            mock_config_service = Mock()
            mock_config_service.get_all_exchange_configs.return_value = {
                'bitunix': Mock(
                    is_active=True,
                    connection_status=Mock(value='connected'),
                    last_sync=None
                )
            }
            mock_app_state.config_service = mock_config_service
            mock_get_state.return_value = mock_app_state
            
            render_connection_status()
            
            mock_subheader.assert_called_once_with("Exchange Status")
            mock_caption.assert_called()
    
    @patch('streamlit.set_page_config')
    @patch('streamlit.error')
    def test_main_function(self, mock_error, mock_set_page_config):
        """Test main function execution."""
        with patch('app.main.get_app_state') as mock_get_state, \
             patch('app.main.render_sidebar_navigation') as mock_sidebar, \
             patch('app.main.render_messages') as mock_messages:
            
            mock_sidebar.return_value = "trade_history"
            mock_app_state = Mock()
            mock_get_state.return_value = mock_app_state
            
            # Mock the page import and function
            with patch('app.pages.trade_history.show_trade_history_page') as mock_page:
                main()
                
                mock_set_page_config.assert_called_once()
                mock_get_state.assert_called_once()
                mock_sidebar.assert_called_once()
                mock_messages.assert_called_once()
                mock_page.assert_called_once()
    
    @patch('streamlit.set_page_config')
    @patch('streamlit.error')
    def test_main_function_with_error(self, mock_error, mock_set_page_config):
        """Test main function with error handling."""
        with patch('app.main.get_app_state', side_effect=Exception("Test error")):
            main()
            
            mock_error.assert_called()


if __name__ == '__main__':
    pytest.main([__file__])