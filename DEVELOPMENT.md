# Development Guide - Crypto Trading Journal

## Overview

This guide covers setting up and working with the Crypto Trading Journal development environment. The project supports multiple development approaches: local development with virtual environments, Docker-based development, and VS Code Dev Containers.

## Development Environment Options

### 1. VS Code Dev Container (Recommended)

The easiest way to get started with a fully configured development environment.

**Prerequisites:**
- VS Code with Dev Containers extension
- Docker Desktop

**Setup:**
1. Open the project in VS Code
2. When prompted, click "Reopen in Container" or use Command Palette: "Dev Containers: Reopen in Container"
3. Wait for the container to build and start
4. The environment will be ready with all dependencies installed

**Features:**
- Pre-configured Python environment with all dependencies
- VS Code extensions for Python development
- Docker-in-Docker support for testing containers
- Pre-commit hooks automatically installed
- Streamlit app accessible at `http://localhost:8501`

### 2. Local Development with Virtual Environment

For developers who prefer local development.

**Prerequisites:**
- Python 3.11+
- pip
- Git

**Setup:**
```bash
# Run automated setup
./setup-dev.sh

# Or manual setup:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install black flake8 mypy isort pytest pytest-cov pre-commit
mkdir -p data
pre-commit install
```

### 3. Docker-based Development

Use Docker for development without installing Python locally.

**Prerequisites:**
- Docker
- Docker Compose

**Setup:**
```bash
# Start development environment
make run-dev

# Or directly with docker-compose
docker-compose --profile dev up -d trading-journal-dev
```

## Development Workflow

### Daily Development

1. **Activate Environment** (if using local development):
   ```bash
   source venv/bin/activate
   ```

2. **Start the Application**:
   ```bash
   # Using make
   make streamlit

   # Or directly
   streamlit run app/main.py --server.port=8501 --server.address=0.0.0.0
   ```

3. **Run Tests**:
   ```bash
   # All tests
   make test

   # Specific test categories
   make test-unit
   make test-integration
   make test-security
   ```

4. **Code Quality**:
   ```bash
   # Format code
   make format

   # Lint code
   make lint

   # Type checking
   make type-check

   # Run all quality checks
   make qa
   ```

### Code Quality Standards

The project enforces code quality through:

- **Black**: Code formatting (88 character line length)
- **isort**: Import sorting
- **flake8**: Linting and style checking
- **mypy**: Static type checking
- **pre-commit**: Automated quality checks on commit

### Testing Strategy

#### Test Categories

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test component interactions
3. **Security Tests**: Test security features and encryption
4. **End-to-End Tests**: Test complete user workflows

#### Running Tests

```bash
# All tests with coverage
make test-coverage

# Specific test file
python -m pytest tests/test_specific_file.py -v

# Tests matching pattern
python -m pytest tests/ -k "test_pattern" -v

# Debug mode (with pdb)
python -m pytest tests/ -v -s --pdb
```

#### Writing Tests

- Place tests in the `tests/` directory
- Mirror the app structure: `tests/test_services/test_data_service.py`
- Use descriptive test names: `test_should_encrypt_api_key_when_saving_config`
- Include docstrings explaining test purpose
- Use fixtures for common test data

Example test structure:
```python
import pytest
from unittest.mock import Mock, patch
from app.services.data_service import DataService

class TestDataService:
    """Test suite for DataService class."""
    
    def test_should_load_trades_from_file_when_file_exists(self):
        """Test that trades are loaded correctly from existing file."""
        # Arrange
        service = DataService()
        
        # Act
        result = service.load_trades()
        
        # Assert
        assert isinstance(result, list)
```

## Project Structure

```
crypto-trading-journal/
├── .devcontainer/          # Dev container configuration
│   ├── devcontainer.json   # Main dev container config
│   ├── Dockerfile          # Development container
│   └── docker-compose.yml  # Dev container services
├── .vscode/                # VS Code configuration
│   ├── settings.json       # Editor settings
│   ├── launch.json         # Debug configurations
│   └── tasks.json          # Build tasks
├── app/                    # Application source code
│   ├── main.py            # Streamlit entry point
│   ├── pages/             # Streamlit pages
│   ├── services/          # Business logic
│   ├── models/            # Data models
│   ├── integrations/      # Exchange integrations
│   └── utils/             # Utilities and helpers
├── tests/                 # Test suite
│   ├── test_services/     # Service tests
│   ├── test_models/       # Model tests
│   ├── test_integrations/ # Integration tests
│   └── fixtures/          # Test fixtures
├── data/                  # Development data (gitignored)
├── docs/                  # Documentation
├── Makefile              # Development commands
├── setup-dev.sh          # Development setup script
└── requirements.txt      # Python dependencies
```

