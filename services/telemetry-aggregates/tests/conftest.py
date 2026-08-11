import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from telemetry_aggregates.config import Settings
from telemetry_aggregates.db import Base, make_session_factory
from telemetry_aggregates.main import create_app
from telemetry_aggregates.telemetry_read_models import metadata as telemetry_metadata

INTERNAL_TOKEN_SECRET = "test-secret"
ISSUER = "internstore-gateway"

TEST_SETTINGS_KWARGS = dict(
    database_url="sqlite+aiosqlite:///:memory:",
    internal_token_secret=INTERNAL_TOKEN_SECRET,
    telemetry_db_url="sqlite+aiosqlite:///:memory:",
    kafka_bootstrap_servers="kafka.invalid:9092",
)


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
async def session_factory():
    """This service's own database — hourly_aggregates/processed_events."""
    factory = make_session_factory(TEST_SETTINGS_KWARGS["database_url"])
    engine = factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield factory
    await engine.dispose()


@pytest.fixture
async def telemetry_session_factory():
    """A stand-in for telemetry-db, seeded via the same Core tables
    backfill.py reads (telemetry_read_models). A separate in-memory engine
    from `session_factory` — this fixture models the physical-instance
    separation the real deployment has."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(telemetry_metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def client(session_factory):
    settings = Settings(**TEST_SETTINGS_KWARGS)
    app = create_app(settings=settings)
    app.state.session_factory = session_factory  # reuse the already-migrated engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app  # tests that need direct DB access go via ac.app.state.session_factory
        yield ac


@pytest.fixture
def admin_token() -> str:
    return mint_internal_token(sub="admin-1", role="admin")


@pytest.fixture
def customer_token() -> str:
    return mint_internal_token(sub="customer-1", role="customer")
