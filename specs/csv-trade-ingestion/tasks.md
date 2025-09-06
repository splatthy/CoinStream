# CSV Trade Ingestion Implementation Tasks

## Implementation Plan

- [ ] 1. Set up CSV processing infrastructure
  - [ ] 1.1 Create CSV data models and validation schemas
    - Write ColumnMapping dataclass with validation methods
    - Write ImportResult and ValidationResult models
    - Add lightweight CSVValidationIssue (warning/info container) — reuse app/utils/validators.ValidationError for exceptions
    - Write unit tests for all data models
    - _Requirements: 2.1, 2.4, 6.2_

  - [ ] 1.2 Implement CSV file parsing utilities
    - Write CSVParser class with delimiter and encoding detection (csv.Sniffer, utf-8 → latin-1 fallback)
    - Implement multi-format date parsing with fallback strategies
    - Create file validation for size, format, and encoding (no API usage, offline only)
    - Write unit tests for parsing edge cases and error conditions
    - _Requirements: 1.5, 8.4, 9.1_

- [ ] 2. Build CSV validation and error handling system
  - [ ] 2.1 Create comprehensive CSV validator
    - Write CSVValidator class with data type validation
    - Implement required field validation and missing data detection
    - Create duplicate trade detection based on timestamp and symbol
    - Write detailed error reporting with row and column information
    - Write unit tests for all validation scenarios
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 4.4_

  - [ ] 2.2 Implement column mapping system
    - Write ColumnMapper class to load shipped, exchange-specific mapping templates (JSON)
    - Create pattern matching fallback for common column names (used only if no template found)
    - Do NOT implement manual override UI or save/load in MVP; mappings are shipped with the app
    - Store templates under `app/services/csv_import/mappings/<exchange>.json` (e.g., Bitunix)
    - Write unit tests for mapping selection (exchange → template) and fallback logic
    - _Requirements: 6.1, 6.2 (shipping templates), 6.4_

- [ ] 3. Create data transformation pipeline
  - [ ] 3.1 Build data transformer for Trade model conversion
    - Write DataTransformer class to convert CSV rows to Trade objects
    - Implement PnL calculation for missing values using entry/exit prices
    - Create trade side normalization (Long/Short to TradeSide enum)
    - Implement timestamp parsing with multiple format support
    - Generate deterministic trade ID from fields (e.g., symbol|entry_time|quantity|entry_price hash) to enable future duplicate handling
    - Set `exchange` field from user-selected exchange in UI (e.g., "bitunix")
    - Write unit tests for transformation accuracy and edge cases
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ] 3.2 Implement batch processing for large files
    - MVP: single-pass import with progress bar updates (UI), targeting files up to 50MB
    - Create chunked processing for files larger than 10MB (Post-MVP)
    - Implement progress tracking and callback system (MVP supports UI progress)
    - Create memory-efficient streaming for very large datasets (Post-MVP)
    - Write transaction-based import with rollback capability (Post-MVP)
    - Write performance tests with large CSV files
    - _Requirements: 4.1, 4.2, 4.3, 5.2_

- [ ] 4. Build CSV import service orchestrator
  - [ ] 4.1 Create main CSV import service
    - Write CSVImportService class as main orchestrator
    - Implement full import workflow with validation, transformation, and storage (offline only; no API usage)
    - Create preview functionality for data verification before import
    - Implement comprehensive error handling and recovery
    - Write integration tests for complete import process
    - _Requirements: 1.1, 4.1, 4.2, 7.1, 7.4_

  - [ ] 4.2 Add duplicate handling and data integrity
    - MVP: Generate deterministic trade IDs; skip duplicates automatically and count in summary (no user prompt)
    - Create data integrity checks before and after import
    - Implement import summary with statistics and warnings
    - Plan for future strategies (overwrite/merge) without breaking current design
    - Create rollback functionality for failed imports (Post-MVP)
    - Write tests for duplicate scenarios and data integrity
    - _Requirements: 4.4, 4.5, 9.5_

- [ ] 5. Create CSV import user interface
  - [ ] 5.1 Design CSV import UX flow and page structure
    - Design multi-step import workflow: Upload → Select Exchange → Validate → Preview → Import
    - Create step indicator showing current progress in import process
    - Implement proper Streamlit form structure for each step
    - Design error state handling and recovery within the workflow
    - Create wireframes for each step of the import process
    - _Requirements: 1.1, 5.1, 7.4_

  - [ ] 5.2 Build file upload component using Streamlit file_uploader
    - Create file upload using `st.file_uploader()` with CSV MIME type restriction
    - Implement file validation and size checking (max 50MB)
    - Create file information display (name, size, row count estimate)
    - Add file format validation and encoding detection
    - Store uploaded file in session state for workflow persistence
    - Write UI tests for upload functionality
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ] 5.2 Implement exchange selection and mapping preview
    - Add exchange selection dropdown (e.g., Bitunix, etc.)
    - Load and display read-only mapping derived from shipped template for selected exchange
    - Show header-to-field preview; no manual overrides in MVP
    - Validate mapping presence and show helpful errors if unsupported
    - Write UI tests for exchange selection and mapping preview
    - _Requirements: 6.1, 6.2 (shipped), 6.4_

