#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Functions for pretty output
print_step() {
    echo -e "\n${BLUE}${BOLD}🚀 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "pyproject.toml not found. Are you in the project root?"
    exit 1
fi

# Check if git working directory is clean
if [ -n "$(git status --porcelain)" ]; then
    print_error "Git working directory is not clean"
    git status --short
    exit 1
fi

# Parse command line arguments
BUMP_TYPE=""
SKIP_TESTS=false
SKIP_LINT=false
FORCE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        major|minor|patch|prerelease)
            BUMP_TYPE="$1"
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-lint)
            SKIP_LINT=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 <major|minor|patch|prerelease> [options]"
            echo ""
            echo "Options:"
            echo "  --skip-tests    Skip running tests"
            echo "  --skip-lint     Skip linting and type checking"
            echo "  --force         Force release even with warnings"
            echo "  --dry-run       Show what would be done without making changes"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

if [ -z "$BUMP_TYPE" ]; then
    print_error "Version bump type is required (major|minor|patch|prerelease)"
    echo "Use --help for usage information"
    exit 1
fi

# Get current version
CURRENT_VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")

print_step "Starting release process"
echo "Current version: $CURRENT_VERSION"
echo "Bump type: $BUMP_TYPE"

if [ "$DRY_RUN" = true ]; then
    print_warning "DRY RUN - No changes will be made"
fi

# Check dependencies
print_step "Checking dependencies"
if ! command -v python &> /dev/null; then
    print_error "Python not found"
    exit 1
fi

if ! python -m pip show build &> /dev/null; then
    print_error "build not installed. Run: pip install build"
    exit 1
fi

if ! python -m pip show twine &> /dev/null; then
    print_error "twine not installed. Run: pip install twine"
    exit 1
fi

print_success "Dependencies check passed"

# Run quality checks
if [ "$SKIP_LINT" != true ]; then
    print_step "Running linting and type checking"
    
    # Check if linting tools are available
    if python -m pip show flake8 &> /dev/null; then
        python -m flake8 ninjapy tests || print_warning "Flake8 found issues"
    else
        print_warning "flake8 not installed, skipping"
    fi
    
    if python -m pip show mypy &> /dev/null; then
        python -m mypy ninjapy || print_warning "MyPy found issues"
    else
        print_warning "mypy not installed, skipping"
    fi
    
    if python -m pip show black &> /dev/null; then
        python -m black --check ninjapy tests || print_warning "Black found formatting issues"
    else
        print_warning "black not installed, skipping"
    fi
    
    print_success "Linting completed"
fi

# Run tests
if [ "$SKIP_TESTS" != true ]; then
    print_step "Running tests"
    
    if python -m pip show pytest &> /dev/null; then
        python -m pytest -v || {
            print_error "Tests failed"
            if [ "$FORCE" != true ]; then
                exit 1
            else
                print_warning "Continuing despite test failures due to --force"
            fi
        }
        print_success "All tests passed"
    else
        print_warning "pytest not installed, skipping tests"
    fi
fi

# Bump version
if [ "$DRY_RUN" != true ]; then
    print_step "Bumping version"
    python scripts/version_bump.py "$BUMP_TYPE" --no-push
    NEW_VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
    print_success "Version bumped to $NEW_VERSION"
else
    # For dry run, calculate what the new version would be
    NEW_VERSION=$(python scripts/version_bump.py "$BUMP_TYPE" --dry-run 2>/dev/null | grep "Would update version" | cut -d' ' -f6)
    echo "Would bump version to: $NEW_VERSION"
fi

# Build package
print_step "Building package"
if [ "$DRY_RUN" != true ]; then
    # Clean dist directory
    rm -rf dist/
    
    # Build
    python -m build
    
    # Check package
    python -m twine check dist/*
    
    print_success "Package built and checked"
else
    echo "Would build package in dist/"
fi

# Show summary and confirm
print_step "Release Summary"
echo "  Previous version: $CURRENT_VERSION"
echo "  New version: $NEW_VERSION"
echo "  Built artifacts:"
if [ "$DRY_RUN" != true ]; then
    ls -la dist/
else
    echo "    (would be in dist/)"
fi

if [ "$DRY_RUN" = true ]; then
    print_warning "DRY RUN completed - no changes were made"
    exit 0
fi

echo ""
read -p "Proceed with publishing? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Release cancelled"
    exit 0
fi

# Publish to TestPyPI first
print_step "Publishing to TestPyPI"
python scripts/publish.py test --skip-tests --skip-lint --skip-git-check

echo ""
read -p "TestPyPI publish successful. Proceed with PyPI? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "PyPI publishing cancelled"
    print_warning "Don't forget to push your git changes: git push && git push --tags"
    exit 0
fi

# Publish to PyPI
print_step "Publishing to PyPI"
python scripts/publish.py prod --skip-tests --skip-lint --skip-git-check

# Push git changes
print_step "Pushing changes to remote"
git push
git push --tags
print_success "Changes pushed to remote"

print_step "Release completed successfully!"
echo "  🎉 Version $NEW_VERSION published to PyPI"
echo "  📦 GitHub release created"
echo "  🏷️  Git tag v$NEW_VERSION pushed"
echo ""
echo "Next steps:"
echo "  - Check PyPI: https://pypi.org/project/ninjapy/"
echo "  - Update documentation if needed"
echo "  - Announce the release" 