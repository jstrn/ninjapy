# NinjaPy - Python API Client for NinjaRMM (NinjaOne)

[![PyPI version](https://badge.fury.io/py/ninjapy.svg)](https://badge.fury.io/py/ninjapy)
[![Python Support](https://img.shields.io/pypi/pyversions/ninjapy.svg)](https://pypi.org/project/ninjapy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive Python API client for NinjaRMM (NinjaOne) with support for all major endpoints including device management, organization management, policy control, and more.

## Features

- **Complete API Coverage**: ~70% of NinjaRMM API endpoints implemented with ongoing development
- **OAuth2 Authentication**: Secure token-based authentication with automatic refresh
- **Type Safety**: Full type hints and runtime type checking
- **Error Handling**: Comprehensive exception handling with detailed error messages
- **Rate Limiting**: Built-in retry logic and rate limit handling
- **Timestamp Conversion**: Automatic conversion of epoch timestamps to ISO datetime format
- **Async Ready**: Designed with future async support in mind

## Installation

Install NinjaPy using pip:

```bash
pip install ninjapy
```

For development features:

```bash
pip install ninjapy[dev]
```

## Quick Start

### Authentication Setup

First, you'll need to set up OAuth2 credentials in your NinjaRMM instance:

1. Log into your NinjaOne dashboard
2. Go to **Administration** → **Apps** → **API**
3. Create a new **API Application**
4. Note down your `Client ID`, `Client Secret`, and `Token URL`
5. Set appropriate scopes: `monitoring`, `management`, `control`

### Basic Usage

```python
from ninjapy import NinjaRMMClient

# Initialize the client
client = NinjaRMMClient(
    token_url="https://app.ninjarmm.com/oauth/token",
    client_id="your_client_id",
    client_secret="your_client_secret", 
    scope="monitoring management control"
)

# Get all organizations
organizations = client.get_organizations()
print(f"Found {len(organizations)} organizations")

# Get devices for a specific organization
if organizations:
    org_id = organizations[0]["id"]
    devices = client.get_organization_devices(org_id)
    print(f"Organization {org_id} has {len(devices)} devices")

# Get device details
if devices:
    device_id = devices[0]["id"]
    device_details = client.get_device(device_id)
    print(f"Device: {device_details['displayName']}")
    
    # Get device alerts
    alerts = client.get_device_alerts(device_id)
    if alerts:
        print(f"Device has {len(alerts)} active alerts")
```

### Context Manager Usage

```python
# Recommended: Use as a context manager for automatic cleanup
with NinjaRMMClient(
    token_url="https://app.ninjarmm.com/oauth/token",
    client_id="your_client_id", 
    client_secret="your_client_secret",
    scope="monitoring management control"
) as client:
    # Perform operations
    organizations = client.get_organizations()
    
    # Client will automatically close when exiting the context
```

### Device Management

```python
# Search for devices
search_results = client.search_devices("server", page_size=50)

# Get device activities
activities = client.get_device_activities(
    device_id=123,
    start_time=1640995200,  # Unix timestamp
    activity_type="SCRIPT_EXECUTION"
)

# Reboot a device
client.reboot_device(device_id=123, mode="GRACEFUL")

# Enable maintenance mode
client.enable_maintenance_mode(device_id=123, duration=3600)  # 1 hour

# Run a script on a device
job = client.run_device_script(
    device_id=123,
    script_id=456,
    parameters={"param1": "value1"}
)
```

### Organization Management

```python
# Create a new organization
new_org = client.create_organization(
    name="New Client Organization",
    description="Created via API",
    locations=[{
        "name": "Main Office",
        "address": "123 Business St, City, State"
    }]
)

# Update organization settings
client.update_organization(
    org_id=new_org["id"],
    name="Updated Organization Name",
    node_approval_mode="MANUAL"
)

# Get organization custom fields
custom_fields = client.get_organization_custom_fields(new_org["id"])
```

### Policy Management

```python
# List all policies
policies = client.list_policies()

# Create a custom field policy condition
condition = client.create_custom_fields_policy_condition(
    policy_id=123,
    display_name="Server Memory Check",
    match_all=[{
        "fieldName": "totalMemory",
        "operator": "GREATER_THAN", 
        "value": "8192"
    }]
)
```

### Auto-Pagination Features

The NinjaRMM API supports two types of pagination, and this client automatically handles both:

#### Standard Pagination (with `after` parameter)

```python
# Get ALL organizations automatically (handles pagination)
all_orgs = client.get_all_organizations(page_size=100)
print(f"Retrieved {len(all_orgs)} organizations total")

# Get ALL devices automatically 
all_devices = client.get_all_devices(page_size=50)
print(f"Retrieved {len(all_devices)} devices total")

# Memory-efficient iteration (doesn't load all into memory)
for org in client.iter_all_organizations(page_size=100):
    print(f"Processing org: {org['name']}")
```

#### Cursor-Based Pagination (for `/v2/queries` endpoints)

```python
# Query ALL Windows services across all devices
all_services = client.query_all_windows_services(
    device_filter="deviceClass eq 'WINDOWS_WORKSTATION'",
    page_size=100
)
print(f"Found {len(all_services)} Windows services")

# Search ALL devices matching criteria
search_results = client.search_all_devices(
    query="Windows Server",
    page_size=25
)
print(f"Found {len(search_results)} matching devices")

# Get ALL custom fields with automatic pagination
custom_fields = client.query_all_custom_fields(page_size=50)
print(f"Retrieved {len(custom_fields)} custom field entries")
```

#### Available Auto-Pagination Methods

**Standard Pagination:**
- `get_all_organizations()`, `get_all_devices()`, `get_all_devices_detailed()`
- `iter_all_organizations()`, `iter_all_devices()` (memory-efficient iterators)

**Cursor-Based Pagination:**
- `search_all_devices()`, `get_all_device_activities()`, `get_all_activities()`
- `query_all_windows_services()`, `query_all_os_patches()`, `query_all_custom_fields()`
- `query_all_software()`, `query_all_backup_usage()` and more...
- Iterator versions: `iter_query_windows_services()`, `iter_query_custom_fields()`

### Error Handling

```python
from ninjapy.exceptions import NinjaRMMAuthError, NinjaRMMAPIError

try:
    organizations = client.get_organizations()
except NinjaRMMAuthError:
    print("Authentication failed - check your credentials")
except NinjaRMMAPIError as e:
    print(f"API error: {e.message} (Status: {e.status_code})")
    print(f"Details: {e.details}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## API Coverage

### ✅ Fully Implemented (70%+)

- **Organizations**: CRUD operations, locations, policies, custom fields
- **Devices**: CRUD, maintenance, patch management, scripting, custom fields
- **Policies**: Conditions, overrides, assignments
- **Queries**: Comprehensive reporting endpoints
- **Activities**: Device and system activity logs
- **Alerts**: Alert management and reset functionality
- **Webhooks**: Configuration and management
- **Document Management**: Basic document operations

### 🚧 Partially Implemented

- **Ticketing**: Basic ticket operations (creation, limited management)
- **Backup Management**: Usage reporting, basic job querying

### ⏳ Planned for Future Releases

- **Tag Management**: Asset tagging system
- **Knowledge Base**: Article and folder management
- **Checklists**: Template and organization checklist management 
- **Related Items**: Entity relationships and attachments
- **Vulnerability Scanning**: Scan groups and data management
- **Advanced Backup**: Integrity checks, comprehensive job management

## Configuration

### Environment Variables

You can configure the client using environment variables, which is the recommended approach for production applications and keeps sensitive credentials out of your code.

#### Quick Setup with .env Files

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials:**
   ```bash
   # NinjaRMM API Configuration
   NINJA_TOKEN_URL=https://app.ninjarmm.com/oauth/token
   NINJA_CLIENT_ID=your_actual_client_id
   NINJA_CLIENT_SECRET=your_actual_client_secret
   NINJA_SCOPE=monitoring management control
   NINJA_BASE_URL=https://api.ninjarmm.com
   ```

3. **Use in your code:**
   ```python
   import os
   from ninjapy import NinjaRMMClient
   
   # Option 1: Use python-dotenv to automatically load .env file
   from dotenv import load_dotenv
   load_dotenv()
   
   client = NinjaRMMClient(
       token_url=os.getenv("NINJA_TOKEN_URL"),
       client_id=os.getenv("NINJA_CLIENT_ID"), 
       client_secret=os.getenv("NINJA_CLIENT_SECRET"),
       scope=os.getenv("NINJA_SCOPE"),
       base_url=os.getenv("NINJA_BASE_URL")
   )
   
   # Option 2: Direct environment variables (without .env file)
   # Set via shell: export NINJA_CLIENT_ID="your_id"
   client = NinjaRMMClient(
       token_url=os.getenv("NINJA_TOKEN_URL"),
       client_id=os.getenv("NINJA_CLIENT_ID"),
       client_secret=os.getenv("NINJA_CLIENT_SECRET"),
       scope=os.getenv("NINJA_SCOPE", "monitoring management control")
   )
   ```

4. **Run the example:**
   ```bash
   # Install optional dependency for .env support
   pip install python-dotenv
   
   # Run the example script
   python example_with_env.py
   ```

#### Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `NINJA_TOKEN_URL` | ✅ Yes | OAuth2 token endpoint | `https://app.ninjarmm.com/oauth/token` |
| `NINJA_CLIENT_ID` | ✅ Yes | OAuth2 client ID from NinjaRMM Admin > Apps > API | `abc123...` |
| `NINJA_CLIENT_SECRET` | ✅ Yes | OAuth2 client secret from NinjaRMM Admin > Apps > API | `def456...` |
| `NINJA_SCOPE` | ✅ Yes | Space-separated OAuth2 scopes | `monitoring management control` |
| `NINJA_BASE_URL` | ❌ No | API base URL (defaults to US region) | `https://api.ninjarmm.com` |

#### Regional Endpoints

**🇺🇸 United States (Default):**
- Token URL: `https://app.ninjarmm.com/oauth/token`
- Base URL: `https://api.ninjarmm.com`

**🇪🇺 Europe:**
- Token URL: `https://eu.ninjarmm.com/oauth/token`
- Base URL: `https://eu-api.ninjarmm.com`

**🌊 Oceania:**
- Token URL: `https://oc.ninjarmm.com/oauth/token`
- Base URL: `https://oc-api.ninjarmm.com`

> **Security Note:** Never commit your `.env` file to version control! The `.gitignore` file already excludes it.

### Custom Base URL

For different NinjaRMM instances or API versions:

```python
client = NinjaRMMClient(
    token_url="https://your-instance.ninjarmm.com/oauth/token",
    client_id="your_client_id",
    client_secret="your_client_secret",
    scope="monitoring management control",
    base_url="https://your-instance.ninjarmm.com"  # Custom base URL
)
```

## Advanced Usage

### Timestamp Conversion

By default, the library automatically converts epoch timestamps to ISO 8601 datetime format for better readability:

```python
# Automatic timestamp conversion (enabled by default)
client = NinjaRMMClient(
    token_url="https://app.ninjarmm.com/oauth/token",
    client_id="your_client_id", 
    client_secret="your_client_secret",
    scope="monitoring management control",
    convert_timestamps=True  # Default behavior
)

devices = client.get_devices()
device = devices[0]

# Timestamps are automatically converted:
print(device['created'])      # "2024-10-09T14:52:21.725760Z" (ISO format)
print(device['lastContact'])  # "2024-10-09T12:30:45Z" (ISO format)
```

**Disabling Timestamp Conversion:**

```python
# Keep raw epoch timestamps
client = NinjaRMMClient(
    token_url="https://app.ninjarmm.com/oauth/token",
    client_id="your_client_id",
    client_secret="your_client_secret", 
    scope="monitoring management control",
    convert_timestamps=False
)

devices = client.get_devices()
device = devices[0]

# Timestamps remain as epoch values:
print(device['created'])      # 1728487941.725760 (epoch)
print(device['lastContact'])  # 1728484345.0 (epoch)
```

**Dynamic Control:**

```python
client = NinjaRMMClient(...)

# Check current setting
print(client.get_timestamp_conversion_status())  # True

# Disable for raw timestamps
client.set_timestamp_conversion(False)

# Re-enable for ISO format
client.set_timestamp_conversion(True)
```

**Manual Conversion Utilities:**

```python
from ninjapy.utils import convert_epoch_to_iso, is_timestamp_field

# Convert individual timestamps
iso_time = convert_epoch_to_iso(1728487941.725760)
print(iso_time)  # "2024-10-09T14:52:21.725760Z"

# Check if a field name looks like a timestamp
is_timestamp_field("created")     # True
is_timestamp_field("lastUpdate")  # True
is_timestamp_field("name")        # False
```

### Pagination

Many endpoints support pagination. Use the built-in iterator for easy handling:

```python
# Iterate through all organizations automatically
for org in client.iter_organizations(page_size=100):
    print(f"Processing organization: {org['name']}")
    
    # Process devices for each organization
    devices = client.get_organization_devices(org["id"])
    for device in devices:
        print(f"  - Device: {device['displayName']}")
```

### Filtering and Querying

```python
# Use device filters for targeted queries
windows_servers = client.get_devices(
    org_filter="organization_id=123",
    expand="references"  # Include detailed reference data
)

# Query specific device information
patch_data = client.query_os_patches(
    device_filter="node_class=WINDOWS_SERVER",
    status="PENDING",
    page_size=50
)
```

## Development

### Setting up for Development

```bash
# Clone the repository
git clone https://github.com/yourusername/ninjapy.git
cd ninjapy

# Install in development mode
pip install -e .[dev]

# Run tests
pytest

# Run linting
black ninjapy/
flake8 ninjapy/
mypy ninjapy/
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ninjapy --cov-report=html

# Run specific test files
pytest tests/test_auth.py
pytest tests/test_client.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial Python client for the NinjaRMM (NinjaOne) API. It is not affiliated with, endorsed by, or officially connected to NinjaRMM or NinjaOne in any way.

## Support

- 📖 [Documentation](https://github.com/jstrn/ninjapy#readme)
- 🐛 [Bug Reports](https://github.com/jstrn/ninjapy/issues)
- 💡 [Feature Requests](https://github.com/jstrn/ninjapy/issues)
- 📝 [Changelog](CHANGELOG.md)

## Links

- [NinjaRMM Official Documentation](https://app.ninjarmm.com/apidocs)
- [PyPI Package](https://pypi.org/project/ninjapy/)
- [GitHub Repository](https://github.com/jstrn/ninjapy) 