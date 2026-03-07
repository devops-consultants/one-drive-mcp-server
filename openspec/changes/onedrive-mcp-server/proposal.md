# Proposal: OneDrive MCP Server

## Problem

AI agents running in ephemeral containers (like the errand task-runner) have no access to cloud storage. Users store documents, data, and collaborative content in Microsoft OneDrive, but agents can only work with git repositories and local files. This prevents agents from reading source materials, producing deliverables in shared folders, or collaborating across tasks via shared cloud documents.

Microsoft's official `files-mcp-server` is STDIO-only with certificate-based auth (client credentials flow), making it incompatible with containerized agents that require Streamable HTTP transport and user-delegated OAuth tokens.

## Solution

Build an open-source OneDrive MCP server using FastMCP with Streamable HTTP transport. The server provides path-based file operations (list, read, write, delete, move, create folder) against the Microsoft Graph API, with stateless Bearer token authentication per session.

The server is designed to be deployed as a standalone service alongside application backends (like errand) that manage OAuth token lifecycle. It receives a pre-refreshed access token in the Authorization header of each MCP session — it never stores or refreshes tokens itself.

### Key Design Decisions

- **Streamable HTTP transport** — compatible with containerized MCP clients that cannot run STDIO subprocesses
- **Stateless auth** — Bearer token per session, no token storage, no OAuth flow in the server itself
- **Path-based interface** — agents use human-readable paths like `/Documents/report.md`; the Microsoft Graph API natively supports path-based access (`/me/drive/root:/path`), making this simpler than the Google Drive equivalent
- **Optimistic concurrency** — read operations return ETags (`@odata.etag`), write operations accept an optional ETag parameter with `If-Match` header; mismatches return a conflict error
- **Multi-session concurrent access** — multiple agents can connect simultaneously with different tokens; no shared state between sessions
- **Permission error handling** — requests `Files.ReadWrite.All` scope, but gracefully returns clear error messages when the authenticated user lacks access to specific files/folders
- **Text-first, binary-aware** — text files returned as UTF-8 strings, binary files as base64-encoded content with mime_type metadata

### Tool Interface

Identical tool names and schemas to the Google Drive MCP server — agents get a consistent interface regardless of cloud provider:

- `list_files(path)` — list contents of a folder
- `read_file(path)` — read file content + metadata (etag, mime_type, size)
- `write_file(path, content, etag?)` — create or update a file with optional conflict detection
- `delete_file(path)` — delete a file
- `file_info(path)` — get metadata without content
- `create_folder(path)` — create a folder (including intermediate folders)
- `move_file(source, destination)` — move/rename a file

### Path Resolution

Microsoft Graph API supports path-based access natively:

- `/Documents/report.md` → `GET /me/drive/root:/Documents/report.md`
- `/Shared/Team/data.csv` → `GET /me/drive/root:/Shared/Team/data.csv`
- `/` → root of user's OneDrive

## Tech Stack

- **Python** with **FastMCP** (Streamable HTTP mode)
- **Microsoft Graph API** via direct HTTP with `httpx`
- **Docker** container image published to `ghcr.io/devops-consultants/one-drive-mcp-server`
- CI/CD via GitHub Actions (build image, push to GHCR)

## Non-Goals

- OAuth consent flow — the calling application (errand) handles this
- Token refresh — the calling application provides fresh tokens
- SharePoint site access (future enhancement — Graph API supports it, but scoping to OneDrive first)
- Office document format conversion (future enhancement)
- File sharing/permission management
- Real-time file watching or change notifications
