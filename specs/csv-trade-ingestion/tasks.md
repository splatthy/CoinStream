# CSV Trade Ingestion Implementation Tasks

## Implementation Plan

- [ ] 1. Set up CSV processing infrastructure
  - [x] 1.1 Create CSV data models and validation schemas
    - [x] Write ColumnMapping dataclass with validation methods
    - [x] Write ImportResult and ValidationResult models
    - [x] Add lightweight CSVValidationIssue (warning/info container) — reuse app/utils/validators.ValidationError for exceptions
    - [x] Write unit tests for all data models
    - _Requirements: 2.1, 2.4, 6.2_

  - [x] 1.2 Implement CSV file parsing utilities
    - [x] Write CSVParser class with delimiter and encoding detection (csv.Sniffer, utf-8 → latin-1 fallback)
    - [x] Implement multi-format date parsing with fallback strategies
    - [x] Create file validation for size, format, and encoding (no API usage, offline only)
    - [x] Write unit tests for parsing edge cases and error conditions
    - _Requirements: 1.5, 8.4, 9.1_

- [ ] 2. Build CSV validation and error handling system
  - [x] 2.1 Create comprehensive CSV validator
    - [x] Write CSVValidator class with data type validation
    - [x] Implement required field validation and missing data detection
    - [x] Create duplicate trade detection based on timestamp and symbol
    - [x] Write detailed error reporting with row and column information
    - [x] Write unit tests for all validation scenarios
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 4.4_

  - [x] 2.2 Implement column mapping system
    - [x] Write ColumnMapper class to load shipped, exchange-specific mapping templates (JSON)
    - [x] Create pattern matching fallback for common column names (used only if no template found)
    - [x] Do NOT implement manual override UI or save/load in MVP; mappings are shipped with the app
    - [x] Store templates under `app/services/csv_import/mappings/<exchange>.json` (e.g., Bitunix)
    - [x] Write unit tests for mapping selection (exchange → template) and fallback logic
    - _Requirements: 6.1, 6.2 (shipping templates), 6.4_

- [ ] 3. Create data transformation pipeline
  - [x] 3.1 Build data transformer for Trade model conversion
    - [x] Write DataTransformer class to convert CSV rows to Trade objects
    - [x] Implement PnL calculation for missing values using entry/exit prices
    - [x] Create trade side normalization (Long/Short to TradeSide enum)
    - [x] Implement timestamp parsing with multiple format support and normalize to UTC (timezone-naive) for consistency
    - [x] Generate deterministic trade ID from fields (e.g., symbol|entry_time|quantity|entry_price hash) to enable future duplicate handling
    - [x] Set `exchange` field from user-selected exchange in UI (e.g., "bitunix")
    - [x] Write unit tests for transformation accuracy and edge cases
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.2 Implement batch processing for large files
    - [x] MVP: single-pass import with progress bar updates (UI), targeting files up to 50MB
    - [x] Implement progress tracking and callback system (MVP supports UI progress)
    - _Requirements: 4.1, 4.2, 4.3, 5.2_

- [ ] 4. Build CSV import service orchestrator
  - [x] 4.1 Create main CSV import service
    - [x] Write CSVImportService class as main orchestrator
    - [x] Implement full import workflow with validation, transformation, and storage (offline only; no API usage)
    - [x] Create preview functionality for data verification before import
    - [x] Implement basic error handling and progress callback support (MVP)
    - [x] Write integration tests for complete import process
    - _Requirements: 1.1, 4.1, 4.2, 7.1, 7.4_

  - [x] 4.2 Add duplicate handling and data integrity
    - [x] MVP: Generate deterministic trade IDs; skip duplicates automatically and count in summary (no user prompt)
    - [x] Create data integrity checks before and after import (unique ID check prior to save)
    - [x] Implement import summary with statistics and warnings
    - [x] Plan for future strategies (overwrite/merge) without breaking current design
    
    - [x] Write tests for duplicate scenarios (within-file and against existing) and data integrity
    - _Requirements: 4.4, 4.5, 9.5_

- [ ] 5. Create CSV import user interface
  - [x] 5.1 Design CSV import UX flow and page structure
    - [x] Design multi-step import workflow: Upload → Select Exchange → Validate → Preview → Import
    - [x] Create step indicator showing current progress in import process
    - [x] Implement proper Streamlit form structure for each step (MVP: simple buttons)
    - [x] Design error state handling and recovery within the workflow
    - [ ] Create wireframes for each step of the import process (optional)
    - _Requirements: 1.1, 5.1, 7.4_

  - [ ] 5.2 Build file upload component using Streamlit file_uploader
    - [x] Create file upload using `st.file_uploader()` with CSV MIME type restriction
    - [x] Implement file validation and size checking (max 50MB) (via service parser/validator)
    - [x] Create file information display (name, size)
    - [x] Add file format validation and encoding detection (via service parser)
    - [x] Store uploaded file path in session state for workflow persistence
    - [ ] Write UI tests for upload functionality
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ] 5.3 Implement exchange selection and mapping preview
    - [x] Add exchange selection dropdown (e.g., Bitunix)
    - [x] Load mapping derived from shipped template for selected exchange (used during validate/preview/import)
    - [x] Show header-to-field mapping preview UI (read-only)
    - [x] Validate mapping presence and show helpful errors if unsupported
    - [ ] Write UI tests for exchange selection and mapping preview
    - _Requirements: 6.1, 6.2 (shipped), 6.4_

