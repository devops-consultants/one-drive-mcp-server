# Code Style and Conventions

## General
- Python 3.12+
- Type hints on all function signatures
- Async/await throughout (httpx async client, FastMCP async handlers)
- Logging via `logging.getLogger(__name__)`

## Naming
- snake_case for functions, methods, variables
- PascalCase for classes
- UPPER_CASE for constants
- Private helpers prefixed with `_` (e.g., `_get_client`, `_error_response`, `_build_path_url`)

## Error Handling
- `GraphAPIError` custom exception with structured `to_dict()` output
- All tool handlers wrap calls in `try/except GraphAPIError` — errors return structured JSON, never propagate
- Error format: `{"error": "<code>", "message": "<description>"}`

## Session Pattern
- `GraphClient` cached in MCP session state via `ctx.set_state("graph_client", ...)`
- Token extracted from Authorization header per session by `BearerTokenMiddleware`

## Testing
- All HTTP mocked with `respx` — no real API calls
- `pytest-asyncio` with `asyncio_mode = "auto"`
- Test both success and error paths
- Always clean up `GraphClient` instances with `await client.close()`

## Project Management
- OpenSpec workflow for structured changes
- Companion project: google-drive-mcp-server (must maintain identical tool schemas)
