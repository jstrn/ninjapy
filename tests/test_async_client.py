"""Async client tests."""

from unittest.mock import AsyncMock, patch

import pytest
from aioresponses import aioresponses

from ninjapy.client import AsyncNinjaRMMClient
from tests.conftest import (
    get_request_url,
    mock_get,
    mock_patch,
    mock_post,
    mock_put,
    mock_delete,
    patch_valid_token,
    patch_valid_token_async,
)


@pytest.mark.asyncio
async def test_async_get_organizations(async_client, aioresponses):
    mock_get(
        aioresponses,
        "https://test.ninjarmm.com/v2/organizations",
        payload=[{"id": 1, "name": "Async Org"}],
        status=200,
    )

    with patch_valid_token_async(async_client):
        orgs = await async_client.get_organizations()

    assert orgs[0]["name"] == "Async Org"


@pytest.mark.asyncio
async def test_async_get_organization_uses_singular_detail_endpoint(
    async_client, aioresponses
):
    mock_get(
        aioresponses,
        "https://test.ninjarmm.com/v2/organization/1",
        payload={"id": 1, "name": "Async Org"},
        status=200,
    )

    with patch_valid_token_async(async_client):
        org = await async_client.get_organization(1)

    assert org["name"] == "Async Org"


@pytest.mark.asyncio
async def test_async_context_manager_closes_session(aioresponses, client_kwargs):
    with patch("ninjapy.client.AsyncTokenManager") as mock_cls:
        mock_cls.return_value.get_valid_token = AsyncMock(return_value="test_token")
        mock_cls.return_value.close = AsyncMock()

        async with AsyncNinjaRMMClient(**client_kwargs) as client:
            assert client is not None

        mock_cls.return_value.close.assert_called()


@pytest.mark.asyncio
async def test_async_iterator_pagination(async_client, aioresponses):
    mock_get(
        aioresponses,
        "https://test.ninjarmm.com/v2/organizations",
        payload=[{"id": 1, "name": "org1"}, {"id": 2, "name": "org2"}],
        status=200,
    )
    mock_get(
        aioresponses,
        "https://test.ninjarmm.com/v2/organizations",
        payload=[{"id": 3, "name": "org3"}],
        status=200,
    )

    with patch_valid_token_async(async_client):
        items = [
            item async for item in async_client.iter_all_organizations(page_size=2)
        ]

    assert len(items) == 3


@pytest.mark.asyncio
async def test_get_devices_by_org_specific_orgs(async_client, aioresponses):
    base_url = async_client.base_url
    mock_get(
        aioresponses,
        f"{base_url}/v2/devices-detailed",
        payload=[{"id": 1, "organizationId": 9}],
        status=200,
        repeat=True,
    )

    with patch_valid_token_async(async_client):
        devices = await async_client.get_devices_by_org(
            org_ids=[9, 32],
            max_concurrency=2,
        )

    assert len(devices) == 2
    assert all(isinstance(device, dict) for device in devices)
    assert all(device["id"] == 1 for device in devices)


@pytest.mark.asyncio
async def test_get_devices_by_org_all_orgs(async_client, aioresponses):
    base_url = async_client.base_url
    mock_get(
        aioresponses,
        f"{base_url}/v2/organizations",
        payload=[{"id": 9, "name": "Org A"}, {"id": 32, "name": "Org B"}],
        status=200,
    )
    mock_get(
        aioresponses,
        f"{base_url}/v2/devices-detailed",
        payload=[{"id": 1, "organizationId": 9}],
        status=200,
        repeat=True,
    )

    with patch_valid_token_async(async_client):
        devices = await async_client.get_devices_by_org(max_concurrency=2)

    assert len(devices) == 2
    assert all(device["id"] == 1 for device in devices)


def test_get_devices_by_org_sync_wrapper(client, aioresponses):
    base_url = client.base_url
    mock_get(
        aioresponses,
        f"{base_url}/v2/devices-detailed",
        payload=[{"id": 1, "organizationId": 9}],
        status=200,
        repeat=True,
    )

    with patch_valid_token(client):
        devices = client.get_devices_by_org(org_ids=[9], max_concurrency=1)

    assert devices == [{"id": 1, "organizationId": 9}]


@pytest.mark.asyncio
async def test_get_organizations_by_org(async_client, aioresponses):
    base_url = async_client.base_url
    mock_get(
        aioresponses,
        f"{base_url}/v2/organizations",
        payload=[{"id": 9, "name": "Org A"}, {"id": 32, "name": "Org B"}],
        status=200,
    )
    mock_get(
        aioresponses,
        f"{base_url}/v2/organization/9",
        payload={"id": 9, "name": "Org A", "locations": []},
        status=200,
    )
    mock_get(
        aioresponses,
        f"{base_url}/v2/organization/32",
        payload={"id": 32, "name": "Org B", "locations": []},
        status=200,
    )

    with patch_valid_token_async(async_client):
        orgs = await async_client.get_organizations_by_org(max_concurrency=2)

    assert len(orgs) == 2
    assert {org["id"] for org in orgs} == {9, 32}


