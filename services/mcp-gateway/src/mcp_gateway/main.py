import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

from mcp_gateway.auth import InternalClaims, get_internal_claims
from mcp_gateway.config import Settings, load_settings
from mcp_gateway.db import make_session_factory
from mcp_gateway.router import GatewayClients, ToolNotFoundError, build_tool_registry, call_tool
from mcp_gateway.schema import TOOL_SPECS
from mcp_gateway.tools.catalog import CatalogToolsClient, ProductSearchClient
from mcp_gateway.tools.chat import ChatToolsClient
from mcp_gateway.tools.inventory import InventoryToolsClient
from mcp_gateway.tools.orders import OrdersToolsClient
from mcp_gateway.tools.security import SecurityToolsClient
from mcp_gateway.tools.telemetry import TelemetryToolsClient

SERVER_NAME = "internstore-mcp-gateway"
SERVER_VERSION = "0.1.0"


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


def build_clients(settings: Settings) -> GatewayClients:
    timeout = settings.http_timeout_seconds
    secret = settings.internal_token_secret
    session_factory = make_session_factory(settings.ai_db_url)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    return GatewayClients(
        orders=OrdersToolsClient(settings.orders_service_url, timeout, secret),
        inventory=InventoryToolsClient(settings.inventory_service_url, timeout, secret),
        catalog=CatalogToolsClient(settings.catalog_service_url, timeout, secret),
        product_search=ProductSearchClient(session_factory, openai_client, settings.embedding_model),
        telemetry=TelemetryToolsClient(settings.telemetry_service_url, timeout, secret),
        security=SecurityToolsClient(settings.security_service_url, timeout, secret),
        chat=ChatToolsClient(settings.chat_service_url, timeout, secret),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="mcp-gateway")
    app.state.settings = settings
    clients = build_clients(settings)
    app.state.tool_registry = build_tool_registry(clients)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Every /mcp/* route requires an internal token, same as any other
    # domain service — this is an internal-only service with no nginx
    # route (see docker-compose.yml), but never trusts its network
    # position alone.
    @app.get("/mcp")
    async def mcp_info(claims: Annotated[InternalClaims, Depends(get_internal_claims)]) -> dict[str, Any]:
        return {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
        }

    @app.get("/mcp/tools")
    async def list_tools(claims: Annotated[InternalClaims, Depends(get_internal_claims)]) -> dict[str, Any]:
        return {"tools": TOOL_SPECS}

    @app.post("/mcp/tools/call")
    async def call_tool_endpoint(
        payload: ToolCallRequest,
        claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    ) -> dict[str, Any]:
        try:
            result = await call_tool(app.state.tool_registry, payload.name, payload.arguments)
        except ToolNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except TypeError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid arguments for tool {payload.name!r}: {exc}") from exc
        return {"name": payload.name, "result": result}

    # SSE handshake per the MCP spec's SSE transport: a single `endpoint`
    # event telling the client where to POST tool calls, then the stream
    # stays open for the caller to read from. Tool *results* still travel
    # back over POST /mcp/tools/call's own response, not pushed down this
    # channel — a full bidirectional SSE transport is out of scope here.
    @app.get("/mcp/sse")
    async def mcp_sse(claims: Annotated[InternalClaims, Depends(get_internal_claims)]) -> StreamingResponse:
        async def event_stream() -> AsyncIterator[str]:
            yield f"event: endpoint\ndata: {json.dumps({'url': '/mcp/tools/call'})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return app
