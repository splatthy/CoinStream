"""
User guidance and help utilities for data management operations.
"""

import streamlit as st
from typing import Dict, List, Optional


class UserGuidance:
    """Provides user guidance and help for data management operations."""
    
    @staticmethod
    def show_backup_guidance() -> None:
        """Show guidance for backup operations."""
        with st.expander("📖 Backup Guide", expanded=False):
            st.markdown("""
            ### Creating Backups
            
            **When to create backups:**
            - Before major data imports or changes
            - Before restoring from another backup
            - Regularly (recommended: daily or weekly)
            - Before application updates
            
            **Backup Types:**
            - **Compressed (ZIP)**: Smaller file size, good for storage and transfer
            - **Directory**: Faster to create, easier to inspect individual files
            
            **Best Practices:**
            - Use descriptive backup names (e.g., "before_import_2024", "weekly_backup")
            - Keep multiple backups (don't rely on just one)
            - Verify backup integrity regularly
            - Store important backups outside the application directory
            
            **Automatic Cleanup:**
            - Configure cleanup to keep recent backups and remove old ones
            - Balance storage space with backup history needs
            - Always keep at least a few recent backups
            """)
    
    @staticmethod
    def show_restore_guidance() -> None:
        """Show guidance for restore operations."""
        with st.expander("📖 Restore Guide", expanded=False):
            st.markdown("""
            ### Restoring Data
            
            **⚠️ Important Warnings:**
            - Restoring will **overwrite all current data**
            - A backup of current data is created automatically before restore
            - This operation cannot be undone (except by restoring another backup)
            
            **Before Restoring:**
            1. Verify the backup you want to restore is valid
            2. Check the backup creation date and contents
            3. Ensure you have enough disk space
            4. Close any other applications using the data
            
            **After Restoring:**
            - Refresh the application to see restored data
            - Verify the restored data is correct
            - Check that all features work as expected
            - Consider creating a new backup of the restored state
            """)
    
    @staticmethod
    def show_export_guidance() -> None:
        """Show guidance for data export operations."""
        with st.expander("📖 Export Guide", expanded=False):
            st.markdown("""
            ### Exporting Data
            
            **Export Formats:**
            - **CSV**: Best for spreadsheet applications (Excel, Google Sheets)
            - **JSON**: Best for technical users and data processing
            - **Excel**: Best for detailed analysis with multiple sheets
            
            **Date Range Filtering:**
            - Use date filters to export only relevant data
            - Smaller exports are faster and easier to work with
            - Consider your analysis needs when selecting date ranges
            
            **Data Selection:**
            - **Trade Data**: Your trading history and performance
            - **Position Data**: Current and historical position information
            - **Configuration**: Application settings and custom fields
            
            **Uses for Exported Data:**
            - External analysis in Excel or other tools
            - Backup for external storage
            - Sharing data with advisors or tax professionals
            - Migration to other trading journal applications
            """)
    
    @staticmethod
    def show_import_guidance() -> None:
        """Show guidance for data import operations."""
        with st.expander("📖 Import Guide", expanded=False):
            st.markdown("""
            ### Importing Data
            
            **⚠️ Important Notes:**
            - Always create a backup before importing
            - Importing can modify your existing data
            - Test with small datasets first
            
            **Import Modes:**
            - **Merge**: Adds imported data to existing data
            - **Replace**: Overwrites existing data with imported data
            
            **Supported File Types:**
            - CSV files with proper column headers
            - JSON files in the correct format
            - Excel files (.xlsx) with data in the first sheet
            
            **Data Format Requirements:**
            - CSV files must have column headers matching field names
            - Dates should be in YYYY-MM-DD format
            - Numbers should not contain currency symbols or commas
            - Required fields must be present in all records
            
            **Before Importing:**
            1. Validate your data file format
            2. Check for duplicate records
            3. Ensure all required fields are present
            4. Create a backup of current data
            """)
    
    @staticmethod
    def show_validation_guidance() -> None:
        """Show guidance for data validation operations."""
        with st.expander("📖 Validation Guide", expanded=False):
            st.markdown("""
            ### Data Validation
            
            **Validation Checks:**
            
            **Data Integrity:**
            - Checks if data files are readable and properly formatted
            - Verifies data structure matches expected schema
            - Identifies corrupted or incomplete records
            
            **Duplicate Detection:**
            - Finds duplicate trade records
            - Identifies potential data import errors
            - Helps maintain data quality
            
            **Data Consistency:**
            - Verifies relationships between related data
            - Checks for logical inconsistencies
            - Validates calculated fields
            
            **Data Completeness:**
            - Identifies missing required fields
            - Checks for incomplete records
            - Validates data coverage
            
            **When to Run Validation:**
            - After importing data
            - Before important analysis
            - Regularly as part of maintenance
            - When experiencing application issues
            
            **Interpreting Results:**
            - ✅ Green checkmarks indicate no issues found
            - ⚠️ Yellow warnings indicate potential issues
            - ❌ Red errors indicate problems that need attention
            """)
    
    @staticmethod
    def show_troubleshooting_guide() -> None:
        """Show troubleshooting guide."""
        with st.expander("🔧 Troubleshooting", expanded=False):
            st.markdown("""
            ### Common Issues and Solutions
            
            **Backup Creation Fails:**
            - Check available disk space
            - Ensure data directory is accessible
            - Verify file permissions
            - Try creating an uncompressed backup
            
            **Restore Operation Fails:**
            - Verify backup file integrity
            - Check available disk space
            - Ensure no other applications are using data files
            - Try restoring to a different location first
            
            **Export Issues:**
            - Reduce date range if export is too large
            - Check available memory and disk space
            - Try exporting smaller data subsets
            - Verify data exists for selected date range
            
            **Import Problems:**
            - Verify file format matches expected structure
            - Check for special characters in data
            - Ensure file is not corrupted
            - Try importing smaller batches
            
            **Validation Errors:**
            - Review specific error messages
            - Check data file permissions
            - Verify data directory structure
            - Consider restoring from a known good backup
            
            **General Performance Issues:**
            - Clear application cache
            - Restart the application
            - Check system resources (memory, disk space)
            - Consider archiving old data
            
            **Getting Help:**
            - Check application logs for detailed error messages
            - Document the steps that led to the issue
            - Note any error messages exactly as they appear
            - Consider creating a backup before attempting fixes
            """)
    
    @staticmethod
    def show_best_practices() -> None:
        """Show best practices guide."""
        with st.expander("⭐ Best Practices", expanded=False):
            st.markdown("""
            ### Data Management Best Practices
            
            **Regular Maintenance:**
            - Create backups regularly (daily/weekly)
            - Run data validation monthly
            - Clean up old backups to save space
            - Monitor data file sizes and growth
            
            **Before Major Operations:**
            - Always create a backup first
            - Test operations on small datasets
            - Verify results before proceeding
            - Document what you're doing and why
            
            **Data Quality:**
            - Import data in small batches when possible
            - Validate data after imports
            - Review and clean data regularly
            - Use consistent naming conventions
            
            **Security:**
            - Keep backups in secure locations
            - Don't share sensitive trading data unnecessarily
            - Use strong passwords for any external storage
            - Be cautious when importing data from unknown sources
            
            **Organization:**
            - Use descriptive names for backups and exports
            - Keep a log of major data operations
            - Document any custom configurations
            - Maintain a schedule for regular maintenance
            
            **Performance:**
            - Archive old data that's no longer needed
            - Keep the data directory clean and organized
            - Monitor application performance regularly
            - Consider data retention policies
            """)
    
    @staticmethod
    def render_all_guidance() -> None:
        """Render all guidance sections."""
        st.subheader("📚 User Guide")
        
        UserGuidance.show_backup_guidance()
        UserGuidance.show_restore_guidance()
        UserGuidance.show_export_guidance()
        UserGuidance.show_import_guidance()
        UserGuidance.show_validation_guidance()
        UserGuidance.show_troubleshooting_guide()
        UserGuidance.show_best_practices()
    
    @staticmethod
    def show_quick_tips() -> None:
        """Show quick tips for data management."""
        st.info("""
        💡 **Quick Tips:**
        - Always backup before major changes
        - Use descriptive names for backups
        - Validate data after imports
        - Export data regularly for external analysis
        - Run cleanup periodically to save space
        """)


def render_user_guidance() -> None:
    """Render user guidance interface."""
    guidance = UserGuidance()
    guidance.render_all_guidance()


def show_context_help(context: str) -> None:
    """Show context-specific help."""
    guidance = UserGuidance()
    
    if context == "backup":
        guidance.show_backup_guidance()
    elif context == "restore":
        guidance.show_restore_guidance()
    elif context == "export":
        guidance.show_export_guidance()
    elif context == "import":
        guidance.show_import_guidance()
    elif context == "validation":
        guidance.show_validation_guidance()
    elif context == "troubleshooting":
        guidance.show_troubleshooting_guide()
    elif context == "best_practices":
        guidance.show_best_practices()
    else:
        guidance.show_quick_tips()