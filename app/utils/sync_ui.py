"""
UI components for data synchronization and refresh operations.
"""

import streamlit as st
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from .state_management import get_state_manager, get_loading_manager
from .notifications import get_notification_manager
from ..services.exchange_sync_service import ExchangeSyncService, SyncResult, SyncStatus

logger = logging.getLogger(__name__)


@dataclass
class SyncStatusInfo:
    """Information about sync status for display."""
    exchange_name: str
    last_sync: Optional[datetime]
    connection_status: str
    is_syncing: bool
    sync_message: Optional[str]
    positions_count: int
    partial_positions_count: int


class SyncUIManager:
    """Manages sync-related UI components."""
    
    def __init__(self):
        """Initialize sync UI manager."""
        self.state_manager = get_state_manager()
        self.loading_manager = get_loading_manager()
        self.notification_manager = get_notification_manager()
    
    def render_sync_status_card(self, exchange_name: str = None) -> None:
        """
        Render a sync status card showing current sync information.
        
        Args:
            exchange_name: Specific exchange to show, or None for all
        """
        st.subheader("📊 Sync Status")
        
        try:
            # Get app state
            from ..main import get_app_state
            app_state = get_app_state()
            
            if not app_state.config_service:
                st.warning("Configuration service not available")
                return
            
            # Get exchange configurations
            if exchange_name:
                exchange_configs = {exchange_name: app_state.config_service.get_exchange_config(exchange_name)}
                exchange_configs = {k: v for k, v in exchange_configs.items() if v is not None}
            else:
                exchange_configs = app_state.config_service.get_all_exchange_configs()
            
            if not exchange_configs:
                st.info("No exchanges configured")
                return
            
            # Create sync service to get position counts
            sync_service = ExchangeSyncService(app_state.config_service)
            
            # Display status for each exchange
            for name, config in exchange_configs.items():
                if not config.is_active:
                    continue
                
                # Get sync status info
                status_info = self._get_sync_status_info(name, config, sync_service)
                
                # Render status card
                self._render_exchange_status_card(status_info)
        
        except Exception as e:
            logger.error(f"Error rendering sync status: {e}")
            st.error(f"Error loading sync status: {e}")
    
    def render_sync_controls(self, exchange_name: str = None, show_advanced: bool = True) -> None:
        """
        Render sync control buttons.
        
        Args:
            exchange_name: Specific exchange to control, or None for all
            show_advanced: Whether to show advanced controls
        """
        st.subheader("🔄 Sync Controls")
        
        # Main sync buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Refresh Data", key=f"refresh_data_{exchange_name or 'all'}", 
                        use_container_width=True):
                self._refresh_data()
                st.rerun()
        
        with col2:
            if st.button("🔗 Sync Exchange", key=f"sync_exchange_{exchange_name or 'all'}", 
                        use_container_width=True):
                self._sync_exchange_data(exchange_name)
                st.rerun()
        
        with col3:
            if st.button("⚡ Force Sync", key=f"force_sync_{exchange_name or 'all'}", 
                        use_container_width=True):
                self._force_full_sync(exchange_name)
                st.rerun()
        
        if show_advanced:
            # Advanced controls in expander
            with st.expander("Advanced Sync Options"):
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🔄 Partial Positions", key=f"partial_sync_{exchange_name or 'all'}", 
                                use_container_width=True):
                        self._sync_partial_positions(exchange_name)
                        st.rerun()
                
                with col2:
                    if st.button("🗑️ Clear Cache", key=f"clear_cache_{exchange_name or 'all'}", 
                                use_container_width=True):
                        self._clear_caches()
                        st.rerun()
    
    def render_sync_progress(self) -> None:
        """Render sync progress indicators."""
        loading_ops = self.loading_manager.get_all_loading_operations()
        
        if not loading_ops:
            return
        
        st.subheader("⏳ Sync Progress")
        
        for operation, data in loading_ops.items():
            message = data.get('message', f"Processing {operation}...")
            timestamp = data.get('timestamp')
            
            # Calculate elapsed time
            if timestamp:
                elapsed = datetime.now() - timestamp
                elapsed_str = f" ({elapsed.seconds}s)"
            else:
                elapsed_str = ""
            
            # Show progress bar (indeterminate)
            st.info(f"🔄 {message}{elapsed_str}")
            st.progress(0.5)  # Indeterminate progress
    
    def render_sync_history(self, limit: int = 10) -> None:
        """
        Render recent sync history.
        
        Args:
            limit: Maximum number of history entries to show
        """
        st.subheader("📜 Recent Sync History")
        
        # Get sync history from state
        sync_history = self.state_manager.get("sync_history", [])
        
        if not sync_history:
            st.info("No sync history available")
            return
        
        # Show recent entries
        recent_history = sync_history[-limit:]
        
        for entry in reversed(recent_history):
            timestamp = entry.get('timestamp', 'Unknown time')
            operation = entry.get('operation', 'Unknown operation')
            status = entry.get('status', 'unknown')
            details = entry.get('details', '')
            
            # Choose icon based on status
            if status == 'success':
                icon = "✅"
                color = "success"
            elif status == 'error':
                icon = "❌"
                color = "error"
            elif status == 'warning':
                icon = "⚠️"
                color = "warning"
            else:
                icon = "ℹ️"
                color = "info"
            
            # Format timestamp
            if isinstance(timestamp, datetime):
                time_str = timestamp.strftime('%H:%M:%S')
            else:
                time_str = str(timestamp)
            
            # Display entry
            with st.container():
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.caption(time_str)
                with col2:
                    if color == "success":
                        st.success(f"{icon} {operation}: {details}")
                    elif color == "error":
                        st.error(f"{icon} {operation}: {details}")
                    elif color == "warning":
                        st.warning(f"{icon} {operation}: {details}")
                    else:
                        st.info(f"{icon} {operation}: {details}")
    
    def _get_sync_status_info(self, exchange_name: str, config: Any, 
                             sync_service: ExchangeSyncService) -> SyncStatusInfo:
        """Get sync status information for an exchange."""
        # Check if currently syncing
        is_syncing = (
            self.loading_manager.is_loading(f"exchange_sync_{exchange_name}") or
            self.loading_manager.is_loading("exchange_sync") or
            self.loading_manager.is_loading("full_sync")
        )
        
        sync_message = None
        if is_syncing:
            sync_message = (
                self.loading_manager.get_loading_message(f"exchange_sync_{exchange_name}") or
                self.loading_manager.get_loading_message("exchange_sync") or
                self.loading_manager.get_loading_message("full_sync")
            )
        
        # Get position counts
        try:
            positions = sync_service.get_positions(exchange_name)
            positions_count = len(positions.get(exchange_name, []))
            
            partial_positions = sync_service.get_partial_positions(exchange_name)
            partial_positions_count = len(partial_positions.get(exchange_name, []))
        except Exception as e:
            logger.error(f"Error getting position counts for {exchange_name}: {e}")
            positions_count = 0
            partial_positions_count = 0
        
        return SyncStatusInfo(
            exchange_name=exchange_name,
            last_sync=config.last_sync,
            connection_status=config.connection_status.value,
            is_syncing=is_syncing,
            sync_message=sync_message,
            positions_count=positions_count,
            partial_positions_count=partial_positions_count
        )
    
    def _render_exchange_status_card(self, status_info: SyncStatusInfo) -> None:
        """Render status card for a single exchange."""
        with st.container():
            # Header with exchange name and status
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.subheader(f"📈 {status_info.exchange_name.title()}")
            
            with col2:
                # Connection status indicator
                status_colors = {
                    "connected": "🟢",
                    "error": "🔴",
                    "testing": "🟡",
                    "unknown": "⚪"
                }
                status_icon = status_colors.get(status_info.connection_status.lower(), "⚪")
                st.write(f"{status_icon} {status_info.connection_status.title()}")
            
            with col3:
                # Sync status
                if status_info.is_syncing:
                    st.write("🔄 Syncing...")
                elif status_info.last_sync:
                    time_ago = datetime.now() - status_info.last_sync
                    if time_ago.total_seconds() < 60:
                        st.write("✅ Just synced")
                    elif time_ago.total_seconds() < 3600:
                        minutes = int(time_ago.total_seconds() / 60)
                        st.write(f"✅ {minutes}m ago")
                    else:
                        hours = int(time_ago.total_seconds() / 3600)
                        st.write(f"⏰ {hours}h ago")
                else:
                    st.write("❓ Never synced")
            
            # Details row
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Positions", status_info.positions_count)
            
            with col2:
                st.metric("Partial Positions", status_info.partial_positions_count)
            
            with col3:
                if status_info.last_sync:
                    last_sync_str = status_info.last_sync.strftime('%Y-%m-%d %H:%M')
                    st.metric("Last Sync", last_sync_str)
                else:
                    st.metric("Last Sync", "Never")
            
            # Show sync message if syncing
            if status_info.is_syncing and status_info.sync_message:
                st.info(f"⏳ {status_info.sync_message}")
            
            st.divider()
    
    def _refresh_data(self) -> None:
        """Refresh application data."""
        try:
            from ..main import get_app_state
            app_state = get_app_state()
            app_state.refresh_data()
            self._add_sync_history("Data Refresh", "success", "Application data refreshed")
        except Exception as e:
            logger.error(f"Data refresh failed: {e}")
            self.notification_manager.error(f"Data refresh failed: {e}")
            self._add_sync_history("Data Refresh", "error", str(e))
    
    def _sync_exchange_data(self, exchange_name: str = None) -> None:
        """Sync exchange data."""
        try:
            from ..main import get_app_state
            app_state = get_app_state()
            
            if not app_state.config_service:
                raise ValueError("Configuration service not available")
            
            operation_key = f"exchange_sync_{exchange_name}" if exchange_name else "exchange_sync"
            self.loading_manager.set_loading(operation_key, True, "Syncing exchange data...")
            
            sync_service = ExchangeSyncService(app_state.config_service)
            
            if exchange_name:
                result = sync_service.sync_exchange(exchange_name)
                results = {exchange_name: result}
            else:
                results = sync_service.sync_all_exchanges()
            
            # Process results
            successful_syncs = []
            failed_syncs = []
            
            for name, result in results.items():
                if result.is_successful():
                    successful_syncs.append(f"{name}: {result.positions_added} added, {result.positions_updated} updated")
                else:
                    failed_syncs.append(f"{name}: {', '.join(result.errors)}")
            
            if successful_syncs:
                message = "Exchange sync completed:\n" + "\n".join(successful_syncs)
                self.notification_manager.success(message)
                self._add_sync_history("Exchange Sync", "success", message)
            
            if failed_syncs:
                message = "Some exchanges failed to sync:\n" + "\n".join(failed_syncs)
                self.notification_manager.warning(message)
                self._add_sync_history("Exchange Sync", "warning", message)
        
        except Exception as e:
            logger.error(f"Exchange sync failed: {e}")
            self.notification_manager.error(f"Exchange sync failed: {e}")
            self._add_sync_history("Exchange Sync", "error", str(e))
        
        finally:
            operation_key = f"exchange_sync_{exchange_name}" if exchange_name else "exchange_sync"
            self.loading_manager.clear_loading(operation_key)
    
    def _force_full_sync(self, exchange_name: str = None) -> None:
        """Force full sync of exchange data."""
        try:
            from ..main import get_app_state
            app_state = get_app_state()
            
            if not app_state.config_service:
                raise ValueError("Configuration service not available")
            
            self.loading_manager.set_loading("full_sync", True, "Performing full sync...")
            
            sync_service = ExchangeSyncService(app_state.config_service)
            
            if exchange_name:
                result = sync_service.sync_exchange(exchange_name, force_full_sync=True)
                total_added = result.positions_added
                total_updated = result.positions_updated
            else:
                results = sync_service.sync_all_exchanges(force_full_sync=True)
                total_added = sum(r.positions_added for r in results.values())
                total_updated = sum(r.positions_updated for r in results.values())
            
            message = f"Full sync completed: {total_added} positions added, {total_updated} updated"
            self.notification_manager.success(message)
            self._add_sync_history("Full Sync", "success", message)
            
            # Clear caches
            app_state.state_manager.clear_cache()
        
        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            self.notification_manager.error(f"Full sync failed: {e}")
            self._add_sync_history("Full Sync", "error", str(e))
        
        finally:
            self.loading_manager.clear_loading("full_sync")
    
    def _sync_partial_positions(self, exchange_name: str = None) -> None:
        """Sync partial positions."""
        try:
            from ..main import get_app_state
            app_state = get_app_state()
            
            if not app_state.config_service:
                raise ValueError("Configuration service not available")
            
            self.loading_manager.set_loading("partial_sync", True, "Syncing partial positions...")
            
            sync_service = ExchangeSyncService(app_state.config_service)
            
            if exchange_name:
                result = sync_service.sync_partial_positions(exchange_name)
                total_updated = result.positions_updated
            else:
                active_exchanges = app_state.config_service.get_active_exchanges()
                total_updated = 0
                for exchange_config in active_exchanges:
                    result = sync_service.sync_partial_positions(exchange_config.name)
                    total_updated += result.positions_updated
            
            message = f"Partial positions sync completed: {total_updated} positions updated"
            self.notification_manager.success(message)
            self._add_sync_history("Partial Sync", "success", message)
        
        except Exception as e:
            logger.error(f"Partial sync failed: {e}")
            self.notification_manager.error(f"Partial sync failed: {e}")
            self._add_sync_history("Partial Sync", "error", str(e))
        
        finally:
            self.loading_manager.clear_loading("partial_sync")
    
    def _clear_caches(self) -> None:
        """Clear all caches."""
        try:
            from ..main import get_app_state
            app_state = get_app_state()
            
            # Clear various caches
            app_state.state_manager.clear_cache()
            
            if app_state.data_service:
                app_state.data_service.clear_cache()
            
            app_state.data_refresh_manager.invalidate_all_caches()
            
            self.notification_manager.info("All caches cleared")
            self._add_sync_history("Clear Cache", "success", "All caches cleared")
        
        except Exception as e:
            logger.error(f"Failed to clear caches: {e}")
            self.notification_manager.error(f"Failed to clear caches: {e}")
            self._add_sync_history("Clear Cache", "error", str(e))
    
    def _add_sync_history(self, operation: str, status: str, details: str) -> None:
        """Add entry to sync history."""
        try:
            sync_history = self.state_manager.get("sync_history", [])
            
            entry = {
                'timestamp': datetime.now(),
                'operation': operation,
                'status': status,
                'details': details
            }
            
            sync_history.append(entry)
            
            # Keep only last 50 entries
            if len(sync_history) > 50:
                sync_history = sync_history[-50:]
            
            self.state_manager.set("sync_history", sync_history)
        
        except Exception as e:
            logger.error(f"Failed to add sync history: {e}")


def get_sync_ui_manager() -> SyncUIManager:
    """Get or create global sync UI manager."""
    if 'sync_ui_manager' not in st.session_state:
        st.session_state.sync_ui_manager = SyncUIManager()
    
    return st.session_state.sync_ui_manager


def render_sync_status_card(exchange_name: str = None) -> None:
    """Render sync status card."""
    manager = get_sync_ui_manager()
    manager.render_sync_status_card(exchange_name)


def render_sync_controls(exchange_name: str = None, show_advanced: bool = True) -> None:
    """Render sync controls."""
    manager = get_sync_ui_manager()
    manager.render_sync_controls(exchange_name, show_advanced)


def render_sync_progress() -> None:
    """Render sync progress indicators."""
    manager = get_sync_ui_manager()
    manager.render_sync_progress()


def render_sync_history(limit: int = 10) -> None:
    """Render sync history."""
    manager = get_sync_ui_manager()
    manager.render_sync_history(limit)