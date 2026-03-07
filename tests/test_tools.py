"""Tests for MCP tool handler error paths."""

from unittest.mock import AsyncMock, patch

import pytest

from onedrive_mcp.graph_client import GraphAPIError
from onedrive_mcp.server import (
    list_files,
    read_file,
    write_file,
    delete_file,
    file_info,
    create_folder,
    move_file,
)


def _mock_ctx_no_token():
    """Create a mock Context with no bearer token (simulates missing auth)."""
    ctx = AsyncMock()
    ctx.get_state = AsyncMock(return_value=None)
    return ctx


@pytest.mark.asyncio
class TestToolAuthError:
    """All tool handlers should return a structured error when auth is missing."""

    async def test_list_files_no_auth(self):
        result = await list_files(path="/", ctx=_mock_ctx_no_token())
        assert result["error"] == "authentication_required"

    async def test_read_file_no_auth(self):
        result = await read_file(path="/test.txt", ctx=_mock_ctx_no_token())
        assert result["error"] == "authentication_required"

    async def test_write_file_no_auth(self):
        result = await write_file(path="/test.txt", content="x", ctx=_mock_ctx_no_token())
        assert result["error"] == "authentication_required"

    async def test_delete_file_no_auth(self):
        result = await delete_file(path="/test.txt", ctx=_mock_ctx_no_token())
        assert result["error"] == "authentication_required"

    async def test_file_info_no_auth(self):
        result = await file_info(path="/test.txt", ctx=_mock_ctx_no_token())
        assert result["error"] == "authentication_required"

    async def test_create_folder_no_auth(self):
        result = await create_folder(path="/test", ctx=_mock_ctx_no_token())
        assert result["error"] == "authentication_required"

    async def test_move_file_no_auth(self):
        result = await move_file(source="/a.txt", destination="/b.txt", ctx=_mock_ctx_no_token())
        assert result["error"] == "authentication_required"
