"""Async Microsoft Graph API client for OneDrive operations."""

import asyncio
import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

# Default maximum file size for read operations (25 MB)
DEFAULT_MAX_FILE_SIZE = 25 * 1024 * 1024

# Threshold for upload sessions (4 MB)
UPLOAD_SESSION_THRESHOLD = 4 * 1024 * 1024

# Mime types considered text
TEXT_MIME_PREFIXES = ("text/",)
TEXT_MIME_EXACT = (
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/javascript",
    "application/typescript",
    "application/xhtml+xml",
    "application/sql",
    "application/graphql",
    "application/ld+json",
    "application/x-sh",
    "application/x-python",
)


def is_text_mime(mime_type: str | None) -> bool:
    """Determine if a MIME type represents text content."""
    if not mime_type:
        return False
    mime_lower = mime_type.lower().split(";")[0].strip()
    if any(mime_lower.startswith(p) for p in TEXT_MIME_PREFIXES):
        return True
    return mime_lower in TEXT_MIME_EXACT


class GraphAPIError(Exception):
    """Structured error from Graph API operations."""

    def __init__(self, error: str, message: str, status_code: int | None = None, etag: str | None = None):
        self.error = error
        self.message = message
        self.status_code = status_code
        self.etag = etag
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"error": self.error, "message": self.message}
        if self.etag:
            result["etag"] = self.etag
        return result


def _map_error(response: httpx.Response, context: str = "") -> GraphAPIError:
    """Map HTTP status codes to structured errors."""
    status = response.status_code
    try:
        body = response.json()
        detail = body.get("error", {}).get("message", response.text[:200])
    except Exception:
        detail = response.text[:200] if response.text else "Unknown error"

    prefix = f"{context}: " if context else ""

    if status == 401:
        return GraphAPIError("auth_expired", f"{prefix}Authentication token has expired or is invalid. {detail}", status)
    elif status == 403:
        return GraphAPIError("permission_denied", f"{prefix}Access denied. {detail}", status)
    elif status == 404:
        return GraphAPIError("not_found", f"{prefix}Resource not found. {detail}", status)
    elif status == 409:
        return GraphAPIError("conflict", f"{prefix}Conflict. {detail}", status)
    elif status == 412:
        # Precondition failed - ETag mismatch
        return GraphAPIError("conflict", f"{prefix}File has been modified (ETag mismatch). {detail}", status)
    elif status == 429:
        retry_after = response.headers.get("Retry-After", "unknown")
        return GraphAPIError("rate_limited", f"{prefix}Rate limited. Retry after {retry_after} seconds. {detail}", status)
    else:
        return GraphAPIError("api_error", f"{prefix}Graph API error (HTTP {status}): {detail}", status)


def _build_path_url(path: str, suffix: str = "") -> str:
    """Build a Graph API URL from a user-facing path.

    Examples:
        "/" -> "/me/drive/root" + suffix
        "/Documents" -> "/me/drive/root:/Documents:" + suffix
        "/Documents/report.md" -> "/me/drive/root:/Documents/report.md:" + suffix
    """
    clean = path.strip()
    if not clean or clean == "/":
        return f"{GRAPH_BASE_URL}/me/drive/root{suffix}"
    # Ensure leading slash
    if not clean.startswith("/"):
        clean = "/" + clean
    # Remove trailing slash
    clean = clean.rstrip("/")
    return f"{GRAPH_BASE_URL}/me/drive/root:{clean}:{suffix}"


