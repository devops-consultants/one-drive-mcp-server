"""Tests for the Microsoft Graph API client."""

import json
import re
import pytest
import httpx
import respx
from respx.patterns import M

from onedrive_mcp.graph_client import (
    GraphClient,
    GraphAPIError,
    _build_path_url,
    _map_error,
    is_text_mime,
    GRAPH_BASE_URL,
    DEFAULT_MAX_FILE_SIZE,
)


# --- Unit tests for helper functions ---


class TestIsTextMime:
    def test_text_plain(self):
        assert is_text_mime("text/plain") is True

    def test_text_html(self):
        assert is_text_mime("text/html") is True

    def test_application_json(self):
        assert is_text_mime("application/json") is True

    def test_application_xml(self):
        assert is_text_mime("application/xml") is True

    def test_application_yaml(self):
        assert is_text_mime("application/yaml") is True

    def test_application_octet_stream(self):
        assert is_text_mime("application/octet-stream") is False

    def test_image_png(self):
        assert is_text_mime("image/png") is False

    def test_none_type(self):
        assert is_text_mime(None) is False

    def test_text_with_charset(self):
        assert is_text_mime("text/plain; charset=utf-8") is True


class TestBuildPathUrl:
    def test_root_path(self):
        assert _build_path_url("/") == f"{GRAPH_BASE_URL}/me/drive/root"

    def test_empty_path(self):
        assert _build_path_url("") == f"{GRAPH_BASE_URL}/me/drive/root"

    def test_subfolder(self):
        assert _build_path_url("/Documents") == f"{GRAPH_BASE_URL}/me/drive/root:/Documents:"

    def test_file_path(self):
        assert _build_path_url("/Documents/report.md") == f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:"

    def test_path_with_suffix(self):
        assert _build_path_url("/Documents/report.md", "/content") == f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:/content"

    def test_root_with_suffix(self):
        assert _build_path_url("/", "/children") == f"{GRAPH_BASE_URL}/me/drive/root/children"

    def test_trailing_slash_stripped(self):
        assert _build_path_url("/Documents/") == f"{GRAPH_BASE_URL}/me/drive/root:/Documents:"

    def test_no_leading_slash(self):
        assert _build_path_url("Documents/report.md") == f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:"


class TestMapError:
    def test_401_maps_to_auth_expired(self):
        response = httpx.Response(401, json={"error": {"message": "Token expired"}})
        err = _map_error(response)
        assert err.error == "auth_expired"

    def test_403_maps_to_permission_denied(self):
        response = httpx.Response(403, json={"error": {"message": "Access denied"}})
        err = _map_error(response)
        assert err.error == "permission_denied"

    def test_404_maps_to_not_found(self):
        response = httpx.Response(404, json={"error": {"message": "Item not found"}})
        err = _map_error(response)
        assert err.error == "not_found"

    def test_409_maps_to_conflict(self):
        response = httpx.Response(409, json={"error": {"message": "Conflict"}})
        err = _map_error(response)
        assert err.error == "conflict"

    def test_412_maps_to_conflict(self):
        response = httpx.Response(412, json={"error": {"message": "Precondition failed"}})
        err = _map_error(response)
        assert err.error == "conflict"

    def test_429_maps_to_rate_limited(self):
        response = httpx.Response(429, headers={"Retry-After": "5"}, json={"error": {"message": "Throttled"}})
        err = _map_error(response)
        assert err.error == "rate_limited"
        assert "5" in err.message

    def test_500_maps_to_api_error(self):
        response = httpx.Response(500, json={"error": {"message": "Internal error"}})
        err = _map_error(response)
        assert err.error == "api_error"

    def test_context_included_in_message(self):
        response = httpx.Response(404, json={"error": {"message": "Not found"}})
        err = _map_error(response, "list_files(/test)")
        assert "list_files(/test)" in err.message


class TestGraphAPIError:
    def test_to_dict_basic(self):
        err = GraphAPIError("not_found", "File not found")
        assert err.to_dict() == {"error": "not_found", "message": "File not found"}

    def test_to_dict_with_etag(self):
        err = GraphAPIError("conflict", "ETag mismatch", etag="abc123")
        d = err.to_dict()
        assert d["error"] == "conflict"
        assert d["etag"] == "abc123"


# --- Integration tests with mocked HTTP ---


def _url_startswith(prefix: str):
    """Match URLs that start with the given prefix (ignoring query params)."""
    def check(request: httpx.Request) -> bool:
        url_str = str(request.url)
        base_url = url_str.split("?")[0]
        return base_url == prefix
    return check


