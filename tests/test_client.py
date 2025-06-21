"""
Tests for NinjaRMM client functionality.
"""

import pytest
import responses
from unittest.mock import Mock, patch
import json

from ninjapy.client import NinjaRMMClient
from ninjapy.exceptions import NinjaRMMError, NinjaRMMAuthError, NinjaRMMAPIError


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
        with patch('ninjapy.client.TokenManager') as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"
            
            self.client = NinjaRMMClient(
                token_url=self.token_url,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scope=self.scope,
                base_url=self.base_url
            )
    
    def test_client_initialization(self):
        """Test client initialization."""
        assert self.client.base_url == self.base_url
        assert hasattr(self.client, 'token_manager')
        assert hasattr(self.client, 'session')
    
    @responses.activate
    def test_get_organizations_success(self):
        """Test successful organizations retrieval."""
        mock_orgs = [
            {"id": 1, "name": "Test Org 1", "description": "Test organization 1"},
            {"id": 2, "name": "Test Org 2", "description": "Test organization 2"}
        ]
        
        responses.add(
            responses.GET,
            f"{self.base_url}/v2/organizations",
            json=mock_orgs,
            status=200
        )
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
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
            status=200
        )
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
            orgs = self.client.get_organizations(page_size=10, after=100, org_filter="test")
        
        # Check that parameters were included in the request
        request = responses.calls[0].request
        assert "pageSize=10" in request.url
        assert "after=100" in request.url
        assert "of=test" in request.url
    
    @responses.activate
    def test_get_devices_success(self):
        """Test successful devices retrieval."""
        mock_devices = [
            {"id": 1, "displayName": "Test Device 1", "nodeClass": "WINDOWS_WORKSTATION"},
            {"id": 2, "displayName": "Test Device 2", "nodeClass": "WINDOWS_SERVER"}
        ]
        
        responses.add(
            responses.GET,
            f"{self.base_url}/v2/devices",
            json=mock_devices,
            status=200
        )
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
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
            "system": {
                "manufacturer": "Dell Inc.",
                "model": "OptiPlex 7090"
            }
        }
        
        responses.add(
            responses.GET,
            f"{self.base_url}/v2/devices/1",
            json=mock_device,
            status=200
        )
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
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
            "description": "A new test organization"
        }
        
        responses.add(
            responses.POST,
            f"{self.base_url}/v2/organizations",
            json=mock_org,
            status=201
        )
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
            org = self.client.create_organization(
                name="New Test Organization",
                description="A new test organization"
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
            status=401
        )
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
            with pytest.raises(NinjaRMMAuthError):
                self.client.get_organizations()
    
    @responses.activate
    def test_api_error_handling(self):
        """Test API error handling for non-auth errors."""
        responses.add(
            responses.GET,
            f"{self.base_url}/v2/devices/999",
            json={"message": "Device not found"},
            status=404
        )
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
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
            headers={"Retry-After": "1"}
        )
        responses.add(
            responses.GET,
            f"{self.base_url}/v2/organizations",
            json=[{"id": 1, "name": "Test Org"}],
            status=200
        )
        
        # Temporarily remove retry adapters so our rate limit logic is tested
        from requests.adapters import HTTPAdapter
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
            # Replace session adapters with ones that don't retry on 429
            original_adapters = dict(self.client.session.adapters)
            self.client.session.mount("https://", HTTPAdapter())
            self.client.session.mount("http://", HTTPAdapter())
            
            try:
                with patch('ninjapy.client.time.sleep') as mock_sleep:  # Mock sleep to speed up test
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
            responses.DELETE,
            f"{self.base_url}/v2/organizations/123",
            status=204
        )
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
            result = self.client.delete_organization(123)
        
        assert result is None
    
    def test_context_manager(self):
        """Test client as context manager."""
        with patch('ninjapy.client.TokenManager') as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"
            
            with NinjaRMMClient(
                token_url=self.token_url,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scope=self.scope,
                base_url=self.base_url
            ) as client:
                assert isinstance(client, NinjaRMMClient)
                assert hasattr(client, 'session')


class TestClientValidation:
    """Test cases for client input validation."""
    
    def test_endpoint_normalization(self):
        """Test that endpoints are properly normalized."""
        with patch('ninjapy.client.TokenManager') as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"
            
            client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com"
            )
            
            # Test that endpoint gets normalized (leading slash added)
            with responses.RequestsMock() as rsps:
                rsps.add(responses.GET, "https://test.com/v2/test", json={}, status=200)
                
                # This should work whether we pass "v2/test" or "/v2/test"
                with patch.object(client.token_manager, 'get_valid_token', return_value="test_token"):
                    client._request('GET', 'v2/test')
                    client._request('GET', '/v2/test')


class TestClientErrorHandling:
    """Test cases for various error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('ninjapy.client.TokenManager') as mock_token_manager:
            mock_token_manager.return_value.get_valid_token.return_value = "test_token"
            
            self.client = NinjaRMMClient(
                token_url="https://test.com/token",
                client_id="test",
                client_secret="test",
                scope="test",
                base_url="https://test.com"
            )
    
    def test_timeout_handling(self):
        """Test timeout error handling."""
        import requests
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
            with patch.object(self.client.session, 'request') as mock_request:
                mock_request.side_effect = requests.exceptions.Timeout("Request timed out")
                
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
            content_type="application/json"
        )
        
        with patch.object(self.client.token_manager, 'get_valid_token', return_value="test_token"):
            with pytest.raises(Exception):  # Should raise some form of JSON decode error
                self.client.get_organizations() 