# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2025-06-21

### Added
- 

### Changed
- 

### Fixed
- 

### Added
- Preparation for PyPI publishing
- Comprehensive test suite
- Code quality tools configuration

## [0.1.0] - 2025-06-20

### Added
- Initial release of NinjaPy
- OAuth2 authentication with automatic token refresh
- Core API client with comprehensive endpoint coverage (~70%)
- Organization management (CRUD, locations, policies, custom fields)
- Device management (CRUD, maintenance, patch management, scripting)
- Policy management (conditions, overrides, assignments)  
- Query endpoints for comprehensive reporting
- Activity and alert management
- Webhook configuration
- Document management (basic operations)
- Error handling with custom exceptions
- Type hints throughout the codebase
- Context manager support for automatic resource cleanup
- Rate limiting and retry logic
- Pagination support for large datasets

### Supported Endpoints
- `/v2/organizations` - Organization CRUD operations
- `/v2/devices` - Device management and operations
- `/v2/policies` - Policy management and conditions
- `/v2/queries/*` - Comprehensive reporting queries
- `/v2/activities` - Activity logs and tracking
- `/v2/alerts` - Alert management
- `/v2/webhook` - Webhook configuration
- `/v2/organization/documents` - Basic document operations
- And many more...

### Dependencies
- `requests` >= 2.25.0 for HTTP operations
- `typing-extensions` >= 4.0.0 for Python < 3.10 compatibility

### Known Limitations
- Ticketing system partially implemented
- Knowledge base management not yet implemented
- Checklist management not yet implemented
- Tag management not yet implemented (Ninja's API tags endpoint is broken)
- Related items management not yet implemented
- Vulnerability scanning not yet implemented

[Unreleased]: https://github.com/jstrn/ninjapy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jstrn/ninjapy/releases/tag/v0.1.0 