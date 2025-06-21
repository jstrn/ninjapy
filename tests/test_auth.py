"""
Tests for authentication functionality.
"""

import time
from unittest.mock import patch

import pytest
import responses

from ninjapy.auth import TokenManager
from ninjapy.exceptions import NinjaRMMAuthError


class TestTokenManager:
    """Test cases for TokenManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.token_url = "https://test.ninjarmm.com/oauth/token"
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.scope = "monitoring management control"

        self.token_manager = TokenManager(
            token_url=self.token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scope=self.scope,
        )

    @responses.activate
    def test_get_token_success(self):
        """Test successful token retrieval."""
        # Mock successful token response
        responses.add(
            responses.POST,
            self.token_url,
            json={
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self.scope,
            },
            status=200,
        )

        token = self.token_manager._get_new_access_token()

        assert token == "test_access_token"
        assert self.token_manager._access_token == "test_access_token"
        assert self.token_manager._token_expiry is not None
        assert self.token_manager._token_expiry > time.time()

    @responses.activate
    def test_get_token_failure(self):
        """Test token retrieval failure."""
        # Mock failed token response
        responses.add(
            responses.POST, self.token_url, json={"error": "invalid_client"}, status=401
        )

        with pytest.raises(NinjaRMMAuthError):
            self.token_manager._get_new_access_token()

    @responses.activate
    def test_get_valid_token_when_token_is_none(self):
        """Test getting valid token when no token exists."""
        responses.add(
            responses.POST,
            self.token_url,
            json={
                "access_token": "new_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self.scope,
            },
            status=200,
        )

        token = self.token_manager.get_valid_token()

        assert token == "new_token"

    @responses.activate
    def test_get_valid_token_when_token_expired(self):
        """Test getting valid token when current token is expired."""
        # Set up expired token
        self.token_manager._access_token = "expired_token"
        self.token_manager._token_expiry = time.time() - 100

        # Mock new token response
        responses.add(
            responses.POST,
            self.token_url,
            json={
                "access_token": "refreshed_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self.scope,
            },
            status=200,
        )

        token = self.token_manager.get_valid_token()

        assert token == "refreshed_token"
        assert self.token_manager._access_token == "refreshed_token"

    def test_get_valid_token_when_token_valid(self):
        """Test getting valid token when current token is still valid."""
        # Set up valid token
        self.token_manager._access_token = "valid_token"
        self.token_manager._token_expiry = time.time() + 1800  # 30 minutes from now

        token = self.token_manager.get_valid_token()

        assert token == "valid_token"

    def test_is_token_expired_when_none(self):
        """Test token expiration check when no token exists."""
        assert self.token_manager._is_token_expired() is True

    def test_is_token_expired_when_expired(self):
        """Test token expiration check when token is expired."""
        self.token_manager._token_expiry = time.time() - 100
        assert self.token_manager._is_token_expired() is True

    def test_is_token_expired_when_valid(self):
        """Test token expiration check when token is still valid."""
        self.token_manager._token_expiry = time.time() + 1800
        assert self.token_manager._is_token_expired() is False

    @responses.activate
    def test_request_token_parameters(self):
        """Test that correct parameters are sent in token request."""
        responses.add(
            responses.POST,
            self.token_url,
            json={
                "access_token": "test_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self.scope,
            },
            status=200,
        )

        self.token_manager._get_new_access_token()

        # Check that the request was made with correct parameters
        assert len(responses.calls) == 1
        request = responses.calls[0].request

        # Parse the request body
        body = request.body if isinstance(request.body, str) else request.body.decode()
        body_params = dict(param.split("=") for param in body.split("&"))

        assert body_params["grant_type"] == "client_credentials"
        assert body_params["client_id"] == self.client_id
        assert body_params["client_secret"] == self.client_secret
        assert body_params["scope"] == self.scope.replace(" ", "+")

    def test_network_error_handling(self):
        """Test handling of network errors during token request."""
        # Mock the requests.post to raise a requests ConnectionError
        import requests

        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

            with pytest.raises(NinjaRMMAuthError):
                self.token_manager._get_new_access_token()

    @responses.activate
    def test_malformed_response_handling(self):
        """Test handling of malformed JSON responses."""
        responses.add(responses.POST, self.token_url, body="invalid json", status=200)

        with pytest.raises(NinjaRMMAuthError):
            self.token_manager._get_new_access_token()
