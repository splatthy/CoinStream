# Development Setup

This document describes how to set up the development environment for the Crypto Trading Journal application.

## Prerequisites

- Python 3.11 or higher
- Git

## Quick Setup

Run the setup script to create a virtual environment and install all dependencies:

```bash
./setup-dev.sh
```

## Manual Setup

If you prefer to set up manually:

1. Create a virtual environment:
```bash
python3 -m venv venv
```

2. Activate the virtual environment:
```bash
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements-dev.txt
pip install -r requirements.txt
```

## Development Commands

### Using Make (Recommended)

```bash
# Run tests
make test

# Run tests with coverage
make test-cov

# Format code
make format

# Check code style
make lint

# Run type checking
make type-check

# Clean temporary files
make clean

# Run development server
make run-dev
```

### Using Direct Commands

```bash
# Activate virtual environment (required for all commands)
source venv/bin/activate

# Run tests
python -m pytest tests/ -v

# Run tests with coverage
python -m pytest tests/ --cov=app --cov-report=html

# Format code
black app/ tests/

# Check code style
flake8 app/ tests/

# Run type checking
mypy app/

# Run development server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Project Structure

```
├── app/                    # Application code
│   ├── models/            # Data models
│   ├── services/          # Business logic
│   ├── utils/             # Utility functions
│   ├── pages/             # Web pages/routes
│   └── integrations/      # External integrations
├── tests/                 # Test files
├── venv/                  # Virtual environment (excluded from git)
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
├── pytest.ini           # Pytest configuration
├── Makefile              # Development commands
└── setup-dev.sh          # Development setup script
```

## Testing

The project uses pytest for testing. Tests are organized by module:

- `tests/test_models.py` - Tests for data models
- `tests/test_serialization.py` - Tests for serialization utilities

### Test Coverage

Current test coverage is around 45%. The models and serialization utilities are well tested.

To generate an HTML coverage report:
```bash
make test-cov
```

The report will be available in `htmlcov/index.html`.

## Code Quality

The project uses several tools for code quality:

- **Black**: Code formatting
- **Flake8**: Style checking and linting
- **MyPy**: Static type checking
- **Pytest**: Testing framework

## Docker Development

The application can also be run in Docker for development:

```bash
# Build the development image
docker build -t crypto-journal-dev .

# Run the container
docker run -p 8000:8000 crypto-journal-dev
```

## Environment Variables

For development, you may need to set these environment variables:

- `DEBUG=true` - Enable debug mode
- `LOG_LEVEL=debug` - Set logging level

## Contributing

1. Ensure all tests pass: `make test`
2. Format your code: `make format`
3. Check code style: `make lint`
4. Run type checking: `make type-check`
5. Add tests for new functionality
6. Update documentation as needed

## Troubleshooting

### Virtual Environment Issues

If you encounter issues with the virtual environment:

1. Delete the existing environment: `rm -rf venv/`
2. Recreate it: `python3 -m venv venv`
3. Rerun setup: `./setup-dev.sh`

### Import Errors

Make sure you're using the correct import paths in tests. Use absolute imports from the app package:

```python
from app.models.trade import Trade
from app.utils.serialization import DataSerializer
```

### Test Failures

If tests fail due to enum comparison issues, ensure you're importing from the same paths used in the application code.