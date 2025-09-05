"""
Data refresh utilities for managing data synchronization and caching.
"""

import streamlit as st
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.utils.state_management import get_state_manager, get_loading_manager
from app.utils.notifications import get_notification_manager, NotificationContext

logger = logging.getLogger(__name__)


@dataclass
class RefreshConfig:
    """Configuration for data refresh operations."""
    operation_name: str
    refresh_function: Callable[[], Any]
    cache_key: str
    cache_ttl: timedelta = timedelta(minutes=5)
    loading_message: str = "Refreshing data..."
    success_message: str = "Data refreshed successfully"
    error_message: str = "Failed to refresh data"
    auto_refresh: bool = False
    auto_refresh_interval: timedelta = timedelta(minutes=30)


class DataRefreshManager:
    """Manages data refresh operations with caching and loading states."""
    
    def __init__(self):
        """Initialize data refresh manager."""
        self.state_manager = get_state_manager()
        self.loading_manager = get_loading_manager()
        self.notification_manager = get_notification_manager()
        self.refresh_configs: Dict[str, RefreshConfig] = {}
    
    def register_refresh_operation(self, config: RefreshConfig) -> None:
        """
        Register a data refresh operation.
        
        Args:
            config: Refresh configuration
        """
        self.refresh_configs[config.operation_name] = config
        logger.debug(f"Registered refresh operation: {config.operation_name}")
    
    def refresh_data(self, operation_name: str, force: bool = False) -> Any:
        """
        Refresh data for a specific operation.
        
        Args:
            operation_name: Name of the operation to refresh
            force: Force refresh even if cached data is valid
            
        Returns:
            Refreshed data
            
        Raises:
            ValueError: If operation not registered
            Exception: If refresh fails
        """
        if operation_name not in self.refresh_configs:
            raise ValueError(f"Refresh operation '{operation_name}' not registered")
        
        config = self.refresh_configs[operation_name]
        
        # Check if we should use cached data
        if not force and not self._should_refresh(config):
            cached_data = self.state_manager.get(config.cache_key)
            if cached_data is not None:
                logger.debug(f"Using cached data for {operation_name}")
                return cached_data
        
        # Perform refresh
        try:
            self.loading_manager.set_loading(
                operation_name, True, config.loading_message
            )
            
            logger.info(f"Refreshing data for {operation_name}")
            data = config.refresh_function()
            
            # Cache the data
            self.state_manager.set(config.cache_key, data, config.cache_ttl)
            
            # Update last refresh time
            self._update_last_refresh_time(operation_name)
            
            self.notification_manager.success(config.success_message)
            logger.info(f"Successfully refreshed data for {operation_name}")
            
            return data
            
        except Exception as e:
            error_msg = f"{config.error_message}: {e}"
            self.notification_manager.error(error_msg)
            logger.error(f"Failed to refresh data for {operation_name}: {e}")
            raise
        
        finally:
            self.loading_manager.clear_loading(operation_name)
    
    def refresh_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Refresh data for all registered operations.
        
        Args:
            force: Force refresh even if cached data is valid
            
        Returns:
            Dictionary mapping operation names to refreshed data
        """
        results = {}
        errors = []
        
        with NotificationContext("Refresh all data"):
            for operation_name in self.refresh_configs:
                try:
                    results[operation_name] = self.refresh_data(operation_name, force)
                except Exception as e:
                    errors.append(f"{operation_name}: {e}")
                    logger.error(f"Failed to refresh {operation_name}: {e}")
            
            if errors:
                error_summary = f"Some operations failed: {'; '.join(errors)}"
                self.notification_manager.warning(error_summary)
        
        return results
    
    def get_cached_data(self, operation_name: str) -> Any:
        """
        Get cached data for an operation without refreshing.
        
        Args:
            operation_name: Name of the operation
            
        Returns:
            Cached data or None if not found
        """
        if operation_name not in self.refresh_configs:
            return None
        
        config = self.refresh_configs[operation_name]
        return self.state_manager.get(config.cache_key)
    
    def invalidate_cache(self, operation_name: str) -> None:
        """
        Invalidate cached data for an operation.
        
        Args:
            operation_name: Name of the operation
        """
        if operation_name not in self.refresh_configs:
            return
        
        config = self.refresh_configs[operation_name]
        self.state_manager.invalidate(config.cache_key)
        logger.debug(f"Invalidated cache for {operation_name}")
    
    def invalidate_all_caches(self) -> None:
        """Invalidate all cached data."""
        for operation_name in self.refresh_configs:
            self.invalidate_cache(operation_name)
        
        logger.debug("Invalidated all caches")
    
    def get_refresh_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get refresh status for all operations.
        
        Returns:
            Dictionary with refresh status information
        """
        status = {}
        
        for operation_name, config in self.refresh_configs.items():
            last_refresh = self._get_last_refresh_time(operation_name)
            cached_data = self.get_cached_data(operation_name)
            is_loading = self.loading_manager.is_loading(operation_name)
            
            status[operation_name] = {
                'last_refresh': last_refresh.isoformat() if last_refresh else None,
                'has_cached_data': cached_data is not None,
                'is_loading': is_loading,
                'cache_ttl_minutes': config.cache_ttl.total_seconds() / 60,
                'auto_refresh': config.auto_refresh,
                'needs_refresh': self._should_refresh(config)
            }
        
        return status
    
    def check_auto_refresh(self) -> None:
        """Check and perform auto-refresh for operations that need it."""
        for operation_name, config in self.refresh_configs.items():
            if config.auto_refresh and self._should_auto_refresh(config):
                try:
                    logger.info(f"Auto-refreshing {operation_name}")
                    self.refresh_data(operation_name)
                except Exception as e:
                    logger.error(f"Auto-refresh failed for {operation_name}: {e}")
    
    def render_refresh_controls(self) -> None:
        """Render refresh controls in the UI."""
        st.subheader("Data Refresh")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Refresh All", key="refresh_all_button"):
                self.refresh_all(force=True)
                st.rerun()
        
        with col2:
            if st.button("🗑️ Clear Cache", key="clear_cache_button"):
                self.invalidate_all_caches()
                self.notification_manager.info("All caches cleared")
                st.rerun()
        
        with col3:
            if st.button("📊 Refresh Status", key="refresh_status_button"):
                status = self.get_refresh_status()
                st.json(status)
        
        # Show individual operation controls
        if st.expander("Individual Operations"):
            for operation_name in self.refresh_configs:
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.write(operation_name.replace('_', ' ').title())
                
                with col2:
                    if st.button(f"Refresh", key=f"refresh_{operation_name}"):
                        self.refresh_data(operation_name, force=True)
                        st.rerun()
                
                with col3:
                    if st.button(f"Clear", key=f"clear_{operation_name}"):
                        self.invalidate_cache(operation_name)
                        st.rerun()
    
    def _should_refresh(self, config: RefreshConfig) -> bool:
        """Check if data should be refreshed based on cache TTL."""
        last_refresh = self._get_last_refresh_time(config.operation_name)
        
        if last_refresh is None:
            return True
        
        age = datetime.now() - last_refresh
        return age > config.cache_ttl
    
    def _should_auto_refresh(self, config: RefreshConfig) -> bool:
        """Check if data should be auto-refreshed."""
        if not config.auto_refresh:
            return False
        
        last_refresh = self._get_last_refresh_time(config.operation_name)
        
        if last_refresh is None:
            return True
        
        age = datetime.now() - last_refresh
        return age > config.auto_refresh_interval
    
    def _get_last_refresh_time(self, operation_name: str) -> Optional[datetime]:
        """Get last refresh time for an operation."""
        key = f"last_refresh_{operation_name}"
        return self.state_manager.get(key)
    
    def _update_last_refresh_time(self, operation_name: str) -> None:
        """Update last refresh time for an operation."""
        key = f"last_refresh_{operation_name}"
        self.state_manager.set(key, datetime.now())