## Development Commands

### Make Targets

```bash
# Setup and Installation
make install              # Install dependencies
make dev                 # Setup development environment

# Testing
make test                # Run all tests
make test-unit           # Run unit tests only
make test-integration    # Run integration tests
make test-security       # Run security tests
make test-coverage       # Run tests with coverage

# Code Quality
make format              # Format code (black, isort)
make lint                # Lint code (flake8)
make type-check          # Type checking (mypy)
make pre-commit          # Run pre-commit hooks
make qa                  # Run full quality pipeline

# Docker
make build               # Build Docker images
make run                 # Run production environment
make run-dev             # Run development environment
make stop                # Stop containers
make logs                # View logs

# Utilities
make clean               # Clean temporary files
make backup              # Create data backup
make streamlit           # Run Streamlit directly
make jupyter             # Start Jupyter Lab
```

### VS Code Integration

#### Debug Configurations

- **Python: Streamlit App**: Debug the main Streamlit application
- **Python: Current File**: Debug the currently open Python file
- **Python: Pytest Current File**: Debug tests in the current file
- **Python: Pytest All Tests**: Debug all tests with coverage

#### Tasks

- **Run Streamlit App**: Start the application
- **Run Tests**: Execute test suite
- **Format Code**: Format with Black
- **Lint Code**: Run flake8 linting
- **Build Docker Image**: Build production image

#### Extensions

The dev container includes these VS Code extensions:
- Python language support
- Docker support
- YAML support
- GitHub Copilot (if available)
- Testing extensions

## Environment Variables

### Development Environment

```bash
# Required
PYTHONPATH=/workspace          # Python module path
DATA_PATH=/workspace/data      # Data storage path

# Optional
LOG_LEVEL=DEBUG               # Logging level
TZ=UTC                        # Timezone
```

### Configuration Files

- **`.env`**: Local environment variables (gitignored)
- **`data/config.json`**: Application configuration
- **`data/credentials.enc`**: Encrypted API credentials

## Debugging

### VS Code Debugging

1. Set breakpoints in your code
2. Use F5 or select a debug configuration
3. Use the debug console for interactive debugging

### Print Debugging

```python
import logging
logger = logging.getLogger(__name__)

# Debug logging
logger.debug(f"Variable value: {variable}")

# Streamlit debugging
import streamlit as st
st.write("Debug info:", variable)
```

### Docker Debugging

```bash
# Access running container
docker-compose exec trading-journal-dev bash

# View container logs
docker-compose logs -f trading-journal-dev

# Inspect container
docker inspect crypto-trading-journal-dev
```

## Performance Optimization

### Development Performance

- Use `--server.runOnSave=true` for hot reload
- Enable `--server.fileWatcherType=poll` for better file watching
- Use `st.cache_data` for expensive computations
- Profile with `cProfile` for performance bottlenecks

### Testing Performance

- Use `pytest-xdist` for parallel test execution
- Mock external dependencies in unit tests
- Use fixtures to avoid repeated setup
- Run specific test categories during development

## Contributing Guidelines

### Code Style

- Follow PEP 8 with 88-character line length
- Use type hints for all function parameters and returns
- Write docstrings for all public functions and classes
- Use descriptive variable and function names

### Commit Messages

Follow conventional commit format:
```
type(scope): description

feat(auth): add API key encryption
fix(ui): resolve chart rendering issue
docs(readme): update installation instructions
test(services): add data service tests
```

### Pull Request Process

1. Create feature branch from main
2. Make changes with tests
3. Ensure all quality checks pass
4. Update documentation if needed
5. Submit pull request with description

### Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No security vulnerabilities
- [ ] Performance impact considered
- [ ] Backward compatibility maintained

## Troubleshooting Development Issues

### Common Issues

#### Import Errors
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=/workspace
# Or add to your shell profile
echo 'export PYTHONPATH=/workspace' >> ~/.bashrc
```

#### Port Conflicts
```bash
# Check what's using the port
lsof -i :8501
# Kill the process or use different port
streamlit run app/main.py --server.port=8502
```

#### Permission Issues
```bash
# Fix data directory permissions
chmod 755 data/
# Fix file permissions
find . -name "*.py" -exec chmod 644 {} \;
```

#### Docker Issues
```bash
# Clean Docker cache
docker system prune -af
# Rebuild without cache
docker-compose build --no-cache
```

### Getting Help

1. Check the logs for error messages
2. Verify environment setup
3. Run diagnostic commands
4. Check GitHub issues for similar problems
5. Ask for help with specific error messages

---

**Happy coding!** The development environment is designed to be productive and enjoyable. If you encounter any issues or have suggestions for improvements, please let us know.