- [ ] 6. Build data preview and confirmation system
  - [ ] 6.1 Create data preview component
    - [x] Build preview table showing first 10-20 rows of mapped data
    - [x] Implement highlighting of calculated/derived fields
    - [x] Create expandable view for detailed row inspection
    - [x] Add validation status indicators for each preview row
    - [ ] Write UI tests for preview functionality
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ] 6.2 Implement import confirmation and progress tracking
    - [x] Create import confirmation dialog with summary statistics (MVP: post-run summary)
    - [x] Build real-time progress bar with row count and percentage (MVP requirement)
    - [x] Create import completion summary with success/error statistics
    - [ ] Write UI tests for progress tracking and completion
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
    - [x] Integrate CSVImportService with existing DataService
    - [x] Ensure imported trades appear in Trade History immediately
    - [x] Update data refresh mechanisms to include imported data
    - [x] Create cache invalidation after successful imports
    - [ ] Write integration tests with existing data flows
    - _Requirements: 10.1, 10.4_

  - [ ] 8.2 Ensure compatibility with analysis features
    - [x] Verify imported trades work with trend analysis calculations
    - [x] Test confluence analysis with imported trade data (via UI edits post-import)
    - [x] Ensure custom fields from CSV are properly handled
    - [x] Validate PnL calculations work with imported data
    - [ ] Write end-to-end tests with analysis features
    - _Requirements: 10.2, 10.3, 10.4, 10.5_

- [ ] 9. Create CSV import page following Streamlit multipage best practices
  - [x] 9.1 Create dedicated CSV import page module
    - [x] Create `app/pages/csv_import.py` following Streamlit multipage structure
    - [x] Implement `show_csv_import_page()` function as main entry point
    - [x] Use Streamlit session state for import workflow (file_path, selected_exchange, validation, preview, import_result)
    - [x] Implement page-specific error handling and state cleanup
    - [x] Follow Streamlit naming conventions for multipage apps
    - [ ] Write unit tests for page functionality
    - _Requirements: 1.1, 7.4_

  - [x] 9.2 Update main navigation to include CSV import
    - [x] Add "Import Data" option to main.py navigation menu
    - [x] Update `render_sidebar_navigation()` to include CSV import page
    - [x] Ensure proper page routing in main application
    - [x] Update page routing logic to handle csv_import page
    - [ ] Write navigation tests for new page integration
    - _Requirements: 1.1, 8.1_

  - [ ] 9.3 Implement proper Streamlit session state management
    - [x] Create session state keys for CSV import workflow (file_path, selected_exchange, validation, preview, import_result)
    - [x] Implement state cleanup when rerunning steps/import
    - [x] Use `st.rerun()` for state updates during the workflow
    - [ ] Implement proper form handling with `st.form()` for file upload and mapping (optional refinement)
    - [x] Handle file upload state persistence across page interactions
    - [ ] Write tests for session state management
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

- [ ] 11. Parquet storage and migration (MVP)
  - [ ] 11.1 Add storage backend configuration
    - Introduce `storage_backend` app config key with values `json` or `parquet` (default `parquet` for POC)
    - Expose read-only indication in UI (optional)
    - _Notes: backward-compatible; default remains JSON_

  - [x] 11.2 Refactor DataService to pluggable storage (minimal)
    - [x] Wire `DataService` to select Parquet backend via app config
    - [x] Keep public DataService API unchanged

  - [x] 11.3 Implement ParquetTradeStore
    - [x] Use `pyarrow` with Pandas to write/read Parquet
    - [x] Dataset path `DATA_PATH/trades_parquet/` (partition by year/month on `entry_time`)
    - [x] Store JSON-serialized fields to preserve compatibility; use DataSerializer for round-trip
    - [x] Deterministic ID and duplicate handling remain at service level

  - [ ] 11.4 Initialization strategy (no migration for MVP)
    - Start with a fresh Parquet dataset; do not migrate existing JSON
    - If a legacy `trades.json` exists, ignore or allow manual deletion via docs
    - Document that early adopters should re-import CSVs after enabling Parquet

  - [ ] 11.5 Tests and performance validation
    - [x] Add unit test for Parquet store round-trip
    - [ ] Verify `DataService` returns the same `Trade` objects across backends
    - [ ] Add simple benchmark to compare load/save vs JSON

  - [x] 11.6 Dependencies and Docker updates
    - [x] Add `pyarrow>=14` to `requirements.txt`
    - [x] Docker uses pip install from requirements (wheels expected)

  - [ ] 11.7 Documentation
    - Document enabling Parquet backend and migration steps
    - Note partitioning strategy and retention guidance
    - Explain Decimal precision approach and any caveats

- [ ] P1. Post-MVP Enhancements
  - [ ] P1.1 Chunked processing for files >10MB
  - [ ] P1.2 Memory-efficient streaming for very large datasets
  - [ ] P1.3 Transaction/rollback capability for imports
  - [ ] P1.4 Import cancellation control in UI
  - [ ] P1.5 Performance tests with large CSV files
  - [ ] P1.6 UI tests for upload, mapping preview, navigation, session state
  - [ ] P1.7 Portfolio Size & Risk Framework (planning)
    - Capture user-defined portfolio size (config) and desired risk %
    - Show suggested max risk per trade; lay groundwork for RR metrics
    - Plan time-series portfolio curve and risk evolution over time
    - Decide where to surface (Config panel + analytics cards)
  - [ ] P1.8 Partial-close reconciliation and dedupe strategy
    - Research exchange export semantics for partial vs. full closes
    - Propose grouping/merge rules across multiple closes (same symbol/opening time)
    - Add tolerant duplicate keys (e.g., rounded price/qty) if exchange rounding shifts
