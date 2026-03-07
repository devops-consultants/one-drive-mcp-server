# OneDrive MCP Server - Project Overview

## Purpose
MCP (Model Context Protocol) server for Microsoft OneDrive, exposing path-based file operations against the Microsoft Graph API. Designed for containerized deployment alongside applications that manage OAuth token lifecycle.

## Tech Stack
- **Python 3.12** with **FastMCP** (Streamable HTTP mode)
- **httpx** (async) for Microsoft Graph API calls
- **uvicorn** as ASGI server
- **Docker** container published to `ghcr.io/devops-consultants/one-drive-mcp-server`
- **pytest** + **respx** for testing (all mocked HTTP, no network access needed)

## Architecture
- MCP endpoint at `/mcp` using Streamable HTTP transport
- Health check at `GET /health`
- Stateless Bearer token auth: token extracted from `Authorization` header per session
- Path-based access using Graph API native syntax: `/me/drive/root:/path/to/file`
- ETag-based optimistic concurrency for conflict detection
- Upload sessions for files >4MB
- Error mapping: 404→not_found, 403→permission_denied, 401→auth_expired, 429→rate_limited

## Tools (7 tools, matching companion Google Drive MCP server)
- `list_files(path)` — list folder contents
- `read_file(path)` — read content + metadata
- `write_file(path, content, etag?)` — create/update with optional conflict detection
- `delete_file(path)` — delete a file
- `file_info(path)` — metadata without content
- `create_folder(path)` — create folder including intermediates
- `move_file(source, destination)` — move/rename

## Key Design Constraints
- Server never stores or refreshes OAuth tokens
- Response schemas must match the Google Drive MCP server exactly
- Text detection: `text/*`, `application/json`, `application/xml`, `application/yaml` → text; else binary/base64