class GraphClient:
    """Async client for Microsoft Graph API OneDrive operations."""

    def __init__(self, token: str, max_file_size: int = DEFAULT_MAX_FILE_SIZE):
        self.token = token
        self.max_file_size = max_file_size
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def close(self):
        await self._client.aclose()

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.token}"}
        if extra:
            headers.update(extra)
        return headers

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict | None = None,
        content: bytes | None = None,
        follow_redirects: bool = True,
        max_retries: int = 2,
    ) -> httpx.Response:
        """Make a request with automatic retry on 429."""
        all_headers = self._headers(headers)
        for attempt in range(max_retries + 1):
            response = await self._client.request(
                method,
                url,
                headers=all_headers,
                json=json,
                content=content,
                follow_redirects=follow_redirects,
            )
            if response.status_code == 429 and attempt < max_retries:
                retry_after = int(response.headers.get("Retry-After", "1"))
                logger.warning(f"Rate limited (429), retrying after {retry_after}s (attempt {attempt + 1})")
                await asyncio.sleep(retry_after)
                continue
            return response
        return response  # Return last response if all retries exhausted

    async def list_files(self, path: str = "/") -> list[dict[str, Any]]:
        """List files in a folder."""
        if not path or path == "/":
            url = f"{GRAPH_BASE_URL}/me/drive/root/children"
        else:
            clean = path.strip().rstrip("/")
            if not clean.startswith("/"):
                clean = "/" + clean
            url = f"{GRAPH_BASE_URL}/me/drive/root:{clean}:/children"

        url += "?$select=name,size,lastModifiedDateTime,file,folder,parentReference,eTag"
        response = await self._request("GET", url)

        if response.status_code != 200:
            raise _map_error(response, f"list_files({path})")

        data = response.json()
        entries = []
        for item in data.get("value", []):
            parent_path = item.get("parentReference", {}).get("path", "")
            # parentReference.path is like /drive/root:/Documents
            if ":" in parent_path:
                parent = parent_path.split(":", 1)[1]
            else:
                parent = "/"
            item_path = f"{parent}/{item['name']}".replace("//", "/")

            entry: dict[str, Any] = {
                "name": item["name"],
                "path": item_path,
                "type": "folder" if "folder" in item else "file",
                "size": item.get("size") if "file" in item else None,
                "modified": item.get("lastModifiedDateTime"),
                "etag": item.get("eTag"),
            }
            entries.append(entry)
        return entries

    async def read_file(self, path: str) -> dict[str, Any]:
        """Read file content and metadata."""
        # First get metadata to check size and mime type
        meta_url = _build_path_url(path)
        meta_url += "?$select=name,size,lastModifiedDateTime,file,eTag"
        meta_response = await self._request("GET", meta_url)

        if meta_response.status_code != 200:
            raise _map_error(meta_response, f"read_file({path})")

        meta = meta_response.json()
        file_size = meta.get("size", 0)

        # Check file size limit
        if file_size > self.max_file_size:
            raise GraphAPIError(
                "file_too_large",
                f"File size ({file_size} bytes) exceeds maximum allowed size ({self.max_file_size} bytes)",
            )

        mime_type = meta.get("file", {}).get("mimeType", "application/octet-stream")
        etag = meta.get("eTag")

        # Download content
        content_url = _build_path_url(path, "/content")
        content_response = await self._request("GET", content_url)

        if content_response.status_code not in (200, 302):
            raise _map_error(content_response, f"read_file({path}) content")

        raw_content = content_response.content
        is_binary = not is_text_mime(mime_type)

        if is_binary:
            content_str = base64.b64encode(raw_content).decode("ascii")
        else:
            content_str = raw_content.decode("utf-8", errors="replace")

        return {
            "content": content_str,
            "etag": etag,
            "mime_type": mime_type,
            "size": file_size,
            "binary": is_binary,
        }

    async def write_file(self, path: str, content: str, etag: str | None = None) -> dict[str, Any]:
        """Create or update a file."""
        content_bytes = content.encode("utf-8")

        if len(content_bytes) > UPLOAD_SESSION_THRESHOLD:
            return await self._upload_session(path, content_bytes, etag)

        url = _build_path_url(path, "/content")
        headers: dict[str, str] = {"Content-Type": "application/octet-stream"}
        if etag:
            headers["If-Match"] = etag

        response = await self._request("PUT", url, headers=headers, content=content_bytes)

        if response.status_code not in (200, 201):
            if response.status_code == 412:
                # ETag mismatch - try to get current etag
                err = _map_error(response, f"write_file({path})")
                try:
                    current_meta = await self._request("GET", _build_path_url(path) + "?$select=eTag")
                    if current_meta.status_code == 200:
                        err.etag = current_meta.json().get("eTag")
                except Exception:
                    pass
                raise err
            raise _map_error(response, f"write_file({path})")

        data = response.json()
        clean = path.strip()
        if not clean.startswith("/"):
            clean = "/" + clean
        return {
            "path": clean,
            "etag": data.get("eTag"),
            "size": data.get("size"),
        }

    async def _upload_session(self, path: str, content_bytes: bytes, etag: str | None = None) -> dict[str, Any]:
        """Upload a file using an upload session (for files >4MB)."""
        url = _build_path_url(path, "/createUploadSession")
        body: dict[str, Any] = {
            "item": {
                "@microsoft.graph.conflictBehavior": "replace",
            }
        }
        if etag:
            body["item"]["@odata.etag"] = etag

        session_headers: dict[str, str] = {"Content-Type": "application/json"}
        if etag:
            session_headers["If-Match"] = etag

        response = await self._request("POST", url, headers=session_headers, json=body)

        if response.status_code not in (200, 201):
            raise _map_error(response, f"write_file({path}) create upload session")

        upload_url = response.json()["uploadUrl"]
        total_size = len(content_bytes)

        # Upload in chunks of 3.75 MB (must be multiple of 320KB)
        chunk_size = 320 * 1024 * 12  # 3,840 KB ≈ 3.75 MB
        offset = 0
        last_response = None

        while offset < total_size:
            end = min(offset + chunk_size, total_size)
            chunk = content_bytes[offset:end]
            chunk_headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {offset}-{end - 1}/{total_size}",
            }
            # Upload session URL has its own auth - don't use Bearer token
            last_response = await self._client.put(
                upload_url,
                content=chunk,
                headers=chunk_headers,
                timeout=httpx.Timeout(60.0),
            )
            if last_response.status_code not in (200, 201, 202):
                raise GraphAPIError(
                    "api_error",
                    f"Upload session chunk failed (HTTP {last_response.status_code}): {last_response.text[:200]}",
                    last_response.status_code,
                )
            offset = end

        if last_response and last_response.status_code in (200, 201):
            data = last_response.json()
            clean = path.strip()
            if not clean.startswith("/"):
                clean = "/" + clean
            return {
                "path": clean,
                "etag": data.get("eTag"),
                "size": data.get("size"),
            }

        raise GraphAPIError("api_error", "Upload session completed without a final response")

    async def delete_file(self, path: str) -> dict[str, bool]:
        """Delete a file."""
        url = _build_path_url(path)
        response = await self._request("DELETE", url)

        if response.status_code == 204:
            return {"success": True}
        raise _map_error(response, f"delete_file({path})")

    async def file_info(self, path: str) -> dict[str, Any]:
        """Get file metadata without content."""
        url = _build_path_url(path)
        url += "?$select=name,size,lastModifiedDateTime,file,folder,parentReference,eTag"
        response = await self._request("GET", url)

        if response.status_code != 200:
            raise _map_error(response, f"file_info({path})")

        item = response.json()
        mime_type = item.get("file", {}).get("mimeType") if "file" in item else None

        parent_path = item.get("parentReference", {}).get("path", "")
        if ":" in parent_path:
            parent = parent_path.split(":", 1)[1]
        else:
            parent = "/"
        item_path = f"{parent}/{item['name']}".replace("//", "/")

        return {
            "name": item["name"],
            "path": item_path,
            "type": "folder" if "folder" in item else "file",
            "size": item.get("size"),
            "modified": item.get("lastModifiedDateTime"),
            "etag": item.get("eTag"),
            "mime_type": mime_type,
        }

    async def create_folder(self, path: str) -> dict[str, str]:
        """Create a folder including intermediate folders."""
        clean = path.strip()
        if not clean.startswith("/"):
            clean = "/" + clean
        clean = clean.rstrip("/")

        parts = [p for p in clean.split("/") if p]
        current_path = ""

        for part in parts:
            parent_path = current_path if current_path else "/"
            if parent_path == "/":
                url = f"{GRAPH_BASE_URL}/me/drive/root/children"
            else:
                url = f"{GRAPH_BASE_URL}/me/drive/root:{parent_path}:/children"

            body = {
                "name": part,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "fail",
            }
            response = await self._request(
                "POST", url, headers={"Content-Type": "application/json"}, json=body
            )

            if response.status_code in (200, 201):
                current_path = f"{current_path}/{part}"
            elif response.status_code == 409:
                # Folder already exists - this is fine (idempotent)
                current_path = f"{current_path}/{part}"
            else:
                raise _map_error(response, f"create_folder({path})")

        return {"path": clean}

    async def move_file(self, source: str, destination: str) -> dict[str, str]:
        """Move or rename a file."""
        # Get item URL for source
        url = _build_path_url(source)

        # Parse destination to get parent path and new name
        dest_clean = destination.strip()
        if not dest_clean.startswith("/"):
            dest_clean = "/" + dest_clean
        dest_clean = dest_clean.rstrip("/")

        dest_parts = dest_clean.rsplit("/", 1)
        if len(dest_parts) == 2:
            dest_parent = dest_parts[0] if dest_parts[0] else "/"
            dest_name = dest_parts[1]
        else:
            dest_parent = "/"
            dest_name = dest_parts[0]

        # Build the PATCH body
        body: dict[str, Any] = {"name": dest_name}

        # If moving to a different folder, set parentReference
        source_clean = source.strip()
        if not source_clean.startswith("/"):
            source_clean = "/" + source_clean
        source_parent = source_clean.rsplit("/", 1)[0] or "/"

        if dest_parent != source_parent:
            # Need to resolve the destination parent's item ID
            if dest_parent == "/":
                parent_url = f"{GRAPH_BASE_URL}/me/drive/root?$select=id"
            else:
                parent_url = f"{GRAPH_BASE_URL}/me/drive/root:{dest_parent}:?$select=id"
            parent_response = await self._request("GET", parent_url)
            if parent_response.status_code != 200:
                raise _map_error(parent_response, f"move_file - resolve destination parent({dest_parent})")
            parent_id = parent_response.json()["id"]
            body["parentReference"] = {"id": parent_id}

        response = await self._request(
            "PATCH", url, headers={"Content-Type": "application/json"}, json=body
        )

        if response.status_code != 200:
            raise _map_error(response, f"move_file({source} -> {destination})")

        return {"path": dest_clean}
