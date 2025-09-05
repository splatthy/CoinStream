"""
Unit tests for the logging configuration system.
"""

import pytest
import logging
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from app.utils.logging_config import (
    TradingJournalFormatter, LoggingConfig, 
    setup_application_logging, get_logger
)


class TestTradingJournalFormatter:
    """Test custom log formatter."""
    
    def test_format_info_message(self):
        """Test formatting INFO level message."""
        formatter = TradingJournalFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test info message",
            args=(),
            exc_info=None,
            func="test_function"
        )
        
        formatted = formatter.format(record)
        
        assert "test.logger" in formatted
        assert "INFO" in formatted
        assert "Test info message" in formatted
        # INFO level should not include pathname/lineno
        assert "/path/to/file.py" not in formatted
        assert "42" not in formatted
    
    def test_format_error_message(self):
        """Test formatting ERROR level message."""
        formatter = TradingJournalFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test error message",
            args=(),
            exc_info=None,
            func="test_function"
        )
        
        formatted = formatter.format(record)
        
        assert "test.logger" in formatted
        assert "ERROR" in formatted
        assert "Test error message" in formatted
        # ERROR level should include pathname/lineno
        assert "/path/to/file.py" in formatted
        assert "42" in formatted
        assert "test_function" in formatted


class TestLoggingConfig:
    """Test LoggingConfig class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.logging_config = LoggingConfig(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Reset logging configuration
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)
    
    def test_initialization(self):
        """Test LoggingConfig initialization."""
        assert self.logging_config.data_path == Path(self.temp_dir)
        assert self.logging_config.log_dir == Path(self.temp_dir) / "logs"
        assert self.logging_config.log_dir.exists()
        assert not self.logging_config._configured
    
    def test_setup_logging_default(self):
        """Test setting up logging with default configuration."""
        self.logging_config.setup_logging()
        
        assert self.logging_config._configured
        
        # Check root logger configuration
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) >= 2  # Console + file handlers
    
    def test_setup_logging_custom_level(self):
        """Test setting up logging with custom level."""
        self.logging_config.setup_logging(log_level="DEBUG")
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
    
    @patch.dict(os.environ, {'LOG_LEVEL': 'WARNING'})
    def test_setup_logging_env_level(self):
        """Test setting up logging with environment variable level."""
        self.logging_config.setup_logging()
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
    
    def test_setup_logging_console_only(self):
        """Test setting up logging with console output only."""
        self.logging_config.setup_logging(
            console_output=True,
            file_output=False
        )
        
        root_logger = logging.getLogger()
        # Should have only console handler
        console_handlers = [h for h in root_logger.handlers 
                          if isinstance(h, logging.StreamHandler) 
                          and not hasattr(h, 'baseFilename')]
        assert len(console_handlers) >= 1
    
    def test_setup_logging_file_only(self):
        """Test setting up logging with file output only."""
        self.logging_config.setup_logging(
            console_output=False,
            file_output=True
        )
        
        root_logger = logging.getLogger()
        # Should have file handlers
        file_handlers = [h for h in root_logger.handlers 
                        if hasattr(h, 'baseFilename')]
        assert len(file_handlers) >= 2  # Main log + error log
    
    def test_log_level_parsing(self):
        """Test log level string parsing."""
        test_cases = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
            ("invalid", logging.INFO),  # Default fallback
            (None, logging.INFO)  # Default fallback
        ]
        
        for level_str, expected_level in test_cases:
            actual_level = self.logging_config._get_log_level(level_str)
            assert actual_level == expected_level
    
    def test_component_logger_configuration(self):
        """Test that component loggers are configured correctly."""
        self.logging_config.setup_logging(log_level="DEBUG")
        
        # Test application component loggers
        app_logger = logging.getLogger("app.services")
        assert app_logger.level == logging.DEBUG
        
        # Test external library loggers are set to WARNING
        urllib_logger = logging.getLogger("urllib3")
        assert urllib_logger.level == logging.WARNING
    
    def test_get_log_files(self):
        """Test getting list of log files."""
        # Initially no log files
        log_files = self.logging_config.get_log_files()
        assert len(log_files) == 0
        
        # Set up logging to create files
        self.logging_config.setup_logging(file_output=True)
        
        # Log something to create files
        logger = logging.getLogger("test")
        logger.info("Test message")
        logger.error("Test error")
        
        # Check files exist
        log_files = self.logging_config.get_log_files()
        assert len(log_files) >= 1
        
        # Check specific files
        log_names = [f.name for f in log_files]
        assert "trading_journal.log" in log_names
    
    def test_get_log_stats(self):
        """Test getting log file statistics."""
        self.logging_config.setup_logging(file_output=True)
        
        # Log some messages to create files
        logger = logging.getLogger("test")
        logger.info("Test message")
        logger.error("Test error")
        
        stats = self.logging_config.get_log_stats()
        
        assert "log_directory" in stats
        assert "log_files" in stats
        assert "total_size" in stats
        assert stats["log_directory"] == str(self.logging_config.log_dir)
        assert len(stats["log_files"]) >= 1
        assert stats["total_size"] > 0
        
        # Check file info structure
        for file_info in stats["log_files"]:
            assert "name" in file_info
            assert "size" in file_info
            assert "modified" in file_info
            assert isinstance(file_info["modified"], datetime)
    
    def test_cleanup_old_logs(self):
        """Test cleaning up old log files."""
        self.logging_config.setup_logging(file_output=True)
        
        # Create some log files
        logger = logging.getLogger("test")
        logger.info("Test message")
        
        # Get initial file count
        initial_files = self.logging_config.get_log_files()
        initial_count = len(initial_files)
        
        # Create an "old" log file by modifying timestamp
        if initial_files:
            old_file = initial_files[0]
            old_time = datetime.now().timestamp() - (40 * 24 * 60 * 60)  # 40 days ago
            os.utime(old_file, (old_time, old_time))
        
        # Clean up files older than 30 days
        deleted_count = self.logging_config.cleanup_old_logs(days_to_keep=30)
        
        # Check that old file was deleted
        if initial_count > 0:
            assert deleted_count >= 1
            remaining_files = self.logging_config.get_log_files()
            assert len(remaining_files) < initial_count
    
    def test_multiple_setup_calls(self):
        """Test that multiple setup calls don't create duplicate handlers."""
        self.logging_config.setup_logging()
        initial_handler_count = len(logging.getLogger().handlers)
        
        # Call setup again
        self.logging_config.setup_logging()
        
        # Should not add more handlers
        final_handler_count = len(logging.getLogger().handlers)
        assert final_handler_count == initial_handler_count


