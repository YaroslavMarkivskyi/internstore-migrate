from contextlib import asynccontextmanager

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from mcp_gateway.config import Settings
from mcp_gateway.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode({"sub": sub, "role": role, "iss": ISSUER}, INTERNAL_TOKEN_SECRET, algorithm="HS256")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        orders_service_url="http://orders.invalid",
        inventory_service_url="http://inventory.invalid",
        catalog_service_url="http://catalog.invalid",
        telemetry_service_url="http://telemetry.invalid",
        security_service_url="http://security.invalid",
        chat_service_url="http://chat.invalid",
        ai_db_url="postgresql+asyncpg://ai:ai@ai-db.invalid/ai",
        gcp_project="test-project",
    )


@pytest.fixture
def app(settings: Settings):
    return create_app(settings=settings)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app
        yield ac


@pytest.fixture
def admin_token() -> str:
    return mint_internal_token(sub="mcp-gateway", role="admin")


@asynccontextmanager
async def mcp_session(app, token: str | None, extra_headers: dict | None = None):
    """A real MCP client session over the in-process ASGI app, talking to the
    Streamable HTTP endpoint at /mcp."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"X-Internal-Token": token} if token else {}
    headers.update(extra_headers or {})

    def _factory(*, headers=None, timeout=None, auth=None) -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=headers, timeout=timeout
        )

    async with (
        app.router.lifespan_context(app),
        streamablehttp_client("http://test/mcp", headers=headers, httpx_client_factory=_factory) as (r, w, _),
        ClientSession(r, w) as session,
    ):
        await session.initialize()
        yield session
