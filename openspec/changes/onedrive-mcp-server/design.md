## Context

This is a greenfield project — a standalone MCP server that exposes OneDrive operations via Streamable HTTP transport. It will be deployed alongside the errand backend (as a K8s Deployment/Service or an Apple Containerization container) and consumed by task-runner agents via the MCP protocol.

The server is stateless — it receives a Microsoft OAuth access token in the Authorization header of each MCP session and proxies requests to the Microsoft Graph API. Multiple concurrent agents can connect simultaneously with different tokens.

Unlike Google Drive, the Microsoft Graph API natively supports path-based file access (`/me/drive/root:/path/to/file`), making path resolution significantly simpler.

## Goals / Non-Goals

**Goals:**

- Provide a reliable, path-based file operations interface over Microsoft Graph API
- Use identical tool names, parameters, and response shapes as the Google Drive MCP server
- Support concurrent multi-session access with independent Bearer tokens
- Handle optimistic concurrency via ETags for safe parallel writes
- Return clear, actionable error messages for permission and conflict errors
- Be deployable as a standalone Docker container with no external dependencies

**Non-Goals:**

- OAuth consent flow or token refresh (the calling application handles this)
- SharePoint site access (future enhancement)
- Office document format conversion (future enhancement)
- File sharing, permissions management, or admin operations
- Real-time change notifications (delta queries are a future possibility)

## Decisions

### 1. FastMCP with Streamable HTTP transport

**Choice:** Python FastMCP in HTTP mode, same as the Google Drive server.

**Rationale:** Consistency across the two cloud storage MCP servers. Same language, same framework, same deployment model.

### 2. Stateless Bearer token authentication

**Choice:** Same as Google Drive server — extract Bearer token from Authorization header per session.

**Rationale:** Same architecture. The errand worker provides pre-refreshed Microsoft OAuth tokens.

### 3. Native path-based access via Graph API

**Choice:** Use the Microsoft Graph API's native path addressing: `/me/drive/root:/Documents/report.md:/content` for file operations.

**Rationale:** Unlike Google Drive, no path-to-ID resolution is needed. The Graph API translates paths to item IDs server-side. This makes the implementation simpler and more efficient — each operation is a single API call.

**Note:** For operations that return item metadata (list, info), the response includes an `id` field, but we don't expose it to agents — they always use paths.

### 4. httpx for Microsoft Graph API calls

**Choice:** Use `httpx.AsyncClient` with direct HTTP calls to the Graph API endpoints.

**Rationale:** Same as Google Drive server — async-native, lightweight, full header control for ETags. The Graph API REST endpoints are well-documented. No Microsoft SDK dependency needed.

### 5. ETag-based optimistic concurrency

**Choice:** Return the `@odata.etag` from Graph API responses on reads. Accept optional `etag` parameter on writes, send as `If-Match` header. Return conflict error on mismatch.

**Rationale:** Microsoft Graph API natively supports `If-Match` with ETags. Consistent behavior with the Google Drive server.

### 6. Response format consistency

**Choice:** All tool responses use the exact same JSON schema as the Google Drive server — same field names, same types, same error format.

**Rationale:** Agents should not need to know which cloud provider they're talking to. System prompts can describe the tools once and they apply to both providers. Tool names are identical; only the MCP server name differs (`google_drive` vs `onedrive`).

## Risks / Trade-offs

**[Graph API throttling]** Microsoft Graph enforces throttling with `Retry-After` headers. **Mitigation:** Respect `Retry-After` on 429 responses with automatic retry. Document throttling behavior.

**[Token expiry mid-session]** Same risk as Google Drive — access tokens typically expire after 1 hour. **Mitigation:** Clear "token expired" error message. Agent reports failure.

**[Large file transfers]** Graph API uses upload sessions for files >4MB. **Mitigation:** For writes >4MB, use the Graph upload session API. For reads, stream content. Document recommended file size limit. Return error above configurable threshold (default 25MB).

**[Shared drives / SharePoint]** Users may expect access to SharePoint document libraries. The initial implementation only covers personal OneDrive (`/me/drive`). **Mitigation:** Document scope clearly. SharePoint access is a natural future extension via `/sites/{site-id}/drive`.
