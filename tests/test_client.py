"""
Tests for NinjaRMM client functionality.
"""

from unittest.mock import patch

import pytest
import responses

from ninjapy.client import NinjaRMMClient
from ninjapy.exceptions import NinjaRMMAuthError, NinjaRMMError


class TestNinjaRMMClient:
    """Test cases for NinjaRMMClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.token_url = "https://test.ninjarmm.com/oauth/token"
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.scope = "monitoring management control"
        self.base_url = "https://test.ninjarmm.com"

        # Mock the token manager to avoid actual OAuth calls
        with patch("ninjapy.client.TokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"

            self.client = NinjaRMMClient(
                token_url=self.token_url,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scope=self.scope,
                base_url=self.base_url,
            )

    def test_client_initialization(self):
        """Test client initialization."""
        assert self.client.base_url == self.base_url
        assert hasattr(self.client, "token_manager")
        assert hasattr(self.client, "session")

    @responses.activate
    def test_get_organizations_success(self):
        """Test successful organizations retrieval."""
        mock_orgs = [
            {"id": 1, "name": "Test Org 1", "description": "Test organization 1"},
            {"id": 2, "name": "Test Org 2", "description": "Test organization 2"},
        ]

        responses.add(
            responses.GET,
            f"{self.base_url}/v2/organizations",
            json=mock_orgs,
            status=200,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            orgs = self.client.get_organizations()

        assert len(orgs) == 2
        assert orgs[0]["name"] == "Test Org 1"
        assert orgs[1]["name"] == "Test Org 2"

    @responses.activate
    def test_get_organizations_with_parameters(self):
        """Test organizations retrieval with query parameters."""
        mock_orgs = [{"id": 1, "name": "Test Org"}]

        responses.add(
            responses.GET,
            f"{self.base_url}/v2/organizations",
            json=mock_orgs,
            status=200,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            self.client.get_organizations(page_size=10, after=100, org_filter="test")

        # Check that parameters were included in the request
        request = responses.calls[0].request
        assert "pageSize=10" in request.url
        assert "after=100" in request.url
        assert "of=test" in request.url

    @responses.activate
    def test_get_devices_success(self):
        """Test successful devices retrieval."""
        mock_devices = [
            {
                "id": 1,
                "displayName": "Test Device 1",
                "nodeClass": "WINDOWS_WORKSTATION",
            },
            {"id": 2, "displayName": "Test Device 2", "nodeClass": "WINDOWS_SERVER"},
        ]

        responses.add(
            responses.GET, f"{self.base_url}/v2/devices", json=mock_devices, status=200
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            devices = self.client.get_devices()

        assert len(devices) == 2
        assert devices[0]["displayName"] == "Test Device 1"
        assert devices[1]["displayName"] == "Test Device 2"

    @responses.activate
    def test_get_device_success(self):
        """Test successful device retrieval."""
        mock_device = {
            "id": 1,
            "displayName": "Test Device",
            "nodeClass": "WINDOWS_WORKSTATION",
            "system": {"manufacturer": "Dell Inc.", "model": "OptiPlex 7090"},
        }

        responses.add(
            responses.GET, f"{self.base_url}/v2/devices/1", json=mock_device, status=200
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            device = self.client.get_device(1)

        assert device["id"] == 1
        assert device["displayName"] == "Test Device"
        assert device["system"]["manufacturer"] == "Dell Inc."

    @responses.activate
    def test_create_organization_success(self):
        """Test successful organization creation."""
        mock_org = {
            "id": 123,
            "name": "New Test Organization",
            "description": "A new test organization",
        }

        responses.add(
            responses.POST,
            f"{self.base_url}/v2/organizations",
            json=mock_org,
            status=201,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            org = self.client.create_organization(
                name="New Test Organization", description="A new test organization"
            )

        assert org["id"] == 123
        assert org["name"] == "New Test Organization"

    @responses.activate
    def test_http_error_handling(self):
        """Test HTTP error handling."""
        responses.add(
            responses.GET,
            f"{self.base_url}/v2/organizations",
            json={"message": "Unauthorized"},
            status=401,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            with pytest.raises(NinjaRMMAuthError):
                self.client.get_organizations()

    @responses.activate
    def test_api_error_handling(self):
        """Test API error handling for non-auth errors."""
        responses.add(
            responses.GET,
            f"{self.base_url}/v2/devices/999",
            json={"message": "Device not found"},
            status=404,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            with pytest.raises(NinjaRMMError):
                self.client.get_device(999)

    @responses.activate
    def test_rate_limit_handling(self):
        """Test rate limit handling."""
        # First call returns 429, second call succeeds
        responses.add(
            responses.GET,
            f"{self.base_url}/v2/organizations",
            status=429,
            headers={"Retry-After": "1"},
        )
        responses.add(
            responses.GET,
            f"{self.base_url}/v2/organizations",
            json=[{"id": 1, "name": "Test Org"}],
            status=200,
        )

        # Temporarily remove retry adapters so our rate limit logic is tested
        from requests.adapters import HTTPAdapter

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            # Replace session adapters with ones that don't retry on 429
            original_adapters = dict(self.client.session.adapters)
            self.client.session.mount("https://", HTTPAdapter())
            self.client.session.mount("http://", HTTPAdapter())

            try:
                with patch(
                    "ninjapy.client.time.sleep"
                ) as mock_sleep:  # Mock sleep to speed up test
                    orgs = self.client.get_organizations()

                assert len(orgs) == 1
                assert orgs[0]["name"] == "Test Org"
                mock_sleep.assert_called_once_with(1)
            finally:
                # Restore original adapters
                for prefix, adapter in original_adapters.items():
                    self.client.session.mount(prefix, adapter)

    @responses.activate
    def test_no_content_response(self):
        """Test handling of 204 No Content responses."""
        responses.add(
            responses.DELETE, f"{self.base_url}/v2/organizations/123", status=204
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            result = self.client.delete_organization(123)

        assert result is None

    def test_context_manager(self):
        """Test client as context manager."""
        with patch("ninjapy.client.TokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"

            with NinjaRMMClient(
                token_url=self.token_url,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scope=self.scope,
                base_url=self.base_url,
            ) as client:
                assert isinstance(client, NinjaRMMClient)
                assert hasattr(client, "session")

    def test_pagination_with_after_basic(self):
        """Test basic pagination with 'after' parameter"""
        # Mock responses for pagination
        page1 = [{"id": 1, "name": "org1"}, {"id": 2, "name": "org2"}]
        page2 = [{"id": 3, "name": "org3"}]

        with responses.RequestsMock() as rsps:
            # First page
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/organizations",
                json=page1,
                status=200,
            )
            # Second page
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/organizations",
                json=page2,
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
                len(rsps.calls) == 2
            )  # Only 2 calls needed since second page had less than page_size

            # First call should have no 'after' parameter
            assert "pageSize=2" in rsps.calls[0].request.url
            assert "after=" not in rsps.calls[0].request.url

            # Second call should have after=2
            assert "pageSize=2" in rsps.calls[1].request.url
            assert "after=2" in rsps.calls[1].request.url

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

        with responses.RequestsMock() as rsps:
            # First page
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/devices/search",
                json=page1_response,
                status=200,
            )
            # Second page
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/devices/search",
                json=page2_response,
                status=200,
            )
            # Third page (empty)
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/devices/search",
                json=page3_response,
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
            assert len(rsps.calls) == 3

            # First call should have no cursor
            assert "pageSize=2" in rsps.calls[0].request.url
            assert "q=test" in rsps.calls[0].request.url
            assert "cursor=" not in rsps.calls[0].request.url

            # Second call should have cursor=cursor1
            assert "pageSize=2" in rsps.calls[1].request.url
            assert "cursor=cursor1" in rsps.calls[1].request.url

            # Third call should have cursor=cursor2
            assert "pageSize=2" in rsps.calls[2].request.url
            assert "cursor=cursor2" in rsps.calls[2].request.url

    def test_iter_all_organizations(self):
        """Test iterator for organizations"""
        # Mock responses for pagination
        page1 = [{"id": 1, "name": "org1"}, {"id": 2, "name": "org2"}]
        page2 = [{"id": 3, "name": "org3"}]

        with responses.RequestsMock() as rsps:
            # First page (no after parameter)
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/organizations?pageSize=2",
                json=page1,
                status=200,
            )
            # Second page (after=2 from last item of page1)
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/organizations?pageSize=2&after=2",
                json=page2,
                status=200,
            )
            # Third page would be empty (but since page2 has only 1 item < page_size=2,
            # pagination should stop automatically)

            # Test iterator
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

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/queries/windows-services",
                json=response,
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
            call = rsps.calls[0]
            assert "pageSize=50" in call.request.url
            assert "df=deviceClass+eq+%27WINDOWS_WORKSTATION%27" in call.request.url
            assert "name=test" in call.request.url
            assert "state=running" in call.request.url

    def test_pagination_empty_response(self):
        """Test pagination with empty response"""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/organizations",
                json=[],
                status=200,
            )

            # Should return empty list
            orgs = self.client.get_all_organizations()
            assert len(orgs) == 0

            # Should only make one call
            assert len(rsps.calls) == 1

    def test_pagination_single_page(self):
        """Test pagination when all results fit in one page"""
        page1 = [{"id": 1, "name": "org1"}, {"id": 2, "name": "org2"}]

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/organizations",
                json=page1,
                status=200,
            )

            # With page_size=10, should not need another call
            orgs = self.client.get_all_organizations(page_size=10)

            assert len(orgs) == 2
            assert len(rsps.calls) == 1  # Only one call needed

    def test_pagination_with_missing_id(self):
        """Test pagination behavior when ID field is missing"""
        page1 = [{"name": "org1"}, {"name": "org2"}]  # Missing 'id' field

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/organizations",
                json=page1,
                status=200,
            )

            # Should still return the results but log warning and stop pagination
            orgs = self.client.get_all_organizations(page_size=10)

            assert len(orgs) == 2
            assert len(rsps.calls) == 1

    def test_cursor_pagination_malformed_response(self):
        """Test cursor pagination with malformed response"""
        bad_response = {"not_results": []}  # Missing 'results' key

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/devices/search",
                json=bad_response,
                status=200,
            )

            # Should return empty list when response is malformed
            devices = self.client.search_all_devices("test")

            assert len(devices) == 0
            assert len(rsps.calls) == 1

    def test_get_all_devices_with_params(self):
        """Test get_all_devices with various parameters"""
        page1 = [{"id": 1, "name": "device1"}, {"id": 2, "name": "device2"}]

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{self.client.base_url}/v2/devices",
                json=page1,
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
            call = rsps.calls[0]
            assert "pageSize=50" in call.request.url
            assert "of=test_org" in call.request.url
            assert "expand=volumes" in call.request.url
            assert "includeBackupUsage=true" in call.request.url


class TestClientValidation:
    """Test cases for client input validation."""

    def test_endpoint_normalization(self):
        """Test that endpoints are properly normalized."""
        with patch("ninjapy.client.TokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"

            client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
            )

            # Test that endpoint gets normalized (leading slash added)
            with responses.RequestsMock() as rsps:
                rsps.add(responses.GET, "https://test.com/v2/test", json={}, status=200)

                # This should work whether we pass "v2/test" or "/v2/test"
                with patch.object(
                    client.token_manager, "get_valid_token", return_value="test_token"
                ):
                    client._request("GET", "v2/test")
                    client._request("GET", "/v2/test")


class TestTimestampConversion:
    """Test cases for timestamp conversion feature."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch("ninjapy.client.TokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"

            self.client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
                convert_timestamps=True,
            )

    @responses.activate
    def test_timestamp_conversion_enabled(self):
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

        responses.add(
            responses.GET, "https://test.com/v2/devices", json=mock_response, status=200
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            result = self.client.get_devices()

        device = result[0]
        assert device["created"] == "2024-10-09T15:32:21.725760Z"
        assert device["lastContact"] == "2022-01-01T00:00:00Z"
        # Non-timestamp field unchanged
        assert device["description"] == "Test device"

    @responses.activate
    def test_timestamp_conversion_disabled(self):
        """Test timestamp conversion when disabled."""
        # Create client with timestamp conversion disabled
        with patch("ninjapy.client.TokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"

            client_no_conversion = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
                convert_timestamps=False,
            )

        mock_response = [{"id": 1, "created": 1728487941.725760}]

        responses.add(
            responses.GET, "https://test.com/v2/devices", json=mock_response, status=200
        )

        result = client_no_conversion.get_devices()

        # Should return original timestamp values
        assert result[0]["created"] == 1728487941.725760

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
        with patch("ninjapy.client.TokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"

            self.client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
            )

    def test_timeout_handling(self):
        """Test timeout error handling."""
        import requests

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            with patch.object(self.client.session, "request") as mock_request:
                mock_request.side_effect = requests.exceptions.Timeout(
                    "Request timed out"
                )

                with pytest.raises(NinjaRMMError, match="Request timed out"):
                    self.client.get_organizations()

    @responses.activate
    def test_malformed_json_response(self):
        """Test handling of malformed JSON responses."""
        responses.add(
            responses.GET,
            "https://test.com/v2/organizations",
            body="invalid json response",
            status=200,
            content_type="application/json",
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            with pytest.raises(
                Exception
            ):  # Should raise some form of JSON decode error
                self.client.get_organizations()


class TestAssetTagsAPI:
    """Test cases for Asset Tags API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch("ninjapy.client.TokenManager") as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"

            self.client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com",
            )

    @responses.activate
    def test_get_tags_success(self):
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

        responses.add(
            responses.GET,
            "https://test.com/v2/tag",
            json=mock_response,
            status=200,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            result = self.client.get_tags()

        assert "tags" in result
        assert len(result["tags"]) == 2
        assert result["tags"][0]["name"] == "Production"
        assert result["tags"][1]["name"] == "Development"

    @responses.activate
    def test_create_tag_success(self):
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

        responses.add(
            responses.POST,
            "https://test.com/v2/tag",
            json=mock_response,
            status=200,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            result = self.client.create_tag(name="Test Tag", description="A test tag")

        assert result["id"] == 3
        assert result["name"] == "Test Tag"
        assert result["description"] == "A test tag"

        # Verify request body
        import json

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["name"] == "Test Tag"
        assert request_body["description"] == "A test tag"

    @responses.activate
    def test_create_tag_without_description(self):
        """Test creating a tag without a description."""
        mock_response = {
            "id": 4,
            "name": "Simple Tag",
            "createTime": 1704067200.0,
            "updateTime": 1704067200.0,
            "createdByUserId": 10,
            "updatedByUserId": 10,
        }

        responses.add(
            responses.POST,
            "https://test.com/v2/tag",
            json=mock_response,
            status=200,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            result = self.client.create_tag(name="Simple Tag")

        assert result["id"] == 4
        assert result["name"] == "Simple Tag"

    @responses.activate
    def test_update_tag_success(self):
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

        responses.add(
            responses.PUT,
            "https://test.com/v2/tag/1",
            json=mock_response,
            status=200,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            result = self.client.update_tag(
                tag_id=1, name="Updated Tag", description="Updated description"
            )

        assert result["id"] == 1
        assert result["name"] == "Updated Tag"
        assert result["description"] == "Updated description"

    @responses.activate
    def test_update_tag_partial(self):
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

        responses.add(
            responses.PUT,
            "https://test.com/v2/tag/1",
            json=mock_response,
            status=200,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            result = self.client.update_tag(tag_id=1, name="New Name Only")

        assert result["name"] == "New Name Only"

        # Verify request body only contains name
        import json

        request_body = json.loads(responses.calls[0].request.body)
        assert "name" in request_body
        assert "description" not in request_body

    @responses.activate
    def test_delete_tag_success(self):
        """Test successful deletion of a single asset tag."""
        responses.add(
            responses.DELETE,
            "https://test.com/v2/tag/1",
            status=204,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            # Should not raise an exception
            self.client.delete_tag(tag_id=1)

        assert len(responses.calls) == 1

    @responses.activate
    def test_delete_tags_batch_success(self):
        """Test successful batch deletion of multiple asset tags."""
        responses.add(
            responses.POST,
            "https://test.com/v2/tag/delete",
            status=204,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            self.client.delete_tags(tag_ids=[1, 2, 3])

        # Verify request body
        import json

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body == [1, 2, 3]

    @responses.activate
    def test_merge_tags_into_existing(self):
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

        responses.add(
            responses.POST,
            "https://test.com/v2/tag/merge",
            json=mock_response,
            status=200,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            result = self.client.merge_tags(
                tag_ids=[2, 3, 4],
                merge_method="MERGE_INTO_EXISTING_TAG",
                merge_into_tag_id=1,
            )

        assert result["id"] == 1
        assert result["name"] == "Target Tag"

        # Verify request body
        import json

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["tagIds"] == [2, 3, 4]
        assert request_body["mergeMethod"] == "MERGE_INTO_EXISTING_TAG"
        assert request_body["mergeIntoTagId"] == 1

    @responses.activate
    def test_merge_tags_into_new(self):
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

        responses.add(
            responses.POST,
            "https://test.com/v2/tag/merge",
            json=mock_response,
            status=200,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
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

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["tagIds"] == [1, 2, 3]
        assert request_body["mergeMethod"] == "MERGE_INTO_NEW_TAG"
        assert request_body["name"] == "Merged New Tag"
        assert request_body["description"] == "All merged together"

    @responses.activate
    def test_batch_tag_assets_add_and_remove(self):
        """Test batch adding and removing tags from assets."""
        responses.add(
            responses.POST,
            "https://test.com/v2/tag/device",
            status=200,
            json={},
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            self.client.batch_tag_assets(
                asset_type="device",
                asset_ids=[100, 101, 102],
                tag_ids_to_add=[1, 2],
                tag_ids_to_remove=[3],
            )

        # Verify request body
        import json

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["assetIds"] == [100, 101, 102]
        assert request_body["tagIdsToAdd"] == [1, 2]
        assert request_body["tagIdsToRemove"] == [3]

    @responses.activate
    def test_batch_tag_assets_add_only(self):
        """Test batch adding tags to assets without removing."""
        responses.add(
            responses.POST,
            "https://test.com/v2/tag/device",
            status=200,
            json={},
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            self.client.batch_tag_assets(
                asset_type="device",
                asset_ids=[100],
                tag_ids_to_add=[1, 2, 3],
            )

        # Verify request body doesn't include tagIdsToRemove
        import json

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["assetIds"] == [100]
        assert request_body["tagIdsToAdd"] == [1, 2, 3]
        assert "tagIdsToRemove" not in request_body

    @responses.activate
    def test_set_asset_tags_success(self):
        """Test setting exact tags for an asset."""
        responses.add(
            responses.PUT,
            "https://test.com/v2/tag/device/100",
            status=200,
            json={},
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            self.client.set_asset_tags(
                asset_type="device",
                asset_id=100,
                tag_ids=[1, 2, 3],
            )

        # Verify request body
        import json

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["tagIds"] == [1, 2, 3]

    @responses.activate
    def test_set_asset_tags_empty(self):
        """Test clearing all tags from an asset."""
        responses.add(
            responses.PUT,
            "https://test.com/v2/tag/device/100",
            status=200,
            json={},
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            self.client.set_asset_tags(
                asset_type="device",
                asset_id=100,
                tag_ids=[],
            )

        # Verify request body has empty array
        import json

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["tagIds"] == []

    @responses.activate
    def test_get_tags_error_handling(self):
        """Test error handling for get_tags."""
        responses.add(
            responses.GET,
            "https://test.com/v2/tag",
            json={"message": "Unauthorized"},
            status=401,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            with pytest.raises(NinjaRMMAuthError):
                self.client.get_tags()

    @responses.activate
    def test_delete_tag_not_found(self):
        """Test deleting a tag that doesn't exist."""
        responses.add(
            responses.DELETE,
            "https://test.com/v2/tag/999",
            json={"message": "Tag not found"},
            status=404,
        )

        with patch.object(
            self.client.token_manager, "get_valid_token", return_value="test_token"
        ):
            with pytest.raises(NinjaRMMError):
                self.client.delete_tag(tag_id=999)