@pytest.mark.asyncio
class TestGraphClientListFiles:
    @respx.mock
    async def test_list_root(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root/children").mock(
            return_value=httpx.Response(200, json={
                "value": [
                    {
                        "name": "Documents",
                        "folder": {"childCount": 5},
                        "size": 0,
                        "lastModifiedDateTime": "2024-01-01T00:00:00Z",
                        "eTag": "etag1",
                        "parentReference": {"path": "/drive/root:"},
                    },
                    {
                        "name": "report.md",
                        "file": {"mimeType": "text/markdown"},
                        "size": 1024,
                        "lastModifiedDateTime": "2024-01-02T00:00:00Z",
                        "eTag": "etag2",
                        "parentReference": {"path": "/drive/root:"},
                    },
                ]
            })
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.list_files("/")
            assert len(result) == 2
            assert result[0]["name"] == "Documents"
            assert result[0]["type"] == "folder"
            assert result[0]["size"] is None
            assert result[1]["name"] == "report.md"
            assert result[1]["type"] == "file"
            assert result[1]["size"] == 1024
        finally:
            await client.close()

    @respx.mock
    async def test_list_subfolder(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/Documents/Reports:/children").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.list_files("/Documents/Reports")
            assert result == []
        finally:
            await client.close()

    @respx.mock
    async def test_list_not_found(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/nonexistent:/children").mock(
            return_value=httpx.Response(404, json={"error": {"message": "Item not found"}})
        )
        client = GraphClient(token="test-token")
        try:
            with pytest.raises(GraphAPIError) as exc_info:
                await client.list_files("/nonexistent")
            assert exc_info.value.error == "not_found"
        finally:
            await client.close()

    @respx.mock
    async def test_list_permission_denied(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/restricted:/children").mock(
            return_value=httpx.Response(403, json={"error": {"message": "Access denied"}})
        )
        client = GraphClient(token="test-token")
        try:
            with pytest.raises(GraphAPIError) as exc_info:
                await client.list_files("/restricted")
            assert exc_info.value.error == "permission_denied"
        finally:
            await client.close()


@pytest.mark.asyncio
class TestGraphClientReadFile:
    @respx.mock
    async def test_read_text_file(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:").mock(
            side_effect=lambda request: httpx.Response(200, json={
                "name": "report.md",
                "size": 13,
                "lastModifiedDateTime": "2024-01-01T00:00:00Z",
                "eTag": "etag1",
                "file": {"mimeType": "text/markdown"},
            }) if "/content" not in str(request.url) else httpx.Response(200, content=b"# Hello World")
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.read_file("/Documents/report.md")
            assert result["content"] == "# Hello World"
            assert result["binary"] is False
            assert result["mime_type"] == "text/markdown"
            assert result["etag"] == "etag1"
            assert result["size"] == 13
        finally:
            await client.close()

    @respx.mock
    async def test_read_binary_file(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/Images/logo.png:").mock(
            side_effect=lambda request: httpx.Response(200, json={
                "name": "logo.png",
                "size": 4,
                "lastModifiedDateTime": "2024-01-01T00:00:00Z",
                "eTag": "etag2",
                "file": {"mimeType": "image/png"},
            }) if "/content" not in str(request.url) else httpx.Response(200, content=b"\x89PNG")
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.read_file("/Images/logo.png")
            assert result["binary"] is True
            assert result["mime_type"] == "image/png"
            import base64
            decoded = base64.b64decode(result["content"])
            assert decoded == b"\x89PNG"
        finally:
            await client.close()

    @respx.mock
    async def test_read_file_not_found(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/nonexistent.txt:").mock(
            return_value=httpx.Response(404, json={"error": {"message": "Item not found"}})
        )
        client = GraphClient(token="test-token")
        try:
            with pytest.raises(GraphAPIError) as exc_info:
                await client.read_file("/nonexistent.txt")
            assert exc_info.value.error == "not_found"
        finally:
            await client.close()

    @respx.mock
    async def test_read_file_too_large(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/bigfile.bin:").mock(
            return_value=httpx.Response(200, json={
                "name": "bigfile.bin",
                "size": 30 * 1024 * 1024,  # 30MB
                "lastModifiedDateTime": "2024-01-01T00:00:00Z",
                "eTag": "etag3",
                "file": {"mimeType": "application/octet-stream"},
            })
        )
        client = GraphClient(token="test-token")
        try:
            with pytest.raises(GraphAPIError) as exc_info:
                await client.read_file("/bigfile.bin")
            assert exc_info.value.error == "file_too_large"
        finally:
            await client.close()

    @respx.mock
    async def test_read_file_custom_max_size(self):
        """File size limit is configurable."""
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/medium.bin:").mock(
            return_value=httpx.Response(200, json={
                "name": "medium.bin",
                "size": 1024,
                "lastModifiedDateTime": "2024-01-01T00:00:00Z",
                "eTag": "etag4",
                "file": {"mimeType": "application/octet-stream"},
            })
        )
        client = GraphClient(token="test-token", max_file_size=512)
        try:
            with pytest.raises(GraphAPIError) as exc_info:
                await client.read_file("/medium.bin")
            assert exc_info.value.error == "file_too_large"
        finally:
            await client.close()


@pytest.mark.asyncio
class TestGraphClientWriteFile:
    @respx.mock
    async def test_write_new_file(self):
        respx.put(f"{GRAPH_BASE_URL}/me/drive/root:/Documents/new-report.md:/content").mock(
            return_value=httpx.Response(201, json={
                "name": "new-report.md",
                "size": 12,
                "eTag": "new-etag",
            })
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.write_file("/Documents/new-report.md", "# Report\n...")
            assert result["path"] == "/Documents/new-report.md"
            assert result["etag"] == "new-etag"
            assert result["size"] == 12
        finally:
            await client.close()

    @respx.mock
    async def test_write_with_valid_etag(self):
        route = respx.put(f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:/content").mock(
            return_value=httpx.Response(200, json={
                "name": "report.md",
                "size": 7,
                "eTag": "new-etag",
            })
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.write_file("/Documents/report.md", "updated", etag="abc123")
            assert result["etag"] == "new-etag"
            # Verify If-Match header was sent
            assert route.calls[0].request.headers["if-match"] == "abc123"
        finally:
            await client.close()

    @respx.mock
    async def test_write_with_stale_etag(self):
        respx.put(f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:/content").mock(
            return_value=httpx.Response(412, json={"error": {"message": "Precondition failed"}})
        )
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:").mock(
            return_value=httpx.Response(200, json={"eTag": "current-etag"})
        )
        client = GraphClient(token="test-token")
        try:
            with pytest.raises(GraphAPIError) as exc_info:
                await client.write_file("/Documents/report.md", "updated", etag="old-etag")
            assert exc_info.value.error == "conflict"
            assert exc_info.value.etag == "current-etag"
        finally:
            await client.close()

    @respx.mock
    async def test_write_without_etag(self):
        route = respx.put(f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:/content").mock(
            return_value=httpx.Response(200, json={
                "name": "report.md",
                "size": 7,
                "eTag": "new-etag",
            })
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.write_file("/Documents/report.md", "updated")
            assert result["etag"] == "new-etag"
            # Verify no If-Match header
            assert "if-match" not in route.calls[0].request.headers
        finally:
            await client.close()


@pytest.mark.asyncio
class TestGraphClientDeleteFile:
    @respx.mock
    async def test_delete_existing_file(self):
        respx.delete(f"{GRAPH_BASE_URL}/me/drive/root:/Documents/old-report.md:").mock(
            return_value=httpx.Response(204)
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.delete_file("/Documents/old-report.md")
            assert result == {"success": True}
        finally:
            await client.close()

    @respx.mock
    async def test_delete_not_found(self):
        respx.delete(f"{GRAPH_BASE_URL}/me/drive/root:/nonexistent.txt:").mock(
            return_value=httpx.Response(404, json={"error": {"message": "Item not found"}})
        )
        client = GraphClient(token="test-token")
        try:
            with pytest.raises(GraphAPIError) as exc_info:
                await client.delete_file("/nonexistent.txt")
            assert exc_info.value.error == "not_found"
        finally:
            await client.close()


@pytest.mark.asyncio
class TestGraphClientFileInfo:
    @respx.mock
    async def test_file_info(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:").mock(
            return_value=httpx.Response(200, json={
                "name": "report.md",
                "size": 1024,
                "lastModifiedDateTime": "2024-01-01T00:00:00Z",
                "eTag": "etag1",
                "file": {"mimeType": "text/markdown"},
                "parentReference": {"path": "/drive/root:/Documents"},
            })
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.file_info("/Documents/report.md")
            assert result["name"] == "report.md"
            assert result["path"] == "/Documents/report.md"
            assert result["type"] == "file"
            assert result["size"] == 1024
            assert result["etag"] == "etag1"
            assert result["mime_type"] == "text/markdown"
        finally:
            await client.close()

    @respx.mock
    async def test_folder_info(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/Documents:").mock(
            return_value=httpx.Response(200, json={
                "name": "Documents",
                "size": 0,
                "lastModifiedDateTime": "2024-01-01T00:00:00Z",
                "eTag": "etag2",
                "folder": {"childCount": 10},
                "parentReference": {"path": "/drive/root:"},
            })
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.file_info("/Documents")
            assert result["name"] == "Documents"
            assert result["type"] == "folder"
            assert result["mime_type"] is None
        finally:
            await client.close()


@pytest.mark.asyncio
class TestGraphClientCreateFolder:
    @respx.mock
    async def test_create_single_folder(self):
        respx.post(f"{GRAPH_BASE_URL}/me/drive/root/children").mock(
            return_value=httpx.Response(201, json={"name": "NewFolder", "id": "123"})
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.create_folder("/NewFolder")
            assert result == {"path": "/NewFolder"}
        finally:
            await client.close()

    @respx.mock
    async def test_create_nested_folders(self):
        respx.post(f"{GRAPH_BASE_URL}/me/drive/root/children").mock(
            return_value=httpx.Response(201, json={"name": "Documents", "id": "1"})
        )
        respx.post(f"{GRAPH_BASE_URL}/me/drive/root:/Documents:/children").mock(
            return_value=httpx.Response(201, json={"name": "Reports", "id": "2"})
        )
        respx.post(f"{GRAPH_BASE_URL}/me/drive/root:/Documents/Reports:/children").mock(
            return_value=httpx.Response(201, json={"name": "2024", "id": "3"})
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.create_folder("/Documents/Reports/2024")
            assert result == {"path": "/Documents/Reports/2024"}
        finally:
            await client.close()

    @respx.mock
    async def test_create_existing_folder_idempotent(self):
        respx.post(f"{GRAPH_BASE_URL}/me/drive/root/children").mock(
            return_value=httpx.Response(409, json={"error": {"message": "Name conflict"}})
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.create_folder("/ExistingFolder")
            assert result == {"path": "/ExistingFolder"}
        finally:
            await client.close()


@pytest.mark.asyncio
class TestGraphClientMoveFile:
    @respx.mock
    async def test_move_to_different_folder(self):
        # Resolve destination parent ID
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/Archive:").mock(
            return_value=httpx.Response(200, json={"id": "archive-id"})
        )
        # PATCH to move
        respx.patch(f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:").mock(
            return_value=httpx.Response(200, json={
                "name": "report.md",
                "parentReference": {"path": "/drive/root:/Archive"},
            })
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.move_file("/Documents/report.md", "/Archive/report.md")
            assert result == {"path": "/Archive/report.md"}
        finally:
            await client.close()

    @respx.mock
    async def test_rename_file(self):
        # Same parent - just rename
        respx.patch(f"{GRAPH_BASE_URL}/me/drive/root:/Documents/report.md:").mock(
            return_value=httpx.Response(200, json={
                "name": "final-report.md",
                "parentReference": {"path": "/drive/root:/Documents"},
            })
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.move_file("/Documents/report.md", "/Documents/final-report.md")
            assert result == {"path": "/Documents/final-report.md"}
        finally:
            await client.close()


@pytest.mark.asyncio
class TestGraphClientRetry:
    @respx.mock
    async def test_retry_on_429(self):
        """Test that 429 responses trigger retries."""
        route = respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/test.txt:").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}, json={"error": {"message": "Throttled"}}),
                httpx.Response(200, json={
                    "name": "test.txt",
                    "size": 5,
                    "lastModifiedDateTime": "2024-01-01T00:00:00Z",
                    "eTag": "etag1",
                    "file": {"mimeType": "text/plain"},
                    "parentReference": {"path": "/drive/root:"},
                }),
            ]
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.file_info("/test.txt")
            assert result["name"] == "test.txt"
            assert route.call_count == 2
        finally:
            await client.close()

    @respx.mock
    async def test_auth_expired(self):
        respx.get(url__startswith=f"{GRAPH_BASE_URL}/me/drive/root:/test.txt:").mock(
            return_value=httpx.Response(401, json={"error": {"message": "Token expired"}})
        )
        client = GraphClient(token="expired-token")
        try:
            with pytest.raises(GraphAPIError) as exc_info:
                await client.file_info("/test.txt")
            assert exc_info.value.error == "auth_expired"
        finally:
            await client.close()


@pytest.mark.asyncio
class TestGraphClientUploadSession:
    @respx.mock
    async def test_upload_session_for_large_file(self):
        """Files >4MB should use upload sessions."""
        large_content = "x" * (5 * 1024 * 1024)  # 5MB

        respx.post(f"{GRAPH_BASE_URL}/me/drive/root:/Documents/large.txt:/createUploadSession").mock(
            return_value=httpx.Response(200, json={
                "uploadUrl": "https://upload.example.com/session123",
            })
        )
        # Mock chunk uploads - there will be multiple
        respx.put("https://upload.example.com/session123").mock(
            side_effect=[
                httpx.Response(202),  # First chunk accepted
                httpx.Response(200, json={  # Final chunk completes
                    "name": "large.txt",
                    "size": 5 * 1024 * 1024,
                    "eTag": "large-etag",
                }),
            ]
        )
        client = GraphClient(token="test-token")
        try:
            result = await client.write_file("/Documents/large.txt", large_content)
            assert result["path"] == "/Documents/large.txt"
            assert result["etag"] == "large-etag"
        finally:
            await client.close()
