import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from google import genai
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.routing import Route

from mcp_gateway.config import Settings, load_settings
from mcp_gateway.db import make_session_factory
from mcp_gateway.mcp_server import MCP_PATH, build_streamable_http_asgi
from mcp_gateway.observability import setup_observability
from mcp_gateway.router import GatewayClients, build_tool_registry
from mcp_gateway.tools.catalog import CatalogToolsClient, ProductSearchClient
from mcp_gateway.tools.chat import ChatToolsClient
from mcp_gateway.tools.help import HelpSearchClient
from mcp_gateway.tools.inventory import InventoryToolsClient
from mcp_gateway.tools.orders import OrdersToolsClient
from mcp_gateway.tools.security import SecurityToolsClient
from mcp_gateway.tools.telemetry import TelemetryToolsClient


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

    clients = build_clients(settings)
    tool_registry = build_tool_registry(clients)

    # The MCP protocol surface: a real MCP server (Streamable HTTP transport,
    # JSON-RPC) at MCP_PATH. This internal-only service has no nginx route
    # (see docker-compose.yml) but the server still verifies the caller's
    # X-Internal-Token per request — see mcp_server.
    mcp_manager, mcp_asgi = build_streamable_http_asgi(tool_registry, settings.internal_token_secret)

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with mcp_manager.run():
            yield

    app = FastAPI(title="mcp-gateway", lifespan=lifespan)
    FastAPIInstrumentor.instrument_app(app)
    app.state.settings = settings
    app.state.tool_registry = tool_registry
    app.state.mcp_manager = mcp_manager
    # A Route (not a Mount) with the ASGI app as endpoint — same shape the
    # mcp SDK's own streamable_http_app() uses; a Mount would 307-redirect
    # the bare path to a trailing slash, which MCP clients don't follow.
    app.router.routes.append(Route(MCP_PATH, endpoint=mcp_asgi))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