@pytest.mark.asyncio
async def test_query_custom_fields_by_org(async_client, aioresponses):
    base_url = async_client.base_url
    mock_get(
        aioresponses,
        f"{base_url}/v2/queries/custom-fields",
        payload={
            "results": [{"id": 1, "organizationId": 9, "systemName": "HOST-1"}],
            "cursor": {},
        },
        status=200,
        repeat=True,
    )

    with patch_valid_token_async(async_client):
        records = await async_client.query_custom_fields_by_org(
            org_ids=[9, 32],
            max_concurrency=2,
        )

    assert len(records) == 2
    assert records[0]["systemName"] == "HOST-1"


@pytest.mark.asyncio
async def test_async_create_organization_document_returns_single_document(
    async_client, aioresponses
):
    base_url = async_client.base_url
    created_document = {
        "documentId": 123,
        "documentName": "Audit",
        "organizationId": 9,
    }
    mock_post(
        aioresponses,
        f"{base_url}/v2/organization/documents",
        payload=[created_document],
        status=200,
    )

    with patch_valid_token_async(async_client):
        result = await async_client.create_organization_document(
            organization_id=9,
            document_template_id=42,
            document_name="Audit",
        )

    assert result == created_document


def test_create_organization_document_sync_wrapper_returns_single_document(
    client, aioresponses
):
    base_url = client.base_url
    created_document = {
        "documentId": 123,
        "documentName": "Audit",
        "organizationId": 9,
    }
    mock_post(
        aioresponses,
        f"{base_url}/v2/organization/documents",
        payload=[created_document],
        status=200,
    )

    with patch_valid_token(client):
        result = client.create_organization_document(
            organization_id=9,
            document_template_id=42,
            document_name="Audit",
        )

    assert result == created_document


@pytest.mark.asyncio
async def test_device_endpoints_use_singular_path(async_client, aioresponses):
    """Per-device endpoints must hit ``/v2/device/{id}/...`` (not plural)."""
    base = async_client.base_url
    device_id = 42

    mock_get(aioresponses, f"{base}/v2/device/{device_id}", payload={"id": device_id})
    mock_patch(aioresponses, f"{base}/v2/device/{device_id}", payload={"id": device_id})
    mock_get(aioresponses, f"{base}/v2/device/{device_id}/alerts", payload=[])
    mock_get(aioresponses, f"{base}/v2/device/{device_id}/activities", payload={})
    mock_get(aioresponses, f"{base}/v2/device/{device_id}/software", payload=[])
    mock_get(aioresponses, f"{base}/v2/device/{device_id}/volumes", payload=[])

    with patch_valid_token_async(async_client):
        await async_client.get_device(device_id)
        await async_client.update_device(device_id, displayName="x")
        await async_client.get_device_alerts(device_id)
        await async_client.get_device_activities(device_id)
        await async_client.get_device_software(device_id)
        await async_client.get_device_volumes(device_id)


@pytest.mark.asyncio
async def test_enable_maintenance_mode_uses_put_singular(async_client, aioresponses):
    """``enable_maintenance_mode`` must PUT to singular path with ``end`` in body."""
    base = async_client.base_url
    device_id = 7

    mock_put(
        aioresponses,
        f"{base}/v2/device/{device_id}/maintenance",
        status=200,
        payload={"ok": True},
    )

    with patch_valid_token_async(async_client):
        await async_client.enable_maintenance_mode(device_id, duration=3600)

    # First (and only) captured request key encodes method + URL.
    request_key = next(iter(aioresponses.requests.keys()))
    method, url = request_key[0], str(request_key[1])
    assert method == "PUT"
    assert url.endswith(f"/v2/device/{device_id}/maintenance")


@pytest.mark.asyncio
async def test_disable_maintenance_mode_uses_singular_delete(async_client, aioresponses):
    base = async_client.base_url
    device_id = 7

    mock_delete(
        aioresponses,
        f"{base}/v2/device/{device_id}/maintenance",
        status=204,
    )

    with patch_valid_token_async(async_client):
        await async_client.disable_maintenance_mode(device_id)

    request_key = next(iter(aioresponses.requests.keys()))
    method, url = request_key[0], str(request_key[1])
    assert method == "DELETE"
    assert url.endswith(f"/v2/device/{device_id}/maintenance")