class TestLoggingUtilities:
    """Test logging utility functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Reset logging
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)
    
    def test_setup_application_logging(self):
        """Test setup_application_logging utility function."""
        setup_application_logging(log_level="DEBUG", data_path=self.temp_dir)
        
        # Check that logging was configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        
        # Check that log directory was created
        log_dir = Path(self.temp_dir) / "logs"
        assert log_dir.exists()
    
    def test_get_logger(self):
        """Test get_logger utility function."""
        setup_application_logging(data_path=self.temp_dir)
        
        logger = get_logger("test.module")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"
    
    def test_logger_hierarchy(self):
        """Test that logger hierarchy works correctly."""
        setup_application_logging(log_level="DEBUG", data_path=self.temp_dir)
        
        # Create loggers at different levels
        parent_logger = get_logger("app")
        child_logger = get_logger("app.services")
        grandchild_logger = get_logger("app.services.data")
        
        # All should be Logger instances
        assert isinstance(parent_logger, logging.Logger)
        assert isinstance(child_logger, logging.Logger)
        assert isinstance(grandchild_logger, logging.Logger)
        
        # Check hierarchy
        assert child_logger.parent == parent_logger
        assert grandchild_logger.parent == child_logger


class TestLoggingIntegration:
    """Integration tests for logging system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Reset logging
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)
    
    def test_end_to_end_logging(self):
        """Test complete logging workflow."""
        # Set up logging
        setup_application_logging(log_level="INFO", data_path=self.temp_dir)
        
        # Get logger and log messages
        logger = get_logger("test.integration")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        # Check that log files were created
        log_dir = Path(self.temp_dir) / "logs"
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) >= 1
        
        # Check main log content
        main_log = log_dir / "trading_journal.log"
        if main_log.exists():
            with open(main_log, 'r') as f:
                content = f.read()
                assert "Info message" in content
                assert "Warning message" in content
                assert "Error message" in content
        
        # Check error log content
        error_log = log_dir / "errors.log"
        if error_log.exists():
            with open(error_log, 'r') as f:
                content = f.read()
                assert "Error message" in content
                # Info and warning should not be in error log
                assert "Info message" not in content
    
    def test_log_rotation(self):
        """Test log file rotation functionality."""
        # Set up logging with small file size for testing
        logging_config = LoggingConfig(self.temp_dir)
        logging_config.setup_logging(
            log_level="INFO",
            max_file_size=1024,  # 1KB
            backup_count=2
        )
        
        # Generate enough log messages to trigger rotation
        logger = get_logger("test.rotation")
        for i in range(100):
            logger.info(f"Log message {i} - " + "x" * 50)  # Make messages longer
        
        # Check that log files exist (original + backups)
        log_files = list(Path(self.temp_dir).glob("logs/*.log*"))
        # Should have at least the main log file
        assert len(log_files) >= 1