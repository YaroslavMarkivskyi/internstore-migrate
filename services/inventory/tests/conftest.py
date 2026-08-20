import pytest
from httpx import ASGITransport, AsyncClient

from inventory.catalog_client import get_catalog_client
from inventory.config import Settings
from inventory.db import Base, make_session_factory
from inventory.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"


class FakeCatalogClient:
    """Swapped in via app.dependency_overrides — no real HTTP call is made."""

    def __init__(self) -> None:
        self.unpublished: list[str] = []

    async def unpublish_product(self, product_id: str) -> None:
        self.unpublished.append(product_id)


@pytest.fixture
def fake_catalog_client() -> FakeCatalogClient:
    return FakeCatalogClient()


@pytest.fixture
async def client(fake_catalog_client: FakeCatalogClient):
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        kafka_bootstrap_servers="kafka.invalid:9092",
        catalog_base_url="http://catalog.invalid",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory
    app.dependency_overrides[get_catalog_client] = lambda: fake_catalog_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app  # tests that need direct DB access go via ac.app.state.session_factory
        yield ac

    await engine.dispose()


# inventory no longer checks the internal token or its role at all --
# admin/identity-only enforcement moved to inventory-gate/internal-gate
# ahead of this app (see docker-compose.yml, nginx/internal-gate/
# inventory.conf, and scripts/verify-inventory-gate.sh for the tests that
# actually exercise that). These fixtures just supply *some*
# X-Internal-Token value for the many call sites in this suite that still
# send one -- the value itself is never validated by anything here.
@pytest.fixture
def admin_token() -> str:
    return "test-token-admin-1"


@pytest.fixture
def customer_token() -> str:
    return "test-token-customer-1"


@pytest.fixture
def guest_token() -> str:
    return "test-token-guest-1"


async def create_stock(client, admin_token: str, name: str = "Warehouse A") -> str:
    resp = await client.post(
        "/stocks",
        json={"name": name},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]
