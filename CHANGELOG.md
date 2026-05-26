# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.3] - 2026-05-26

### Fixed
- `ManagedClientSession.refresh_if_needed()` now treats `pool_max_age=None` as "never auto-recycle" instead of recreating the aiohttp session on every request (logic inversion regression from the async migration).
- `ManagedClientSession.refresh_if_needed()` is now concurrency-safe: refresh decisions are serialized through an `asyncio.Lock` so concurrent requests no longer race into double-closing the underlying session.
- `sync_iterator_from_async()` (which backs every `iter_*` method on the sync `NinjaRMMClient`) now streams items lazily instead of eagerly draining the entire async generator into memory.
- Corrected the URL path for the per-device endpoint family to the spec-compliant singular form `/v2/device/{id}/…`: `get_device`, `update_device`, `delete_device`, `get_device_alerts`, `get_device_activities`, `get_device_processes`, `get_device_services`, `get_device_software`, `get_device_volumes`, `enable_maintenance_mode`, `disable_maintenance_mode`.
- `enable_maintenance_mode()` now issues `PUT /v2/device/{id}/maintenance` with the spec-compliant `{"end": <epoch>}` body derived from `duration` (previously `POST … {"duration": n}` — wrong verb, wrong path, wrong body shape).
- Corrected the URL path for the per-organization endpoint family to the spec-compliant singular form `/v2/organization/{id}/…`: `delete_organization`, `get_organization_settings`, `update_organization_settings`, `get_organization_locations`, `create_organization_location`, `update_organization_location`, `delete_organization_location`, `get_organization_policies`, `update_organization_policies`.
- `update_document_template()` now targets the spec-compliant `PUT /v2/document-templates/{id}` (was `PUT /v2/templates/{id}`, which is not in the spec).
- `update_organization_document()` now wraps the documented bulk `PATCH /v2/organization/documents` endpoint with a one-element payload and returns the first updated document (the single-document path it previously hit is not in the spec).
- Docstrings on methods whose endpoints are not in the current public NinjaRMM API spec now call that out explicitly.

## [0.2.2] - 2026-05-26

### Fixed
- `get_organization()` now calls NinjaOne's singular detail endpoint (`/v2/organization/{id}`) to avoid 404 responses.
- Tests now close client sessions after use, removing unclosed `aiohttp` session errors from client test runs.

## [0.2.1] - 2026-05-26

### Fixed
- `create_organization_document()` now returns the created document dict in async and sync usage, matching the pre-async sync method shape.

## [0.2.0] - 2026-05-22

### Added
- Native async client (`AsyncNinjaRMMClient`) backed by `aiohttp`
- Async pagination helpers: `paginate_after`, `paginate_cursor`, `collect_all`, `map_concurrent`
- Sync `NinjaRMMClient` wrapper for backward-compatible synchronous usage
- `get_devices_by_org()` for concurrent device fetching grouped by organization
- `get_organizations_by_org()` for concurrent organization detail fetching by org ID
- Runtime dependencies on `pandas` and `tqdm` for data processing and progress display

### Changed
- Replaced `requests`/`urllib3` runtime dependencies with `aiohttp>=3.12.14`
- HTTP transport now uses aiohttp session pooling with configurable pool refresh
- OAuth token management now uses async locking via `AsyncTokenManager`
- Device endpoints now map `org_filter` to the API `df` query parameter (`org={id}`)
- Tests migrated from `responses` to `aioresponses`

### Removed
- Direct dependency on `requests` and `urllib3`
- `ExpiringHTTPAdapter` requests/urllib3 session adapter

## [0.1.4] - 2026-04-22

### Changed
- HTTP sessions now recycle pooled connections after a configurable max age to avoid reusing stale idle sockets behind load balancers and NATs
- HTTP sessions now enable TCP keepalive on pooled sockets where the platform supports it
- `request_timeout` now accepts either a single timeout value or a `(connect_timeout, read_timeout)` tuple
- Runtime dependency resolution now requires `urllib3>=2.6.3` via a newer `requests` floor to avoid known high-severity urllib3 issues in older installs
- Removed the unused `safety` UV dev-group dependency so critical `authlib` and `nltk` findings are no longer pulled into the lockfile by an unused scanner

## [0.1.3] - 2026-01-01

### Added
- **Asset Tags API**: Complete implementation of tag management endpoints
  - `get_tags()` - List all asset tags
  - `create_tag()` - Create a new tag
  - `update_tag()` - Update an existing tag
  - `delete_tag()` - Delete a single tag
  - `delete_tags()` - Batch delete multiple tags
  - `merge_tags()` - Merge tags into existing or new tag
  - `batch_tag_assets()` - Bulk add/remove tags on assets
  - `set_asset_tags()` - Set exact tags for an asset
- New TypedDict types: `TagUser`, `AssetTag`
- New enum: `TagMergeMethod`
- Comprehensive test coverage for all tag endpoints

### Changed
- Version is now dynamically read from package metadata (single source of truth)
- Security checks now use SafeDep `vet` instead of `safety` for dependency scanning
- Makefile `security` target auto-installs `vet` if not present

### Fixed
- Version sync issue between `pyproject.toml` and `__init__.py`

## [0.1.2] - 2025-06-22

### Changed
- Minor updates and fixes

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
- Related items management not yet implemented
- Vulnerability scanning not yet implemented

[Unreleased]: https://github.com/jstrn/ninjapy/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/jstrn/ninjapy/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/jstrn/ninjapy/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jstrn/ninjapy/compare/v0.1.4...v0.2.0
[0.1.4]: https://github.com/jstrn/ninjapy/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/jstrn/ninjapy/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/jstrn/ninjapy/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/jstrn/ninjapy/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jstrn/ninjapy/releases/tag/v0.1.0 
