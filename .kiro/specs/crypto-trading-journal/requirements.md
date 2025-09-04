# Requirements Document

## Introduction

This document outlines the requirements for a Python Streamlit-based crypto trading journal application. The application will run in a Docker container, sync with crypto exchanges via API, and provide comprehensive trade analysis and visualization capabilities. The system will support multiple exchanges (starting with Bitunix), persist data locally, and offer extensible data models for future enhancements.

## Requirements

### Requirement 1

**User Story:** As a crypto trader, I want to run the trading journal application in a Docker container, so that I can have a consistent, isolated environment that's easy to deploy and manage.

#### Acceptance Criteria

1. WHEN the user builds the Docker image THEN the system SHALL create a container with Python, Streamlit, and all required dependencies
2. WHEN the user runs the container THEN the system SHALL expose the Streamlit web interface on a configurable port
3. WHEN the container is started THEN the system SHALL mount a persistent volume for data storage
4. WHEN the container is stopped and restarted THEN the system SHALL retain all cached data and configuration

### Requirement 2

**User Story:** As a crypto trader, I want to configure exchange API connections, so that I can securely connect to my trading accounts and import trade data.

#### Acceptance Criteria

1. WHEN the user accesses the Config page THEN the system SHALL display a list of supported exchanges with API key input fields
2. WHEN the user enters an API key THEN the system SHALL provide a show/hide toggle for the key visibility
3. WHEN an API key is saved THEN the system SHALL indicate the key is stored without displaying the actual key value
4. WHEN the user saves an API key THEN the system SHALL test the key validity and display the connection status
5. WHEN the system starts THEN the system SHALL initially support Bitunix exchange with extensibility for additional exchanges

### Requirement 3

**User Story:** As a crypto trader, I want to import and sync trade data from exchanges, so that I can maintain an up-to-date record of my trading activity.

#### Acceptance Criteria

1. WHEN the user clicks the refresh button THEN the system SHALL fetch position history data from the configured exchange
2. WHEN importing data THEN the system SHALL reconcile new data with existing cached records
3. WHEN processing position data THEN the system SHALL identify partially closed positions that require future updates
4. WHEN a position is partially closed THEN the system SHALL mark it for re-checking on subsequent syncs
5. WHEN data import completes THEN the system SHALL update the local cache with new and modified records

### Requirement 4

**User Story:** As a crypto trader, I want to view my complete trade history, so that I can review all my trading activity in one place.

#### Acceptance Criteria

1. WHEN the user navigates to Trade History page THEN the system SHALL display all cached trade records
2. WHEN displaying trades THEN the system SHALL show position status (fully closed or partially closed)
3. WHEN displaying trades THEN the system SHALL include all exchange data plus user-defined fields
4. WHEN displaying trades THEN the system SHALL show confluence selections and win/loss status
5. WHEN the user views a trade THEN the system SHALL display all relevant trading information including PnL

### Requirement 5

**User Story:** As a crypto trader, I want to analyze my trading performance over time, so that I can identify trends and improve my trading strategy.

#### Acceptance Criteria

1. WHEN the user navigates to Trend Analysis page THEN the system SHALL display a time series graph of PnL
2. WHEN viewing the trend graph THEN the system SHALL default to daily aggregation
3. WHEN the user selects a time frame THEN the system SHALL update the graph to show Daily, Weekly, or Monthly aggregation
4. WHEN displaying trend data THEN the system SHALL calculate cumulative PnL over the selected time period
5. WHEN the graph loads THEN the system SHALL provide interactive features for data exploration

### Requirement 6

**User Story:** As a crypto trader, I want to analyze the effectiveness of different trading confluences, so that I can identify which setups provide the best results.

#### Acceptance Criteria

1. WHEN the user navigates to Confluence Analysis page THEN the system SHALL display win rate statistics for each confluence
2. WHEN displaying confluence data THEN the system SHALL show PnL percentage for each confluence type
3. WHEN analyzing confluences THEN the system SHALL calculate independent performance metrics for each confluence
4. WHEN multiple confluences are selected for a trade THEN the system SHALL include that trade in analysis for all selected confluences
5. WHEN displaying results THEN the system SHALL rank confluences by performance metrics

### Requirement 7

**User Story:** As a crypto trader, I want to add custom data to my trades beyond exchange information, so that I can track additional factors that influence my trading decisions.

#### Acceptance Criteria

1. WHEN the user views a trade THEN the system SHALL provide a confluence multi-select field
2. WHEN the user selects confluences THEN the system SHALL allow multiple selections from predefined options
3. WHEN the user views a trade THEN the system SHALL display a win/loss field that determines trade outcome
4. WHEN the user saves trade modifications THEN the system SHALL persist the custom data with the trade record
5. WHEN custom fields are added THEN the system SHALL maintain data integrity across application restarts

### Requirement 8

**User Story:** As a crypto trader, I want to configure custom field options, so that I can define the available values for dropdown and multi-select fields.

#### Acceptance Criteria

1. WHEN the user accesses the Config page THEN the system SHALL provide a section for managing custom field definitions
2. WHEN the user defines confluence options THEN the system SHALL allow adding, editing, and removing confluence values
3. WHEN confluence options are modified THEN the system SHALL update all relevant UI components immediately
4. WHEN the user saves configuration changes THEN the system SHALL persist the settings to the data volume
5. WHEN the application starts THEN the system SHALL load custom field definitions from persistent storage

### Requirement 9

**User Story:** As a crypto trader, I want the data model to be extensible, so that new features and fields can be added without breaking existing functionality.

#### Acceptance Criteria

1. WHEN new fields are added to the data model THEN the system SHALL maintain compatibility with existing trade records
2. WHEN the application is updated THEN the system SHALL handle data migration automatically
3. WHEN new custom field types are introduced THEN the system SHALL support them through the configuration interface
4. WHEN the data structure changes THEN the system SHALL preserve all existing user data and settings
5. WHEN extending the model THEN the system SHALL maintain performance and data integrity

### Requirement 10

**User Story:** As a crypto trader, I want secure and persistent data storage, so that my trading data and API credentials are safely maintained across container restarts.

#### Acceptance Criteria

1. WHEN the container starts THEN the system SHALL mount a persistent volume for data storage
2. WHEN API keys are stored THEN the system SHALL encrypt sensitive credentials
3. WHEN trade data is cached THEN the system SHALL use efficient storage formats to minimize disk usage
4. WHEN the application shuts down THEN the system SHALL ensure all data is properly saved to persistent storage
5. WHEN data corruption is detected THEN the system SHALL provide recovery mechanisms and error reporting