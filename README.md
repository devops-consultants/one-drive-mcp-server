# OneDrive MCP Server

An open-source [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for Microsoft OneDrive, built with [FastMCP](https://github.com/jlowin/fastmcp) and Streamable HTTP transport.

Exposes path-based file operations (list, read, write, delete, move, create folder) against the Microsoft Graph API. Designed for containerized deployment alongside applications that manage OAuth token lifecycle.

## Features

- **Streamable HTTP transport** — MCP endpoint at `/mcp`, compatible with containerized MCP clients
- **Stateless Bearer token auth** — token per session via `Authorization` header, no OAuth flow in server
- **Path-based interface** — agents use human-readable paths like `/Documents/report.md`
- **Optimistic concurrency** — ETag-based conflict detection for safe parallel writes
- **Multi-session support** — concurrent agents with independent tokens
- **Text and binary** — text files as UTF-8, binary files as base64
- **Upload sessions** — automatic chunked upload for files >4MB
- **Rate limit handling** — automatic retry with `Retry-After` support

## Quick Start

### Docker

```bash
docker pull ghcr.io/devops-consultants/one-drive-mcp-server:latest
docker run -p 8080:8080 ghcr.io/devops-consultants/one-drive-mcp-server:latest
```

### Docker Compose

```bash
docker-compose up
```

### Local Development

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m onedrive_mcp.server
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Server listening port |
| `HOST` | `0.0.0.0` | Server bind address |
| `MAX_FILE_SIZE` | `26214400` (25MB) | Maximum file size for read operations (bytes) |

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp` | POST | MCP Streamable HTTP endpoint |
| `/health` | GET | Health check — returns `{"status": "ok"}` |

## Authentication

The server expects a Microsoft OAuth access token in the `Authorization` header of each MCP session:

```
Authorization: Bearer <microsoft-oauth-token>
```

The token must have the `Files.ReadWrite.All` scope. The server **never stores or refreshes tokens** — the calling application is responsible for obtaining and refreshing tokens.

## Tools

Seven tools with identical names and schemas to the companion Google Drive MCP server:

### `list_files(path)`

List files and folders in a directory.

**Parameters:**
- `path` (string, default: `"/"`) — Directory path to list

**Returns:** Array of entries, each with `name`, `path`, `type` ("file"/"folder"), `size`, `modified`, `etag`

### `read_file(path)`

Read a file's content and metadata.

**Parameters:**
- `path` (string) — Path to the file

**Returns:** `content`, `etag`, `mime_type`, `size`, `binary` (boolean)

Text files (mime types starting with `text/`, plus `application/json`, `application/xml`, `application/yaml`) are returned as UTF-8 strings with `binary: false`. All other files are base64-encoded with `binary: true`.

### `write_file(path, content, etag?)`

Create or update a file.

**Parameters:**
- `path` (string) — File path
- `content` (string) — File content
- `etag` (string, optional) — ETag for conflict detection

**Returns:** `path`, `etag` (new), `size`

When `etag` is provided, the server sends an `If-Match` header. On mismatch, returns a `conflict` error with the current ETag.

### `delete_file(path)`

Delete a file.

**Parameters:**
- `path` (string) — Path to the file

**Returns:** `{"success": true}`

### `file_info(path)`

Get file/folder metadata without downloading content.

**Parameters:**
- `path` (string) — Path to the file or folder

**Returns:** `name`, `path`, `type`, `size`, `modified`, `etag`, `mime_type`

### `create_folder(path)`

Create a folder (including intermediate folders).

**Parameters:**
- `path` (string) — Folder path to create

**Returns:** `{"path": "<created path>"}`

### `move_file(source, destination)`

Move or rename a file.

**Parameters:**
- `source` (string) — Current file path
- `destination` (string) — New file path

**Returns:** `{"path": "<new path>"}`

## Graph API Path Syntax

The Microsoft Graph API natively supports path-based file access, making this simpler than Google Drive:

| User Path | Graph API URL |
|-----------|--------------|
| `/` (root) | `GET /me/drive/root` |
| `/Documents` | `GET /me/drive/root:/Documents:` |
| `/Documents/report.md` | `GET /me/drive/root:/Documents/report.md:` |
| `/Documents/report.md` (content) | `GET /me/drive/root:/Documents/report.md:/content` |
| `/Documents` (children) | `GET /me/drive/root:/Documents:/children` |

No path-to-ID resolution is needed — the Graph API translates paths to item IDs server-side.

## OneDrive-Specific Behaviors

- **ETag format**: Microsoft uses `@odata.etag` in the format `"{guid},{version}"`. These are opaque strings — store and pass them as-is.
- **Upload sessions**: Files larger than 4MB are uploaded using the Graph API upload session mechanism, which uploads in chunks of ~3.75MB.
- **Throttling**: Microsoft Graph enforces rate limits. The server automatically retries on HTTP 429 responses, respecting the `Retry-After` header.
- **Path encoding**: The Graph API handles URL encoding internally. Paths with spaces and special characters work naturally.
- **Folder creation**: Uses `@microsoft.graph.conflictBehavior: "fail"` to detect existing folders, making `create_folder` idempotent.

## Error Responses

All errors follow a consistent format:

```json
{"error": "<error_code>", "message": "<human-readable description>"}
```

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `not_found` | 404 | File or folder does not exist |
| `permission_denied` | 403 | User lacks access to the resource |
| `auth_expired` | 401 | OAuth token has expired or is invalid |
| `rate_limited` | 429 | Microsoft Graph rate limit exceeded |
| `conflict` | 412 | ETag mismatch (file modified since last read) |
| `file_too_large` | — | File exceeds configured maximum size |
| `api_error` | Various | Other Graph API errors |

## License

MIT
