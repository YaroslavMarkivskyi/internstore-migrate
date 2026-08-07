import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from inventory.authz import get_authz_client
from inventory.catalog_client import get_catalog_client
from inventory.config import Settings
from inventory.db import Base, make_session_factory
from inventory.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


class FakeCatalogClient:
    """Swapped in via app.dependency_overrides — no real HTTP call is made."""

    def __init__(self) -> None:
        self.unpublished: list[str] = []

    async def unpublish_product(self, product_id: str) -> None:
        self.unpublished.append(product_id)


@pytest.fixture
def fake_catalog_client() -> FakeCatalogClient:
    return FakeCatalogClient()


class FakeAuthzClient:
    """Swapped in via app.dependency_overrides -- no real OPA sidecar call
    is made. Mirrors policies/inventory.rego's admin-only baseline (route
    tests exercise the actual policy separately, see test_authz_client.py
    and opa test policies/)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def check(self, subject: dict, action: str, resource: dict, package: str = "inventory") -> bool:
        self.calls.append({"subject": subject, "action": action, "resource": resource, "package": package})
        return subject.get("role") == "admin"


@pytest.fixture
def fake_authz_client() -> FakeAuthzClient:
    return FakeAuthzClient()


@pytest.fixture
async def client(fake_catalog_client: FakeCatalogClient, fake_authz_client: FakeAuthzClient):
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
    app.dependency_overrides[get_authz_client] = lambda: fake_authz_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app  # tests that need direct DB access go via ac.app.state.session_factory
        yield ac

    await engine.dispose()


@pytest.fixture
def admin_token() -> str:
    return mint_internal_token(sub="admin-1", role="admin")


@pytest.fixture
def customer_token() -> str:
    return mint_internal_token(sub="customer-1", role="customer")


@pytest.fixture
def guest_token() -> str:
    return mint_internal_token(sub="guest-1", role="guest")


async def create_stock(client, admin_token: str, name: str = "Warehouse A") -> str:
    resp = await client.post(
        "/stocks",
        json={"name": name},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]
