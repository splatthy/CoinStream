#!/bin/bash

# Crypto Trading Journal - Development Setup Script
# This script sets up the development environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.11 or later."
        exit 1
    fi
    
    if ! command_exists pip; then
        print_error "pip is not installed. Please install pip."
        exit 1
    fi
    
    # Check Python version
    PYTHON_VERSION=$(python3 --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
    REQUIRED_VERSION="3.11"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        print_warning "Python version $PYTHON_VERSION detected. Python 3.11+ recommended."
    fi
    
    print_success "Prerequisites check passed"
}

# Setup virtual environment
setup_venv() {
    print_status "Setting up virtual environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_warning "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    
    print_success "Virtual environment setup completed"
}

# Install dependencies
install_dependencies() {
    print_status "Installing dependencies..."
    
    # Install main dependencies
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_success "Main dependencies installed"
    else
        print_error "requirements.txt not found"
        exit 1
    fi
    
    # Install development dependencies
    pip install \
        black \
        flake8 \
        mypy \
        isort \
        pytest \
        pytest-cov \
        pytest-mock \
        pre-commit \
        jupyter \
        ipython \
        debugpy
    
    print_success "Development dependencies installed"
}

# Setup directories
setup_directories() {
    print_status "Setting up directories..."
    
    # Create data directory if it doesn't exist
    if [ ! -d "data" ]; then
        mkdir -p data
        touch data/.gitkeep
        print_success "Created data directory"
    else
        print_warning "Data directory already exists"
    fi
    
    # Set proper permissions
    chmod 755 data
    
    print_success "Directory setup completed"
}

# Setup pre-commit hooks
setup_precommit() {
    print_status "Setting up pre-commit hooks..."
    
    # Copy pre-commit config if it doesn't exist
    if [ ! -f ".pre-commit-config.yaml" ] && [ -f ".devcontainer/pre-commit-config.yaml" ]; then
        cp .devcontainer/pre-commit-config.yaml .pre-commit-config.yaml
        print_success "Pre-commit config copied"
    fi
    
    # Install pre-commit hooks
    if command_exists pre-commit; then
        pre-commit install
        print_success "Pre-commit hooks installed"
    else
        print_warning "pre-commit not available, skipping hook installation"
    fi
}

# Setup IDE configuration
setup_ide() {
    print_status "Setting up IDE configuration..."
    
    # Create .vscode directory if it doesn't exist
    if [ ! -d ".vscode" ]; then
        mkdir -p .vscode
    fi
    
    # Copy VS Code settings if they don't exist
    if [ ! -f ".vscode/settings.json" ] && [ -f ".vscode/settings.json" ]; then
        print_success "VS Code settings already configured"
    else
        print_warning "VS Code settings not found, using defaults"
    fi
    
    print_success "IDE configuration completed"
}

# Run initial tests
run_tests() {
    print_status "Running initial tests..."
    
    if command_exists pytest; then
        # Run a quick test to ensure everything is working
        python -m pytest tests/ -v --tb=short -x
        print_success "Initial tests passed"
    else
        print_warning "pytest not available, skipping tests"
    fi
}

# Display setup summary
show_summary() {
    print_status "Development Environment Setup Summary:"
    echo ""
    echo "✅ Virtual environment: venv/"
    echo "✅ Dependencies installed"
    echo "✅ Data directory: data/"
    echo "✅ Pre-commit hooks configured"
    echo "✅ IDE configuration ready"
    echo ""
    print_success "Development environment setup completed!"
    echo ""
    echo "To activate the environment:"
    echo "  source venv/bin/activate"
    echo ""
    echo "To start development:"
    echo "  make run-dev          # Start development server"
    echo "  make test             # Run tests"
    echo "  make streamlit        # Run Streamlit directly"
    echo ""
    echo "Available make targets:"
    echo "  make help             # Show all available commands"
    echo "  make test             # Run tests"
    echo "  make format           # Format code"
    echo "  make lint             # Lint code"
    echo "  make qa               # Run quality assurance pipeline"
    echo ""
}

# Cleanup function
cleanup() {
    print_status "Cleaning up development environment..."
    
    # Remove virtual environment
    if [ -d "venv" ]; then
        rm -rf venv
        print_success "Virtual environment removed"
    fi
    
    # Remove pre-commit hooks
    if [ -f ".git/hooks/pre-commit" ]; then
        pre-commit uninstall
        print_success "Pre-commit hooks removed"
    fi
    
    # Clean Python cache
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    find . -type d -name ".pytest_cache" -delete
    rm -rf htmlcov/
    rm -rf .coverage
    
    print_success "Cleanup completed"
}

# Main function
main() {
    echo "=============================================="
    echo "  Crypto Trading Journal - Development Setup  "
    echo "=============================================="
    echo ""
    
    case "${1:-}" in
        --cleanup)
            cleanup
            ;;
        --help)
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Options:"
            echo "  (no option)    Full development setup"
            echo "  --cleanup      Clean up development environment"
            echo "  --help         Show this help message"
            echo ""
            ;;
        *)
            check_prerequisites
            setup_venv
            install_dependencies
            setup_directories
            setup_precommit
            setup_ide
            run_tests
            show_summary
            ;;
    esac
}

# Run main function with all arguments
main "$@"