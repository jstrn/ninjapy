"""Tests for public enum definitions."""

from ninjapy.enums import (
    InstallerType,
    NodeApprovalMode,
    Priority,
    Severity,
    TagMergeMethod,
)


def test_node_approval_mode_values():
    assert NodeApprovalMode.AUTOMATIC.value == "AUTOMATIC"
    assert NodeApprovalMode.MANUAL.value == "MANUAL"
    assert NodeApprovalMode.REJECT.value == "REJECT"


def test_severity_values():
    assert Severity.CRITICAL.value == "CRITICAL"
    assert len(Severity) == 5


def test_priority_values():
    assert Priority.HIGH.value == "HIGH"
    assert Priority.NONE.value == "NONE"


def test_installer_type_values():
    assert InstallerType.WINDOWS_MSI.value == "WINDOWS_MSI"
    assert InstallerType.LINUX_RPM.value == "LINUX_RPM"


def test_tag_merge_method_values():
    assert TagMergeMethod.MERGE_INTO_EXISTING_TAG.value == "MERGE_INTO_EXISTING_TAG"
    assert TagMergeMethod.MERGE_INTO_NEW_TAG.value == "MERGE_INTO_NEW_TAG"
