import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from catalog.authz import AuthzResult, get_authz_client
from catalog.config import Settings
from catalog.db import Base, make_session_factory
from catalog.inventory_client import get_inventory_client
from catalog.main import create_app
from catalog.minio_dep import get_minio_client

INTERNAL_TOKEN_SECRET = "test-secret"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


class FakeMinioClient:
    """Swapped in via app.dependency_overrides -- no real MinIO/S3 call is
    made. Mirrors services/chat/tests/conftest.py's FakeMinioClient."""

    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []
        self.deleted_keys: list[str] = []

    async def put_object(self, key: str, body: bytes, content_type: str) -> str:
        self.uploads.append((key, body, content_type))
        return f"http://minio.invalid/catalog-product-images/{key}"

    async def delete_object(self, key: str) -> None:
        self.deleted_keys.append(key)


@pytest.fixture
def fake_minio_client() -> FakeMinioClient:
    return FakeMinioClient()


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


class FakeAuthzClient:
    """Swapped in via app.dependency_overrides -- no real OPA sidecar call
    is made. Verifies the token itself (mirroring what OPA's common.rego
    now does with io.jwt.decode_verify, since catalog no longer does this
    locally -- see auth.py/authz.py) and mirrors policies/catalog.rego's
    admin-only baseline. The actual policy is exercised separately, see
    test_authz_client.py and opa test policies/."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def _verify(self, token: str) -> dict | None:
        try:
            return jwt.decode(token, INTERNAL_TOKEN_SECRET, algorithms=["HS256"], issuer=ISSUER)
        except jwt.InvalidTokenError:
            return None

    async def identify(self, token: str) -> dict | None:
        payload = self._verify(token)
        if payload is None or "sub" not in payload or "role" not in payload:
            return None
        return {"sub": payload["sub"], "role": payload["role"]}

    async def check(self, token: str, action: str, resource: dict, package: str = "catalog") -> AuthzResult:
        self.calls.append({"token": token, "action": action, "resource": resource, "package": package})
        payload = self._verify(token)
        if payload is None or "sub" not in payload or "role" not in payload:
            return AuthzResult(subject=None, allowed=False)
        subject = {"sub": payload["sub"], "role": payload["role"]}
        return AuthzResult(subject=subject, allowed=subject["role"] == "admin")


@pytest.fixture
def fake_authz_client() -> FakeAuthzClient:
    return FakeAuthzClient()


@pytest.fixture
async def client(
    fake_minio_client: FakeMinioClient,
    fake_inventory_client: FakeInventoryClient,
    fake_authz_client: FakeAuthzClient,
):
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        kafka_bootstrap_servers="kafka.invalid:9092",
        minio_endpoint="http://minio.invalid:9000",
        minio_public_base_url="http://minio.invalid:9000",
        minio_access_key="test",
        minio_secret_key="test",
        inventory_base_url="http://inventory.invalid",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory
    app.dependency_overrides[get_minio_client] = lambda: fake_minio_client
    app.dependency_overrides[get_inventory_client] = lambda: fake_inventory_client
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
