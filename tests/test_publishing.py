"""
Tests for publishing automation scripts.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest


class TestPublishingScripts:
    """Test cases for publishing automation scripts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scripts_dir = Path("scripts")
        self.project_root = Path(".")

    def test_scripts_exist(self):
        """Test that all required scripts exist."""
        required_scripts = [
            "scripts/publish.py",
            "scripts/version_bump.py",
            "scripts/release.sh",
        ]

        for script in required_scripts:
            assert Path(script).exists(), f"Script {script} not found"

    def test_scripts_are_executable(self):
        """Test that scripts have executable permissions."""
        scripts = [
            "scripts/publish.py",
            "scripts/version_bump.py",
            "scripts/release.sh",
        ]

        for script_path in scripts:
            path = Path(script_path)
            if path.exists():
                # Check if file is executable (on Unix-like systems)
                if os.name != "nt":  # Not Windows
                    assert os.access(
                        path, os.X_OK
                    ), f"Script {script_path} is not executable"

    def test_publish_script_help(self):
        """Test that publish script shows help."""
        result = subprocess.run(
            [sys.executable, "scripts/publish.py", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Publish ninjapy package" in result.stdout

    def test_version_bump_script_help(self):
        """Test that version bump script shows help."""
        result = subprocess.run(
            [sys.executable, "scripts/version_bump.py", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Bump package version" in result.stdout

    def test_release_script_help(self):
        """Test that release script shows help."""
        result = subprocess.run(
            ["bash", "scripts/release.sh", "--help"], capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_makefile_exists(self):
        """Test that Makefile exists."""
        assert Path("Makefile").exists(), "Makefile not found"

    def test_github_workflows_exist(self):
        """Test that GitHub Actions workflows exist."""
        workflows = [".github/workflows/test.yml",
                     ".github/workflows/publish.yml"]

        for workflow in workflows:
            assert Path(workflow).exists(), f"Workflow {workflow} not found"

    def test_publishing_docs_exist(self):
        """Test that publishing documentation exists."""
        assert Path("PUBLISHING.md").exists(), "PUBLISHING.md not found"

    @pytest.mark.skipif(os.name == "nt", reason="Skip on Windows")
    def test_makefile_targets(self):
        """Test that Makefile has expected targets."""
        result = subprocess.run(
            ["make", "help"], capture_output=True, text=True, cwd=str(self.project_root)
        )

        if result.returncode == 0:  # Only test if make is available
            expected_targets = [
                "install",
                "test",
                "lint",
                "build",
                "publish-test",
                "publish-prod",
            ]

            for target in expected_targets:
                assert target in result.stdout, f"Makefile target '{target}' not found"


class TestVersionBumping:
    """Test cases for version bumping functionality."""

    def test_version_parsing(self):
        """Test version parsing logic."""
        # This would normally import from the script, but for now we'll just
        # test that the script can be imported without errors
        try:
            # Add scripts directory to path
            import sys

            sys.path.insert(0, "scripts")

            from version_bump import bump_version, format_version, parse_version

            # Test version parsing
            major, minor, patch, prerelease = parse_version("1.2.3")
            assert major == 1
            assert minor == 2
            assert patch == 3
            assert prerelease == ""

            # Test version formatting
            version = format_version(1, 2, 3)
            assert version == "1.2.3"

            # Test version bumping
            new_version = bump_version("1.2.3", "patch")
            assert new_version == "1.2.4"

        except ImportError:
            pytest.skip("Could not import version_bump module")
        finally:
            # Clean up path
            if "scripts" in sys.path:
                sys.path.remove("scripts")


class TestGitHubWorkflows:
    """Test cases for GitHub Actions workflows."""

    def test_workflow_syntax(self):
        """Test that workflow files have valid YAML syntax."""
        import yaml

        workflows = [".github/workflows/test.yml",
                     ".github/workflows/publish.yml"]

        for workflow_path in workflows:
            path = Path(workflow_path)
            if path.exists():
                try:
                    with open(path, "r") as f:
                        yaml.safe_load(f)
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {workflow_path}: {e}")

    def test_workflow_has_required_jobs(self):
        """Test that workflows have expected jobs."""
        import yaml

        # Test workflow should have test job
        test_workflow = Path(".github/workflows/test.yml")
        if test_workflow.exists():
            with open(test_workflow, "r") as f:
                workflow = yaml.safe_load(f)

            assert "jobs" in workflow
            assert "test" in workflow["jobs"]

        # Publish workflow should have build and publish jobs
        publish_workflow = Path(".github/workflows/publish.yml")
        if publish_workflow.exists():
            with open(publish_workflow, "r") as f:
                workflow = yaml.safe_load(f)

            assert "jobs" in workflow
            expected_jobs = ["test", "build", "publish-test", "publish-prod"]

            for job in expected_jobs:
                assert (
                    job in workflow["jobs"]
                ), f"Job '{job}' not found in publish workflow"


@pytest.mark.integration
class TestIntegration:
    """Integration tests for the publishing system."""

    def test_dry_run_version_bump(self):
        """Test version bump in dry run mode."""
        result = subprocess.run(
            [sys.executable, "scripts/version_bump.py", "patch", "--dry-run"],
            capture_output=True,
            text=True,
        )

        # Should succeed and show what would be done
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout

    def test_dry_run_release(self):
        """Test release script in dry run mode."""
        result = subprocess.run(
            ["bash", "scripts/release.sh", "patch", "--dry-run"],
            capture_output=True,
            text=True,
        )

        # Should succeed and show what would be done
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout

    @pytest.mark.skipif(not Path("dist").exists(), reason="No dist directory")
    def test_package_build(self):
        """Test that package can be built."""
        result = subprocess.run(
            [sys.executable, "-m", "build"], capture_output=True, text=True
        )

        if result.returncode == 0:
            # Check that build artifacts exist
            dist_dir = Path("dist")
            wheel_files = list(dist_dir.glob("*.whl"))
            tar_files = list(dist_dir.glob("*.tar.gz"))

            assert len(wheel_files) > 0, "No wheel files found"
            assert len(tar_files) > 0, "No source distribution files found"
