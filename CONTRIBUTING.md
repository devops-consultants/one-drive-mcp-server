# Contributing

## Development Setup

### Prerequisites

- Python 3.12+
- pip

### Install Dependencies

```bash
# Install the package with development dependencies
pip install -e ".[dev]"
```

### Run the Server Locally

```bash
PYTHONPATH=src python -m onedrive_mcp.server
```

The server starts on `http://localhost:8080` by default. Override with the `PORT` environment variable.

### Run Tests

```bash
pytest tests/ -v
```

All tests use mocked HTTP responses (via `respx`) and do not require a Microsoft account or network access.

### Project Structure

```
src/onedrive_mcp/
├── __init__.py           # Package init
├── server.py             # FastMCP server, tool definitions, health endpoint
└── graph_client.py       # Async Microsoft Graph API client

tests/
├── __init__.py
├── conftest.py           # Shared test fixtures
├── test_auth.py          # Bearer token extraction tests
├── test_graph_client.py  # Graph API client tests (mocked HTTP)
└── test_health.py        # Health endpoint tests
```

### Docker

Build and run locally:

```bash
docker build -t one-drive-mcp-server .
docker run -p 8080:8080 one-drive-mcp-server
```

Or use docker-compose:

```bash
docker-compose up --build
```

### Code Style

- Follow existing patterns in the codebase
- Use type hints for all function signatures
- Keep functions focused and well-documented
- All new features should include tests

### Testing Guidelines

- Use `respx` for mocking HTTP requests to the Microsoft Graph API
- Test both success and error paths
- Test edge cases (empty paths, missing parameters, etc.)
- Use `pytest.raises` for expected exceptions
- Always clean up `GraphClient` instances with `await client.close()`
