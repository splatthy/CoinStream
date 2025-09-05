"""
Unit tests for the error handling system.
"""

import pytest
import logging
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.utils.error_handler import (
    TradingJournalError, ConfigurationError, ExchangeAPIError,
    DataValidationError, DataPersistenceError, EncryptionError,
    ErrorHandler, handle_exceptions, safe_execute, create_error_with_recovery
)


class TestTradingJournalError:
    """Test custom exception classes."""
    
    def test_base_error_creation(self):
        """Test creating base TradingJournalError."""
        error = TradingJournalError(
            message="Test error",
            error_code="TEST_001",
            recovery_suggestion="Try again"
        )
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.error_code == "TEST_001"
        assert error.recovery_suggestion == "Try again"
        assert isinstance(error.timestamp, datetime)
    
    def test_error_without_optional_params(self):
        """Test creating error without optional parameters."""
        error = TradingJournalError("Simple error")
        
        assert str(error) == "Simple error"
        assert error.message == "Simple error"
        assert error.error_code == "GENERAL_ERROR"
        assert error.recovery_suggestion is None
    
    def test_specific_error_types(self):
        """Test specific error type creation."""
        config_error = ConfigurationError("Config issue")
        api_error = ExchangeAPIError("API issue")
        validation_error = DataValidationError("Validation issue")
        persistence_error = DataPersistenceError("Storage issue")
        encryption_error = EncryptionError("Encryption issue")
        
        assert isinstance(config_error, TradingJournalError)
        assert isinstance(api_error, TradingJournalError)
        assert isinstance(validation_error, TradingJournalError)
        assert isinstance(persistence_error, TradingJournalError)
        assert isinstance(encryption_error, TradingJournalError)


