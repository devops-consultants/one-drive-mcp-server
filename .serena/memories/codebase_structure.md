# Codebase Structure

## Source Code
```
src/onedrive_mcp/
├── __init__.py           # Package init
├── server.py             # FastMCP server, tool definitions, health endpoint, middleware
└── graph_client.py       # Async Microsoft Graph API client
```

### server.py - Key Symbols
- `BearerTokenMiddleware` — extracts Bearer token on session init
- `_extract_bearer_token()`, `_get_client()`, `_error_response()` — helpers
- `list_files()`, `read_file()`, `write_file()`, `delete_file()`, `file_info()`, `create_folder()`, `move_file()` — MCP tool handlers
- `health()` — health check endpoint
- `create_app()`, `main()` — app factory and entrypoint

### graph_client.py - Key Symbols
- `GraphAPIError` — custom exception with `to_dict()` for structured error responses
- `GraphClient` — async client wrapping httpx for Graph API calls
  - Methods mirror tool names: `list_files`, `read_file`, `write_file`, `delete_file`, `file_info`, `create_folder`, `move_file`
  - `_upload_session()` for chunked uploads >4MB
  - `_request()` — central HTTP method with error mapping and retry
- Constants: `GRAPH_BASE_URL`, `DEFAULT_MAX_FILE_SIZE`, `UPLOAD_SESSION_THRESHOLD`, `TEXT_MIME_PREFIXES`, `TEXT_MIME_EXACT`
- Helpers: `is_text_mime()`, `_map_error()`, `_build_path_url()`

## Tests
```
tests/
├── __init__.py
├── conftest.py           # Shared test fixtures
├── test_auth.py          # Bearer token extraction tests
├── test_graph_client.py  # Graph API client tests (mocked HTTP)
├── test_health.py        # Health endpoint tests
└── test_tools.py         # MCP tool handler tests
```

## Config & CI
- `pyproject.toml` — package config, dependencies, pytest config
- `.python-version` — 3.12
- `Dockerfile` — python:3.12-slim based
- `docker-compose.yml` — local dev compose
- `.github/workflows/build.yml` — CI: test then build/push Docker image

## OpenSpec
- `openspec/specs/` — main specifications (server-transport, file-operations)
- `openspec/changes/archive/` — archived changes
- `openspec/config.yaml` — OpenSpec configuration
