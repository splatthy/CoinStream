# Crypto Trading Journal - Development Makefile

.PHONY: help install dev test test-unit test-integration test-security test-coverage lint format type-check clean build run run-dev stop logs backup restore docs

# Default target
help:
	@echo "Crypto Trading Journal - Development Commands"
	@echo ""
	@echo "Setup Commands:"
	@echo "  install          Install development dependencies"
	@echo "  dev              Set up development environment"
	@echo ""
	@echo "Testing Commands:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-security    Run security tests only"
	@echo "  test-coverage    Run tests with coverage report"
	@echo ""
	@echo "Code Quality Commands:"
	@echo "  lint             Run linting (flake8)"
	@echo "  format           Format code (black, isort)"
	@echo "  type-check       Run type checking (mypy)"
	@echo "  pre-commit       Run pre-commit hooks"
	@echo ""
	@echo "Docker Commands:"
	@echo "  build            Build Docker images"
	@echo "  run              Run production environment"
	@echo "  run-dev          Run development environment"
	@echo "  stop             Stop all containers"
	@echo "  logs             View container logs"
	@echo ""
	@echo "Utility Commands:"
	@echo "  clean            Clean up temporary files"
	@echo "  backup           Create data backup"
	@echo "  restore          Restore from backup"
	@echo "  docs             Generate documentation"

# Setup Commands
install:
	pip install -r requirements.txt
	pip install black flake8 mypy isort pytest pytest-cov pytest-mock pre-commit

dev: install
	mkdir -p data
	pre-commit install
	@echo "Development environment ready!"

# Testing Commands
test:
	python -m pytest tests/ -v

test-unit:
	python -m pytest tests/ -v -k "not integration and not security"

test-integration:
	python -m pytest tests/ -v -k "integration"

test-security:
	python -m pytest tests/ -v -k "security"

test-coverage:
	python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/"

# Code Quality Commands
lint:
	flake8 app/ tests/ --max-line-length=88 --extend-ignore=E203,W503

format:
	black app/ tests/ --line-length=88
	isort app/ tests/ --profile=black

type-check:
	mypy app/ --ignore-missing-imports

pre-commit:
	pre-commit run --all-files

# Docker Commands
build:
	docker-compose build

run:
	./setup-production.sh

run-dev:
	docker-compose --profile dev up -d trading-journal-dev
	@echo "Development server running at http://localhost:8502"

stop:
	docker-compose down
	docker-compose -f docker-compose.prod.yml down

logs:
	docker-compose logs -f

logs-prod:
	docker-compose -f docker-compose.prod.yml logs -f

# Utility Commands
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/

backup:
	@if [ ! -d "data" ]; then echo "No data directory found"; exit 1; fi
	tar -czf backup-$$(date +%Y%m%d-%H%M%S).tar.gz data/
	@echo "Backup created: backup-$$(date +%Y%m%d-%H%M%S).tar.gz"

restore:
	@echo "Available backups:"
	@ls -la backup-*.tar.gz 2>/dev/null || echo "No backups found"
	@echo "To restore, run: tar -xzf backup-YYYYMMDD-HHMMSS.tar.gz"

docs:
	@echo "Documentation files:"
	@echo "  README.md - Main documentation"
	@echo "  USER_GUIDE.md - User guide"
	@echo "  DEPLOYMENT.md - Deployment guide"
	@echo "  TROUBLESHOOTING.md - Troubleshooting guide"
	@echo "  FEATURES.md - Feature documentation"
	@echo "  BITUNIX_API_SETUP.md - API setup guide"

# Development shortcuts
streamlit:
	streamlit run app/main.py --server.port=8501 --server.address=0.0.0.0

jupyter:
	jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root

# Quality assurance pipeline
qa: format lint type-check test-coverage
	@echo "Quality assurance pipeline completed!"

# CI/CD simulation
ci: install lint type-check test-coverage
	@echo "CI pipeline completed successfully!"