# Crypto Trading Journal

A containerized Python Streamlit application for comprehensive crypto trading analysis and data management.

## Quick Start

### Prerequisites
- Docker
- Docker Compose

### Running the Application

1. Clone the repository
2. Build and run with Docker Compose:
   ```bash
   docker-compose up --build
   ```
3. Access the application at http://localhost:8501

### Development Mode

For development with hot-reload:
```bash
docker-compose --profile dev up trading-journal-dev --build
```
Access at http://localhost:8502

## Project Structure

```
crypto-trading-journal/
├── app/                    # Application source code
│   ├── main.py            # Streamlit entry point
│   ├── pages/             # Streamlit pages
│   ├── services/          # Business logic
│   ├── models/            # Data models
│   ├── integrations/      # Exchange integrations
│   └── utils/             # Utilities
├── data/                  # Persistent data (volume mount)
├── Dockerfile             # Container configuration
├── docker-compose.yml     # Local development setup
└── requirements.txt       # Python dependencies
```

## Features

- Docker containerized deployment
- Exchange API integration (starting with Bitunix)
- Persistent data storage
- Trade history management
- Performance trend analysis
- Confluence analysis
- Extensible data models

## Configuration

The application uses volume-mounted persistent storage for:
- Trade data cache
- Exchange API configurations
- Custom field definitions

All sensitive data (API keys) are encrypted before storage.