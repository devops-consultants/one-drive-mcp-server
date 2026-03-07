## 1. Project Setup

- [ ] 1.1 Initialize Python project with pyproject.toml, requirements.txt (fastmcp, httpx, uvicorn)
- [ ] 1.2 Create Dockerfile (Python base, install deps, EXPOSE 8080, CMD)
- [ ] 1.3 Create .github/workflows/build.yml (build + push image to ghcr.io/devops-consultants/one-drive-mcp-server)
- [ ] 1.4 Create docker-compose.yml for local development/testing

## 2. Server Transport and Auth

- [ ] 2.1 Create main server entry point with FastMCP in Streamable HTTP mode on configurable PORT (default 8080)
- [ ] 2.2 Implement Bearer token extraction from Authorization header on session init
- [ ] 2.3 Implement /health endpoint returning {"status": "ok"}
- [ ] 2.4 Add error handling for missing/invalid Authorization header
- [ ] 2.5 Write tests for session auth and health endpoint

## 3. Microsoft Graph API Client

- [ ] 3.1 Create async Graph API client class using httpx (accepts Bearer token per-request)
- [ ] 3.2 Implement path-based access using Graph API native path syntax (/me/drive/root:/path)
- [ ] 3.3 Add error mapping: 404 → not_found, 403 → permission_denied, 401 → auth_expired, 429 → rate_limited
- [ ] 3.4 Add retry with Retry-After header support for 429 (throttled) responses
- [ ] 3.5 Implement upload session handling for files >4MB
- [ ] 3.6 Write tests for Graph API client (mocked API responses)

## 4. File Operation Tools

- [ ] 4.1 Implement list_files tool (query /me/drive/root:/path:/children, return structured entries)
- [ ] 4.2 Implement read_file tool (GET /me/drive/root:/path:/content, detect text/binary, return with etag)
- [ ] 4.3 Implement write_file tool (PUT /me/drive/root:/path:/content, handle If-Match etag, use upload session for large files)
- [ ] 4.4 Implement delete_file tool (DELETE /me/drive/root:/path)
- [ ] 4.5 Implement file_info tool (GET /me/drive/root:/path, return metadata without content)
- [ ] 4.6 Implement create_folder tool (POST children with folder type, handle intermediates)
- [ ] 4.7 Implement move_file tool (PATCH item with new parentReference and name)
- [ ] 4.8 Add file size limit check in read_file (configurable, default 25MB)
- [ ] 4.9 Write tests for all seven tools (mocked API responses, including error cases and ETag conflicts)

## 5. Documentation

- [ ] 5.1 Write README with project overview, deployment instructions, environment variables, tool reference
- [ ] 5.2 Document the Graph API path syntax and any OneDrive-specific behaviors
- [ ] 5.3 Add CONTRIBUTING.md with development setup instructions
