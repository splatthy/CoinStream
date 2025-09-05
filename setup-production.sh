#!/bin/bash

# Crypto Trading Journal - Production Setup Script
# This script sets up the production environment for the trading journal application

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
    
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check Docker version
    DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
    REQUIRED_VERSION="20.10"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$DOCKER_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        print_error "Docker version $DOCKER_VERSION is too old. Please upgrade to $REQUIRED_VERSION or later."
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Create necessary directories
setup_directories() {
    print_status "Setting up directories..."
    
    # Create data directory if it doesn't exist
    if [ ! -d "data" ]; then
        mkdir -p data
        print_success "Created data directory"
    else
        print_warning "Data directory already exists"
    fi
    
    # Set proper permissions
    chmod 755 data
    
    # Create .gitkeep if it doesn't exist
    if [ ! -f "data/.gitkeep" ]; then
        touch data/.gitkeep
    fi
    
    print_success "Directory setup completed"
}

# Build Docker image
build_image() {
    print_status "Building Docker image..."
    
    if docker-compose -f docker-compose.prod.yml build; then
        print_success "Docker image built successfully"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
}

# Start services
start_services() {
    print_status "Starting services..."
    
    if docker-compose -f docker-compose.prod.yml up -d; then
        print_success "Services started successfully"
    else
        print_error "Failed to start services"
        exit 1
    fi
}

# Wait for health check
wait_for_health() {
    print_status "Waiting for application to be healthy..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f docker-compose.prod.yml ps | grep -q "healthy"; then
            print_success "Application is healthy and ready"
            return 0
        fi
        
        print_status "Attempt $attempt/$max_attempts - waiting for health check..."
        sleep 10
        attempt=$((attempt + 1))
    done
    
    print_error "Application failed to become healthy within expected time"
    print_status "Checking logs..."
    docker-compose -f docker-compose.prod.yml logs --tail=20
    exit 1
}

# Display status
show_status() {
    print_status "Application Status:"
    docker-compose -f docker-compose.prod.yml ps
    
    echo ""
    print_success "Setup completed successfully!"
    echo ""
    echo "Application is available at: http://localhost:8501"
    echo ""
    echo "Useful commands:"
    echo "  View logs:    docker-compose -f docker-compose.prod.yml logs -f"
    echo "  Stop app:     docker-compose -f docker-compose.prod.yml down"
    echo "  Restart app:  docker-compose -f docker-compose.prod.yml restart"
    echo "  Update app:   ./setup-production.sh --update"
    echo ""
}

# Update existing installation
update_installation() {
    print_status "Updating installation..."
    
    # Stop services
    print_status "Stopping services..."
    docker-compose -f docker-compose.prod.yml down
    
    # Rebuild image
    build_image
    
    # Start services
    start_services
    
    # Wait for health
    wait_for_health
    
    print_success "Update completed successfully"
}

# Cleanup function
cleanup() {
    print_status "Cleaning up Docker resources..."
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes (be careful with this)
    if [ "$1" = "--full" ]; then
        print_warning "Performing full cleanup including volumes..."
        docker system prune -af --volumes
    else
        docker system prune -af
    fi
    
    print_success "Cleanup completed"
}

# Main function
main() {
    echo "=============================================="
    echo "  Crypto Trading Journal - Production Setup  "
    echo "=============================================="
    echo ""
    
    case "${1:-}" in
        --update)
            check_prerequisites
            update_installation
            show_status
            ;;
        --cleanup)
            cleanup
            ;;
        --cleanup-full)
            cleanup --full
            ;;
        --help)
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Options:"
            echo "  (no option)    Full setup - check prerequisites, build, and start"
            echo "  --update       Update existing installation"
            echo "  --cleanup      Clean up unused Docker resources"
            echo "  --cleanup-full Clean up all unused Docker resources including volumes"
            echo "  --help         Show this help message"
            echo ""
            ;;
        *)
            check_prerequisites
            setup_directories
            build_image
            start_services
            wait_for_health
            show_status
            ;;
    esac
}

# Run main function with all arguments
main "$@"