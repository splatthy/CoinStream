"""
Logging configuration for the crypto trading journal application.
Provides structured logging with appropriate levels and formatters.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class TradingJournalFormatter(logging.Formatter):
    """Custom formatter for trading journal logs."""
    
    def __init__(self):
        super().__init__()
        self.default_format = (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self.error_format = (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s\n"
            "%(pathname)s:%(lineno)d in %(funcName)s"
        )
    
    def format(self, record):
        if record.levelno >= logging.ERROR:
            formatter = logging.Formatter(self.error_format)
        else:
            formatter = logging.Formatter(self.default_format)
        
        return formatter.format(record)


class LoggingConfig:
    """Centralized logging configuration manager."""
    
    def __init__(self, data_path: str = "data"):
        self.data_path = Path(data_path)
        self.log_dir = self.data_path / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._configured = False
    
    def setup_logging(
        self,
        log_level: str = None,
        console_output: bool = True,
        file_output: bool = True,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ) -> None:
        """
        Set up application logging configuration.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_output: Whether to output logs to console
            file_output: Whether to output logs to file
            max_file_size: Maximum size of log files before rotation
            backup_count: Number of backup log files to keep
        """
        if self._configured:
            return
        
        # Determine log level
        level = self._get_log_level(log_level)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Create formatter
        formatter = TradingJournalFormatter()
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # File handler with rotation
        if file_output:
            log_file = self.log_dir / "trading_journal.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
            # Separate error log file
            error_log_file = self.log_dir / "errors.log"
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=max_file_size,
                backupCount=backup_count
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            root_logger.addHandler(error_handler)
        
        # Configure specific loggers
        self._configure_component_loggers(level)
        
        self._configured = True
        
        # Log configuration completion
        logger = logging.getLogger(__name__)
        logger.info(f"Logging configured - Level: {logging.getLevelName(level)}")
    
    def _get_log_level(self, log_level: Optional[str]) -> int:
        """Get logging level from string or environment."""
        if log_level:
            level_str = log_level.upper()
        else:
            level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        
        return level_map.get(level_str, logging.INFO)
    
    def _configure_component_loggers(self, level: int) -> None:
        """Configure loggers for specific application components."""
        # Application components
        components = [
            "app.services",
            "app.integrations",
            "app.utils",
            "app.models",
            "app.pages"
        ]
        
        for component in components:
            logger = logging.getLogger(component)
            logger.setLevel(level)
        
        # External libraries - set to WARNING to reduce noise
        external_loggers = [
            "urllib3",
            "requests",
            "streamlit"
        ]
        
        for ext_logger in external_loggers:
            logger = logging.getLogger(ext_logger)
            logger.setLevel(logging.WARNING)
    
    def get_log_files(self) -> list:
        """Get list of current log files."""
        if not self.log_dir.exists():
            return []
        
        return [f for f in self.log_dir.iterdir() if f.suffix == ".log"]
    
    def get_log_stats(self) -> dict:
        """Get statistics about log files."""
        log_files = self.get_log_files()
        stats = {
            "log_directory": str(self.log_dir),
            "log_files": [],
            "total_size": 0
        }
        
        for log_file in log_files:
            file_stats = log_file.stat()
            stats["log_files"].append({
                "name": log_file.name,
                "size": file_stats.st_size,
                "modified": datetime.fromtimestamp(file_stats.st_mtime)
            })
            stats["total_size"] += file_stats.st_size
        
        return stats
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """
        Clean up log files older than specified days.
        
        Args:
            days_to_keep: Number of days of logs to keep
        
        Returns:
            Number of files deleted
        """
        if not self.log_dir.exists():
            return 0
        
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0
        
        for log_file in self.log_dir.iterdir():
            if log_file.suffix == ".log" and log_file.stat().st_mtime < cutoff_time:
                try:
                    log_file.unlink()
                    deleted_count += 1
                except OSError as e:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to delete old log file {log_file}: {e}")
        
        return deleted_count


# Global logging configuration instance
logging_config = LoggingConfig()


def setup_application_logging(
    log_level: str = None,
    data_path: str = "data"
) -> None:
    """
    Set up application logging with default configuration.
    
    Args:
        log_level: Logging level override
        data_path: Path to data directory for log files
    """
    global logging_config
    logging_config = LoggingConfig(data_path)
    logging_config.setup_logging(log_level=log_level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific component.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)