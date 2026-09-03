"""The Gateway's MCP protocol surface.

A real MCP server — `mcp.server.lowlevel.Server` over the Streamable HTTP
transport (JSON-RPC) — served at `/mcp`. Tools + JSON Schemas come from
`schema.TOOL_SPECS`; execution goes through `router.call_tool` over the
`build_tool_registry` dict.

Pinned to `mcp` 1.x deliberately: the ai-assistant side consumes this through
Google ADK's `McpToolset`, and ADK requires the 1.x client SDK. Keeping both
ends on 1.x avoids a cross-major protocol negotiation.

Auth: every request must carry a Gateway-minted `X-Internal-Token`, same as
every other route on this internal-only service. The transport stashes the
Starlette request on `server.request_context`, so the handler reads and
verifies the header there and forwards the *raw* token downstream per tool
call — so Orders' `owner_id == claims.sub` check resolves against the real
caller (customer / guest / admin / the Assistant), not the Gateway.

Phase 3 (TODO) adds the public OAuth door and moves the tool-tier gating
(currently `McpToolset(tool_filter=...)` on the agent side) into the Gateway.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import mcp.types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.types import Receive, Scope, Send

from mcp_gateway.auth import mint_internal_token, verify_internal_token
from mcp_gateway.authz import authorized_tools
from mcp_gateway.oauth.provider import SCOPE as PUBLIC_SCOPE
from mcp_gateway.router import ToolFunc, call_tool
from mcp_gateway.schema import TOOL_SPECS

logger = logging.getLogger(__name__)

MCP_PATH = "/mcp"


_TOOLS: list[mcp_types.Tool] = [
    mcp_types.Tool(
        name=spec["name"],
        description=spec["description"],
        inputSchema=spec["input_schema"],
    )
    for spec in TOOL_SPECS
]
_ALL_TOOL_NAMES = frozenset(t.name for t in _TOOLS)


@dataclass
class _Caller:
    role: str
    downstream_token: str  # the internal token forwarded to domain services


def _identify(server: Server, secret: str) -> _Caller:
    """Resolve who is calling, from one of two doors:

    - internal mesh: an `X-Internal-Token` — verified, forwarded downstream
      as-is (STR-146: ownership resolves against the real caller).
    - public: an OAuth access token, already validated by
      `RequireAuthMiddleware` and stashed in the auth context. Its scope is
      `mcp:shopping`, so the caller is a `customer` regardless of the
      underlying Firebase role — ops/telemetry/security tools stay
      mesh-only. A fresh internal token is minted for the fan-out.
    """
    try:
        request = server.request_context.request
    except LookupError:  # pragma: no cover
        request = None
    raw = request.headers.get("x-internal-token") if request is not None else None
    if raw:
        try:
            claims = verify_internal_token(raw, secret)
        except ValueError as exc:
            raise ValueError("Invalid internal token") from exc
        return _Caller(role=claims.role, downstream_token=raw)

    # Public door: RequireAuthMiddleware has already validated the Bearer and
    # Starlette's AuthenticationMiddleware put the principal on the request
    # (scope-carried, so it survives into this handler's task — a ContextVar
    # would not). Scope is `mcp:shopping` -> a customer, whatever the
    # underlying Firebase role.
    user = getattr(request, "user", None)
    access = getattr(user, "access_token", None)
    if access is not None and PUBLIC_SCOPE in access.scopes and access.subject:
        return _Caller(role="customer", downstream_token=mint_internal_token(access.subject, "customer", secret))

    raise ValueError("Missing internal token")


def build_mcp_server(registry: dict[str, ToolFunc], internal_token_secret: str) -> Server:
    """Build the low-level MCP server. `registry` is the same dict object
    main.py stores on `app.state.tool_registry` — passed by reference so tests
    that swap an entry are reflected here too."""
    server: Server = Server(
        "internstore-mcp-gateway",
        version="0.1.0",
        instructions=(
            "Internal tool gateway for the InternStore microservices (catalog, orders, cart, "
            "inventory, telemetry, chat, help). Every call runs as the caller's forwarded identity."
        ),
    )

    @server.list_tools()
    async def list_tools() -> list[mcp_types.Tool]:
        caller = _identify(server, internal_token_secret)
        allowed = authorized_tools(caller.role, _ALL_TOOL_NAMES)
        return [t for t in _TOOLS if t.name in allowed]

    # validate_input=False: the Gateway's own tool clients already validate
    # (tools/orders.py's _require_uuid / _require_sane_quantity give the model
    # a far more actionable message than a raw jsonschema error).
    @server.call_tool(validate_input=False)
    async def call_tool_handler(name: str, arguments: dict[str, Any]) -> dict | mcp_types.CallToolResult:
        caller = _identify(server, internal_token_secret)
        if name in _ALL_TOOL_NAMES and name not in authorized_tools(caller.role, _ALL_TOOL_NAMES):
            return mcp_types.CallToolResult(
                content=[mcp_types.TextContent(type="text", text=f"{name}: not available to this caller")],
                isError=True,
            )
        try:
            result = await call_tool(registry, name, arguments or {}, caller.downstream_token)
        except Exception as exc:  # noqa: BLE001 - surfaced to the model as an error result
            return mcp_types.CallToolResult(
                content=[mcp_types.TextContent(type="text", text=f"{name}: {exc}")],
                isError=True,
            )
        if isinstance(result, dict):
            return result
        return mcp_types.CallToolResult(
            content=[mcp_types.TextContent(type="text", text=json.dumps(result, default=str))],
            isError=False,
        )

    return server


class _StreamableHTTPASGIApp:
    """Thin ASGI adapter — `mcp` 1.x keeps the equivalent inside
    `mcp.server.fastmcp`, importing which pulls in the whole FastMCP layer."""

    def __init__(self, manager: StreamableHTTPSessionManager) -> None:
        self._manager = manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._manager.handle_request(scope, receive, send)


def build_streamable_http_asgi(
    registry: dict[str, ToolFunc], internal_token_secret: str
) -> tuple[StreamableHTTPSessionManager, _StreamableHTTPASGIApp]:
    """Return the session manager (its `.run()` must be entered in the host
    app's lifespan) and the ASGI app to mount at `MCP_PATH`.

    `stateless=True`: mesh clients open a fresh connection per call and need no
    server-tracked session; `json_response=True`: one JSON reply per request."""
    server = build_mcp_server(registry, internal_token_secret)
    manager = StreamableHTTPSessionManager(app=server, json_response=True, stateless=True)
    return manager, _StreamableHTTPASGIApp(manager)
