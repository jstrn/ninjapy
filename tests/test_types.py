"""Tests for TypedDict type definitions."""

from ninjapy.types import (
    AssetTag,
    CustomFieldCondition,
    Device,
    NotificationChannel,
    Organization,
    PolicyConditionScript,
    TagUser,
)


def test_type_definitions_are_usable():
    org: Organization = {"id": 1, "name": "Example Org"}
    device: Device = {
        "id": 1,
        "organizationId": 1,
        "locationId": None,
        "nodeClass": "WINDOWS_WORKSTATION",
        "nodeRoleId": None,
        "policyId": None,
        "approvalStatus": "APPROVED",
        "offline": False,
        "displayName": "Workstation",
        "systemName": "WS-1",
        "created": 1.0,
        "lastContact": 2.0,
        "lastUpdate": 3.0,
    }
    condition: CustomFieldCondition = {
        "fieldName": "status",
        "operator": "EQUALS",
        "value": "active",
    }
    script: PolicyConditionScript = {
        "scriptId": 1,
        "runAs": "SYSTEM",
        "scriptParam": None,
        "scriptVariables": [],
    }
    channel: NotificationChannel = {
        "id": 1,
        "name": "Email",
        "description": None,
        "enabled": True,
        "type": "EMAIL",
    }
    tag_user: TagUser = {"id": 1, "name": "Admin", "email": "admin@example.com"}
    tag: AssetTag = {"id": 1, "name": "Production", "createdBy": tag_user}

    assert org["name"] == "Example Org"
    assert device["systemName"] == "WS-1"
    assert condition["operator"] == "EQUALS"
    assert script["runAs"] == "SYSTEM"
    assert channel["enabled"] is True
    assert tag["createdBy"]["email"] == "admin@example.com"
