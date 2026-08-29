import pytest
from httpx import ASGITransport, AsyncClient

from catalog.config import Settings
from catalog.db import Base, make_session_factory
from catalog.inventory_client import get_inventory_client
from catalog.main import create_app
from catalog.object_storage_dep import get_object_storage_client


class FakeObjectStorageClient:
    """Swapped in via app.dependency_overrides -- no real MinIO/S3 call is
    made. Mirrors services/chat/tests/conftest.py's FakeObjectStorageClient."""

    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []
        self.deleted_keys: list[str] = []

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        self.uploads.append((key, body, content_type))

    async def delete_object(self, key: str) -> None:
        self.deleted_keys.append(key)

    async def generate_presigned_url(self, key: str) -> str:
        return f"http://object-storage.invalid/catalog-product-images/{key}?X-Amz-Signature=fake"


@pytest.fixture
def fake_object_storage_client() -> FakeObjectStorageClient:
    return FakeObjectStorageClient()


class FakeInventoryClient:
    """Swapped in via app.dependency_overrides -- no real HTTP call is
    made. Quantities default to a nonzero value so publish-related tests
    that don't care about stock don't have to set one up explicitly."""

    def __init__(self) -> None:
        self.quantities: dict[str, int] = {}
        self.default_quantity = 10

    def set_quantity(self, product_id: str, quantity: int) -> None:
        self.quantities[product_id] = quantity

    async def get_total_quantity(self, product_id: str, internal_token: str) -> int:
        return self.quantities.get(product_id, self.default_quantity)


@pytest.fixture
def fake_inventory_client() -> FakeInventoryClient:
    return FakeInventoryClient()


@pytest.fixture
async def client(
    fake_object_storage_client: FakeObjectStorageClient,
    fake_inventory_client: FakeInventoryClient,
):
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        kafka_bootstrap_servers="kafka.invalid:9092",
        object_storage_endpoint="http://object-storage.invalid:9000",
        object_storage_public_base_url="http://object-storage.invalid:9000",
        object_storage_access_key="test",
        object_storage_secret_key="test",
        inventory_base_url="http://inventory.invalid",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory
    app.dependency_overrides[get_object_storage_client] = lambda: fake_object_storage_client
    app.dependency_overrides[get_inventory_client] = lambda: fake_inventory_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app  # tests that need direct DB access go via ac.app.state.session_factory
        yield ac

    await engine.dispose()


# catalog no longer checks the internal token or its role at all --
# admin-only enforcement moved to catalog-gate/internal-gate ahead of this
# app (see docker-compose.yml, nginx/internal-gate/catalog.conf, and
# scripts/verify-catalog-gate.sh for the tests that actually exercise
# that). These fixtures just supply *some* X-Internal-Token value for
# routes that forward it downstream to Inventory (see
# routers/products.py's update_product) -- the value itself is never
# validated by anything in this test suite.
@pytest.fixture
def admin_token() -> str:
    return "test-token-admin-1"


@pytest.fixture
def customer_token() -> str:
    return "test-token-customer-1"


@pytest.fixture
def guest_token() -> str:
    return "test-token-guest-1"
