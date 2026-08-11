from unittest.mock import AsyncMock

import fakeredis
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from ai_assistant.config import Settings
from ai_assistant.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str, **extra_claims) -> str:
    return jwt.encode({"sub": sub, "role": role, "iss": ISSUER, **extra_claims}, INTERNAL_TOKEN_SECRET, algorithm="HS256")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        kafka_bootstrap_servers="kafka.invalid:9092",
        redis_url="redis://redis.invalid:6379",
        chat_service_url="http://chat.invalid",
        orders_service_url="http://orders.invalid",
        mcp_gateway_url="http://mcp-gateway.invalid",
        auth_backend_url="http://auth-backend.invalid",
        openai_api_key="sk-test-dummy",
    )


@pytest.fixture
def app(settings: Settings):
    # Deliberately not running the real lifespan (ASGITransport doesn't
    # trigger it) — it would start real Kafka consumers against a
    # bootstrap server that doesn't exist. /agent/shopping only touches
    # app.state.{redis,chat_client,mcp_client,auth_backend_client,
    # openai_client}, all replaced below with fakes/mocks, same pattern as
    # every other service's tests in this repo.
    app = create_app(settings=settings)
    app.state.redis = fakeredis.aioredis.FakeRedis(server=fakeredis.aioredis.FakeServer(), decode_responses=True)
    app.state.chat_client = AsyncMock()
    app.state.chat_client.get_recent_messages = AsyncMock(return_value=[])
    app.state.mcp_client = AsyncMock()
    app.state.auth_backend_client = AsyncMock()
    app.state.openai_client = AsyncMock()
    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app
        yield ac


@pytest.fixture
def customer_token() -> str:
    return mint_internal_token(sub="customer-1", role="customer")


@pytest.fixture
def guest_token() -> str:
    return mint_internal_token(sub="guest-session-1", role="guest")
