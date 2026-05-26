"""
Tests for NinjaRMM client functionality.
"""

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioresponses import aioresponses

from ninjapy.client import AsyncNinjaRMMClient, NinjaRMMClient
from ninjapy.exceptions import NinjaRMMAPIError, NinjaRMMAuthError, NinjaRMMError
from ninjapy._http import ManagedClientSession
from tests.conftest import (
    get_request_json,
    get_request_url,
    mock_delete,
    mock_get,
    mock_patch,
    mock_post,
    mock_put,
    patch_valid_token,
)


class TestNinjaRMMClient:
    """Test cases for NinjaRMMClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.token_url = "https://test.ninjarmm.com/oauth/token"
        self.client_id = "test_client_id"
        self.client_secret = uuid.uuid4().hex
        self.scope = "monitoring management control"
        self.base_url = "https://test.ninjarmm.com"

        # Mock the token manager to avoid actual OAuth calls
        with patch("ninjapy.client.AsyncTokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token = AsyncMock(
                return_value="test_token"
            )
            mock_token_manager.return_value.close = AsyncMock()

            self.client = NinjaRMMClient(
                token_url=self.token_url,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scope=self.scope,
                base_url=self.base_url,
            )

    def teardown_method(self):
        """Close client resources."""
        self.client.close()

    def test_client_initialization(self):
        """Test client initialization."""
        assert self.client.base_url == self.base_url
        assert hasattr(self.client, "token_manager")
        assert hasattr(self.client._async, "_http")
        assert isinstance(self.client._async._http, ManagedClientSession)

    def test_get_organizations_success(self, aioresponses):
        """Test successful organizations retrieval."""
        mock_orgs = [
            {"id": 1, "name": "Test Org 1", "description": "Test organization 1"},
            {"id": 2, "name": "Test Org 2", "description": "Test organization 2"},
        ]

        mock_get(
            aioresponses,
            f"{self.base_url}/v2/organizations",
            payload=mock_orgs,
            status=200,
        )

        with patch_valid_token(self.client):
            orgs = self.client.get_organizations()

        assert len(orgs) == 2
        assert orgs[0]["name"] == "Test Org 1"
        assert orgs[1]["name"] == "Test Org 2"

    def test_get_organizations_with_parameters(self, aioresponses):
        """Test organizations retrieval with query parameters."""
        mock_orgs = [{"id": 1, "name": "Test Org"}]

        mock_get(
            aioresponses,
            f"{self.base_url}/v2/organizations",
            payload=mock_orgs,
            status=200,
        )

        with patch_valid_token(self.client):
            self.client.get_organizations(page_size=10, after=100, org_filter="test")

        # Check that parameters were included in the request
        assert "pageSize=10" in get_request_url(aioresponses)
        assert "after=100" in get_request_url(aioresponses)
        assert "of=test" in get_request_url(aioresponses)

    def test_get_devices_success(self, aioresponses):
        """Test successful devices retrieval."""
        mock_devices = [
            {
                "id": 1,
                "displayName": "Test Device 1",
                "nodeClass": "WINDOWS_WORKSTATION",
            },
            {"id": 2, "displayName": "Test Device 2", "nodeClass": "WINDOWS_SERVER"},
        ]

        mock_get(
            aioresponses,
            f"{self.base_url}/v2/devices",
            payload=mock_devices,
            status=200,
        )

        with patch_valid_token(self.client):
            devices = self.client.get_devices()

        assert len(devices) == 2
        assert devices[0]["displayName"] == "Test Device 1"
        assert devices[1]["displayName"] == "Test Device 2"

    def test_get_device_success(self, aioresponses):
        """Test successful device retrieval."""
        mock_device = {
            "id": 1,
            "displayName": "Test Device",
            "nodeClass": "WINDOWS_WORKSTATION",
            "system": {"manufacturer": "Dell Inc.", "model": "OptiPlex 7090"},
        }

        mock_get(
            aioresponses,
            f"{self.base_url}/v2/devices/1",
            payload=mock_device,
            status=200,
        )

        with patch_valid_token(self.client):
            device = self.client.get_device(1)

        assert device["id"] == 1
        assert device["displayName"] == "Test Device"
        assert device["system"]["manufacturer"] == "Dell Inc."

    def test_create_organization_success(self, aioresponses):
        """Test successful organization creation."""
        mock_org = {
            "id": 123,
            "name": "New Test Organization",
            "description": "A new test organization",
        }

        mock_post(
            aioresponses,
            f"{self.base_url}/v2/organizations",
            payload=mock_org,
            status=201,
        )

        with patch_valid_token(self.client):
            org = self.client.create_organization(
                name="New Test Organization", description="A new test organization"
            )

        assert org["id"] == 123
        assert org["name"] == "New Test Organization"

    def test_http_error_handling(self, aioresponses):
        """Test HTTP error handling."""
        mock_get(
            aioresponses,
            f"{self.base_url}/v2/organizations",
            payload={"message": "Unauthorized"},
            status=401,
        )

        with patch_valid_token(self.client):
            with pytest.raises(NinjaRMMAuthError):
                self.client.get_organizations()

    def test_api_error_handling(self, aioresponses):
        """Test API error handling for non-auth errors."""
        mock_get(
            aioresponses,
            f"{self.base_url}/v2/devices/999",
            payload={"message": "Device not found"},
            status=404,
        )

        with patch_valid_token(self.client):
            with pytest.raises(NinjaRMMError):
                self.client.get_device(999)

    def test_rate_limit_handling(self, aioresponses):
        """Test rate limit handling."""
        mock_get(
            aioresponses,
            f"{self.base_url}/v2/organizations",
            status=429,
            headers={"Retry-After": "1"},
        )
        mock_get(
            aioresponses,
            f"{self.base_url}/v2/organizations",
            payload=[{"id": 1, "name": "Test Org"}],
            status=200,
        )

        with patch_valid_token(self.client):
            with patch("ninjapy.client.asyncio.sleep", new=AsyncMock()) as mock_sleep:
                orgs = self.client.get_organizations()

            assert len(orgs) == 1
            assert orgs[0]["name"] == "Test Org"
            mock_sleep.assert_called_once_with(1)

    def test_request_timeout_tuple_is_preserved(self):
        """Test tuple timeouts are preserved on the async client."""
        timeout = (2, 15)

        with patch("ninjapy.client.AsyncTokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token = AsyncMock(
                return_value="test_token"
            )
            mock_token_manager.return_value.close = AsyncMock()
            client = NinjaRMMClient(
                token_url=self.token_url,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scope=self.scope,
                base_url=self.base_url,
                request_timeout=timeout,
            )

        try:
            assert client._async._client_timeout.connect == 2
            assert client._async._client_timeout.sock_read == 15
        finally:
            client.close()

    @pytest.mark.asyncio
    async def test_managed_session_refreshes_stale_pools(self):
        """Test stale aiohttp sessions are recycled before the next request."""
        session = ManagedClientSession(pool_max_age=1)
        try:
            _ = session.session
            session._last_refresh = time.monotonic() - 5

            with patch.object(session, "close", wraps=session.close) as mock_close:
                await session.refresh_if_needed()

            mock_close.assert_called_once()
            assert session._last_refresh > time.monotonic() - 2
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_managed_session_forces_recycle_when_disabled(self):
        """Test non-positive pool max age recycles the session on each access."""
        session = ManagedClientSession(pool_max_age=0)
        try:
            _ = session.session

            with patch.object(session, "close", wraps=session.close) as mock_close:
                await session.refresh_if_needed()

            mock_close.assert_called_once()
        finally:
            await session.close()

    def test_no_content_response(self, aioresponses):
        """Test handling of 204 No Content responses."""
        mock_delete(aioresponses, f"{self.base_url}/v2/organizations/123", status=204)

        with patch_valid_token(self.client):
            result = self.client.delete_organization(123)

        assert result is None

    def test_context_manager(self):
        """Test client as context manager."""
        with patch("ninjapy.client.AsyncTokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token = AsyncMock(
                return_value="test_token"
            )
            mock_token_manager.return_value.close = AsyncMock()

            with NinjaRMMClient(
                token_url=self.token_url,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scope=self.scope,
                base_url=self.base_url,
            ) as client:
                assert isinstance(client, NinjaRMMClient)
                assert hasattr(client._async, "_http")

    def test_pagination_with_after_basic(self):
        """Test basic pagination with 'after' parameter"""
        # Mock responses for pagination
        page1 = [{"id": 1, "name": "org1"}, {"id": 2, "name": "org2"}]
        page2 = [{"id": 3, "name": "org3"}]

        with aioresponses() as rsps:
            # First page
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/organizations",
                payload=page1,
                status=200,
            )
            # Second page
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/organizations",
                payload=page2,
                status=200,
            )

            # Test get_all_organizations
            all_orgs = self.client.get_all_organizations(page_size=2)

            # Should have all organizations from both pages
            assert len(all_orgs) == 3
            assert all_orgs[0]["id"] == 1
            assert all_orgs[1]["id"] == 2
            assert all_orgs[2]["id"] == 3

            # Check that the right parameters were used
            assert (
                len(rsps.requests) == 2
            )  # Only 2 calls needed since second page had less than page_size

            # First call should have no 'after' parameter
            assert "pageSize=2" in get_request_url(rsps, 0)
            assert "after=" not in get_request_url(rsps, 0)

            # Second call should have after=2
            assert "pageSize=2" in get_request_url(rsps, 1)
            assert "after=2" in get_request_url(rsps, 1)

    def test_pagination_with_cursor_basic(self):
        """Test basic pagination with cursor"""
        # Mock responses for cursor-based pagination
        page1_response = {
            "results": [{"id": 1, "name": "device1"}, {"id": 2, "name": "device2"}],
            "cursor": {
                "name": "cursor1",
                "offset": 0,
                "count": 2,
                "expires": 1750461858.667844000,
            },
        }

        page2_response = {
            "results": [{"id": 3, "name": "device3"}],
            "cursor": {
                "name": "cursor2",
                "offset": 2,
                "count": 1,
                "expires": 1750461858.667844000,
            },
        }

        page3_response = {"results": [], "cursor": {}}

        with aioresponses() as rsps:
            # First page
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/devices/search",
                payload=page1_response,
                status=200,
            )
            # Second page
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/devices/search",
                payload=page2_response,
                status=200,
            )
            # Third page (empty)
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/devices/search",
                payload=page3_response,
                status=200,
            )

            # Test search_all_devices
            all_devices = self.client.search_all_devices("test", page_size=2)

            # Should have all devices from both pages
            assert len(all_devices) == 3
            assert all_devices[0]["id"] == 1
            assert all_devices[1]["id"] == 2
            assert all_devices[2]["id"] == 3

            # Check that the right parameters were used
            assert len(rsps.requests) == 3

            # First call should have no cursor
            assert "pageSize=2" in get_request_url(rsps, 0)
            assert "q=test" in get_request_url(rsps, 0)
            assert "cursor=" not in get_request_url(rsps, 0)

            # Second call should have cursor=cursor1
            assert "pageSize=2" in get_request_url(rsps, 1)
            assert "cursor=cursor1" in get_request_url(rsps, 1)

            # Third call should have cursor=cursor2
            assert "pageSize=2" in get_request_url(rsps, 2)
            assert "cursor=cursor2" in get_request_url(rsps, 2)

    def test_iter_all_organizations(self):
        """Test iterator for organizations"""
        # Mock responses for pagination
        page1 = [{"id": 1, "name": "org1"}, {"id": 2, "name": "org2"}]
        page2 = [{"id": 3, "name": "org3"}]

        with aioresponses() as rsps:
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/organizations",
                payload=page1,
                status=200,
            )
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/organizations",
                payload=page2,
                status=200,
            )

            orgs = list(self.client.iter_all_organizations(page_size=2))

            assert len(orgs) == 3
            assert orgs[0]["id"] == 1
            assert orgs[1]["id"] == 2
            assert orgs[2]["id"] == 3

    def test_query_all_with_filters(self):
        """Test query methods with filters"""
        response = {
            "results": [
                {"id": 1, "name": "service1", "state": "running"},
                {"id": 2, "name": "service2", "state": "stopped"},
            ],
            "cursor": {},  # Empty cursor means no more pages
        }

        with aioresponses() as rsps:
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/queries/windows-services",
                payload=response,
                status=200,
            )

            # Test with filters
            services = self.client.query_all_windows_services(
                device_filter="deviceClass eq 'WINDOWS_WORKSTATION'",
                name="test",
                state="running",
                page_size=50,
            )

            assert len(services) == 2
            assert services[0]["id"] == 1
            assert services[1]["id"] == 2

            # Check parameters
            assert "pageSize=50" in get_request_url(rsps)
            assert "df=deviceClass+eq+%2527WINDOWS_WORKSTATION%2527" in get_request_url(
                rsps
            )
            assert "name=test" in get_request_url(rsps)
            assert "state=running" in get_request_url(rsps)

    def test_pagination_empty_response(self):
        """Test pagination with empty response"""
        with aioresponses() as rsps:
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/organizations",
                payload=[],
                status=200,
            )

            # Should return empty list
            orgs = self.client.get_all_organizations()
            assert len(orgs) == 0

            # Should only make one call
            assert len(rsps.requests) == 1

    def test_pagination_single_page(self):
        """Test pagination when all results fit in one page"""
        page1 = [{"id": 1, "name": "org1"}, {"id": 2, "name": "org2"}]

        with aioresponses() as rsps:
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/organizations",
                payload=page1,
                status=200,
            )

            # With page_size=10, should not need another call
            orgs = self.client.get_all_organizations(page_size=10)

            assert len(orgs) == 2
            assert len(rsps.requests) == 1  # Only one call needed

    def test_pagination_with_missing_id(self):
        """Test pagination behavior when ID field is missing"""
        page1 = [{"name": "org1"}, {"name": "org2"}]  # Missing 'id' field

        with aioresponses() as rsps:
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/organizations",
                payload=page1,
                status=200,
            )

            # Should still return the results but log warning and stop pagination
            orgs = self.client.get_all_organizations(page_size=10)

            assert len(orgs) == 2
            assert len(rsps.requests) == 1

    def test_cursor_pagination_malformed_response(self):
        """Test cursor pagination with malformed response"""
        bad_response = {"not_results": []}  # Missing 'results' key

        with aioresponses() as rsps:
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/devices/search",
                payload=bad_response,
                status=200,
            )

            # Should return empty list when response is malformed
            devices = self.client.search_all_devices("test")

            assert len(devices) == 0
            assert len(rsps.requests) == 1

    def test_get_all_devices_with_params(self):
        """Test get_all_devices with various parameters"""
        page1 = [{"id": 1, "name": "device1"}, {"id": 2, "name": "device2"}]

        with aioresponses() as rsps:
            mock_get(
                rsps,
                f"{self.client.base_url}/v2/devices",
                payload=page1,
                status=200,
            )

            devices = self.client.get_all_devices(
                page_size=50,
                org_filter="test_org",
                expand="volumes",
                include_backup_usage=True,
            )

            assert len(devices) == 2

            # Check all parameters were passed
            assert "pageSize=50" in get_request_url(rsps)
            assert "of=test_org" not in get_request_url(rsps)
            assert "df=test_org" in get_request_url(rsps)
            assert "expand=volumes" in get_request_url(rsps)
            assert "includeBackupUsage=true" in get_request_url(rsps)


class TestClientValidation:
    """Test cases for client input validation."""

    def test_endpoint_normalization(self):
        """Test that endpoints are properly normalized."""
        with patch("ninjapy.client.AsyncTokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token = AsyncMock(
                return_value="test_token"
            )
            mock_token_manager.return_value.close = AsyncMock()

            client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
            )

            try:
                # Test that endpoint gets normalized (leading slash added)
                with aioresponses() as rsps:
                    mock_get(
                        rsps,
                        "https://test.com/v2/test",
                        payload={},
                        status=200,
                        repeat=True,
                    )

                    # This should work whether we pass "v2/test" or "/v2/test"
                    with patch_valid_token(client):
                        client._runner.run(client._async._request("GET", "v2/test"))
                        client._runner.run(client._async._request("GET", "/v2/test"))
            finally:
                client.close()


class TestTimestampConversion:
    """Test cases for timestamp conversion feature."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch("ninjapy.client.AsyncTokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token = AsyncMock(
                return_value="test_token"
            )
            mock_token_manager.return_value.close = AsyncMock()

            self.client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
                convert_timestamps=True,
            )

    def teardown_method(self):
        """Close client resources."""
        self.client.close()

    def test_timestamp_conversion_enabled(self, aioresponses):
        """Test timestamp conversion when enabled."""
        # Mock API response with epoch timestamps
        mock_response = [
            {
                "id": 1,
                "name": "Test Device",
                "created": 1728487941.725760,
                "lastContact": 1640995200,
                "description": "Test device",
            }
        ]

        mock_get(
            aioresponses,
            "https://test.com/v2/devices",
            payload=mock_response,
            status=200,
        )

        with patch_valid_token(self.client):
            result = self.client.get_devices()

        device = result[0]
        assert device["created"] == "2024-10-09T15:32:21.725760Z"
        assert device["lastContact"] == "2022-01-01T00:00:00Z"
        # Non-timestamp field unchanged
        assert device["description"] == "Test device"

    def test_timestamp_conversion_disabled(self, aioresponses):
        """Test timestamp conversion when disabled."""
        # Create client with timestamp conversion disabled
        with patch("ninjapy.client.AsyncTokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token = AsyncMock(
                return_value="test_token"
            )
            mock_token_manager.return_value.close = AsyncMock()

            client_no_conversion = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
                convert_timestamps=False,
            )

        mock_response = [{"id": 1, "created": 1728487941.725760}]

        mock_get(
            aioresponses,
            "https://test.com/v2/devices",
            payload=mock_response,
            status=200,
        )

        try:
            result = client_no_conversion.get_devices()

            # Should return original timestamp values
            assert result[0]["created"] == 1728487941.725760
        finally:
            client_no_conversion.close()

    def test_set_timestamp_conversion(self):
        """Test setting timestamp conversion dynamically."""
        assert self.client.get_timestamp_conversion_status() is True

        self.client.set_timestamp_conversion(False)
        assert self.client.get_timestamp_conversion_status() is False

        self.client.set_timestamp_conversion(True)
        assert self.client.get_timestamp_conversion_status() is True


