import json
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from orders.authz import get_authz_client
from orders.catalog_client import get_catalog_client
from orders.config import Settings
from orders.db import Base, make_session_factory
from orders.inventory_client import InventoryUnavailableError, get_inventory_client
from orders.main import create_app
from orders.stripe_client import get_stripe_client


# orders no longer verifies a JWT itself -- it trusts X-User-Id/X-User-Role,
# forwarded by orders-gate once *it* has verified the caller (see
# orders/auth.py). These headers are what tests send in place of the old
# mint_internal_token(...)-produced JWT.
def mint_internal_token(sub: str, role: str) -> dict[str, str]:
    return {"X-User-Id": sub, "X-User-Role": role}


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


class FakeCatalogClient:
    """Swapped in via app.dependency_overrides — no real HTTP call is made."""

    def __init__(self) -> None:
        self.prices: dict[str, float] = {}

    def set_price(self, product_id: str, price: float) -> None:
        self.prices[product_id] = price

    async def get_product_price(self, product_id: str) -> float:
        return self.prices[product_id]


@pytest.fixture
def fake_catalog_client() -> FakeCatalogClient:
    return FakeCatalogClient()


class FakeStripeClient:
    """Swapped in via app.dependency_overrides — no real Stripe API call is
    made, and construct_webhook_event skips signature verification (tests
    craft the event body directly and pass any Stripe-Signature value)."""

    def __init__(self) -> None:
        self.created_intents: list[dict] = []
        self._counter = 0
        self.raises: Exception | None = None

    def set_idempotency_conflict(self) -> None:
        import stripe

        self.raises = stripe.APIError("another in-progress request using this Idempotent Key")

    async def create_payment_intent(self, *, amount_cents: int, order_id: str) -> SimpleNamespace:
        if self.raises is not None:
            raise self.raises
        self._counter += 1
        intent_id = f"pi_fake_{self._counter}"
        self.created_intents.append({"amount_cents": amount_cents, "order_id": order_id, "id": intent_id})
        return SimpleNamespace(id=intent_id, client_secret=f"{intent_id}_secret")

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> dict:
        return json.loads(payload)


@pytest.fixture
def fake_stripe_client() -> FakeStripeClient:
    return FakeStripeClient()


class FakeAuthzClient:
    """Swapped in via app.dependency_overrides -- no real OPA sidecar call
    is made. Mirrors policies/orders.rego's resource-level rules (own-order
    view/update, guest-can-create) -- the only ones orders' own code still
    calls directly (routers/orders.py's get_order); every route-level tier
    (admin-only, admin-or-assistant, any-authenticated) is enforced by
    orders-gate ahead of this app entirely, so it's not exercised through
    this fake at all -- see scripts/verify-orders-gate.sh and
    opa test policies/ for those."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def check(self, subject: dict, action: str, resource: dict, package: str = "orders") -> bool:
        self.calls.append({"subject": subject, "action": action, "resource": resource, "package": package})
        role = subject.get("role")
        if role == "admin":
            return True
        if action in ("view", "update") and resource.get("type") == "order":
            return role == "customer" and resource.get("owner") == subject.get("sub")
        if action == "create" and resource.get("type") == "order":
            return role == "guest"
        return False


@pytest.fixture
def fake_authz_client() -> FakeAuthzClient:
    return FakeAuthzClient()


@pytest.fixture
async def client(
    fake_inventory_client: FakeInventoryClient,
    fake_catalog_client: FakeCatalogClient,
    fake_stripe_client: FakeStripeClient,
    fake_authz_client: FakeAuthzClient,
):
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        inventory_base_url="http://inventory.invalid",
        catalog_base_url="http://catalog.invalid",
        kafka_bootstrap_servers="kafka.invalid:9092",
        stripe_secret_key="sk_test_dummy",
        stripe_webhook_secret="whsec_dummy",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory
    app.dependency_overrides[get_inventory_client] = lambda: fake_inventory_client
    app.dependency_overrides[get_catalog_client] = lambda: fake_catalog_client
    app.dependency_overrides[get_stripe_client] = lambda: fake_stripe_client
    app.dependency_overrides[get_authz_client] = lambda: fake_authz_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app  # tests that need direct DB access (e.g. outbox rows) go via ac.app.state.session_factory
        yield ac

    await engine.dispose()


@pytest.fixture
def admin_token() -> dict[str, str]:
    return mint_internal_token(sub="admin-1", role="admin")


@pytest.fixture
def customer_token() -> dict[str, str]:
    return mint_internal_token(sub="customer-1", role="customer")


@pytest.fixture
def guest_token() -> dict[str, str]:
    return mint_internal_token(sub="guest-1", role="guest")
