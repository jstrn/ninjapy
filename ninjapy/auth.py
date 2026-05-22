import asyncio
import logging
import time
from typing import Optional

import aiohttp

from ._sync import SyncRunner
from .exceptions import NinjaRMMAuthError

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ninjapy.auth")


class AsyncTokenManager:
    """Manages OAuth2 token lifecycle for NinjaRMM API using aiohttp."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str,
        *,
        session: aiohttp.ClientSession | None = None,
    ):
        logger.info("Initializing AsyncTokenManager with URL: %s", token_url)
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = "monitoring management control"
        self._external_session = session

        self._access_token: Optional[str] = None
        self._refresh_token_value: Optional[str] = None
        self._token_expiry: Optional[float] = None
        self._token_lock = asyncio.Lock()
        self._owned_session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._external_session is not None and not self._external_session.closed:
            return self._external_session
        if self._owned_session is None or self._owned_session.closed:
            self._owned_session = aiohttp.ClientSession()
        return self._owned_session

    def _is_token_expired(self) -> bool:
        if not self._token_expiry:
            logger.info("No token expiry set, considering token expired")
            return True

        is_expired = time.time() + 60 >= self._token_expiry
        logger.info(
            "Token expired check: %s, expires at: %s, current time: %s",
            is_expired,
            self._token_expiry,
            time.time(),
        )
        return is_expired

    async def _get_new_access_token(self) -> str:
        logger.info("Getting new access token")

        payload = [
            ("grant_type", "client_credentials"),
            ("client_id", self.client_id),
            ("client_secret", self.client_secret),
            ("scope", self.scope),
        ]

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        session = await self._get_session()
        try:
            logger.info("Making token request to %s", self.token_url)
            async with session.post(
                self.token_url,
                data=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                logger.info("Token request status code: %s", response.status)
                response.raise_for_status()
                try:
                    token_data = await response.json()
                except (aiohttp.ContentTypeError, ValueError) as exc:
                    raise NinjaRMMAuthError(
                        f"Failed to parse token response: {exc}"
                    ) from exc

            self._access_token = token_data["access_token"]
            self._token_expiry = time.time() + token_data["expires_in"]
            self._refresh_token_value = token_data.get("refresh_token")

            logger.info(
                "Got new token, expires in %s seconds", token_data["expires_in"]
            )
            return token_data["access_token"]

        except aiohttp.ClientError as exc:
            logger.error("Failed to get access token: %s", exc)
            raise NinjaRMMAuthError(f"Failed to get new access token: {exc}") from exc

    async def _refresh_token(self) -> str:
        if not self._refresh_token_value:
            raise NinjaRMMAuthError("No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token_value,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        session = await self._get_session()
        try:
            async with session.post(
                self.token_url,
                data=data,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                token_data = await response.json()

            self._access_token = token_data["access_token"]
            self._token_expiry = time.time() + token_data["expires_in"]
            self._refresh_token_value = token_data.get("refresh_token")

            return token_data["access_token"]

        except Exception as exc:
            raise NinjaRMMAuthError(f"Failed to refresh token: {exc}") from exc

    async def get_valid_token(self) -> str:
        if self._access_token and not self._is_token_expired():
            return self._access_token

        async with self._token_lock:
            logger.info("Getting valid token")
            try:
                if not self._access_token or not self._token_expiry:
                    logger.info("No token exists, getting new one")
                    return await self._get_new_access_token()

                if self._is_token_expired():
                    logger.info("Token is expired")
                    if self._refresh_token_value:
                        logger.info("Attempting to refresh token")
                        try:
                            return await self._refresh_token()
                        except NinjaRMMAuthError:
                            logger.info("Refresh failed, getting new token")
                            return await self._get_new_access_token()
                    logger.info("No refresh token, getting new access token")
                    return await self._get_new_access_token()

                logger.info("Using existing valid token")
                assert self._access_token is not None
                return self._access_token

            except Exception as exc:
                logger.error("Token management failed: %s", exc)
                raise NinjaRMMAuthError(f"Token management failed: {exc}") from exc

    def force_token_expiration(self) -> None:
        logger.info("Forcing token expiration for testing")
        if self._token_expiry:
            self._token_expiry = time.time() - 10
            logger.info("Token expiry forced to past time: %s", self._token_expiry)
        else:
            logger.info("No token exists to expire")

    async def close(self) -> None:
        if self._owned_session is not None and not self._owned_session.closed:
            await self._owned_session.close()
        self._owned_session = None


class TokenManager:
    """Synchronous wrapper around AsyncTokenManager."""

    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str):
        self._async = AsyncTokenManager(token_url, client_id, client_secret, scope)
        self._runner = SyncRunner()

    def __getattr__(self, name: str):
        attr = getattr(self._async, name)
        if asyncio.iscoroutinefunction(attr):

            def sync_wrapper(*args, **kwargs):
                return self._runner.run(attr(*args, **kwargs))

            return sync_wrapper
        return attr

    @property
    def _access_token(self):
        return self._async._access_token

    @_access_token.setter
    def _access_token(self, value):
        self._async._access_token = value

    @property
    def _token_expiry(self):
        return self._async._token_expiry

    @_token_expiry.setter
    def _token_expiry(self, value):
        self._async._token_expiry = value

    @property
    def _refresh_token_value(self):
        return self._async._refresh_token_value

    def close(self) -> None:
        self._runner.run(self._async.close())
        self._runner.close()
