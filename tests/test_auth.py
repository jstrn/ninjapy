"""
Tests for authentication functionality.
"""

import time
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses
from unittest.mock import AsyncMock, MagicMock, patch

from ninjapy.auth import AsyncTokenManager, TokenManager
from ninjapy.exceptions import NinjaRMMAuthError


class TestAsyncTokenManager:
    """Test cases for AsyncTokenManager class."""

    def setup_method(self):
        self.token_url = "https://test.ninjarmm.com/oauth/token"
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.scope = "monitoring management control"
        self.token_manager = AsyncTokenManager(
            token_url=self.token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scope=self.scope,
        )

    @pytest.mark.asyncio
    async def test_get_token_success(self, aioresponses):
        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self.scope,
            },
            status=200,
        )

        token = await self.token_manager._get_new_access_token()

        assert token == "test_access_token"
        assert self.token_manager._access_token == "test_access_token"
        assert self.token_manager._token_expiry is not None
        assert self.token_manager._token_expiry > time.time()

    @pytest.mark.asyncio
    async def test_get_token_failure(self, aioresponses):
        aioresponses.post(
            self.token_url,
            payload={"error": "invalid_client"},
            status=401,
        )

        with pytest.raises(NinjaRMMAuthError):
            await self.token_manager._get_new_access_token()

    @pytest.mark.asyncio
    async def test_get_valid_token_when_token_is_none(self, aioresponses):
        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "new_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self.scope,
            },
            status=200,
        )

        token = await self.token_manager.get_valid_token()

        assert token == "new_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_when_token_expired(self, aioresponses):
        self.token_manager._access_token = "expired_token"
        self.token_manager._token_expiry = time.time() - 100

        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "refreshed_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self.scope,
            },
            status=200,
        )

        token = await self.token_manager.get_valid_token()

        assert token == "refreshed_token"
        assert self.token_manager._access_token == "refreshed_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_when_token_valid(self):
        self.token_manager._access_token = "valid_token"
        self.token_manager._token_expiry = time.time() + 1800

        token = await self.token_manager.get_valid_token()

        assert token == "valid_token"

    def test_is_token_expired_when_none(self):
        assert self.token_manager._is_token_expired() is True

    def test_is_token_expired_when_expired(self):
        self.token_manager._token_expiry = time.time() - 100
        assert self.token_manager._is_token_expired() is True

    def test_is_token_expired_when_valid(self):
        self.token_manager._token_expiry = time.time() + 1800
        assert self.token_manager._is_token_expired() is False

    @pytest.mark.asyncio
    async def test_request_token_parameters(self, aioresponses):
        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "test_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self.scope,
            },
            status=200,
        )

        await self.token_manager._get_new_access_token()

        assert len(aioresponses.requests) == 1
        request = next(iter(aioresponses.requests.values()))[0]
        body = request.kwargs.get("data")
        if isinstance(body, list):
            body_params = dict(body)
        else:
            body_params = dict(param.split("=") for param in body.split("&"))

        assert body_params["grant_type"] == "client_credentials"
        assert body_params["client_id"] == self.client_id
        assert body_params["client_secret"] == self.client_secret
        assert body_params["scope"] == self.scope

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        session = MagicMock()
        session.closed = False
        session.post.side_effect = aiohttp.ClientError("Network error")

        async def get_session():
            return session

        with patch.object(self.token_manager, "_get_session", get_session):
            with pytest.raises(NinjaRMMAuthError):
                await self.token_manager._get_new_access_token()

    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, aioresponses):
        aioresponses.post(self.token_url, body="invalid json", status=200)

        with pytest.raises(NinjaRMMAuthError):
            await self.token_manager._get_new_access_token()

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, aioresponses):
        self.token_manager._refresh_token_value = "refresh-token"

        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "refreshed_access_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "new-refresh-token",
            },
            status=200,
        )

        token = await self.token_manager._refresh_token()

        assert token == "refreshed_access_token"
        assert self.token_manager._access_token == "refreshed_access_token"
        assert self.token_manager._refresh_token_value == "new-refresh-token"

    @pytest.mark.asyncio
    async def test_refresh_token_without_refresh_value(self):
        self.token_manager._refresh_token_value = None

        with pytest.raises(NinjaRMMAuthError, match="No refresh token available"):
            await self.token_manager._refresh_token()

    @pytest.mark.asyncio
    async def test_get_valid_token_uses_refresh_when_expired(self, aioresponses):
        self.token_manager._access_token = "expired_token"
        self.token_manager._token_expiry = time.time() - 100
        self.token_manager._refresh_token_value = "refresh-token"

        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "refreshed_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "refresh-token",
            },
            status=200,
        )

        token = await self.token_manager.get_valid_token()

        assert token == "refreshed_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_falls_back_when_refresh_fails(self, aioresponses):
        self.token_manager._access_token = "expired_token"
        self.token_manager._token_expiry = time.time() - 100
        self.token_manager._refresh_token_value = "bad-refresh-token"

        aioresponses.post(self.token_url, status=401)
        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "new_token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
            status=200,
        )

        token = await self.token_manager.get_valid_token()

        assert token == "new_token"

    def test_force_token_expiration_with_existing_token(self):
        self.token_manager._token_expiry = time.time() + 3600
        original = self.token_manager._token_expiry

        self.token_manager.force_token_expiration()

        assert self.token_manager._token_expiry < original

    def test_force_token_expiration_without_token(self):
        self.token_manager._token_expiry = None

        self.token_manager.force_token_expiration()

        assert self.token_manager._token_expiry is None

    @pytest.mark.asyncio
    async def test_external_session_is_reused(self):
        session = aiohttp.ClientSession()
        manager = AsyncTokenManager(
            token_url=self.token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scope=self.scope,
            session=session,
        )

        assert await manager._get_session() is session

        await manager.close()
        await session.close()

    @pytest.mark.asyncio
    async def test_get_valid_token_without_refresh_uses_new_token(self, aioresponses):
        self.token_manager._access_token = "expired_token"
        self.token_manager._token_expiry = time.time() - 100
        self.token_manager._refresh_token_value = None

        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "fresh_token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
            status=200,
        )

        token = await self.token_manager.get_valid_token()

        assert token == "fresh_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_reuses_token_inside_lock(self):
        self.token_manager._access_token = "valid_token"
        self.token_manager._token_expiry = time.time() + 1800

        with patch.object(
            self.token_manager,
            "_is_token_expired",
            side_effect=[True, False],
        ):
            token = await self.token_manager.get_valid_token()

        assert token == "valid_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_wraps_unexpected_errors(self):
        self.token_manager._access_token = None
        self.token_manager._token_expiry = None

        with patch.object(
            self.token_manager,
            "_get_new_access_token",
            new=AsyncMock(side_effect=ValueError("boom")),
        ):
            with pytest.raises(NinjaRMMAuthError, match="Token management failed"):
                await self.token_manager.get_valid_token()

    @pytest.mark.asyncio
    async def test_close_closes_owned_session(self):
        session = await self.token_manager._get_session()

        await self.token_manager.close()

        assert session.closed


