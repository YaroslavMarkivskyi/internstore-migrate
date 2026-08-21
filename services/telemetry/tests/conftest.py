import pytest
from httpx import ASGITransport, AsyncClient

from telemetry.config import Settings
from telemetry.db import Base, make_session_factory
from telemetry.main import create_app


@pytest.fixture
async def client():
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        kafka_bootstrap_servers="kafka.invalid:9092",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app  # tests that need direct DB access go via ac.app.state.session_factory
        yield ac

    await engine.dispose()


# telemetry no longer checks the internal token or its role at all --
# admin-only enforcement moved to telemetry-gate/internal-gate ahead of
# this app (see docker-compose.yml, nginx/internal-gate/telemetry.conf,
# and scripts/verify-telemetry-gate.sh for the tests that actually
# exercise that). These fixtures just supply *some* X-Internal-Token
# value for the call sites in this suite that still send one -- the value
# itself is never validated by anything here.
@pytest.fixture
def admin_token() -> str:
    return "test-token-admin-1"


@pytest.fixture
def customer_token() -> str:
    return "test-token-customer-1"
