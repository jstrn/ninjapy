## Learned User Preferences

- Chose aiohttp as core HTTP transport with sync wrappers that preserve the existing `NinjaRMMClient` API (not async-only)
- Prefer built-in async helpers (`map_concurrent`, `get_devices_by_org`) over manual `asyncio.Semaphore` + `asyncio.gather` boilerplate
- Do not edit Cursor plan files when implementing from a plan; use them as read-only reference
- In Jupyter or other running event loops, use `AsyncNinjaRMMClient` directly rather than the sync wrapper

## Learned Workspace Facts

- Python API client library for NinjaRMM/NinjaOne (`ninjapy`); public entry points are `AsyncNinjaRMMClient` and sync-wrapped `NinjaRMMClient`
- Local development uses a project `.venv` (Python 3.12) managed with `uv`
- HTTP stack migrated from `requests`/`urllib3` to `aiohttp`; async client is source of truth, sync methods delegate via a runner bridge
- Async helpers live in `ninjapy/async_helpers.py` and are re-exported from `ninjapy` (`map_concurrent`, `collect_all`, `paginate_after`, `paginate_cursor`)
- `get_devices_by_org` fetches devices grouped by org with configurable `max_concurrency`
- Device endpoints map `org_filter` to the API `df` query parameter; correct filter syntax is `org={id}` (not `organization_id={id}`)
- `get_all_*` pagination methods fetch pages sequentially; org-level concurrency requires `map_concurrent` or `get_devices_by_org`
- Sync `NinjaRMMClient` methods fail with a clear error when called from an already-running asyncio event loop
- OpenAPI spec reference file `NinjaRMM-API-v2.json` lives at the repo root
