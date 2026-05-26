from importlib.metadata import version

from .async_helpers import collect_all, map_concurrent, paginate_after, paginate_cursor
from .client import AsyncNinjaRMMClient, NinjaRMMClient
from .exceptions import NinjaRMMAuthError, NinjaRMMError
from .utils import (
    convert_epoch_to_iso,
    convert_timestamps_in_data,
    is_epoch_timestamp,
    is_timestamp_field,
    process_api_response,
)

__version__ = version("ninjapy")
__all__ = [
    "AsyncNinjaRMMClient",
    "NinjaRMMClient",
    "NinjaRMMError",
    "NinjaRMMAuthError",
    "collect_all",
    "map_concurrent",
    "paginate_after",
    "paginate_cursor",
    "convert_epoch_to_iso",
    "is_timestamp_field",
    "is_epoch_timestamp",
    "convert_timestamps_in_data",
    "process_api_response",
]
