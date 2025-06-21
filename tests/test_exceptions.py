"""
Tests for exception classes.
"""

import pytest

from ninjapy.exceptions import (
    NinjaRMMAPIError,
    NinjaRMMAuthError,
    NinjaRMMError,
    NinjaRMMValidationError,
)


class TestNinjaRMMExceptions:
    """Test cases for NinjaRMM exception classes."""

    def test_base_exception(self):
        """Test base NinjaRMMError exception."""
        error = NinjaRMMError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_auth_error(self):
        """Test NinjaRMMAuthError exception."""
        error = NinjaRMMAuthError("Authentication failed")
        assert str(error) == "Authentication failed"
        assert isinstance(error, NinjaRMMError)
        assert isinstance(error, Exception)

    def test_validation_error(self):
        """Test NinjaRMMValidationError exception."""
        error = NinjaRMMValidationError("Invalid input data")
        assert str(error) == "Invalid input data"
        assert isinstance(error, NinjaRMMError)
        assert isinstance(error, Exception)

    def test_api_error_with_message_only(self):
        """Test NinjaRMMAPIError with message only."""
        error = NinjaRMMAPIError("API request failed")
        assert str(error) == "API request failed"
        assert error.message == "API request failed"
        assert error.status_code is None
        assert error.details is None
        assert isinstance(error, NinjaRMMError)

    def test_api_error_with_status_code(self):
        """Test NinjaRMMAPIError with status code."""
        error = NinjaRMMAPIError("Not found", status_code=404)
        assert str(error) == "Not found"
        assert error.message == "Not found"
        assert error.status_code == 404
        assert error.details is None

    def test_api_error_with_details(self):
        """Test NinjaRMMAPIError with details."""
        details = {"field": "organizationId", "error": "required"}
        error = NinjaRMMAPIError("Validation failed", status_code=400, details=details)

        assert str(error) == "Validation failed"
        assert error.message == "Validation failed"
        assert error.status_code == 400
        assert error.details == details

    def test_api_error_full(self):
        """Test NinjaRMMAPIError with all parameters."""
        details = {
            "errors": [
                {"field": "name", "message": "Name is required"},
                {"field": "email", "message": "Invalid email format"},
            ]
        }
        error = NinjaRMMAPIError(
            "Multiple validation errors", status_code=422, details=details
        )

        assert error.message == "Multiple validation errors"
        assert error.status_code == 422
        assert error.details == details
        assert len(error.details["errors"]) == 2

    def test_exception_inheritance(self):
        """Test exception inheritance hierarchy."""
        # Test that all custom exceptions inherit from NinjaRMMError
        auth_error = NinjaRMMAuthError("Auth error")
        validation_error = NinjaRMMValidationError("Validation error")
        api_error = NinjaRMMAPIError("API error")

        assert isinstance(auth_error, NinjaRMMError)
        assert isinstance(validation_error, NinjaRMMError)
        assert isinstance(api_error, NinjaRMMError)

        # Test that all custom exceptions inherit from base Exception
        assert isinstance(auth_error, Exception)
        assert isinstance(validation_error, Exception)
        assert isinstance(api_error, Exception)

    def test_exception_can_be_raised_and_caught(self):
        """Test that exceptions can be properly raised and caught."""
        # Test base exception
        with pytest.raises(NinjaRMMError):
            raise NinjaRMMError("Test error")

        # Test auth exception
        with pytest.raises(NinjaRMMAuthError):
            raise NinjaRMMAuthError("Auth failed")

        # Test validation exception
        with pytest.raises(NinjaRMMValidationError):
            raise NinjaRMMValidationError("Invalid data")

        # Test API exception
        with pytest.raises(NinjaRMMAPIError):
            raise NinjaRMMAPIError("API failed", status_code=500)

    def test_catching_base_exception(self):
        """Test that base exception can catch derived exceptions."""
        # All custom exceptions should be catchable as NinjaRMMError
        with pytest.raises(NinjaRMMError):
            raise NinjaRMMAuthError("Auth error")

        with pytest.raises(NinjaRMMError):
            raise NinjaRMMValidationError("Validation error")

        with pytest.raises(NinjaRMMError):
            raise NinjaRMMAPIError("API error")

    def test_api_error_attributes_accessible(self):
        """Test that NinjaRMMAPIError attributes are accessible."""
        error = NinjaRMMAPIError(
            "Test error", status_code=400, details={"key": "value"}
        )

        # Test that attributes can be accessed without raising errors
        assert hasattr(error, "message")
        assert hasattr(error, "status_code")
        assert hasattr(error, "details")

        # Test attribute values
        assert error.message == "Test error"
        assert error.status_code == 400
        assert error.details["key"] == "value"
