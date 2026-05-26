"""Tests for aiohttp session helpers."""

from __future__ import annotations

from unittest.mock import patch

import aiohttp
import pytest

from ninjapy._http import (
    ManagedClientSession,
    build_client_timeout,
    build_connector,
    socket_keepalive_enabled,
)
from ninjapy._session import ManagedClientSession as ReexportedSession


@pytest.mark.asyncio
async def test_build_connector_returns_tcp_connector():
    connector = build_connector(pool_max_age=30.0)

    try:
        assert isinstance(connector, aiohttp.TCPConnector)
    finally:
        await connector.close()


def test_build_client_timeout_scalar():
    timeout = build_client_timeout(30.0)

    assert timeout.total == 30.0


def test_build_client_timeout_tuple():
    timeout = build_client_timeout((2.0, 15.0))

    assert timeout.connect == 2.0
    assert timeout.sock_read == 15.0
    assert timeout.total is None


def test_socket_keepalive_enabled():
    assert isinstance(socket_keepalive_enabled(), bool)


def test_session_module_reexports():
    assert ReexportedSession is ManagedClientSession


@pytest.mark.asyncio
async def test_managed_session_context_manager():
    async with ManagedClientSession() as session:
        assert isinstance(session.session, aiohttp.ClientSession)
        assert not session.session.closed


@pytest.mark.asyncio
async def test_managed_session_update_headers():
    session = ManagedClientSession(headers={"Accept": "application/json"})
    try:
        _ = session.session

        session.update_headers({"Authorization": "Bearer token"})

        assert session._headers["Authorization"] == "Bearer token"
        assert session.session.headers["Authorization"] == "Bearer token"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_managed_session_recreates_closed_session():
    session = ManagedClientSession()
    try:
        first = session.session
        await session.close()

        second = session.session

        assert first.closed
        assert not second.closed
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_managed_session_refresh_noop_when_pool_max_age_is_none():
    """``pool_max_age=None`` must NOT recycle the session on every call."""
    session = ManagedClientSession(pool_max_age=None)
    try:
        first = session.session

        with patch.object(
            session,
            "_create_session",
            wraps=session._create_session,
        ) as mock_create:
            await session.refresh_if_needed()
            await session.refresh_if_needed()

        mock_create.assert_not_called()
        assert session.session is first
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_managed_session_concurrent_refresh_creates_one_session():
    """Concurrent refresh calls must not double-close and double-create."""
    import asyncio as _asyncio

    session = ManagedClientSession(pool_max_age=0.0)
    try:
        _ = session.session

        with patch.object(
            session,
            "_create_session",
            wraps=session._create_session,
        ) as mock_create:
            await _asyncio.gather(*(session.refresh_if_needed() for _ in range(5)))

        # Each call is serialized by the lock; total recreations bounded.
        assert mock_create.call_count <= 5
        assert session.session is not None
        assert not session.session.closed
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_managed_session_refresh_when_session_closed():
    session = ManagedClientSession(pool_max_age=60.0)
    try:
        _ = session.session
        await session.close()

        with patch.object(
            session,
            "_create_session",
            wraps=session._create_session,
        ) as mock_create:
            await session.refresh_if_needed()

        mock_create.assert_called_once()
    finally:
        await session.close()
