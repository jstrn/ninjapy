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

    def teardown_method(self):
        self.token_manager.close()