def get_data_refresh_manager() -> DataRefreshManager:
    """Get or create global data refresh manager."""
    if 'data_refresh_manager' not in st.session_state:
        st.session_state.data_refresh_manager = DataRefreshManager()
    
    return st.session_state.data_refresh_manager


def register_refresh_operation(operation_name: str, refresh_function: Callable[[], Any],
                             cache_key: str, **kwargs) -> None:
    """
    Register a data refresh operation.
    
    Args:
        operation_name: Name of the operation
        refresh_function: Function to call for refresh
        cache_key: Key for caching data
        **kwargs: Additional configuration options
    """
    config = RefreshConfig(
        operation_name=operation_name,
        refresh_function=refresh_function,
        cache_key=cache_key,
        **kwargs
    )
    
    manager = get_data_refresh_manager()
    manager.register_refresh_operation(config)


def refresh_data(operation_name: str, force: bool = False) -> Any:
    """Refresh data for a specific operation."""
    manager = get_data_refresh_manager()
    return manager.refresh_data(operation_name, force)


def get_cached_data(operation_name: str) -> Any:
    """Get cached data for an operation."""
    manager = get_data_refresh_manager()
    return manager.get_cached_data(operation_name)


def invalidate_cache(operation_name: str) -> None:
    """Invalidate cache for an operation."""
    manager = get_data_refresh_manager()
    manager.invalidate_cache(operation_name)