class TestTokenManager:
    """Test sync wrapper around AsyncTokenManager."""

    def setup_method(self):
        self.token_url = "https://test.ninjarmm.com/oauth/token"
        self.token_manager = TokenManager(
            token_url=self.token_url,
            client_id="test_client_id",
            client_secret="test_client_secret",
            scope="monitoring management control",
        )

    def test_sync_wrapper_delegates_to_async(self, aioresponses):
        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "sync_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "monitoring management control",
            },
            status=200,
        )

        token = self.token_manager.get_valid_token()
        assert token == "sync_token"

    def test_sync_wrapper_exposes_non_async_attributes(self):
        assert self.token_manager.token_url == self.token_url

    def test_sync_wrapper_property_delegation(self, aioresponses):
        aioresponses.post(
            self.token_url,
            payload={
                "access_token": "sync_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "monitoring management control",
            },
            status=200,
        )

        self.token_manager.get_valid_token()

        assert self.token_manager._access_token == "sync_token"
        assert self.token_manager._token_expiry is not None
        assert self.token_manager._refresh_token_value is None

    def test_sync_wrapper_property_setters(self):
        self.token_manager._access_token = "setter-token"
        self.token_manager._token_expiry = 123.0

        assert self.token_manager._async._access_token == "setter-token"
        assert self.token_manager._async._token_expiry == 123.0

    def teardown_method(self):
        self.token_manager.close()