class TestClientErrorHandling:
    """Test cases for various error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch("ninjapy.client.AsyncTokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token = AsyncMock(
                return_value="test_token"
            )
            mock_token_manager.return_value.close = AsyncMock()

            self.client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
            )

    def teardown_method(self):
        """Close client resources."""
        self.client.close()

    def test_timeout_handling(self):
        """Test timeout error handling."""
        client = NinjaRMMClient(
            token_url="https://test.com/token",
            client_id="test",
            client_secret="test",
            scope="test",
            base_url="https://test.com",
            retry_total=0,
        )

        class TimeoutContext:
            async def __aenter__(self):
                raise asyncio.TimeoutError()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.headers = {}
        mock_session.request.return_value = TimeoutContext()

        with patch_valid_token(client):
            with patch.object(client._async._http, "_session", mock_session):
                with pytest.raises(NinjaRMMError, match="Request timed out"):
                    client.get_organizations()

        client.close()

    def test_malformed_json_response(self, aioresponses):
        """Test handling of malformed JSON responses."""
        mock_get(
            aioresponses,
            "https://test.com/v2/organizations",
            body="invalid json response",
            status=200,
        )

        with patch_valid_token(self.client):
            with pytest.raises(NinjaRMMError):
                self.client.get_organizations()

    def test_permission_denied_error(self, aioresponses):
        """Test 403 responses raise permission denied."""
        mock_get(
            aioresponses,
            "https://test.com/v2/organizations",
            payload={"message": "Forbidden"},
            status=403,
        )

        with patch_valid_token(self.client):
            with pytest.raises(NinjaRMMError, match="Permission denied"):
                self.client.get_organizations()

    def test_retry_on_retryable_status(self, aioresponses):
        """Test retryable HTTP statuses are retried before succeeding."""
        mock_get(
            aioresponses,
            "https://test.com/v2/organizations",
            status=503,
        )
        mock_get(
            aioresponses,
            "https://test.com/v2/organizations",
            payload=[{"id": 1, "name": "Recovered Org"}],
            status=200,
        )

        with patch_valid_token(self.client):
            with patch("ninjapy.client.asyncio.sleep", new=AsyncMock()) as mock_sleep:
                orgs = self.client.get_organizations()

        assert orgs[0]["name"] == "Recovered Org"
        mock_sleep.assert_called_once_with(1.0)

    def test_api_error_includes_status_code(self, aioresponses):
        """Test non-auth API errors preserve status code and message."""
        mock_get(
            aioresponses,
            "https://test.com/v2/organizations",
            payload={"message": "Bad request"},
            status=400,
        )

        with patch_valid_token(self.client):
            with pytest.raises(NinjaRMMAPIError) as exc_info:
                self.client.get_organizations()

        assert exc_info.value.status_code == 400
        assert exc_info.value.message == "Bad request"

    def test_error_response_without_json_body(self, aioresponses):
        """Test error responses without JSON fall back to status reason."""
        client = NinjaRMMClient(
            token_url="https://test.com/token",
            client_id="test",
            client_secret="test",
            scope="test",
            base_url="https://test.com",
            retry_total=0,
        )
        mock_get(
            aioresponses,
            "https://test.com/v2/organizations",
            body="Internal Server Error",
            status=400,
        )

        with patch_valid_token(client):
            with pytest.raises(NinjaRMMAPIError) as exc_info:
                client.get_organizations()

        assert exc_info.value.status_code == 400
        client.close()


class TestAssetTagsAPI:
    """Test cases for Asset Tags API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch("ninjapy.client.AsyncTokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token = AsyncMock(
                return_value="test_token"
            )
            mock_token_manager.return_value.close = AsyncMock()

            self.client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
            )

    def teardown_method(self):
        """Close client resources."""
        self.client.close()

    def test_get_tags_success(self, aioresponses):
        """Test successful retrieval of all asset tags."""
        mock_response = {
            "tags": [
                {
                    "id": 1,
                    "name": "Production",
                    "description": "Production servers",
                    "createTime": 1704067200.0,
                    "updateTime": 1704153600.0,
                    "createdByUserId": 10,
                    "updatedByUserId": 10,
                    "targetsCount": 5,
                    "createdBy": {"id": 10, "name": "Admin", "email": "admin@test.com"},
                    "updatedBy": {"id": 10, "name": "Admin", "email": "admin@test.com"},
                },
                {
                    "id": 2,
                    "name": "Development",
                    "description": "Dev machines",
                    "createTime": 1704067200.0,
                    "updateTime": 1704153600.0,
                    "createdByUserId": 10,
                    "updatedByUserId": 10,
                    "targetsCount": 3,
                },
            ]
        }

        mock_get(
            aioresponses,
            "https://test.com/v2/tag",
            payload=mock_response,
            status=200,
        )

        with patch_valid_token(self.client):
            result = self.client.get_tags()

        assert "tags" in result
        assert len(result["tags"]) == 2
        assert result["tags"][0]["name"] == "Production"
        assert result["tags"][1]["name"] == "Development"

    def test_create_tag_success(self, aioresponses):
        """Test successful creation of an asset tag."""
        mock_response = {
            "id": 3,
            "name": "Test Tag",
            "description": "A test tag",
            "createTime": 1704067200.0,
            "updateTime": 1704067200.0,
            "createdByUserId": 10,
            "updatedByUserId": 10,
        }

        mock_post(
            aioresponses,
            "https://test.com/v2/tag",
            payload=mock_response,
            status=200,
        )

        with patch_valid_token(self.client):
            result = self.client.create_tag(name="Test Tag", description="A test tag")

        assert result["id"] == 3
        assert result["name"] == "Test Tag"
        assert result["description"] == "A test tag"

        # Verify request body
        import json

        request_body = get_request_json(aioresponses)
        assert request_body["name"] == "Test Tag"
        assert request_body["description"] == "A test tag"

    def test_create_tag_without_description(self, aioresponses):
        """Test creating a tag without a description."""
        mock_response = {
            "id": 4,
            "name": "Simple Tag",
            "createTime": 1704067200.0,
            "updateTime": 1704067200.0,
            "createdByUserId": 10,
            "updatedByUserId": 10,
        }

        mock_post(
            aioresponses,
            "https://test.com/v2/tag",
            payload=mock_response,
            status=200,
        )

        with patch_valid_token(self.client):
            result = self.client.create_tag(name="Simple Tag")

        assert result["id"] == 4
        assert result["name"] == "Simple Tag"

    def test_update_tag_success(self, aioresponses):
        """Test successful update of an asset tag."""
        mock_response = {
            "id": 1,
            "name": "Updated Tag",
            "description": "Updated description",
            "createTime": 1704067200.0,
            "updateTime": 1704240000.0,
            "createdByUserId": 10,
            "updatedByUserId": 11,
        }

        mock_put(
            aioresponses,
            "https://test.com/v2/tag/1",
            payload=mock_response,
            status=200,
        )

        with patch_valid_token(self.client):
            result = self.client.update_tag(
                tag_id=1, name="Updated Tag", description="Updated description"
            )

        assert result["id"] == 1
        assert result["name"] == "Updated Tag"
        assert result["description"] == "Updated description"

    def test_update_tag_partial(self, aioresponses):
        """Test partial update of an asset tag (name only)."""
        mock_response = {
            "id": 1,
            "name": "New Name Only",
            "description": "Original description",
            "createTime": 1704067200.0,
            "updateTime": 1704240000.0,
            "createdByUserId": 10,
            "updatedByUserId": 11,
        }

        mock_put(
            aioresponses,
            "https://test.com/v2/tag/1",
            payload=mock_response,
            status=200,
        )

        with patch_valid_token(self.client):
            result = self.client.update_tag(tag_id=1, name="New Name Only")

        assert result["name"] == "New Name Only"

        # Verify request body only contains name
        import json

        request_body = get_request_json(aioresponses)
        assert "name" in request_body
        assert "description" not in request_body

    def test_delete_tag_success(self, aioresponses):
        """Test successful deletion of a single asset tag."""
        mock_delete(
            aioresponses,
            "https://test.com/v2/tag/1",
            status=204,
        )

        with patch_valid_token(self.client):
            # Should not raise an exception
            self.client.delete_tag(tag_id=1)

        assert len(aioresponses.requests) == 1

    def test_delete_tags_batch_success(self, aioresponses):
        """Test successful batch deletion of multiple asset tags."""
        mock_post(
            aioresponses,
            "https://test.com/v2/tag/delete",
            status=204,
        )

        with patch_valid_token(self.client):
            self.client.delete_tags(tag_ids=[1, 2, 3])

        # Verify request body
        import json

        request_body = get_request_json(aioresponses)
        assert request_body == [1, 2, 3]

    def test_merge_tags_into_existing(self, aioresponses):
        """Test merging tags into an existing tag."""
        mock_response = {
            "id": 1,
            "name": "Target Tag",
            "description": "Merged tag",
            "createTime": 1704067200.0,
            "updateTime": 1704240000.0,
            "createdByUserId": 10,
            "updatedByUserId": 11,
        }

        mock_post(
            aioresponses,
            "https://test.com/v2/tag/merge",
            payload=mock_response,
            status=200,
        )

        with patch_valid_token(self.client):
            result = self.client.merge_tags(
                tag_ids=[2, 3, 4],
                merge_method="MERGE_INTO_EXISTING_TAG",
                merge_into_tag_id=1,
            )

        assert result["id"] == 1
        assert result["name"] == "Target Tag"

        # Verify request body
        import json

        request_body = get_request_json(aioresponses)
        assert request_body["tagIds"] == [2, 3, 4]
        assert request_body["mergeMethod"] == "MERGE_INTO_EXISTING_TAG"
        assert request_body["mergeIntoTagId"] == 1

    def test_merge_tags_into_new(self, aioresponses):
        """Test merging tags into a new tag."""
        mock_response = {
            "id": 10,
            "name": "Merged New Tag",
            "description": "All merged together",
            "createTime": 1704240000.0,
            "updateTime": 1704240000.0,
            "createdByUserId": 11,
            "updatedByUserId": 11,
        }

        mock_post(
            aioresponses,
            "https://test.com/v2/tag/merge",
            payload=mock_response,
            status=200,
        )

        with patch_valid_token(self.client):
            result = self.client.merge_tags(
                tag_ids=[1, 2, 3],
                merge_method="MERGE_INTO_NEW_TAG",
                name="Merged New Tag",
                description="All merged together",
            )

        assert result["id"] == 10
        assert result["name"] == "Merged New Tag"
        assert result["description"] == "All merged together"

        # Verify request body
        import json

        request_body = get_request_json(aioresponses)
        assert request_body["tagIds"] == [1, 2, 3]
        assert request_body["mergeMethod"] == "MERGE_INTO_NEW_TAG"
        assert request_body["name"] == "Merged New Tag"
        assert request_body["description"] == "All merged together"

    def test_batch_tag_assets_add_and_remove(self, aioresponses):
        """Test batch adding and removing tags from assets."""
        mock_post(
            aioresponses,
            "https://test.com/v2/tag/device",
            status=200,
            payload={},
        )

        with patch_valid_token(self.client):
            self.client.batch_tag_assets(
                asset_type="device",
                asset_ids=[100, 101, 102],
                tag_ids_to_add=[1, 2],
                tag_ids_to_remove=[3],
            )

        # Verify request body
        import json

        request_body = get_request_json(aioresponses)
        assert request_body["assetIds"] == [100, 101, 102]
        assert request_body["tagIdsToAdd"] == [1, 2]
        assert request_body["tagIdsToRemove"] == [3]

    def test_batch_tag_assets_add_only(self, aioresponses):
        """Test batch adding tags to assets without removing."""
        mock_post(
            aioresponses,
            "https://test.com/v2/tag/device",
            status=200,
            payload={},
        )

        with patch_valid_token(self.client):
            self.client.batch_tag_assets(
                asset_type="device",
                asset_ids=[100],
                tag_ids_to_add=[1, 2, 3],
            )

        # Verify request body doesn't include tagIdsToRemove
        import json

        request_body = get_request_json(aioresponses)
        assert request_body["assetIds"] == [100]
        assert request_body["tagIdsToAdd"] == [1, 2, 3]
        assert "tagIdsToRemove" not in request_body

    def test_set_asset_tags_success(self, aioresponses):
        """Test setting exact tags for an asset."""
        mock_put(
            aioresponses,
            "https://test.com/v2/tag/device/100",
            status=200,
            payload={},
        )

        with patch_valid_token(self.client):
            self.client.set_asset_tags(
                asset_type="device",
                asset_id=100,
                tag_ids=[1, 2, 3],
            )

        # Verify request body
        import json

        request_body = get_request_json(aioresponses)
        assert request_body["tagIds"] == [1, 2, 3]

    def test_set_asset_tags_empty(self, aioresponses):
        """Test clearing all tags from an asset."""
        mock_put(
            aioresponses,
            "https://test.com/v2/tag/device/100",
            status=200,
            payload={},
        )

        with patch_valid_token(self.client):
            self.client.set_asset_tags(
                asset_type="device",
                asset_id=100,
                tag_ids=[],
            )

        # Verify request body has empty array
        import json

        request_body = get_request_json(aioresponses)
        assert request_body["tagIds"] == []

    def test_get_tags_error_handling(self, aioresponses):
        """Test error handling for get_tags."""
        mock_get(
            aioresponses,
            "https://test.com/v2/tag",
            payload={"message": "Unauthorized"},
            status=401,
        )

        with patch_valid_token(self.client):
            with pytest.raises(NinjaRMMAuthError):
                self.client.get_tags()

    def test_delete_tag_not_found(self, aioresponses):
        """Test deleting a tag that doesn't exist."""
        mock_delete(
            aioresponses,
            "https://test.com/v2/tag/999",
            payload={"message": "Tag not found"},
            status=404,
        )

        with patch_valid_token(self.client):
            with pytest.raises(NinjaRMMError):
                self.client.delete_tag(tag_id=999)
