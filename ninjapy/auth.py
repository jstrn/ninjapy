import logging
import time
from typing import Optional

import requests

from .exceptions import NinjaRMMAuthError

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ninjapy.auth")


class TokenManager:
    """Manages OAuth2 token lifecycle for NinjaRMM API"""

    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str):
        """
        Initialize the token manager.

        Args:
            token_url (str): OAuth2 token endpoint URL
            client_id (str): OAuth2 client ID
            client_secret (str): OAuth2 client secret
            scope (str): OAuth2 scope(s)
        """
        logger.info(f"Initializing TokenManager with URL: {token_url}")
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = "monitoring management control"

        self._access_token: Optional[str] = None
        self._refresh_token_value: Optional[str] = None
        self._token_expiry: Optional[float] = None

    def _is_token_expired(self) -> bool:
        """
        Check if the current token is expired.

        Returns:
            bool: True if token is expired or will expire in next 60 seconds
        """
        if not self._token_expiry:
            logger.info("No token expiry set, considering token expired")
            return True

        # Add 60-second buffer to prevent edge cases
        is_expired = time.time() + 60 >= self._token_expiry
        logger.info(
            f"Token expired check: {is_expired}, expires at: "
            f"{self._token_expiry}, current time: {time.time()}"
        )
        return is_expired

    def _get_new_access_token(self) -> str:
        """Get new access token using client credentials flow."""
        logger.info("Getting new access token")

        # Format payload exactly like the JavaScript version
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

        try:
            logger.info(f"Making token request to {self.token_url}")
            logger.info(f"Using payload: {payload}")

            # Use data parameter with the list of tuples instead of json
            response = requests.post(
                self.token_url,
                data=payload,  # Send as form data
                headers=headers,
                timeout=30,
            )

            logger.info(f"Token request status code: {response.status_code}")
            logger.info(f"Token response headers: {response.headers}")

            # Log response content for debugging
            try:
                logger.info(
                    f"Token response content: {response.text[:200]}..."
                )  # Log first 200 chars
            except Exception:
                logger.info("Could not log response content")

            response.raise_for_status()
            token_data = response.json()

            self._access_token = token_data["access_token"]
            self._token_expiry = time.time() + token_data["expires_in"]
            self._refresh_token_value = token_data.get("refresh_token")

            logger.info(f"Got new token, expires in {token_data['expires_in']} seconds")
            return self._access_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get access token: {str(e)}")
            # Log more details about the error
            if hasattr(e, "response") and e.response:
                logger.error(f"Error response status: {e.response.status_code}")
                logger.error(f"Error response content: {e.response.text[:200]}...")
            raise NinjaRMMAuthError(f"Failed to get new access token: {str(e)}")

    def _refresh_token(self) -> str:
        """
        Refresh the access token using refresh token.

        Returns:
            str: New access token

        Raises:
            NinjaRMMAuthError: If token refresh fails
        """
        if not self._refresh_token_value:
            raise NinjaRMMAuthError("No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token_value,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

            self._access_token = token_data["access_token"]
            self._token_expiry = time.time() + token_data["expires_in"]
            self._refresh_token_value = token_data.get("refresh_token")

            return self._access_token

        except Exception as e:
            raise NinjaRMMAuthError(f"Failed to refresh token: {str(e)}")

    def get_valid_token(self) -> str:
        """
        Get a valid access token, obtaining or refreshing if necessary.

        Returns:
            str: Valid access token

        Raises:
            NinjaRMMAuthError: If unable to obtain valid token
        """
        logger.info("Getting valid token")
        try:
            if not self._access_token or not self._token_expiry:
                logger.info("No token exists, getting new one")
                # No token exists, get new one
                return self._get_new_access_token()

            if self._is_token_expired():
                logger.info("Token is expired")
                # Token is expired
                if self._refresh_token_value:
                    logger.info("Attempting to refresh token")
                    try:
                        return self._refresh_token()
                    except NinjaRMMAuthError:
                        logger.info("Refresh failed, getting new token")
                        # If refresh fails, try getting new token
                        return self._get_new_access_token()
                else:
                    logger.info("No refresh token, getting new access token")
                    # No refresh token, get new access token
                    return self._get_new_access_token()

            # Token is still valid
            logger.info("Using existing valid token")
            return self._access_token

        except Exception as e:
            logger.error(f"Token management failed: {str(e)}")
            raise NinjaRMMAuthError(f"Token management failed: {str(e)}")

    def force_token_expiration(self):
        """
        Force the current token to be considered expired for testing purposes.
        """
        logger.info("Forcing token expiration for testing")
        if self._token_expiry:
            # Set expiry to current time minus 10 seconds
            self._token_expiry = time.time() - 10
            logger.info(f"Token expiry forced to past time: {self._token_expiry}")
        else:
            logger.info("No token exists to expire")
