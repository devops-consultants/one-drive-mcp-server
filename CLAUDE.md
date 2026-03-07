# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OneDrive MCP server using Python FastMCP with Streamable HTTP transport. Exposes path-based file operations (list, read, write, delete, move, create folder) against the Microsoft Graph API. Designed for containerized deployment alongside applications that manage OAuth token lifecycle.

**Status:** Pre-implementation. OpenSpec change artifacts exist in `openspec/changes/onedrive-mcp-server/` defining the full design, specs, and task breakdown.

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

This project uses OpenSpec for structured change management. Change artifacts are in `openspec/`. Use the `/opsx:*` commands to work with changes (e.g., `/opsx:apply` to implement tasks).

## Design Constraints

- Server never stores or refreshes OAuth tokens — the calling application provides fresh tokens
- Response JSON schemas must match the Google Drive MCP server exactly (provider-agnostic agent interface)
- Text detection: mime types starting with `text/`, `application/json`, `application/xml`, `application/yaml` are text; everything else is binary/base64
