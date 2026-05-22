"""Shared pytest fixtures for aiohttp-based tests."""

from __future__ import annotations

import re
from re import Pattern
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from aioresponses import aioresponses as aioresponses_fixture

from ninjapy.client import AsyncNinjaRMMClient, NinjaRMMClient


def url_pattern(url: str) -> Pattern[str]:
    """Match a URL with optional query parameters."""
    return re.compile(re.escape(url) + r"(\?.*)?$")


def mock_get(
    mocked: Any,
    url: str,
    *,
    payload: Any = None,
    status: int = 200,
    headers: dict[str, str] | None = None,
    body: str | None = None,
    repeat: bool = False,
) -> None:
    kwargs: dict[str, Any] = {"status": status, "repeat": repeat}
    if payload is not None:
        kwargs["payload"] = payload
    if headers is not None:
        kwargs["headers"] = headers
    if body is not None:
        kwargs["body"] = body
    mocked.get(url_pattern(url), **kwargs)


def mock_post(
    mocked: Any,
    url: str,
    *,
    payload: Any = None,
    status: int = 200,
    headers: dict[str, str] | None = None,
    body: str | None = None,
    repeat: bool = False,
) -> None:
    kwargs: dict[str, Any] = {"status": status, "repeat": repeat}
    if payload is not None:
        kwargs["payload"] = payload
    if headers is not None:
        kwargs["headers"] = headers
    if body is not None:
        kwargs["body"] = body
    mocked.post(url_pattern(url), **kwargs)


def mock_put(mocked: Any, url: str, **kwargs: Any) -> None:
    mocked.put(url_pattern(url), **kwargs)


def mock_patch(mocked: Any, url: str, **kwargs: Any) -> None:
    mocked.patch(url_pattern(url), **kwargs)


def mock_delete(mocked: Any, url: str, **kwargs: Any) -> None:
    mocked.delete(url_pattern(url), **kwargs)


@pytest.fixture
def aioresponses():
    with aioresponses_fixture() as mocked:
        yield mocked


@pytest.fixture
def client_kwargs():
    return {
        "token_url": "https://test.ninjarmm.com/oauth/token",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "scope": "monitoring management control",
        "base_url": "https://test.ninjarmm.com",
    }


@pytest.fixture
def mock_async_token_manager():
    with patch("ninjapy.client.AsyncTokenManager") as mock_cls:
        mock_cls.return_value.get_valid_token = AsyncMock(return_value="test_token")
        mock_cls.return_value.close = AsyncMock()
        yield mock_cls


@pytest.fixture
def client(client_kwargs, mock_async_token_manager):
    return NinjaRMMClient(**client_kwargs)


@pytest.fixture
def async_client(client_kwargs, mock_async_token_manager):
    return AsyncNinjaRMMClient(**client_kwargs)


def get_request_json(mocked: Any, index: int = 0) -> Any:
    """Return JSON body from the nth captured aiohttp request."""
    call = next(iter(mocked.requests.values()))[index]
    if "json" in call.kwargs:
        return call.kwargs["json"]
    raw = call.kwargs.get("data") or call.kwargs.get("body")
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    if isinstance(raw, str):
        import json

        return json.loads(raw)
    return raw


def get_request_url(mocked: Any, index: int = 0) -> str:
    """Return URL string from the nth captured aiohttp request."""
    key = list(mocked.requests.keys())[index]
    return str(key[1])


def patch_valid_token(client: NinjaRMMClient):
    """Patch token retrieval on a sync client instance."""
    return patch.object(
        client._async.token_manager,
        "get_valid_token",
        new=AsyncMock(return_value="test_token"),
    )


def patch_valid_token_async(client: AsyncNinjaRMMClient):
    """Patch token retrieval on an async client instance."""
    return patch.object(
        client.token_manager,
        "get_valid_token",
        new=AsyncMock(return_value="test_token"),
    )
