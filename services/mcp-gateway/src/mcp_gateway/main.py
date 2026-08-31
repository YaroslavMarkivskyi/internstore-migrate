import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from mcp_gateway.auth import InternalClaims, get_internal_claims, get_raw_internal_token
from mcp_gateway.config import Settings, load_settings
from mcp_gateway.db import make_session_factory
from mcp_gateway.observability import setup_observability
from mcp_gateway.router import GatewayClients, ToolNotFoundError, build_tool_registry, call_tool
from mcp_gateway.schema import TOOL_SPECS
from mcp_gateway.tools.catalog import CatalogToolsClient, ProductSearchClient
from mcp_gateway.tools.chat import ChatToolsClient
from mcp_gateway.tools.help import HelpSearchClient
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
    session_factory = make_session_factory(settings.ai_db_url)
    # STR-161b: `enterprise=True` targets the Gemini Enterprise Agent
    # Platform (Vertex AI's Cloud Next 2026 rebrand) — IAM/Workload Identity
    # auth via ADC, no API key. Must point at the same gcp_project as
    # ai-assistant's own client (both embed into the same pgvector index).
    genai_client = genai.Client(enterprise=True, project=settings.gcp_project, location=settings.gcp_location)

    return GatewayClients(
        orders=OrdersToolsClient(settings.orders_service_url, timeout, session_factory),
        inventory=InventoryToolsClient(settings.inventory_service_url, timeout),
        catalog=CatalogToolsClient(settings.catalog_service_url, timeout),
        product_search=ProductSearchClient(
            session_factory, genai_client, settings.embedding_model, settings.embedding_dimensions
        ),
        help_search=HelpSearchClient(
            session_factory, genai_client, settings.embedding_model, settings.embedding_dimensions
        ),
        telemetry=TelemetryToolsClient(settings.telemetry_service_url, timeout),
        security=SecurityToolsClient(settings.security_service_url, timeout),
        chat=ChatToolsClient(settings.chat_service_url, timeout),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_observability("mcp-gateway")

    app = FastAPI(title="mcp-gateway")
    FastAPIInstrumentor.instrument_app(app)
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

    # STR-146: `claims` still proves the caller presented a validly-signed,
    # unexpired internal token (get_internal_claims) — but the *value*
    # forwarded downstream is the raw token itself (get_raw_internal_token),
    # not a claims-derived re-mint. Every tool call now runs as whoever
    # actually called this endpoint (customer, guest, admin, or the
    # Assistant's own token), not as the Gateway's old fixed admin identity —
    # that's what makes Orders' ownership check on add_to_cart/get_cart mean
    # anything.
    @app.post("/mcp/tools/call")
    async def call_tool_endpoint(
        payload: ToolCallRequest,
        claims: Annotated[InternalClaims, Depends(get_internal_claims)],
        token: Annotated[str, Depends(get_raw_internal_token)],
    ) -> dict[str, Any]:
        del claims  # validated by the Depends above; only the raw token is forwarded
        try:
            result = await call_tool(app.state.tool_registry, payload.name, payload.arguments, token)
        except ToolNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except TypeError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid arguments for tool {payload.name!r}: {exc}") from exc
        except ValueError as exc:
            # STR-148: e.g. tools/orders.py's _require_uuid — a semantically
            # invalid argument value (right type, wrong content), distinct
            # from TypeError's "wrong shape entirely". Same 422 treatment,
            # message passed through as-is so the caller (the shopping
            # agent's ReAct loop) gets something actionable to retry with.
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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
