"""
Tests for utility functions.
"""

from ninjapy.utils import (
    convert_epoch_to_iso,
    convert_timestamps_in_data,
    is_epoch_timestamp,
    is_timestamp_field,
    process_api_response,
)


class TestTimestampConversion:
    """Test cases for timestamp conversion functions."""

    def test_convert_epoch_to_iso_float(self):
        """Test converting float epoch timestamp."""
        timestamp = 1728487941.725760000
        result = convert_epoch_to_iso(timestamp)
        # Should include microseconds
        assert result == "2024-10-09T15:32:21.725760Z"

    def test_convert_epoch_to_iso_int(self):
        """Test converting integer epoch timestamp."""
        timestamp = 1640995200  # 2022-01-01 00:00:00 UTC
        result = convert_epoch_to_iso(timestamp)
        assert result == "2022-01-01T00:00:00Z"

    def test_convert_epoch_to_iso_string(self):
        """Test converting string epoch timestamp."""
        timestamp = "1728487941.725760"
        result = convert_epoch_to_iso(timestamp)
        assert result == "2024-10-09T15:32:21.725760Z"

    def test_convert_epoch_to_iso_invalid(self):
        """Test handling invalid timestamp."""
        result = convert_epoch_to_iso("invalid")
        assert result == "invalid"  # Should return original value

    def test_is_timestamp_field_exact_match(self):
        """Test exact field name matches."""
        assert is_timestamp_field("created") is True
        assert is_timestamp_field("lastContact") is True
        assert is_timestamp_field("documentUpdateTime") is True
        assert is_timestamp_field("regularField") is False

    def test_is_timestamp_field_pattern_match(self):
        """Test pattern-based field name matching."""
        assert is_timestamp_field("createdAt") is True
        assert is_timestamp_field("updatedOn") is True
        assert is_timestamp_field("someTimestamp") is True
        assert is_timestamp_field("installDate") is True
        assert is_timestamp_field("name") is False

    def test_is_epoch_timestamp_valid(self):
        """Test valid epoch timestamp detection."""
        assert is_epoch_timestamp(1728487941.725760) is True
        assert is_epoch_timestamp(1640995200) is True
        assert is_epoch_timestamp("1728487941.725760") is True

    def test_is_epoch_timestamp_invalid(self):
        """Test invalid epoch timestamp detection."""
        assert is_epoch_timestamp(-1) is False  # Negative
        assert is_epoch_timestamp(9999999999999) is False  # Too large
        assert is_epoch_timestamp("not_a_number") is False
        assert is_epoch_timestamp(None) is False
        assert is_epoch_timestamp([]) is False

    def test_convert_timestamps_in_dict(self):
        """Test timestamp conversion in dictionary."""
        data = {
            "id": 123,
            "name": "Test Device",
            "created": 1728487941.725760,
            "lastContact": 1640995200,
            "description": "Regular field",
        }

        result = convert_timestamps_in_data(data)

        assert result["id"] == 123
        assert result["name"] == "Test Device"
        assert result["created"] == "2024-10-09T15:32:21.725760Z"
        assert result["lastContact"] == "2022-01-01T00:00:00Z"
        assert result["description"] == "Regular field"

    def test_convert_timestamps_in_list(self):
        """Test timestamp conversion in list of dictionaries."""
        data = [
            {"id": 1, "created": 1728487941.725760},
            {"id": 2, "lastUpdate": 1640995200},
        ]

        result = convert_timestamps_in_data(data)

        assert len(result) == 2
        assert result[0]["created"] == "2024-10-09T15:32:21.725760Z"
        assert result[1]["lastUpdate"] == "2022-01-01T00:00:00Z"

    def test_convert_timestamps_nested(self):
        """Test timestamp conversion in nested structures."""
        data = {
            "device": {
                "id": 123,
                "created": 1728487941.725760,
                "details": {"lastUpdate": 1640995200},
            },
            "activities": [
                {"timestamp": 1728487941.725760, "type": "login"},
                {"timestamp": 1640995200, "type": "logout"},
            ],
        }

        result = convert_timestamps_in_data(data)

        assert result["device"]["created"] == "2024-10-09T15:32:21.725760Z"
        assert result["device"]["details"]["lastUpdate"] == "2022-01-01T00:00:00Z"
        assert result["activities"][0]["timestamp"] == "2024-10-09T15:32:21.725760Z"
        assert result["activities"][1]["timestamp"] == "2022-01-01T00:00:00Z"

    def test_convert_timestamps_custom_fields(self):
        """Test timestamp conversion with custom field names."""
        data = {"id": 123, "customTime": 1728487941.725760,
                "regularField": "value"}

        custom_fields = {"customTime"}
        result = convert_timestamps_in_data(data, field_names=custom_fields)

        assert result["customTime"] == "2024-10-09T15:32:21.725760Z"
        assert result["regularField"] == "value"

    def test_process_api_response_enabled(self):
        """Test API response processing with timestamp conversion enabled."""
        response_data = {
            "devices": [
                {
                    "id": 1,
                    "name": "Device 1",
                    "created": 1728487941.725760,
                    "lastContact": 1640995200,
                }
            ]
        }

        result = process_api_response(response_data, convert_timestamps=True)

        device = result["devices"][0]
        assert device["created"] == "2024-10-09T15:32:21.725760Z"
        assert device["lastContact"] == "2022-01-01T00:00:00Z"

    def test_process_api_response_disabled(self):
        """Test API response processing with timestamp conversion disabled."""
        response_data = {"devices": [{"id": 1, "created": 1728487941.725760}]}

        result = process_api_response(response_data, convert_timestamps=False)

        # Should return original data unchanged
        assert result == response_data
        assert result["devices"][0]["created"] == 1728487941.725760

    def test_process_api_response_additional_fields(self):
        """Test API response processing with additional timestamp fields."""
        response_data = {"customTimeField": 1728487941.725760,
                         "regularField": "value"}

        additional_fields = {"customTimeField"}
        result = process_api_response(
            response_data,
            convert_timestamps=True,
            additional_timestamp_fields=additional_fields,
        )

        assert result["customTimeField"] == "2024-10-09T15:32:21.725760Z"
        assert result["regularField"] == "value"
