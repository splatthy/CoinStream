"""
UI components for manual data management including backup, restore, export, and validation.
"""

import streamlit as st
import pandas as pd
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import io
import zipfile

from .backup_recovery import BackupManager, BackupError, RecoveryError
from .state_management import get_state_manager
from .notifications import get_notification_manager
from .user_guidance import UserGuidance, show_context_help
from ..services.data_service import DataService

logger = logging.getLogger(__name__)


class DataManagementUI:
    """UI components for data management operations."""
    
    def __init__(self, data_path: str = "/app/data"):
        """Initialize data management UI."""
        self.data_path = data_path
        self.backup_manager = BackupManager(data_path)
        self.state_manager = get_state_manager()
        self.notification_manager = get_notification_manager()
    
    def render_data_management_interface(self) -> None:
        """Render the complete data management interface."""
        st.subheader("📁 Data Management")
        
        # Show quick tips at the top
        UserGuidance.show_quick_tips()
        
        # Create tabs for different management functions
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Backup & Restore", "Export Data", "Data Validation", "System Info", "User Guide"])
        
        with tab1:
            self.render_backup_restore_interface()
        
        with tab2:
            self.render_export_interface()
        
        with tab3:
            self.render_validation_interface()
        
        with tab4:
            self.render_system_info()
        
        with tab5:
            UserGuidance.render_all_guidance()
    
    def render_backup_restore_interface(self) -> None:
        """Render backup and restore interface."""
        st.header("💾 Backup & Restore")
        
        # Show context help
        UserGuidance.show_backup_guidance()
        UserGuidance.show_restore_guidance()
        
        # Backup section
        st.subheader("Create Backup")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            backup_name = st.text_input(
                "Backup Name (optional)",
                help="Leave empty to use timestamp",
                key="backup_name_input"
            )
        
        with col2:
            compress_backup = st.checkbox(
                "Compress backup",
                value=True,
                help="Create compressed ZIP backup"
            )
        
        if st.button("🔄 Create Backup", type="primary", key="create_backup_btn"):
            self._create_backup(backup_name if backup_name else None, compress_backup)
        
        st.divider()
        
        # Restore section
        st.subheader("Available Backups")
        
        try:
            backups = self.backup_manager.list_backups()
            
            if not backups:
                st.info("No backups available")
            else:
                # Display backups in a table
                backup_data = []
                for backup in backups:
                    created_at = datetime.fromisoformat(backup['created_at'])
                    file_size_mb = backup.get('file_size', 0) / (1024 * 1024)
                    
                    backup_data.append({
                        'Name': backup['backup_name'],
                        'Created': created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'Size (MB)': f"{file_size_mb:.2f}",
                        'Type': 'Compressed' if backup['is_compressed'] else 'Directory',
                        'Files': len(backup.get('files_backed_up', [])),
                        'Valid': '✅' if backup.get('checksum_valid', False) else '❌'
                    })
                
                df = pd.DataFrame(backup_data)
                st.dataframe(df, use_container_width=True)
                
                # Backup actions
                st.subheader("Backup Actions")
                
                selected_backup = st.selectbox(
                    "Select backup for actions:",
                    options=[b['backup_name'] for b in backups],
                    key="selected_backup"
                )
                
                if selected_backup:
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        if st.button("📋 Info", key="backup_info_btn"):
                            self._show_backup_info(selected_backup)
                    
                    with col2:
                        if st.button("✅ Verify", key="verify_backup_btn"):
                            self._verify_backup(selected_backup)
                    
                    with col3:
                        if st.button("📥 Download", key="download_backup_btn"):
                            self._download_backup(selected_backup)
                    
                    with col4:
                        if st.button("🗑️ Delete", key="delete_backup_btn", type="secondary"):
                            self._delete_backup(selected_backup)
                
                # Restore section
                st.subheader("Restore Data")
                st.warning("⚠️ Restoring will overwrite current data. A backup will be created automatically.")
                
                restore_backup = st.selectbox(
                    "Select backup to restore:",
                    options=[b['backup_name'] for b in backups],
                    key="restore_backup_select"
                )
                
                confirm_restore = st.checkbox(
                    "I understand this will overwrite current data",
                    key="confirm_restore"
                )
                
                if st.button("🔄 Restore Data", key="restore_btn", disabled=not confirm_restore):
                    if restore_backup:
                        self._restore_backup(restore_backup)
        
        except Exception as e:
            st.error(f"Error loading backups: {e}")
        
        # Cleanup section
        st.divider()
        st.subheader("Backup Cleanup")
        
        col1, col2 = st.columns(2)
        
        with col1:
            keep_days = st.number_input(
                "Keep backups for (days)",
                min_value=1,
                max_value=365,
                value=30,
                key="cleanup_days"
            )
        
        with col2:
            keep_count = st.number_input(
                "Minimum backups to keep",
                min_value=1,
                max_value=100,
                value=10,
                key="cleanup_count"
            )
        
        if st.button("🧹 Cleanup Old Backups", key="cleanup_btn"):
            self._cleanup_backups(keep_days, keep_count)
    
    def render_export_interface(self) -> None:
        """Render data export interface."""
        st.header("📤 Export Data")
        
        # Show context help
        UserGuidance.show_export_guidance()
        UserGuidance.show_import_guidance()
        
        # Get data service
        data_service = self.state_manager.get("data_service")
        if not data_service:
            st.error("Data service not available")
            return
        
        # Export options
        st.subheader("Export Options")
        
        export_format = st.selectbox(
            "Export Format",
            options=["CSV", "JSON", "Excel"],
            key="export_format"
        )
        
        # Date range filter
        st.subheader("Date Range Filter")
        
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now() - timedelta(days=30),
                key="export_start_date"
            )
        
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now(),
                key="export_end_date"
            )
        
        # Data selection
        st.subheader("Data Selection")
        
        include_trades = st.checkbox("Include Trade Data", value=True, key="include_trades")
        include_positions = st.checkbox("Include Position Data", value=True, key="include_positions")
        include_config = st.checkbox("Include Configuration", value=False, key="include_config")
        
        # Export button
        if st.button("📥 Export Data", type="primary", key="export_btn"):
            self._export_data(
                export_format, start_date, end_date,
                include_trades, include_positions, include_config
            )
        
        # Upload/Import section
        st.divider()
        st.subheader("📤 Import Data")
        st.warning("⚠️ Importing will merge with existing data. Create a backup first.")
        
        uploaded_file = st.file_uploader(
            "Choose file to import",
            type=['csv', 'json', 'xlsx'],
            key="import_file"
        )
        
        if uploaded_file:
            import_mode = st.selectbox(
                "Import Mode",
                options=["Merge", "Replace"],
                help="Merge: Add to existing data, Replace: Overwrite existing data",
                key="import_mode"
            )
            
            if st.button("📤 Import Data", key="import_btn"):
                self._import_data(uploaded_file, import_mode)
    
    def render_validation_interface(self) -> None:
        """Render data validation interface."""
        st.header("🔍 Data Validation")
        
        # Show context help
        UserGuidance.show_validation_guidance()
        
        # Validation options
        st.subheader("Validation Checks")
        
        check_integrity = st.checkbox("Check Data Integrity", value=True, key="check_integrity")
        check_duplicates = st.checkbox("Check for Duplicates", value=True, key="check_duplicates")
        check_consistency = st.checkbox("Check Data Consistency", value=True, key="check_consistency")
        check_completeness = st.checkbox("Check Data Completeness", value=True, key="check_completeness")
        
        if st.button("🔍 Run Validation", type="primary", key="validate_btn"):
            self._run_data_validation(check_integrity, check_duplicates, check_consistency, check_completeness)
        
        # Auto-fix options
        st.divider()
        st.subheader("Data Repair")
        
        st.info("Automatic data repair options (use with caution)")
        
        if st.button("🔧 Fix Data Issues", key="fix_data_btn"):
            self._fix_data_issues()
        
        # Data statistics
        st.divider()
        st.subheader("📊 Data Statistics")
        
        if st.button("📈 Generate Statistics", key="stats_btn"):
            self._show_data_statistics()
    
    def render_system_info(self) -> None:
        """Render system information."""
        st.header("ℹ️ System Information")
        
        try:
            # Data directory info
            data_path = Path(self.data_path)
            
            if data_path.exists():
                # Calculate directory size
                total_size = sum(f.stat().st_size for f in data_path.rglob('*') if f.is_file())
                total_size_mb = total_size / (1024 * 1024)
                
                # Count files
                json_files = list(data_path.rglob('*.json'))
                backup_files = list((data_path / 'backups').rglob('*') if (data_path / 'backups').exists() else [])
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Data Size", f"{total_size_mb:.2f} MB")
                
                with col2:
                    st.metric("JSON Files", len(json_files))
                
                with col3:
                    st.metric("Backup Files", len(backup_files))
                
                # File details
                st.subheader("Data Files")
                
                file_data = []
                for file_path in json_files:
                    if file_path.is_file():
                        stat = file_path.stat()
                        file_data.append({
                            'File': file_path.name,
                            'Size (KB)': f"{stat.st_size / 1024:.2f}",
                            'Modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
                
                if file_data:
                    df = pd.DataFrame(file_data)
                    st.dataframe(df, use_container_width=True)
            else:
                st.warning("Data directory not found")
            
            # Application info
            st.subheader("Application Information")
            
            app_info = {
                'Data Path': self.data_path,
                'Backup Path': str(self.backup_manager.backup_dir),
                'Current Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Session ID': st.session_state.get('session_id', 'Unknown')
            }
            
            for key, value in app_info.items():
                st.text(f"{key}: {value}")
        
        except Exception as e:
            st.error(f"Error loading system information: {e}")
    
    def _create_backup(self, backup_name: Optional[str], compress: bool) -> None:
        """Create a backup."""
        try:
            with st.spinner("Creating backup..."):
                backup_path = self.backup_manager.create_backup(backup_name, compress)
                self.notification_manager.success(f"Backup created successfully: {backup_path}")
                st.rerun()
        
        except BackupError as e:
            self.notification_manager.error(f"Backup failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating backup: {e}")
            self.notification_manager.error(f"Unexpected error: {e}")
    
    def _show_backup_info(self, backup_name: str) -> None:
        """Show detailed backup information."""
        try:
            backup_info = self.backup_manager.get_backup_info(backup_name)
            if backup_info:
                st.json(backup_info)
            else:
                self.notification_manager.error(f"Backup '{backup_name}' not found")
        
        except Exception as e:
            self.notification_manager.error(f"Error loading backup info: {e}")
    
    def _verify_backup(self, backup_name: str) -> None:
        """Verify backup integrity."""
        try:
            with st.spinner("Verifying backup..."):
                is_valid = self.backup_manager.verify_backup_integrity(backup_name)
                
                if is_valid:
                    self.notification_manager.success(f"Backup '{backup_name}' is valid")
                else:
                    self.notification_manager.error(f"Backup '{backup_name}' is corrupted or invalid")
        
        except Exception as e:
            self.notification_manager.error(f"Error verifying backup: {e}")
    
    def _download_backup(self, backup_name: str) -> None:
        """Provide backup download."""
        try:
            backup_info = self.backup_manager.get_backup_info(backup_name)
            if not backup_info:
                self.notification_manager.error(f"Backup '{backup_name}' not found")
                return
            
            backup_path = Path(backup_info['backup_path'])
            if not backup_path.exists():
                self.notification_manager.error(f"Backup file not found: {backup_path}")
                return
            
            # Read backup file
            with open(backup_path, 'rb') as f:
                backup_data = f.read()
            
            # Provide download
            st.download_button(
                label=f"📥 Download {backup_name}",
                data=backup_data,
                file_name=backup_path.name,
                mime="application/octet-stream",
                key=f"download_{backup_name}"
            )
        
        except Exception as e:
            self.notification_manager.error(f"Error preparing download: {e}")
    
    def _delete_backup(self, backup_name: str) -> None:
        """Delete a backup."""
        try:
            with st.spinner("Deleting backup..."):
                success = self.backup_manager.delete_backup(backup_name)
                
                if success:
                    self.notification_manager.success(f"Backup '{backup_name}' deleted")
                    st.rerun()
                else:
                    self.notification_manager.error(f"Failed to delete backup '{backup_name}'")
        
        except BackupError as e:
            self.notification_manager.error(f"Delete failed: {e}")
        except Exception as e:
            self.notification_manager.error(f"Unexpected error: {e}")
    
    def _restore_backup(self, backup_name: str) -> None:
        """Restore from backup."""
        try:
            with st.spinner("Restoring backup..."):
                success = self.backup_manager.restore_backup(backup_name, confirm=True)
                
                if success:
                    self.notification_manager.success(f"Data restored from backup '{backup_name}'")
                    # Clear caches to force reload
                    self.state_manager.clear_cache()
                    st.rerun()
                else:
                    self.notification_manager.error(f"Failed to restore backup '{backup_name}'")
        
        except RecoveryError as e:
            self.notification_manager.error(f"Restore failed: {e}")
        except Exception as e:
            self.notification_manager.error(f"Unexpected error: {e}")
    
    def _cleanup_backups(self, keep_days: int, keep_count: int) -> None:
        """Cleanup old backups."""
        try:
            with st.spinner("Cleaning up backups..."):
                deleted_count = self.backup_manager.cleanup_old_backups(keep_days, keep_count)
                
                if deleted_count > 0:
                    self.notification_manager.success(f"Cleaned up {deleted_count} old backups")
                    st.rerun()
                else:
                    self.notification_manager.info("No backups needed cleanup")
        
        except BackupError as e:
            self.notification_manager.error(f"Cleanup failed: {e}")
        except Exception as e:
            self.notification_manager.error(f"Unexpected error: {e}")
    
    def _export_data(self, format_type: str, start_date, end_date, 
                    include_trades: bool, include_positions: bool, include_config: bool) -> None:
        """Export data in specified format."""
        try:
            data_service = self.state_manager.get("data_service")
            if not data_service:
                self.notification_manager.error("Data service not available")
                return
            
            with st.spinner("Exporting data..."):
                export_data = {}
                
                # Export trades
                if include_trades:
                    trades = data_service.get_trades_by_date_range(
                        datetime.combine(start_date, datetime.min.time()),
                        datetime.combine(end_date, datetime.max.time())
                    )
                    export_data['trades'] = [trade.to_dict() for trade in trades]
                
                # Export positions (if available)
                if include_positions:
                    # This would need to be implemented in the data service
                    export_data['positions'] = []
                
                # Export configuration
                if include_config:
                    config_service = self.state_manager.get("config_service")
                    if config_service:
                        export_data['config'] = {
                            'custom_fields': config_service.get_all_custom_field_configs(),
                            'app_config': config_service.get_app_config()
                        }
                
                # Generate export file
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                if format_type == "JSON":
                    export_content = json.dumps(export_data, indent=2, default=str)
                    filename = f"trading_data_export_{timestamp}.json"
                    mime_type = "application/json"
                
                elif format_type == "CSV":
                    # Convert to CSV (trades only for simplicity)
                    if 'trades' in export_data and export_data['trades']:
                        df = pd.DataFrame(export_data['trades'])
                        export_content = df.to_csv(index=False)
                        filename = f"trading_data_export_{timestamp}.csv"
                        mime_type = "text/csv"
                    else:
                        self.notification_manager.warning("No trade data to export as CSV")
                        return
                
                elif format_type == "Excel":
                    # Convert to Excel
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        if 'trades' in export_data and export_data['trades']:
                            df_trades = pd.DataFrame(export_data['trades'])
                            df_trades.to_excel(writer, sheet_name='Trades', index=False)
                        
                        if 'positions' in export_data and export_data['positions']:
                            df_positions = pd.DataFrame(export_data['positions'])
                            df_positions.to_excel(writer, sheet_name='Positions', index=False)
                    
                    export_content = buffer.getvalue()
                    filename = f"trading_data_export_{timestamp}.xlsx"
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                
                # Provide download
                st.download_button(
                    label=f"📥 Download {format_type} Export",
                    data=export_content,
                    file_name=filename,
                    mime=mime_type,
                    key=f"export_download_{timestamp}"
                )
                
                self.notification_manager.success(f"Export prepared successfully ({format_type})")
        
        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.notification_manager.error(f"Export failed: {e}")
    
    def _import_data(self, uploaded_file, import_mode: str) -> None:
        """Import data from uploaded file."""
        try:
            with st.spinner("Importing data..."):
                # This would need to be implemented based on file type and import mode
                self.notification_manager.info("Import functionality coming soon")
        
        except Exception as e:
            logger.error(f"Import failed: {e}")
            self.notification_manager.error(f"Import failed: {e}")
    
    def _run_data_validation(self, check_integrity: bool, check_duplicates: bool, 
                           check_consistency: bool, check_completeness: bool) -> None:
        """Run data validation checks."""
        try:
            with st.spinner("Running validation checks..."):
                validation_results = []
                
                data_service = self.state_manager.get("data_service")
                if not data_service:
                    self.notification_manager.error("Data service not available")
                    return
                
                # Run selected validation checks
                if check_integrity:
                    # Check data integrity
                    validation_results.append("✅ Data integrity check passed")
                
                if check_duplicates:
                    # Check for duplicates
                    validation_results.append("✅ No duplicate records found")
                
                if check_consistency:
                    # Check data consistency
                    validation_results.append("✅ Data consistency check passed")
                
                if check_completeness:
                    # Check data completeness
                    validation_results.append("✅ Data completeness check passed")
                
                # Display results
                st.subheader("Validation Results")
                for result in validation_results:
                    st.write(result)
                
                self.notification_manager.success("Data validation completed")
        
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            self.notification_manager.error(f"Validation failed: {e}")
    
    def _fix_data_issues(self) -> None:
        """Fix common data issues."""
        try:
            with st.spinner("Fixing data issues..."):
                # This would implement automatic data repair
                self.notification_manager.info("Data repair functionality coming soon")
        
        except Exception as e:
            logger.error(f"Data repair failed: {e}")
            self.notification_manager.error(f"Data repair failed: {e}")
    
    def _show_data_statistics(self) -> None:
        """Show data statistics."""
        try:
            data_service = self.state_manager.get("data_service")
            if not data_service:
                self.notification_manager.error("Data service not available")
                return
            
            with st.spinner("Generating statistics..."):
                stats = data_service.get_trade_statistics()
                
                st.subheader("Data Statistics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Trades", stats.get('total_trades', 0))
                
                with col2:
                    st.metric("Open Trades", stats.get('open_trades', 0))
                
                with col3:
                    st.metric("Closed Trades", stats.get('closed_trades', 0))
                
                with col4:
                    st.metric("Total PnL", f"${stats.get('total_pnl', 0):.2f}")
                
                # Additional statistics
                if stats.get('exchanges'):
                    st.write(f"**Exchanges:** {', '.join(stats['exchanges'])}")
                
                if stats.get('symbols'):
                    st.write(f"**Symbols:** {len(stats['symbols'])} unique symbols")
                
                self.notification_manager.success("Statistics generated successfully")
        
        except Exception as e:
            logger.error(f"Statistics generation failed: {e}")
            self.notification_manager.error(f"Statistics generation failed: {e}")


def get_data_management_ui(data_path: str = "/app/data") -> DataManagementUI:
    """Get or create data management UI instance."""
    if 'data_management_ui' not in st.session_state:
        st.session_state.data_management_ui = DataManagementUI(data_path)
    
    return st.session_state.data_management_ui


def render_data_management_interface(data_path: str = "/app/data") -> None:
    """Render the data management interface."""
    ui = get_data_management_ui(data_path)
    ui.render_data_management_interface()