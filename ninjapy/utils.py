"""
Utility functions for the NinjaRMM Python client.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Set, Union

logger = logging.getLogger("ninjapy.utils")

# Common timestamp field names found in NinjaRMM API responses
TIMESTAMP_FIELDS = {
    "created",
    "lastContact",
    "lastUpdate",
    "timestamp",
    "documentUpdateTime",
    "valueUpdateTime",
    "lastSeen",
    "lastReboot",
    "installDate",
    "patchDate",
    "scanDate",
    "startTime",
    "endTime",
    "modifiedTime",
    "createdTime",
    "updatedTime",
    "lastBootTime",
}

# Lowercase versions for case-insensitive matching
TIMESTAMP_FIELDS_LOWER = {field.lower() for field in TIMESTAMP_FIELDS}


def convert_epoch_to_iso(timestamp: Union[float, int, str]) -> str:
    """
    Convert epoch timestamp to ISO 8601 datetime string.

    Args:
        timestamp: Unix epoch timestamp (can be float, int, or string)

    Returns:
        ISO 8601 formatted datetime string (UTC)

    Examples:
        >>> convert_epoch_to_iso(1728487941.725760000)
        '2024-10-09T14:52:21.725760Z'
        >>> convert_epoch_to_iso(1640995200)
        '2022-01-01T00:00:00Z'
    """
    try:
        if isinstance(timestamp, str):
            timestamp = float(timestamp)

        # Convert to datetime and format as ISO string (using timezone-aware method)
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        # Format with microseconds if present, otherwise without
        if timestamp % 1 != 0:  # Has fractional seconds
            return dt.isoformat().replace('+00:00', 'Z')
        else:
            return dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')

    except (ValueError, OSError, OverflowError) as e:
        logger.warning(f"Failed to convert timestamp {timestamp}: {e}")
        return str(timestamp)  # Return original value if conversion fails


def is_timestamp_field(field_name: str) -> bool:
    """
    Check if a field name appears to be a timestamp field.

    Args:
        field_name: The field name to check

    Returns:
        True if the field appears to be a timestamp field
    """
    field_lower = field_name.lower()

    # Check exact matches first
    if field_lower in TIMESTAMP_FIELDS_LOWER:
        return True

    # Check for common timestamp patterns
    timestamp_patterns = ["time", "date",
                          "timestamp", "created", "updated", "modified"]
    return any(pattern in field_lower for pattern in timestamp_patterns)


def is_epoch_timestamp(value: Any) -> bool:
    """
    Check if a value appears to be an epoch timestamp.

    Args:
        value: The value to check

    Returns:
        True if the value appears to be an epoch timestamp
    """
    if not isinstance(value, (int, float, str)):
        return False

    try:
        timestamp = float(value)

        # Basic sanity checks for epoch timestamps
        # Should be positive and within reasonable range
        # (after 1970-01-01 and before year 2100)
        return 0 < timestamp < 4102444800  # 2100-01-01 00:00:00 UTC

    except (ValueError, TypeError):
        return False


def convert_timestamps_in_data(
    data: Any, field_names: Optional[Set[str]] = None, convert_all_numeric: bool = False
) -> Any:
    """
    Recursively convert epoch timestamps to ISO datetime strings in API response data.

    Args:
        data: The data structure to process (dict, list, or primitive)
        field_names: Set of field names to treat as timestamps (defaults to TIMESTAMP_FIELDS)
        convert_all_numeric: If True, convert all numeric values that look like timestamps

    Returns:
        Data structure with timestamps converted to ISO strings
    """
    if field_names is None:
        field_names = TIMESTAMP_FIELDS

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Check if this field should be converted
            should_convert = key in field_names or (
                convert_all_numeric and is_timestamp_field(key)
            )

            if should_convert and is_epoch_timestamp(value):
                result[key] = convert_epoch_to_iso(value)
            else:
                # Recursively process nested structures
                result[key] = convert_timestamps_in_data(
                    value, field_names, convert_all_numeric
                )
        return result

    elif isinstance(data, list):
        return [
            convert_timestamps_in_data(item, field_names, convert_all_numeric)
            for item in data
        ]

    else:
        # Primitive value, return as-is
        return data


def process_api_response(
    response_data: Any,
    convert_timestamps: bool = True,
    additional_timestamp_fields: Optional[Set[str]] = None,
) -> Any:
    """
    Process API response data with optional timestamp conversion.

    Args:
        response_data: Raw API response data
        convert_timestamps: Whether to convert epoch timestamps to ISO format
        additional_timestamp_fields: Additional field names to treat as timestamps

    Returns:
        Processed response data
    """
    if not convert_timestamps:
        return response_data

    timestamp_fields = TIMESTAMP_FIELDS.copy()
    if additional_timestamp_fields:
        timestamp_fields.update(additional_timestamp_fields)

    return convert_timestamps_in_data(response_data, timestamp_fields)