class TestErrorHandler:
    """Test ErrorHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    @patch('streamlit.error')
    def test_handle_error_with_custom_error(self, mock_st_error):
        """Test handling custom TradingJournalError."""
        error = TradingJournalError(
            "Test error",
            "TEST_001",
            "Try restarting"
        )
        
        with patch.object(self.error_handler.logger, 'log') as mock_log:
            self.error_handler.handle_error(error, "Test Context")
            
            # Check logging was called
            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            assert args[0] == logging.ERROR
            assert "Test Context" in args[1]
            assert "TEST_001" in args[1]
            assert "Try restarting" in args[1]
            
            # Check Streamlit error was shown
            mock_st_error.assert_called_once()
    
    @patch('streamlit.error')
    def test_handle_error_with_standard_exception(self, mock_st_error):
        """Test handling standard Python exception."""
        error = ValueError("Standard error")
        
        with patch.object(self.error_handler.logger, 'log') as mock_log:
            self.error_handler.handle_error(error, "Test Context")
            
            mock_log.assert_called_once()
            mock_st_error.assert_called_once()
    
    def test_handle_error_without_user_display(self):
        """Test handling error without showing to user."""
        error = ValueError("Hidden error")
        
        with patch.object(self.error_handler.logger, 'log') as mock_log:
            with patch('streamlit.error') as mock_st_error:
                self.error_handler.handle_error(error, show_to_user=False)
                
                mock_log.assert_called_once()
                mock_st_error.assert_not_called()
    
    def test_error_statistics(self):
        """Test error statistics tracking."""
        error1 = ValueError("Error 1")
        error2 = ValueError("Error 1")  # Same error
        error3 = TypeError("Error 2")   # Different error
        
        with patch.object(self.error_handler.logger, 'log'):
            with patch('streamlit.error'):
                self.error_handler.handle_error(error1, show_to_user=False)
                self.error_handler.handle_error(error2, show_to_user=False)
                self.error_handler.handle_error(error3, show_to_user=False)
        
        stats = self.error_handler.get_error_stats()
        
        assert stats["total_errors"] == 3
        assert len(stats["error_counts"]) == 2  # Two unique error types
        assert "ValueError:Error 1" in stats["error_counts"]
        assert "TypeError:Error 2" in stats["error_counts"]
        assert stats["error_counts"]["ValueError:Error 1"] == 2
        assert stats["error_counts"]["TypeError:Error 2"] == 1
    
    def test_clear_error_statistics(self):
        """Test clearing error statistics."""
        error = ValueError("Test error")
        
        with patch.object(self.error_handler.logger, 'log'):
            with patch('streamlit.error'):
                self.error_handler.handle_error(error, show_to_user=False)
        
        # Verify stats exist
        stats = self.error_handler.get_error_stats()
        assert stats["total_errors"] == 1
        
        # Clear and verify
        self.error_handler.clear_error_stats()
        stats = self.error_handler.get_error_stats()
        assert stats["total_errors"] == 0
        assert len(stats["error_counts"]) == 0


class TestErrorDecorators:
    """Test error handling decorators and utilities."""
    
    @patch('streamlit.error')
    def test_handle_exceptions_decorator(self, mock_st_error):
        """Test handle_exceptions decorator."""
        @handle_exceptions(context="Test Function", show_to_user=True)
        def failing_function():
            raise ValueError("Function failed")
        
        with patch('app.utils.error_handler.error_handler.handle_error') as mock_handle:
            result = failing_function()
            
            assert result is None  # Default return for failed function
            mock_handle.assert_called_once()
            
            # Check the error was handled with correct context
            args, kwargs = mock_handle.call_args
            assert isinstance(args[0], ValueError)
            assert args[1] == "Test Function"
    
    @patch('streamlit.error')
    def test_handle_exceptions_decorator_with_reraise(self, mock_st_error):
        """Test handle_exceptions decorator with reraise=True."""
        @handle_exceptions(context="Test Function", reraise=True)
        def failing_function():
            raise ValueError("Function failed")
        
        with patch('app.utils.error_handler.error_handler.handle_error') as mock_handle:
            with pytest.raises(ValueError):
                failing_function()
            
            mock_handle.assert_called_once()
    
    def test_handle_exceptions_decorator_success(self):
        """Test handle_exceptions decorator with successful function."""
        @handle_exceptions(context="Test Function")
        def successful_function():
            return "success"
        
        with patch('app.utils.error_handler.error_handler.handle_error') as mock_handle:
            result = successful_function()
            
            assert result == "success"
            mock_handle.assert_not_called()
    
    @patch('streamlit.error')
    def test_safe_execute_with_failure(self, mock_st_error):
        """Test safe_execute with failing function."""
        def failing_function(x, y):
            raise ValueError("Function failed")
        
        with patch('app.utils.error_handler.error_handler.handle_error') as mock_handle:
            result = safe_execute(
                failing_function,
                1, 2,
                context="Safe Test",
                default_return="default"
            )
            
            assert result == "default"
            mock_handle.assert_called_once()
    
    def test_safe_execute_with_success(self):
        """Test safe_execute with successful function."""
        def successful_function(x, y):
            return x + y
        
        with patch('app.utils.error_handler.error_handler.handle_error') as mock_handle:
            result = safe_execute(successful_function, 1, 2)
            
            assert result == 3
            mock_handle.assert_not_called()
    
    def test_create_error_with_recovery(self):
        """Test create_error_with_recovery utility."""
        error = create_error_with_recovery(
            ConfigurationError,
            "Config missing",
            "CONFIG_001",
            "Check config file"
        )
        
        assert isinstance(error, ConfigurationError)
        assert error.message == "Config missing"
        assert error.error_code == "CONFIG_001"
        assert error.recovery_suggestion == "Check config file"


class TestErrorHandlerIntegration:
    """Integration tests for error handling system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('streamlit.error')
    def test_error_handling_with_logging(self, mock_st_error):
        """Test error handling with actual logging."""
        from app.utils.logging_config import LoggingConfig
        
        # Set up logging in temp directory
        logging_config = LoggingConfig(self.temp_dir)
        logging_config.setup_logging(log_level="DEBUG", console_output=False)
        
        error_handler = ErrorHandler()
        error = TradingJournalError("Integration test error", "INT_001")
        
        error_handler.handle_error(error, "Integration Test")
        
        # Check that log file was created
        log_files = logging_config.get_log_files()
        assert len(log_files) > 0
        
        # Check log content
        main_log = next((f for f in log_files if f.name == "trading_journal.log"), None)
        assert main_log is not None
        
        with open(main_log, 'r') as f:
            log_content = f.read()
            assert "Integration test error" in log_content
            assert "INT_001" in log_content
    
    def test_multiple_error_types_tracking(self):
        """Test tracking multiple different error types."""
        error_handler = ErrorHandler()
        
        errors = [
            ConfigurationError("Config error"),
            ExchangeAPIError("API error"),
            DataValidationError("Validation error"),
            ConfigurationError("Another config error")
        ]
        
        with patch.object(error_handler.logger, 'log'):
            with patch('streamlit.error'):
                for error in errors:
                    error_handler.handle_error(error, show_to_user=False)
        
        stats = error_handler.get_error_stats()
        assert stats["total_errors"] == 4
        assert len(stats["error_counts"]) == 3  # Three unique error messages
        
        # Check specific counts
        config_key = "ConfigurationError:Config error"
        assert stats["error_counts"][config_key] == 1
        
        another_config_key = "ConfigurationError:Another config error"
        assert stats["error_counts"][another_config_key] == 1