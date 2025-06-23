#!/usr/bin/env python3
"""
Publishing automation script for ninjapy package.

This script helps with building and publishing the package to PyPI repositories.
It can be used for both test (TestPyPI) and production (PyPI) publishing.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

# ANSI color codes for pretty output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_step(message: str) -> None:
    """Print a step message with formatting."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}📦 {message}{Colors.END}")

def print_success(message: str) -> None:
    """Print a success message with formatting."""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_warning(message: str) -> None:
    """Print a warning message with formatting."""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_error(message: str) -> None:
    """Print an error message with formatting."""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def run_command(cmd: List[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Run a command and handle errors."""
    print(f"  Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {' '.join(cmd)}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        raise

def get_version() -> str:
    """Get the current version from pyproject.toml."""
    import tomllib
    
    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    
    return pyproject["project"]["version"]

def check_git_status() -> bool:
    """Check if git working directory is clean."""
    try:
        result = run_command(["git", "status", "--porcelain"], capture_output=True)
        return len(result.stdout.strip()) == 0
    except subprocess.CalledProcessError:
        print_warning("Could not check git status (not a git repository?)")
        return True

def check_dependencies() -> None:
    """Check if required dependencies are installed."""
    required_tools = ["build", "twine"]
    missing_tools = []
    
    for tool in required_tools:
        try:
            run_command([sys.executable, "-m", tool, "--version"], capture_output=True)
        except subprocess.CalledProcessError:
            missing_tools.append(tool)
    
    if missing_tools:
        print_error(f"Missing required tools: {', '.join(missing_tools)}")
        print("Install them with: pip install build twine")
        sys.exit(1)

def clean_dist() -> None:
    """Clean the dist directory."""
    print_step("Cleaning dist directory")
    
    dist_dir = Path("dist")
    if dist_dir.exists():
        import shutil
        shutil.rmtree(dist_dir)
        print_success("Cleaned dist directory")
    else:
        print_success("Dist directory doesn't exist")

def run_tests() -> None:
    """Run the test suite."""
    print_step("Running tests")
    
    try:
        run_command([sys.executable, "-m", "pytest", "-v"])
        print_success("All tests passed")
    except subprocess.CalledProcessError:
        print_error("Tests failed")
        if not input("Continue anyway? (y/N): ").lower().startswith('y'):
            sys.exit(1)

def run_linting() -> None:
    """Run linting and type checking."""
    print_step("Running linting and type checking")
    
    # Run flake8
    try:
        run_command([sys.executable, "-m", "flake8", "ninjapy", "tests"])
        print_success("Flake8 passed")
    except subprocess.CalledProcessError:
        print_warning("Flake8 found issues")
    
    # Run mypy
    try:
        run_command([sys.executable, "-m", "mypy", "ninjapy"])
        print_success("MyPy passed")
    except subprocess.CalledProcessError:
        print_warning("MyPy found issues")
    
    # Run black check
    try:
        run_command([sys.executable, "-m", "black", "--check", "ninjapy", "tests"])
        print_success("Black formatting check passed")
    except subprocess.CalledProcessError:
        print_warning("Black found formatting issues")

def build_package() -> None:
    """Build the package."""
    print_step("Building package")
    
    run_command([sys.executable, "-m", "build"])
    print_success("Package built successfully")

def check_package() -> None:
    """Check the built package."""
    print_step("Checking package")

    # Check with twine - twine handles the glob pattern
    run_command([sys.executable, "-m", "twine", "check", "dist/*"])

    # Test installation
    print("Testing package installation...")
    try:
        # We need to manually glob for pip, as it doesn't expand the wildcard
        # when not run in a shell.
        dist_dir = Path("dist")
        wheel_file = next(dist_dir.glob("*.whl"))
        run_command(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                str(wheel_file),
            ]
        )
    except StopIteration:
        print_error("Could not find a wheel file in dist/ to test installation.")
        sys.exit(1)

    # Test import
    result = run_command(
        [
            sys.executable,
            "-c",
            "import ninjapy; print(f'Successfully imported ninjapy v{ninjapy.__version__}')",
        ],
        capture_output=True,
    )
    print(result.stdout.strip())

    print_success("Package check completed")

def publish_package(repository: str) -> None:
    """Publish the package to a repository."""
    if repository == "test":
        repo_url = "https://test.pypi.org/legacy/"
        repo_name = "TestPyPI"
        env_var = "TEST_PYPI_API_TOKEN"
    else:
        repo_url = "https://upload.pypi.org/legacy/"
        repo_name = "PyPI"
        env_var = "PYPI_API_TOKEN"
    
    print_step(f"Publishing to {repo_name}")
    
    # Check for API token
    api_token = os.getenv(env_var)
    if not api_token:
        print_warning(f"No {env_var} environment variable found")
        api_token = input(f"Enter your {repo_name} API token: ").strip()
        if not api_token:
            print_error("No API token provided")
            sys.exit(1)
    
    # Publish
    cmd = [
        sys.executable, "-m", "twine", "upload",
        "--repository-url", repo_url,
        "--username", "__token__",
        "--password", api_token,
        "dist/*"
    ]
    
    run_command(cmd)
    print_success(f"Published to {repo_name}")
    
    # Test installation
    if repository == "test":
        print("Waiting for package to be available on TestPyPI...")
        time.sleep(30)
        try:
            run_command([
                sys.executable, "-m", "pip", "install", 
                "--index-url", "https://test.pypi.org/simple/",
                "--extra-index-url", "https://pypi.org/simple/",
                "--force-reinstall",
                "ninjapy"
            ])
            print_success("Test installation from TestPyPI successful")
        except subprocess.CalledProcessError:
            print_warning("Test installation from TestPyPI failed")
    else:
        print("Waiting for package to be available on PyPI...")
        time.sleep(60)
        try:
            run_command([
                sys.executable, "-m", "pip", "install", 
                "--force-reinstall",
                "ninjapy"
            ])
            print_success("Test installation from PyPI successful")
        except subprocess.CalledProcessError:
            print_warning("Test installation from PyPI failed")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Publish ninjapy package")
    parser.add_argument(
        "repository",
        choices=["test", "prod"],
        help="Repository to publish to (test=TestPyPI, prod=PyPI)"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running tests"
    )
    parser.add_argument(
        "--skip-lint",
        action="store_true", 
        help="Skip linting and type checking"
    )
    parser.add_argument(
        "--skip-git-check",
        action="store_true",
        help="Skip git status check"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean dist directory before building"
    )
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}🚀 Publishing ninjapy to {'TestPyPI' if args.repository == 'test' else 'PyPI'}{Colors.END}")
    print(f"Version: {get_version()}")
    
    # Pre-flight checks
    if not args.skip_git_check:
        if not check_git_status():
            print_warning("Git working directory is not clean")
            if not input("Continue anyway? (y/N): ").lower().startswith('y'):
                sys.exit(1)
    
    check_dependencies()
    
    # Clean if requested
    if args.clean:
        clean_dist()
    
    # Quality checks
    if not args.skip_lint:
        run_linting()
    
    if not args.skip_tests:
        run_tests()
    
    # Build and check
    build_package()
    check_package()
    
    # Confirm before publishing
    print(f"\n{Colors.YELLOW}📋 Ready to publish ninjapy v{get_version()} to {'TestPyPI' if args.repository == 'test' else 'PyPI'}{Colors.END}")
    
    if not input("Proceed with publishing? (y/N): ").lower().startswith('y'):
        print("Publishing cancelled")
        sys.exit(0)
    
    # Publish
    publish_package(args.repository)
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Successfully published ninjapy v{get_version()}!{Colors.END}")

if __name__ == "__main__":
    main() 