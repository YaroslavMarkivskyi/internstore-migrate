"""Real Model Context Protocol server for the Gateway (Phase 1).

This is the genuine MCP protocol surface — a `mcp.server.lowlevel.Server`
speaking JSON-RPC over the Streamable HTTP transport — sitting alongside the
older homegrown REST facade (`/mcp/tools`, `/mcp/tools/call` in main.py).
Phase 1 deliberately changes no behaviour: the tools, their JSON Schemas
(`schema.TOOL_SPECS`) and the execution path (`router.call_tool` over the
same `build_tool_registry` dict) are exactly the ones the REST facade uses.

Auth: every MCP request must still carry a Gateway-minted `X-Internal-Token`,
same as every other route on this internal-only service. The transport hands
the raw Starlette request to each handler via `ctx.request`, so we read and
verify the header here and forward the *raw* token downstream per tool call —
identical trust model to main.py's `call_tool_endpoint` (the caller's own
identity is what Orders' ownership checks resolve against, not the Gateway's).

Phase 2 will migrate `ai_assistant/mcp_client.py` onto a real MCP client and
retire the REST facade + hand-maintained schema translation; Phase 3 adds the
public OAuth-authenticated door and moves tool-tier gating into the Gateway.
"""

import json
import logging
from typing import Any

import mcp.types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager

from mcp_gateway.auth import verify_internal_token
from mcp_gateway.router import ToolFunc, ToolNotFoundError, call_tool
from mcp_gateway.schema import TOOL_SPECS

logger = logging.getLogger(__name__)

MCP_STREAM_PATH = "/mcp/stream"


class _Unauthorized(Exception):
    """Raised inside a handler when the request carries no valid internal
    token — surfaced to the client as a JSON-RPC error, not a tool result."""


def _require_token(ctx: Any, secret: str) -> str:
    request = getattr(ctx, "request", None)
    token = request.headers.get("x-internal-token") if request is not None else None
    if not token:
        raise _Unauthorized("Missing internal token")
    try:
        verify_internal_token(token, secret)
    except ValueError as exc:
        raise _Unauthorized("Invalid internal token") from exc
    return token


_TOOLS: list[mcp_types.Tool] = [
    mcp_types.Tool(
        name=spec["name"],
        description=spec["description"],
        input_schema=spec["input_schema"],
    )
    for spec in TOOL_SPECS
]


def build_mcp_server(registry: dict[str, ToolFunc], internal_token_secret: str) -> Server:
    """Build the low-level MCP server. `registry` is the same dict object
    main.py stores on `app.state.tool_registry` — passed by reference so tests
    that swap an entry are reflected here too."""

    async def on_list_tools(ctx: Any, _params: Any) -> mcp_types.ListToolsResult:
        _require_token(ctx, internal_token_secret)
        return mcp_types.ListToolsResult(tools=_TOOLS)

    async def on_call_tool(ctx: Any, params: mcp_types.CallToolRequestParams) -> mcp_types.CallToolResult:
        token = _require_token(ctx, internal_token_secret)
        arguments = params.arguments or {}
        try:
            result = await call_tool(registry, params.name, arguments, token)
        except ToolNotFoundError as exc:
            return _error_result(str(exc))
        except (TypeError, ValueError) as exc:
            # Same classification as main.py: wrong argument shape / invalid
            # value. Handed back as an error result so the calling agent's
            # ReAct loop gets something actionable to retry with.
            return _error_result(f"Invalid arguments for tool {params.name!r}: {exc}")

        text = result if isinstance(result, str) else json.dumps(result, default=str)
        structured = result if isinstance(result, dict) else None
        return mcp_types.CallToolResult(
            content=[mcp_types.TextContent(type="text", text=text)],
            structured_content=structured,
        )

    return Server(
        "internstore-mcp-gateway",
        version="0.1.0",
        instructions="Internal tool gateway for the InternStore microservices (catalog, orders, "
        "cart, inventory, telemetry, chat, help). Every call runs as the caller's forwarded identity.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def _error_result(message: str) -> mcp_types.CallToolResult:
    return mcp_types.CallToolResult(
        content=[mcp_types.TextContent(type="text", text=message)],
        is_error=True,
    )


def build_streamable_http_asgi(
    registry: dict[str, ToolFunc], internal_token_secret: str
) -> tuple[StreamableHTTPSessionManager, StreamableHTTPASGIApp]:
    """Return the session manager (its `.run()` must be entered in the host
    app's lifespan) and the ASGI app to mount at `MCP_STREAM_PATH`.

    `stateless=True`: internal mesh clients open a fresh connection per call
    and don't need server-tracked sessions; `json_response=True`: single JSON
    reply per request rather than an SSE frame, which is all the tool calls
    here need and keeps the transport simple for non-streaming callers."""
    server = build_mcp_server(registry, internal_token_secret)
    manager = StreamableHTTPSessionManager(app=server, json_response=True, stateless=True)
    return manager, StreamableHTTPASGIApp(manager)
