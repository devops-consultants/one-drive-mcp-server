# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OneDrive MCP server using Python FastMCP with Streamable HTTP transport. Exposes path-based file operations (list, read, write, delete, move, create folder) against the Microsoft Graph API. Designed for containerized deployment alongside applications that manage OAuth token lifecycle.

**Status:** Implemented. Main specs in `openspec/specs/`, archived change in `openspec/changes/archive/`.

## Tech Stack

- **Python** with **FastMCP** (Streamable HTTP mode)
- **httpx** (async) for Microsoft Graph API calls
- **uvicorn** as ASGI server
- **Docker** container published to `ghcr.io/devops-consultants/one-drive-mcp-server`

## Architecture

### Transport & Auth
- MCP endpoint at `/mcp` using Streamable HTTP transport
- Stateless Bearer token auth: token extracted from `Authorization` header per session, passed to all Graph API calls
- Multiple concurrent sessions supported, each with independent tokens
- Health check at `GET /health`
- Configurable port via `PORT` env var (default 8080)

### Graph API Integration
- Path-based access using Graph API native syntax: `/me/drive/root:/path/to/file`
- No path-to-ID resolution needed (unlike Google Drive)
- ETag-based optimistic concurrency: reads return ETags, writes accept optional `etag` param sent as `If-Match` header
- Upload sessions for files >4MB
- Configurable max file size (default 25MB)
- Error mapping: 404 → not_found, 403 → permission_denied, 401 → auth_expired, 429 → rate_limited with Retry-After

### Session State
- `GraphClient` is cached in session state (`ctx.set_state("graph_client", ...)`) to reuse httpx connection pool
- All tool handlers wrap `_get_client(ctx)` inside `try/except GraphAPIError` — auth errors must return structured responses, not propagate
- `GraphClient.__del__` provides safety-net cleanup for unclosed connections

### Tools
Seven tools with identical names/schemas to the companion Google Drive MCP server:
- `list_files(path)` — list folder contents
- `read_file(path)` — read content + metadata (text as UTF-8, binary as base64)
- `write_file(path, content, etag?)` — create/update with optional conflict detection
- `delete_file(path)` — delete a file
- `file_info(path)` — metadata without content
- `create_folder(path)` — create folder including intermediates
- `move_file(source, destination)` — move/rename

## OpenSpec Workflow

This project uses OpenSpec for structured change management. Specs in `openspec/specs/`, archived changes in `openspec/changes/archive/`. Use `/opsx:*` commands for new changes.

## Development

- Install: `pip install -e ".[dev]"` (uses pyproject.toml, not requirements.txt)
- Tests: `pytest tests/ -v` (68 tests, all use mocked HTTP via `respx`)
- Run locally: `python -m onedrive_mcp.server`
- Python 3.12+ required (`.python-version` set to 3.12)

## Design Constraints

- Server never stores or refreshes OAuth tokens — the calling application provides fresh tokens
- Response JSON schemas must match the Google Drive MCP server exactly (provider-agnostic agent interface)
- Text detection: mime types starting with `text/`, `application/json`, `application/xml`, `application/yaml` are text; everything else is binary/base64
