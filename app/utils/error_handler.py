"""
Centralized error handling system for the crypto trading journal application.
Provides consistent error handling, logging, and user-friendly error messages.
"""

import logging
import traceback
import functools
from typing import Any, Callable, Dict, Optional, Type, Union
from datetime import datetime
import streamlit as st


class TradingJournalError(Exception):
    """Base exception class for trading journal application."""
    
    def __init__(self, message: str, error_code: str = None, recovery_suggestion: str = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "GENERAL_ERROR"
        self.recovery_suggestion = recovery_suggestion
        self.timestamp = datetime.now()


class ConfigurationError(TradingJournalError):
    """Raised when there are configuration-related issues."""
    pass


class ExchangeAPIError(TradingJournalError):
    """Raised when exchange API operations fail."""
    pass


class DataValidationError(TradingJournalError):
    """Raised when data validation fails."""
    pass


class DataPersistenceError(TradingJournalError):
    """Raised when data storage/retrieval operations fail."""
    pass


class EncryptionError(TradingJournalError):
    """Raised when encryption/decryption operations fail."""
    pass


class ErrorHandler:
    """Centralized error handler with logging and user notification capabilities."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._error_counts = {}
        self._last_errors = {}
    
    def handle_error(
        self, 
        error: Exception, 
        context: str = None,
        show_to_user: bool = True,
        log_level: int = logging.ERROR
    ) -> None:
        """
        Handle an error with logging and optional user notification.
        
        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred
            show_to_user: Whether to show the error to the user in the UI
            log_level: Logging level for the error
        """
        error_key = f"{type(error).__name__}:{str(error)}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
        self._last_errors[error_key] = datetime.now()
        
        # Log the error
        log_message = f"Error in {context}: {str(error)}" if context else str(error)
        
        if isinstance(error, TradingJournalError):
            log_message += f" [Code: {error.error_code}]"
            if error.recovery_suggestion:
                log_message += f" [Recovery: {error.recovery_suggestion}]"
        
        self.logger.log(log_level, log_message, exc_info=True)
        
        # Show to user if requested
        if show_to_user:
            self._show_error_to_user(error, context)
    
    def _show_error_to_user(self, error: Exception, context: str = None) -> None:
        """Display error message to user in Streamlit interface."""
        if isinstance(error, TradingJournalError):
            error_message = error.message
            if error.recovery_suggestion:
                error_message += f"\n\n**Suggestion:** {error.recovery_suggestion}"
        else:
            error_message = f"An unexpected error occurred: {str(error)}"
        
        if context:
            error_message = f"**{context}:** {error_message}"
        
        st.error(error_message)
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        return {
            "error_counts": self._error_counts.copy(),
            "last_errors": self._last_errors.copy(),
            "total_errors": sum(self._error_counts.values())
        }
    
    def clear_error_stats(self) -> None:
        """Clear error statistics."""
        self._error_counts.clear()
        self._last_errors.clear()


# Global error handler instance
error_handler = ErrorHandler()


def handle_exceptions(
    context: str = None,
    show_to_user: bool = True,
    log_level: int = logging.ERROR,
    reraise: bool = False
):
    """
    Decorator to handle exceptions in functions.
    
    Args:
        context: Context description for the error
        show_to_user: Whether to show error to user
        log_level: Logging level for the error
        reraise: Whether to reraise the exception after handling
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                func_context = context or f"{func.__module__}.{func.__name__}"
                error_handler.handle_error(e, func_context, show_to_user, log_level)
                if reraise:
                    raise
                return None
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    *args,
    context: str = None,
    default_return: Any = None,
    show_to_user: bool = True,
    **kwargs
) -> Any:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        context: Context description for errors
        default_return: Value to return if function fails
        show_to_user: Whether to show errors to user
        **kwargs: Keyword arguments for the function
    
    Returns:
        Function result or default_return if function fails
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        func_context = context or f"{func.__module__}.{func.__name__}"
        error_handler.handle_error(e, func_context, show_to_user)
        return default_return


def create_error_with_recovery(
    error_class: Type[TradingJournalError],
    message: str,
    error_code: str = None,
    recovery_suggestion: str = None
) -> TradingJournalError:
    """
    Create an error with recovery suggestion.
    
    Args:
        error_class: The error class to instantiate
        message: Error message
        error_code: Error code for categorization
        recovery_suggestion: Suggestion for recovering from the error
    
    Returns:
        Configured error instance
    """
    return error_class(
        message=message,
        error_code=error_code,
        recovery_suggestion=recovery_suggestion
    )