- [ ] 6. Build data preview and confirmation system
  - [ ] 6.1 Create data preview component
    - Build preview table showing first 10-20 rows of mapped data
    - Implement highlighting of calculated/derived fields
    - Create expandable view for detailed row inspection
    - Add validation status indicators for each preview row
    - Write UI tests for preview functionality
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ] 6.2 Implement import confirmation and progress tracking
    - Create import confirmation dialog with summary statistics
    - Build real-time progress bar with row count and percentage (MVP requirement)
    - Implement cancellation functionality during import
    - Create import completion summary with success/error statistics
    - Write UI tests for progress tracking and completion
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 7.4, 7.5_

- [ ] 7. Add comprehensive error handling and user feedback
  - [ ] 7.1 Create error display and messaging system
    - Build error message display with specific row/column information
    - Implement warning system for non-blocking issues
    - Create error categorization and suggested fixes
    - Add error export functionality for external fixing
    - Write tests for error display and user feedback
    - _Requirements: 2.4, 9.1, 9.2, 9.4_

  - [ ] 7.2 Implement recovery and retry mechanisms
    - Create retry functionality for failed imports
    - Implement partial import with error skipping option
    - Add manual error correction interface for common issues
    - Create import resume functionality for interrupted operations
    - Write tests for recovery scenarios
    - _Requirements: 9.3, 9.5_

- [ ] 8. Integrate with existing application features
  - [ ] 8.1 Connect CSV import to data service
    - Integrate CSVImportService with existing DataService
    - Ensure imported trades appear in Trade History immediately
    - Update data refresh mechanisms to include imported data
    - Create cache invalidation after successful imports
    - Write integration tests with existing data flows
    - _Requirements: 10.1, 10.4_

  - [ ] 8.2 Ensure compatibility with analysis features
    - Verify imported trades work with trend analysis calculations
    - Test confluence analysis with imported trade data
    - Ensure custom fields from CSV are properly handled
    - Validate PnL calculations work with imported data
    - Write end-to-end tests with analysis features
    - _Requirements: 10.2, 10.3, 10.4, 10.5_

- [ ] 9. Create CSV import page following Streamlit multipage best practices
  - [ ] 9.1 Create dedicated CSV import page module
    - Create `app/pages/csv_import.py` following Streamlit multipage structure
    - Implement `show_csv_import_page()` function as main entry point
    - Use proper Streamlit session state management for import workflow
    - Implement page-specific error handling and state cleanup
    - Follow Streamlit naming conventions for multipage apps
    - Write unit tests for page functionality
    - _Requirements: 1.1, 7.4_

  - [ ] 9.2 Update main navigation to include CSV import
    - Add "Import Data" option to main.py navigation menu
    - Update `render_sidebar_navigation()` to include CSV import page
    - Ensure proper page routing in main application
    - Remove all exchange-related navigation elements from sidebar
    - Update page routing logic to handle csv_import page
    - Write navigation tests for new page integration
    - _Requirements: 1.1, 8.1_

  - [ ] 9.3 Implement proper Streamlit session state management
    - Create session state keys for CSV import workflow (file_uploaded, selected_exchange, loaded_mapping, preview_data, import_summary)
    - Implement state cleanup when navigating away from import page
    - Use `st.rerun()` properly for state updates during import process
    - Implement proper form handling with `st.form()` for file upload and mapping
    - Handle file upload state persistence across page interactions
    - Write tests for session state management
    - _Requirements: 5.3, 7.4_

- [ ] 10. Testing and validation
  - [ ] 10.1 Create comprehensive test suite
    - Write unit tests for all CSV processing components
    - Create integration tests for complete import workflows
    - Add performance tests with large CSV files
    - Write UI tests for all user interface components
    - Create error scenario tests for edge cases
    - _Requirements: All requirements_

  - [ ] 10.2 Add sample data and documentation
    - Include sample CSV files (e.g., `bitunix_trades_clean.csv`) and corresponding shipped mapping templates
    - Write user documentation for CSV import process (no API usage; offline-only)
    - Create troubleshooting guide for common issues
    - Add CSV format specification documentation (per exchange template)
    - Write developer documentation for onboarding a new exchange (add new `<exchange>.json` template + tests)
    - _Requirements: 8.1, 8.2, 8.3_
