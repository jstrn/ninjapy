# Automatic Pagination Features

The NinjaRMM Python client now supports automatic pagination for both types of pagination used by the NinjaRMM API.

## Overview

The NinjaRMM API uses two different pagination patterns:

1. **Standard Pagination** (`pageSize` + `after`): Used by most endpoints like `/v2/organizations`, `/v2/devices`
2. **Cursor Pagination** (`pageSize` + `cursor`): Used by query endpoints like `/v2/queries/*`

This client automatically handles both types, making it easy to retrieve all records without manual pagination logic.

## Features

### ✨ Auto-Pagination Methods

**Get All Records at Once:**
```python
# Returns a complete list with all records from all pages
all_orgs = client.get_all_organizations(page_size=100)
all_devices = client.get_all_devices(page_size=50)
all_services = client.query_all_windows_services(page_size=200)
```

**Memory-Efficient Iteration:**
```python
# Process records one at a time without loading all into memory
for org in client.iter_all_organizations(page_size=100):
    process_organization(org)

for device in client.iter_all_devices(page_size=50):
    process_device(device)
```

### 🔧 How It Works

#### Standard Pagination (`after` parameter)

```python
# Manual way (old)
after = None
all_results = []
while True:
    page = client.get_organizations(page_size=100, after=after)
    if not page:
        break
    all_results.extend(page)
    if len(page) < 100:
        break
    after = page[-1]['id']

# Automatic way (new)
all_results = client.get_all_organizations(page_size=100)
```

#### Cursor Pagination (`cursor` parameter)

```python
# Manual way (old)
cursor = None
all_results = []
while True:
    response = client.query_windows_services(page_size=100, cursor=cursor)
    results = response.get('results', [])
    if not results:
        break
    all_results.extend(results)
    cursor_info = response.get('cursor', {})
    cursor = cursor_info.get('name')
    if not cursor:
        break

# Automatic way (new)
all_results = client.query_all_windows_services(page_size=100)
```

## Available Methods

### Standard Pagination Methods

| Method | Description | Iterator Version |
|--------|-------------|------------------|
| `get_all_organizations()` | Get all organizations | `iter_all_organizations()` |
| `get_all_organizations_detailed()` | Get all organizations with details | - |
| `get_all_devices()` | Get all devices | `iter_all_devices()` |
| `get_all_devices_detailed()` | Get all devices with details | - |

### Cursor Pagination Methods

| Method | Description | Iterator Version |
|--------|-------------|------------------|
| `search_all_devices()` | Search all devices | `iter_search_devices()` |
| `get_all_device_activities()` | Get all device activities | - |
| `get_all_activities()` | Get all activities | - |
| `query_all_windows_services()` | Query all Windows services | `iter_query_windows_services()` |
| `query_all_operating_systems()` | Query all operating systems | - |
| `query_all_os_patches()` | Query all OS patches | - |
| `query_all_custom_fields()` | Query all custom fields | `iter_query_custom_fields()` |
| `query_all_software()` | Query all software | - |
| `query_all_backup_usage()` | Query all backup usage | - |

## Usage Examples

### Basic Usage

```python
from ninjapy import NinjaRMMClient

client = NinjaRMMClient(
    token_url="https://app.ninjarmm.com/oauth/token",
    client_id="your_client_id",
    client_secret="your_client_secret",
    scope="monitoring management control"
)

# Get all organizations (standard pagination)
all_orgs = client.get_all_organizations(page_size=100)
print(f"Found {len(all_orgs)} organizations")

# Query all Windows services (cursor pagination)
all_services = client.query_all_windows_services(
    device_filter="deviceClass eq 'WINDOWS_WORKSTATION'",
    page_size=200
)
print(f"Found {len(all_services)} services")
```

### Memory-Efficient Processing

```python
# Process large datasets without memory issues
total_processed = 0
for device in client.iter_all_devices(page_size=100):
    # Process one device at a time
    total_processed += 1
    print(f"Processed device {total_processed}: {device['displayName']}")
    
    # Your processing logic here
    update_device_inventory(device)
```

### With Filters

```python
# Get all devices for specific organization
org_devices = client.get_all_devices(
    org_filter="my-organization",
    page_size=50
)

# Query running services on Windows workstations
running_services = client.query_all_windows_services(
    device_filter="deviceClass eq 'WINDOWS_WORKSTATION'",
    state="running",
    page_size=100
)
```

## Performance Tips

### Page Size Optimization

```python
# Smaller page sizes = more API calls (slower)
devices = client.get_all_devices(page_size=10)  # Many requests

# Larger page sizes = fewer API calls (faster)
devices = client.get_all_devices(page_size=200)  # Fewer requests
```

### Memory Usage

```python
# High memory usage - loads all into memory
all_devices = client.get_all_devices()  # Could use lots of RAM

# Low memory usage - processes one at a time
for device in client.iter_all_devices():  # Minimal RAM usage
    process_device(device)
```

### Filtering

```python
# Filter at the API level (efficient)
workstations = client.get_all_devices(
    org_filter="specific-org",
    page_size=100
)

# Don't filter in Python after getting all data (inefficient)
all_devices = client.get_all_devices()  # Gets everything
workstations = [d for d in all_devices if d.get('nodeClass') == 'WINDOWS_WORKSTATION']
```

## Error Handling

```python
from ninjapy.exceptions import NinjaRMMError, NinjaRMMAuthError

try:
    all_devices = client.get_all_devices(page_size=100)
except NinjaRMMAuthError:
    print("Authentication failed")
except NinjaRMMError as e:
    print(f"API error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Implementation Details

### Automatic Stopping Conditions

The pagination automatically stops when:

1. **Standard Pagination**: 
   - Empty response received
   - Response has fewer items than `page_size`
   - Missing `id` field in response items

2. **Cursor Pagination**:
   - Empty `results` array
   - Missing or empty `cursor` object
   - Missing `cursor.name` field

### Rate Limiting

The client includes built-in rate limiting and retry logic:
- Automatic retry on 429 (rate limited) responses
- Exponential backoff for failed requests
- Respects `Retry-After` headers

### Logging

Enable logging to see pagination progress:

```python
import logging
logging.basicConfig(level=logging.INFO)

# Will show pagination progress
all_orgs = client.get_all_organizations(page_size=50)
```

## Migration Guide

### From Manual Pagination

**Before:**
```python
# Manual pagination (old way)
after = None
all_orgs = []
while True:
    page = client.get_organizations(page_size=100, after=after)
    if not page:
        break
    all_orgs.extend(page)
    if len(page) < 100:
        break
    after = page[-1]['id']
```

**After:**
```python
# Automatic pagination (new way)
all_orgs = client.get_all_organizations(page_size=100)
```

### Performance Comparison

In typical usage scenarios:
- **API Calls**: Same number of API calls (no overhead)
- **Memory**: Iterator methods use minimal memory
- **Code**: 90% less pagination code needed
- **Errors**: Automatic handling of edge cases 