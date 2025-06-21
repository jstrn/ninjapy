# Publishing Automation Guide

This document describes the automated publishing system for the `ninjapy` package.

## Overview

The publishing automation includes:

- **GitHub Actions workflows** - Automated CI/CD pipelines
- **Python scripts** - Interactive publishing tools
- **Shell scripts** - End-to-end release automation
- **Makefile** - Quick development commands

## Quick Start

### For Test Publishing (TestPyPI)
```bash
# Using Makefile
make publish-test

# Using Python script directly
python scripts/publish.py test

# Using GitHub Actions (manual trigger)
# Go to Actions tab → "Build and Publish" → Run workflow → Select "test"
```

### For Production Publishing (PyPI)
```bash
# Using Makefile
make publish-prod

# Using Python script directly
python scripts/publish.py prod

# Using complete release automation
./scripts/release.sh patch
```

## Automated Workflows (GitHub Actions)

### 1. Test Workflow (`.github/workflows/test.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Daily scheduled runs (2 AM UTC)

**What it does:**
- Runs tests on multiple Python versions (3.8-3.12)
- Tests on multiple operating systems (Ubuntu, Windows, macOS)
- Performs linting and type checking
- Runs security checks (bandit, safety)
- Uploads coverage reports

### 2. Publish Workflow (`.github/workflows/publish.yml`)

**Triggers:**
- **TestPyPI publishing:**
  - Push to `main` branch
  - Manual workflow dispatch with "test" option
  - PRs with "test-publish" label
  
- **PyPI publishing:**
  - GitHub releases
  - Git tags starting with `v`
  - Manual workflow dispatch with "prod" option

**What it does:**
- Runs full test suite
- Builds the package
- Validates the package with `twine check`
- Publishes to TestPyPI/PyPI
- Tests installation from the repository
- Creates GitHub releases for tagged versions

## Scripts and Tools

### 1. Publishing Script (`scripts/publish.py`)

Interactive Python script for manual publishing:

```bash
# Publish to TestPyPI
python scripts/publish.py test

# Publish to PyPI
python scripts/publish.py prod

# Options:
# --skip-tests     Skip running tests
# --skip-lint      Skip linting
# --skip-git-check Skip git status check
# --clean          Clean dist directory first
```

**Features:**
- Pre-flight checks (git status, dependencies)
- Quality checks (linting, type checking, tests)
- Package building and validation
- Secure token handling (environment variables or prompts)
- Test installation verification

### 2. Version Bump Script (`scripts/version_bump.py`)

Automated version management:

```bash
# Bump patch version (0.1.0 → 0.1.1)
python scripts/version_bump.py patch

# Bump minor version (0.1.0 → 0.2.0)
python scripts/version_bump.py minor

# Bump major version (0.1.0 → 1.0.0)
python scripts/version_bump.py major

# Create prerelease (0.1.0 → 0.1.1-rc1)
python scripts/version_bump.py prerelease

# Options:
# --prerelease TEXT  Custom prerelease identifier
# --no-git          Don't create git commit/tag
# --no-push         Don't push to remote
# --sign            Sign the git tag
# --dry-run         Show what would be done
```

**Features:**
- Semantic versioning support
- Updates `pyproject.toml` and `__init__.py`
- Creates git commits and tags
- Updates `CHANGELOG.md`
- Handles prerelease versions (alpha, beta, rc)

### 3. Release Script (`scripts/release.sh`)

End-to-end release automation:

```bash
# Complete release process
./scripts/release.sh patch

# Options:
# --skip-tests     Skip running tests
# --skip-lint      Skip linting
# --force          Continue despite warnings
# --dry-run        Show what would be done
```

**Features:**
- Version bumping
- Quality checks
- Package building
- Publishing to TestPyPI → PyPI
- Git operations (commit, tag, push)

### 4. Makefile

Quick development commands:

```bash
# Development setup
make install-dev
make dev-setup

# Quality checks
make lint
make test
make security
make ci-check

# Publishing
make publish-test
make publish-prod
make auto-publish-test  # Skip some checks

# Utilities
make clean
make build
make version
```

## Setup Requirements

### 1. API Tokens

You need API tokens for publishing:

**TestPyPI:**
1. Go to https://test.pypi.org/manage/account/token/
2. Create a new token with scope "Entire account"
3. Set environment variable: `TEST_PYPI_API_TOKEN=pypi-...`

**PyPI:**
1. Go to https://pypi.org/manage/account/token/
2. Create a new token with scope "Entire account"
3. Set environment variable: `PYPI_API_TOKEN=pypi-...`

### 2. GitHub Secrets

For GitHub Actions, add these secrets to your repository:

- `TEST_PYPI_API_TOKEN` - TestPyPI API token
- `PYPI_API_TOKEN` - PyPI API token

Go to: Repository Settings → Secrets and variables → Actions

### 3. Development Dependencies

Install development dependencies:

```bash
pip install -e .[dev,test]
# or
make install-dev
```

## Publishing Workflows

### Development Workflow

1. **Make changes** to the code
2. **Run tests locally**: `make test`
3. **Test publish**: `make publish-test`
4. **Create PR** for review
5. **Merge to main** (triggers TestPyPI publish)

### Release Workflow

#### Option 1: Manual Release
```bash
# 1. Bump version and create tag
python scripts/version_bump.py patch

# 2. Edit CHANGELOG.md with release notes

# 3. Push changes
git push && git push --tags

# 4. Create GitHub release (triggers PyPI publish)
```

#### Option 2: Automated Release
```bash
# Complete release in one command
./scripts/release.sh patch
```

#### Option 3: GitHub Actions Manual Trigger
1. Go to Actions tab → "Build and Publish"
2. Click "Run workflow"
3. Select "prod" option
4. Click "Run workflow"

## Troubleshooting

### Common Issues

**"Package already exists"**
- You're trying to upload a version that already exists
- Bump the version number first

**"Invalid token"**
- Check your API token is correct
- Ensure token has proper permissions
- For TestPyPI, use TestPyPI token (not PyPI token)

**"Tests failed"**
- Fix the failing tests
- Or use `--skip-tests` flag (not recommended)

**"Git working directory not clean"**
- Commit your changes first
- Or use `--skip-git-check` flag

### Debug Mode

For detailed output:

```bash
# Python scripts with verbose output
python scripts/publish.py test --verbose

# GitHub Actions
# Check the workflow logs in the Actions tab
```

## Security Considerations

- **Never commit API tokens** to version control
- **Use environment variables** for sensitive data
- **Rotate tokens regularly**
- **Use least-privilege tokens** (project-specific when possible)
- **Monitor package downloads** for suspicious activity

## Integration with IDEs

### VS Code

Add these tasks to `.vscode/tasks.json`:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Publish to TestPyPI",
            "type": "shell",
            "command": "python",
            "args": ["scripts/publish.py", "test"],
            "group": "build"
        },
        {
            "label": "Run Tests",
            "type": "shell",
            "command": "make",
            "args": ["test"],
            "group": "test"
        }
    ]
}
```

## Monitoring and Maintenance

### Package Statistics
- **PyPI**: https://pypi.org/project/ninjapy/
- **TestPyPI**: https://test.pypi.org/project/ninjapy/
- **Download stats**: https://pypistats.org/packages/ninjapy

### Automated Maintenance
- **Daily test runs** ensure compatibility
- **Security scans** check for vulnerabilities
- **Dependency updates** via Dependabot (if configured)

## Contributing

When contributing to the publishing automation:

1. **Test changes thoroughly** on TestPyPI first
2. **Update documentation** if adding new features
3. **Follow semantic versioning** for changes
4. **Test across different environments** 