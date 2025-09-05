"""
State management utilities for Streamlit session state.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

import streamlit as st

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheManager:
    """Manages data caching with TTL and invalidation."""

    def __init__(self, default_ttl_minutes: int = 5):
        """
        Initialize cache manager.

        Args:
            default_ttl_minutes: Default time-to-live for cached items in minutes
        """
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        self._cache_key_prefix = "cache_"

    def get_cache_key(self, key: str) -> str:
        """Get full cache key with prefix."""
        return f"{self._cache_key_prefix}{key}"

    def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """
        Set a cached value with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live, uses default if None
        """
        cache_key = self.get_cache_key(key)
        ttl = ttl or self.default_ttl

        cache_data = {"value": value, "timestamp": datetime.now(), "ttl": ttl}

        st.session_state[cache_key] = cache_data
        logger.debug(f"Cached value for key '{key}' with TTL {ttl}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a cached value if it exists and hasn't expired.

        Args:
            key: Cache key
            default: Default value if not found or expired

        Returns:
            Cached value or default
        """
        cache_key = self.get_cache_key(key)

        if cache_key not in st.session_state:
            return default

        cache_data = st.session_state[cache_key]

        # Check if expired
        if self._is_expired(cache_data):
            self.invalidate(key)
            return default

        logger.debug(f"Retrieved cached value for key '{key}'")
        return cache_data["value"]

    def invalidate(self, key: str) -> None:
        """
        Invalidate a cached value.

        Args:
            key: Cache key to invalidate
        """
        cache_key = self.get_cache_key(key)
        if cache_key in st.session_state:
            del st.session_state[cache_key]
            logger.debug(f"Invalidated cache for key '{key}'")

    def clear_all(self) -> None:
        """Clear all cached values."""
        keys_to_remove = [
            key
            for key in st.session_state.keys()
            if key.startswith(self._cache_key_prefix)
        ]

        for key in keys_to_remove:
            del st.session_state[key]

        logger.debug(f"Cleared {len(keys_to_remove)} cached items")

    def get_cache_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all cached items.

        Returns:
            Dictionary with cache information
        """
        cache_info = {}

        for key, value in st.session_state.items():
            if key.startswith(self._cache_key_prefix):
                original_key = key[len(self._cache_key_prefix) :]
                cache_info[original_key] = {
                    "timestamp": value["timestamp"],
                    "ttl": value["ttl"],
                    "expired": self._is_expired(value),
                    "size_bytes": len(str(value["value"])),
                }

        return cache_info

    def _is_expired(self, cache_data: Dict[str, Any]) -> bool:
        """Check if cache data has expired."""
        age = datetime.now() - cache_data["timestamp"]
        return age > cache_data["ttl"]


class StateManager:
    """Manages application state with persistence and validation."""

    def __init__(self):
        """Initialize state manager."""
        self.cache_manager = CacheManager()

    def get_or_create(
        self, key: str, factory: Callable[[], T], cache_ttl: Optional[timedelta] = None
    ) -> T:
        """
        Get state value or create it using factory function.

        Args:
            key: State key
            factory: Function to create initial value
            cache_ttl: Cache time-to-live

        Returns:
            State value
        """
        # Try cache first
        cached_value = self.cache_manager.get(key)
        if cached_value is not None:
            return cached_value

        # Try session state
        if key in st.session_state:
            value = st.session_state[key]
            # Cache the value
            self.cache_manager.set(key, value, cache_ttl)
            return value

        # Create new value
        value = factory()
        st.session_state[key] = value
        self.cache_manager.set(key, value, cache_ttl)

        logger.debug(f"Created new state value for key '{key}'")
        return value

    def set(self, key: str, value: T, cache_ttl: Optional[timedelta] = None) -> None:
        """
        Set state value with caching.

        Args:
            key: State key
            value: Value to set
            cache_ttl: Cache time-to-live
        """
        st.session_state[key] = value
        self.cache_manager.set(key, value, cache_ttl)
        logger.debug(f"Set state value for key '{key}'")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get state value with cache fallback.

        Args:
            key: State key
            default: Default value if not found

        Returns:
            State value or default
        """
        # Try cache first
        cached_value = self.cache_manager.get(key)
        if cached_value is not None:
            return cached_value

        # Try session state
        value = st.session_state.get(key, default)

        # Cache if found
        if value != default:
            self.cache_manager.set(key, value)

        return value

    def invalidate(self, key: str) -> None:
        """
        Invalidate state value and cache.

        Args:
            key: State key to invalidate
        """
        if key in st.session_state:
            del st.session_state[key]

        self.cache_manager.invalidate(key)
        logger.debug(f"Invalidated state for key '{key}'")

    def clear_cache(self) -> None:
        """Clear all cached state values."""
        self.cache_manager.clear_all()

    def get_state_info(self) -> Dict[str, Any]:
        """
        Get information about current state.

        Returns:
            Dictionary with state information
        """
        return {
            "session_keys": list(st.session_state.keys()),
            "cache_info": self.cache_manager.get_cache_info(),
            "total_session_items": len(st.session_state),
            "total_cached_items": len(self.cache_manager.get_cache_info()),
        }


