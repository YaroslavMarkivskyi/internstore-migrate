import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from orders.config import Settings
from orders.db import Base, make_session_factory
from orders.inventory_client import InventoryUnavailableError, get_inventory_client
from orders.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


class FakeInventoryClient:
    """Swapped in via app.dependency_overrides — no real HTTP call is made."""

    def __init__(self) -> None:
        self.response: dict | None = None
        self.raises: Exception | None = None
        self.last_call: tuple[list[dict], str] | None = None

    def set_sufficient(self, items: list[dict]) -> None:
        self.response = {
            "sufficient": True,
            "items": [{**item, "requested": item["quantity"], "available": item["quantity"], "sufficient": True} for item in items],
        }

    def set_insufficient(self, results: list[dict]) -> None:
        self.response = {
            "sufficient": all(r["sufficient"] for r in results),
            "items": results,
        }

    def set_unavailable(self) -> None:
        self.raises = InventoryUnavailableError("inventory unreachable")

    async def check_availability(self, items: list[dict], internal_token: str) -> dict:
        self.last_call = (items, internal_token)
        if self.raises is not None:
            raise self.raises
        assert self.response is not None, "FakeInventoryClient response not configured"
        return self.response


@pytest.fixture
def fake_inventory_client() -> FakeInventoryClient:
    return FakeInventoryClient()


@pytest.fixture
async def client(fake_inventory_client: FakeInventoryClient):
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        inventory_base_url="http://inventory.invalid",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory
    app.dependency_overrides[get_inventory_client] = lambda: fake_inventory_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
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
