"""aiohttp session and connector configuration."""

from __future__ import annotations

import socket
import time
from typing import Optional

import aiohttp

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def build_connector(
    pool_max_age: Optional[float] = 60.0,
) -> aiohttp.TCPConnector:
    """Create a TCP connector with keepalive enabled."""
    _ = pool_max_age
    return aiohttp.TCPConnector(
        enable_cleanup_closed=True,
        keepalive_timeout=30,
    )


class ManagedClientSession:
    """aiohttp ClientSession with optional periodic connector refresh."""

    def __init__(
        self,
        *,
        pool_max_age: Optional[float] = 60.0,
        timeout: aiohttp.ClientTimeout | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.pool_max_age = pool_max_age
        self._timeout = timeout
        self._headers = dict(headers or DEFAULT_HEADERS)
        self._session: aiohttp.ClientSession | None = None
        self._connector: aiohttp.TCPConnector | None = None
        self._last_refresh = time.monotonic()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._create_session()
        return self._session

    async def refresh_if_needed(self) -> None:
        if self._session is None or self._session.closed:
            self._create_session()
            return

        if self.pool_max_age is None or self.pool_max_age <= 0:
            await self.close()
            self._create_session()
            return

        if time.monotonic() - self._last_refresh >= self.pool_max_age:
            await self.close()
            self._create_session()

    def _create_session(self) -> None:
        self._connector = build_connector(self.pool_max_age)
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            headers=self._headers,
            timeout=self._timeout,
        )
        self._last_refresh = time.monotonic()

    def update_headers(self, headers: dict[str, str]) -> None:
        self._headers.update(headers)
        if self._session is not None and not self._session.closed:
            self._session.headers.update(headers)

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
        self._connector = None

    async def __aenter__(self) -> "ManagedClientSession":
        await self.refresh_if_needed()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


def build_client_timeout(
    request_timeout: float | tuple[float, float],
) -> aiohttp.ClientTimeout:
    """Map scalar or (connect, read) timeout to aiohttp ClientTimeout."""
    if isinstance(request_timeout, tuple):
        connect_timeout, read_timeout = request_timeout
        return aiohttp.ClientTimeout(
            total=None,
            connect=float(connect_timeout),
            sock_read=float(read_timeout),
        )
    timeout_value = float(request_timeout)
    return aiohttp.ClientTimeout(total=timeout_value)


def socket_keepalive_enabled() -> bool:
    """Report whether the platform exposes TCP keepalive socket options."""
    return hasattr(socket, "TCP_KEEPIDLE") or hasattr(socket, "TCP_KEEPALIVE")