class LoadingStateManager:
    """Manages loading states for long-running operations."""

    def __init__(self, state_manager: StateManager):
        """
        Initialize loading state manager.

        Args:
            state_manager: StateManager instance
        """
        self.state_manager = state_manager
        self._loading_key_prefix = "loading_"

    def set_loading(
        self, operation: str, is_loading: bool, message: Optional[str] = None
    ) -> None:
        """
        Set loading state for an operation.

        Args:
            operation: Operation name
            is_loading: Whether operation is loading
            message: Optional loading message
        """
        key = f"{self._loading_key_prefix}{operation}"

        loading_data = {
            "is_loading": is_loading,
            "message": message,
            "timestamp": datetime.now(),
        }

        self.state_manager.set(key, loading_data)

    def is_loading(self, operation: str) -> bool:
        """
        Check if operation is currently loading.

        Args:
            operation: Operation name

        Returns:
            True if loading, False otherwise
        """
        key = f"{self._loading_key_prefix}{operation}"
        loading_data = self.state_manager.get(key, {})
        return loading_data.get("is_loading", False)

    def get_loading_message(self, operation: str) -> Optional[str]:
        """
        Get loading message for operation.

        Args:
            operation: Operation name

        Returns:
            Loading message or None
        """
        key = f"{self._loading_key_prefix}{operation}"
        loading_data = self.state_manager.get(key, {})
        return loading_data.get("message")

    def clear_loading(self, operation: str) -> None:
        """
        Clear loading state for operation.

        Args:
            operation: Operation name
        """
        self.set_loading(operation, False)

    def get_all_loading_operations(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all currently loading operations.

        Returns:
            Dictionary of loading operations
        """
        loading_ops = {}

        for key in st.session_state.keys():
            if key.startswith(self._loading_key_prefix):
                # Skip the loading_manager key itself
                if key == "loading_manager":
                    continue

                operation = key[len(self._loading_key_prefix) :]
                loading_data = st.session_state[key]

                # Ensure loading_data is a dictionary before calling .get()
                if isinstance(loading_data, dict) and loading_data.get(
                    "is_loading", False
                ):
                    loading_ops[operation] = loading_data

        return loading_ops


def with_loading_state(operation_name: str, loading_message: str = "Loading..."):
    """
    Decorator to automatically manage loading state for functions.

    Args:
        operation_name: Name of the operation
        loading_message: Message to display while loading
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get state manager from session state
            if "state_manager" not in st.session_state:
                st.session_state.state_manager = StateManager()

            state_manager = st.session_state.state_manager
            loading_manager = LoadingStateManager(state_manager)

            try:
                # Set loading state
                loading_manager.set_loading(operation_name, True, loading_message)

                # Execute function
                result = func(*args, **kwargs)

                return result

            finally:
                # Clear loading state
                loading_manager.clear_loading(operation_name)

        return wrapper

    return decorator


def get_state_manager() -> StateManager:
    """Get or create global state manager."""
    if "state_manager" not in st.session_state:
        st.session_state.state_manager = StateManager()

    return st.session_state.state_manager


def get_loading_manager() -> LoadingStateManager:
    """Get or create global loading state manager."""
    state_manager = get_state_manager()

    if "loading_manager" not in st.session_state:
        st.session_state.loading_manager = LoadingStateManager(state_manager)

    return st.session_state.loading_manager


def create_state_hash(data: Any) -> str:
    """
    Create a hash for state data to detect changes.

    Args:
        data: Data to hash

    Returns:
        Hash string
    """
    try:
        # Convert to JSON string for consistent hashing
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()
    except Exception:
        # Fallback to string representation
        return hashlib.md5(str(data).encode()).hexdigest()


def detect_state_change(key: str, new_data: Any) -> bool:
    """
    Detect if state data has changed.

    Args:
        key: State key
        new_data: New data to compare

    Returns:
        True if data has changed, False otherwise
    """
    hash_key = f"{key}_hash"
    new_hash = create_state_hash(new_data)

    if hash_key not in st.session_state:
        st.session_state[hash_key] = new_hash
        return True

    old_hash = st.session_state[hash_key]

    if old_hash != new_hash:
        st.session_state[hash_key] = new_hash
        return True

    return False
