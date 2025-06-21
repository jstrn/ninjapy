# Makefile for ninjapy development and publishing

.PHONY: help install install-dev test lint format clean build publish-test publish-prod check-package docs

# Default target
help:
	@echo "Available targets:"
	@echo "  help           Show this help message"
	@echo "  install        Install package in current environment"
	@echo "  install-dev    Install package with development dependencies"
	@echo "  test           Run tests"
	@echo "  test-cov       Run tests with coverage"
	@echo "  lint           Run all linting and type checking"
	@echo "  format         Format code with black and isort"
	@echo "  clean          Clean build artifacts"
	@echo "  build          Build package"
	@echo "  check-package  Check built package"
	@echo "  publish-test   Publish to TestPyPI (interactive)"
	@echo "  publish-prod   Publish to PyPI (interactive)"
	@echo "  docs           Build documentation"
	@echo "  version        Show current version"

# Installation targets
install:
	pip install -e .

install-dev:
	pip install -e .[dev,test,docs]

# Testing targets
test:
	pytest -v

test-cov:
	pytest -v --cov=ninjapy --cov-report=term-missing --cov-report=html

# Linting and formatting targets
lint:
	flake8 ninjapy tests
	mypy ninjapy
	black --check ninjapy tests
	isort --check-only ninjapy tests

format:
	black ninjapy tests
	isort ninjapy tests

# Security checks
security:
	bandit -r ninjapy
	safety check

# Build targets
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

check-package: build
	twine check dist/*
	pip install --force-reinstall dist/*.whl
	python -c "import ninjapy; print(f'Successfully imported ninjapy v{ninjapy.__version__}')"

# Publishing targets (using the Python script)
publish-test:
	python scripts/publish.py test

publish-prod:
	python scripts/publish.py prod

# Quick publish targets with automation
auto-publish-test:
	python scripts/publish.py test --clean --skip-git-check

auto-publish-prod:
	python scripts/publish.py prod --clean

# Documentation targets
docs:
	@echo "Building documentation..."
	@echo "Note: Documentation setup not yet implemented"

# Version management
version:
	@python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"

# Development workflow
dev-setup: install-dev
	pre-commit install

# Full CI-like check
ci-check: lint test security check-package
	@echo "✅ All CI checks passed!"

# Pre-commit hook equivalent
pre-commit: format lint test
	@echo "✅ Pre-commit checks completed!" 