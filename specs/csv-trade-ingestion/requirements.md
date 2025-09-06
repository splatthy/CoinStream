# CSV Trade Ingestion Requirements

## Introduction

This document outlines the requirements for implementing a secure CSV-only trade ingestion system for the crypto trading journal application. This system will completely replace all exchange API integrations, providing a safe and controlled method for importing trade data without any external network connections or API risks.

## Requirements

### Requirement 1

**User Story:** As a crypto trader, I want to upload CSV files containing my trade history, so that I can import my trading data without any API connections or security risks.

#### Acceptance Criteria

1. WHEN the user navigates to the data import page THEN the system SHALL display a CSV file upload interface
2. WHEN the user drags and drops a CSV file THEN the system SHALL accept the file and show upload progress
3. WHEN the user selects a CSV file via file picker THEN the system SHALL validate the file format before processing
4. WHEN a CSV file is uploaded THEN the system SHALL support files up to 50MB in size
5. WHEN processing CSV files THEN the system SHALL handle UTF-8 encoding and common CSV delimiters (comma, semicolon)

### Requirement 2

**User Story:** As a crypto trader, I want the system to validate my CSV data before import, so that I can identify and fix any data issues before they affect my analysis.

#### Acceptance Criteria

1. WHEN a CSV file is uploaded THEN the system SHALL validate that all required columns are present
2. WHEN validating CSV data THEN the system SHALL check data types for numeric fields (quantity, prices, PnL, fees)
3. WHEN validating CSV data THEN the system SHALL verify date formats and parse timestamps correctly
4. WHEN validation fails THEN the system SHALL display specific error messages indicating which rows and columns have issues
5. WHEN validation succeeds THEN the system SHALL show a preview of the first 10 rows of data before import

### Requirement 3

**User Story:** As a crypto trader, I want my CSV data to be properly mapped to the internal trade model, so that all existing analysis features continue to work with imported data.

#### Acceptance Criteria

1. WHEN processing CSV data THEN the system SHALL map CSV columns to internal Trade model fields correctly
2. WHEN processing dates THEN the system SHALL handle multiple date formats (ISO 8601, common exchange formats)
3. WHEN processing trade sides THEN the system SHALL convert "Long"/"Short" to internal TradeSide enum values
4. WHEN processing PnL data THEN the system SHALL calculate missing PnL values from entry/exit prices when possible
5. WHEN importing trades THEN the system SHALL preserve all original CSV data in a raw_data field for reference

### Requirement 4

**User Story:** As a crypto trader, I want the import process to be reliable and safe, so that I don't lose data or corrupt my existing trade history.

#### Acceptance Criteria

1. WHEN importing CSV data THEN the system SHALL use transaction-based imports (all trades imported or none)
2. WHEN an import fails THEN the system SHALL rollback any partial changes and preserve existing data
3. WHEN importing large files THEN the system SHALL process data in batches to avoid memory issues
4. WHEN importing trades THEN the system SHALL detect and handle duplicate trades based on timestamp and symbol
5. WHEN import completes THEN the system SHALL provide a summary of imported trades and any skipped duplicates

### Requirement 5

**User Story:** As a crypto trader, I want to see the progress of my CSV import, so that I know the system is working and can estimate completion time.

#### Acceptance Criteria

1. WHEN importing a CSV file THEN the system SHALL display a progress bar showing percentage complete
2. WHEN processing large files THEN the system SHALL show the number of rows processed and remaining
3. WHEN import is in progress THEN the system SHALL prevent navigation away from the page
4. WHEN import completes THEN the system SHALL display a success message with import statistics
5. WHEN import fails THEN the system SHALL display clear error messages and allow retry

### Requirement 6

**User Story:** As a crypto trader, I want to configure CSV column mappings, so that I can import data from different exchanges or CSV formats.

#### Acceptance Criteria

1. WHEN uploading a CSV THEN the system SHALL automatically detect and suggest column mappings
2. WHEN column mapping is ambiguous THEN the system SHALL allow manual mapping of CSV columns to trade fields
3. WHEN configuring mappings THEN the system SHALL save mapping configurations for reuse
4. WHEN using saved mappings THEN the system SHALL apply them automatically to files with similar headers
5. WHEN mapping columns THEN the system SHALL validate that all required fields are mapped

### Requirement 7

**User Story:** As a crypto trader, I want to preview my data before final import, so that I can verify the mapping and data quality.

#### Acceptance Criteria

1. WHEN CSV validation passes THEN the system SHALL display a preview table with mapped data
2. WHEN previewing data THEN the system SHALL show the first 10-20 rows with all mapped fields
3. WHEN previewing data THEN the system SHALL highlight any calculated or derived fields
4. WHEN data preview is shown THEN the system SHALL provide "Import" and "Cancel" options
5. WHEN user confirms import THEN the system SHALL proceed with the full data import process

### Requirement 8

**User Story:** As a crypto trader, I want the system to handle various CSV formats from different sources, so that I can import data regardless of the original exchange format.

#### Acceptance Criteria

1. WHEN processing CSV files THEN the system SHALL support the Bitunix format as defined in the sample file
2. WHEN processing CSV files THEN the system SHALL be extensible to support additional exchange formats
3. WHEN encountering unknown formats THEN the system SHALL provide manual column mapping options
4. WHEN processing different date formats THEN the system SHALL attempt multiple parsing strategies
5. WHEN processing numeric fields THEN the system SHALL handle different decimal separators and thousand separators

### Requirement 9

**User Story:** As a crypto trader, I want comprehensive error handling during CSV import, so that I can understand and resolve any data issues.

#### Acceptance Criteria

1. WHEN CSV parsing fails THEN the system SHALL provide specific error messages with row and column information
2. WHEN data validation fails THEN the system SHALL list all validation errors with suggestions for fixes
3. WHEN import is interrupted THEN the system SHALL provide options to retry or cancel the operation
4. WHEN errors occur THEN the system SHALL log detailed error information for troubleshooting
5. WHEN recoverable errors are found THEN the system SHALL offer to skip problematic rows and continue

### Requirement 10

**User Story:** As a crypto trader, I want the CSV import feature to integrate seamlessly with existing application features, so that imported data works with all analysis tools.

#### Acceptance Criteria

1. WHEN trades are imported THEN they SHALL appear in the Trade History page immediately
2. WHEN trades are imported THEN they SHALL be included in trend analysis calculations
3. WHEN trades are imported THEN they SHALL be available for confluence analysis
4. WHEN trades are imported THEN they SHALL support all existing custom field functionality
5. WHEN trades are imported THEN they SHALL maintain data integrity with existing trade records