"""OneDrive MCP Server - FastMCP with Streamable HTTP transport."""

import logging
import os
from typing import Any

import mcp.types as mt
from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from starlette.requests import Request
from starlette.responses import JSONResponse

from onedrive_mcp.graph_client import GraphClient, GraphAPIError

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", str(25 * 1024 * 1024)))


def _extract_bearer_token(authorization: str | None) -> str | None:
    """Extract Bearer token from Authorization header."""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
        return token if token else None
    return None


class BearerTokenMiddleware(Middleware):
    """Extract Bearer token from HTTP Authorization header on session init."""

    async def on_initialize(
        self,
        context: MiddlewareContext[mt.InitializeRequest],
        call_next: CallNext[mt.InitializeRequest, mt.InitializeResult | None],
    ) -> mt.InitializeResult | None:
        # Get the HTTP request to extract the Authorization header
        request = get_http_request()
        auth_header = request.headers.get("authorization")
        token = _extract_bearer_token(auth_header)

        if not token:
            raise ValueError(
                "Missing or invalid Authorization header. Expected: Authorization: Bearer <token>"
            )

        # Store token in session state
        ctx = context.fastmcp_context
        await ctx.set_state("bearer_token", token)

        return await call_next(context)


# Create the FastMCP server
mcp = FastMCP(
    name="onedrive",
    instructions="OneDrive file operations via Microsoft Graph API. Provide a Bearer token in the Authorization header.",
)

# Add auth middleware
mcp.add_middleware(BearerTokenMiddleware())


async def _get_client(ctx: Context) -> GraphClient:
    """Get or create a GraphClient cached in session state."""
    client = await ctx.get_state("graph_client")
    if client is not None:
        return client
    token = await ctx.get_state("bearer_token")
    if not token:
        raise GraphAPIError(
            "authentication_required",
            "No Bearer token found in session. Provide an Authorization: Bearer <token> header.",
        )
    client = GraphClient(token=token, max_file_size=MAX_FILE_SIZE)
    await ctx.set_state("graph_client", client)
    return client


def _error_response(e: GraphAPIError) -> dict[str, Any]:
    """Convert a GraphAPIError to a tool response dict."""
    return e.to_dict()


@mcp.tool
async def list_files(path: str = "/", ctx: Context = None) -> dict[str, Any] | list[dict[str, Any]]:
    """List files and folders in a OneDrive directory.

    Args:
        path: Directory path to list (default: root "/")
    """
    client = await _get_client(ctx)
    try:
        return await client.list_files(path)
    except GraphAPIError as e:
        return _error_response(e)


@mcp.tool
async def read_file(path: str, ctx: Context = None) -> dict[str, Any]:
    """Read a file's content and metadata from OneDrive.

    Args:
        path: Path to the file to read
    """
    client = await _get_client(ctx)
    try:
        return await client.read_file(path)
    except GraphAPIError as e:
        return _error_response(e)


@mcp.tool
async def write_file(path: str, content: str, etag: str | None = None, ctx: Context = None) -> dict[str, Any]:
    """Create or update a file in OneDrive.

    Args:
        path: Path where the file should be written
        content: File content (text)
        etag: Optional ETag for optimistic concurrency (conflict detection)
    """
    client = await _get_client(ctx)
    try:
        return await client.write_file(path, content, etag)
    except GraphAPIError as e:
        return _error_response(e)


@mcp.tool
async def delete_file(path: str, ctx: Context = None) -> dict[str, Any]:
    """Delete a file from OneDrive.

    Args:
        path: Path to the file to delete
    """
    client = await _get_client(ctx)
    try:
        return await client.delete_file(path)
    except GraphAPIError as e:
        return _error_response(e)


@mcp.tool
async def file_info(path: str, ctx: Context = None) -> dict[str, Any]:
    """Get file or folder metadata without downloading content.

    Args:
        path: Path to the file or folder
    """
    client = await _get_client(ctx)
    try:
        return await client.file_info(path)
    except GraphAPIError as e:
        return _error_response(e)


@mcp.tool
async def create_folder(path: str, ctx: Context = None) -> dict[str, Any]:
    """Create a folder in OneDrive (including intermediate folders).

    Args:
        path: Path of the folder to create
    """
    client = await _get_client(ctx)
    try:
        return await client.create_folder(path)
    except GraphAPIError as e:
        return _error_response(e)


@mcp.tool
async def move_file(source: str, destination: str, ctx: Context = None) -> dict[str, Any]:
    """Move or rename a file in OneDrive.

    Args:
        source: Current path of the file
        destination: New path for the file
    """
    client = await _get_client(ctx)
    try:
        return await client.move_file(source, destination)
    except GraphAPIError as e:
        return _error_response(e)


# Health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


def create_app():
    """Create the ASGI application."""
    return mcp.http_app(path="/mcp")


def main():
    """Run the server."""
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info(f"Starting OneDrive MCP server on {host}:{port}")
    mcp.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    main()
