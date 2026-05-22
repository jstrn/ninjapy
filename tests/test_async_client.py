"""Async client tests."""

from unittest.mock import AsyncMock, patch

import pytest
from aioresponses import aioresponses

from ninjapy.client import AsyncNinjaRMMClient
from tests.conftest import mock_get, patch_valid_token_async


@pytest.fixture
def async_client():
    with patch("ninjapy.client.AsyncTokenManager") as mock_cls:
        mock_cls.return_value.get_valid_token = AsyncMock(return_value="test_token")
        mock_cls.return_value.close = AsyncMock()
        yield AsyncNinjaRMMClient(
            token_url="https://test.ninjarmm.com/oauth/token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            scope="monitoring management control",
            base_url="https://test.ninjarmm.com",
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
async def test_async_context_manager_closes_session(aioresponses):
    with patch("ninjapy.client.AsyncTokenManager") as mock_cls:
        mock_cls.return_value.get_valid_token = AsyncMock(return_value="test_token")
        mock_cls.return_value.close = AsyncMock()

        async with AsyncNinjaRMMClient(
            token_url="https://test.ninjarmm.com/oauth/token",
            client_id="id",
            client_secret="secret",
            scope="monitoring management control",
            base_url="https://test.ninjarmm.com",
        ) as client:
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
        items = [item async for item in async_client.iter_all_organizations(page_size=2)]

    assert len(items) == 3
