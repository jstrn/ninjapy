#!/usr/bin/env python3
"""
Version bumping script for ninjapy package.

This script helps with version management, git tagging, and release preparation.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

# Use plain text on Windows to avoid Unicode issues
if os.name == 'nt':
    STEP_PREFIX = "[STEP]"
    SUCCESS_PREFIX = "[OK]"
    WARNING_PREFIX = "[WARN]"
    ERROR_PREFIX = "[ERROR]"
else:
    STEP_PREFIX = "🔢"
    SUCCESS_PREFIX = "✅"
    WARNING_PREFIX = "⚠️"
    ERROR_PREFIX = "❌"

def print_step(message: str) -> None:
    """Print a step message with formatting."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{STEP_PREFIX} {message}{Colors.END}")

def print_success(message: str) -> None:
    """Print a success message with formatting."""
    print(f"{Colors.GREEN}{SUCCESS_PREFIX} {message}{Colors.END}")

def print_warning(message: str) -> None:
    """Print a warning message with formatting."""
    print(f"{Colors.YELLOW}{WARNING_PREFIX} {message}{Colors.END}")

def print_error(message: str) -> None:
    """Print an error message with formatting."""
    print(f"{Colors.RED}{ERROR_PREFIX} {message}{Colors.END}")

def run_command(cmd: list, capture_output: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        result = subprocess.run(cmd, capture_output=capture_output, text=True, check=check)
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {' '.join(cmd)}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        raise

def get_current_version() -> str:
    """Get the current version from pyproject.toml."""
    try:
        import tomllib
    except ImportError:
        # Fallback for Python < 3.11
        try:
            import tomli as tomllib
        except ImportError:
            print_error("tomllib/tomli not available. Install with: pip install tomli")
            sys.exit(1)
    
    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    
    return pyproject["project"]["version"]

def parse_version(version: str) -> Tuple[int, int, int, str]:
    """Parse a semantic version string."""
    # Match pattern: major.minor.patch[-prerelease]
    pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$'
    match = re.match(pattern, version)
    
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    
    major, minor, patch, prerelease = match.groups()
    return int(major), int(minor), int(patch), prerelease or ""

def format_version(major: int, minor: int, patch: int, prerelease: str = "") -> str:
    """Format version components into a version string."""
    version = f"{major}.{minor}.{patch}"
    if prerelease:
        version += f"-{prerelease}"
    return version

def bump_version(current: str, bump_type: str, prerelease: str = "") -> str:
    """Bump version according to type."""
    major, minor, patch, current_prerelease = parse_version(current)
    
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
        prerelease = ""
    elif bump_type == "minor":
        minor += 1
        patch = 0
        prerelease = ""
    elif bump_type == "patch":
        patch += 1
        prerelease = ""
    elif bump_type == "prerelease":
        if not current_prerelease and not prerelease:
            # If no current prerelease and none specified, bump patch and add rc1
            patch += 1
            prerelease = "rc1"
        elif current_prerelease:
            # Bump existing prerelease
            if current_prerelease.startswith("rc"):
                rc_num = int(current_prerelease[2:]) + 1
                prerelease = f"rc{rc_num}"
            elif current_prerelease.startswith("beta"):
                beta_num = int(current_prerelease[4:]) + 1
                prerelease = f"beta{beta_num}"
            elif current_prerelease.startswith("alpha"):
                alpha_num = int(current_prerelease[5:]) + 1
                prerelease = f"alpha{alpha_num}"
            else:
                prerelease = current_prerelease
        else:
            # Use specified prerelease
            pass
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")
    
    return format_version(major, minor, patch, prerelease)

def update_version_in_files(new_version: str) -> None:
    """Update version in project files."""
    print_step(f"Updating version to {new_version}")
    
    # Update pyproject.toml
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()
    
    # Update version line
    content = re.sub(
        r'^version = "[^"]*"',
        f'version = "{new_version}"',
        content,
        flags=re.MULTILINE
    )
    
    pyproject_path.write_text(content)
    print_success("Updated pyproject.toml")
    
    # Update __init__.py
    init_path = Path("ninjapy/__init__.py")
    if init_path.exists():
        content = init_path.read_text()
        content = re.sub(
            r'^__version__ = "[^"]*"',
            f'__version__ = "{new_version}"',
            content,
            flags=re.MULTILINE
        )
        init_path.write_text(content)
        print_success("Updated ninjapy/__init__.py")

def check_git_status() -> bool:
    """Check if git working directory is clean."""
    try:
        result = run_command(["git", "status", "--porcelain"])
        return len(result.stdout.strip()) == 0
    except subprocess.CalledProcessError:
        return False

def create_git_tag(version: str, sign: bool = False) -> None:
    """Create a git tag for the version."""
    print_step(f"Creating git tag v{version}")
    
    # Add and commit version changes
    run_command(["git", "add", "pyproject.toml", "ninjapy/__init__.py"])
    run_command(["git", "commit", "-m", f"Bump version to {version}"])
    
    # Create tag
    tag_cmd = ["git", "tag"]
    if sign:
        tag_cmd.append("-s")
    tag_cmd.extend([f"v{version}", "-m", f"Release v{version}"])
    
    run_command(tag_cmd)
    print_success(f"Created tag v{version}")

def push_changes(push_tags: bool = True) -> None:
    """Push changes and tags to remote."""
    print_step("Pushing changes to remote")
    
    run_command(["git", "push"])
    print_success("Pushed commits")
    
    if push_tags:
        run_command(["git", "push", "--tags"])
        print_success("Pushed tags")

def update_changelog(version: str) -> None:
    """Update CHANGELOG.md with new version."""
    changelog_path = Path("CHANGELOG.md")
    
    if not changelog_path.exists():
        print_warning("CHANGELOG.md not found, creating basic template")
        changelog_content = f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [{version}] - {subprocess.run(['date', '+%Y-%m-%d'], capture_output=True, text=True).stdout.strip()}

### Added
- Initial release
"""
    else:
        content = changelog_path.read_text()
        # Insert new version after [Unreleased]
        date = subprocess.run(['date', '+%Y-%m-%d'], capture_output=True, text=True).stdout.strip()
        new_entry = f"\n## [{version}] - {date}\n\n### Added\n- \n\n### Changed\n- \n\n### Fixed\n- \n"
        
        content = re.sub(
            r'(## \[Unreleased\])\n',
            f'\\1\n{new_entry}',
            content
        )
        changelog_content = content
    
    changelog_path.write_text(changelog_content)
    print_success("Updated CHANGELOG.md")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Bump package version")
    parser.add_argument(
        "bump_type",
        choices=["major", "minor", "patch", "prerelease"],
        help="Type of version bump"
    )
    parser.add_argument(
        "--prerelease",
        help="Prerelease identifier (e.g., rc1, beta1, alpha1)"
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Don't create git commit and tag"
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Don't push changes to remote"
    )
    parser.add_argument(
        "--sign",
        action="store_true",
        help="Sign the git tag"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    current_version = get_current_version()
    new_version = bump_version(current_version, args.bump_type, args.prerelease or "")
    
    print(f"{Colors.BOLD}🚀 Version Bump: {current_version} → {new_version}{Colors.END}")
    
    if args.dry_run:
        print_warning("DRY RUN - No changes will be made")
        print(f"Would update version from {current_version} to {new_version}")
        return
    
    # Check git status
    if not args.no_git and not check_git_status():
        print_error("Git working directory is not clean")
        sys.exit(1)
    
    # Update version in files
    update_version_in_files(new_version)
    
    # Update changelog
    update_changelog(new_version)
    
    # Git operations
    if not args.no_git:
        create_git_tag(new_version, args.sign)
        
        if not args.no_push:
            if input("Push changes to remote? (y/N): ").lower().startswith('y'):
                push_changes()
            else:
                print_warning("Skipped pushing to remote")
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Successfully bumped version to {new_version}!{Colors.END}")
    print(f"\nNext steps:")
    print(f"  1. Review CHANGELOG.md and add details about changes")
    print(f"  2. Push changes: git push && git push --tags")
    print(f"  3. Publish to TestPyPI: make publish-test")
    print(f"  4. Publish to PyPI: make publish-prod")

if __name__ == "__main__":
    main() 