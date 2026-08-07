import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from security.authz import get_authz_client
from security.config import Settings
from security.db import Base, make_session_factory
from security.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


class FakeAuthzClient:
    """Swapped in via app.dependency_overrides -- no real OPA sidecar call
    is made. Mirrors policies/security.rego's admin-only baseline (route
    tests exercise the actual policy separately, see test_authz_client.py
    and opa test policies/)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def check(self, subject: dict, action: str, resource: dict, package: str = "security") -> bool:
        self.calls.append({"subject": subject, "action": action, "resource": resource, "package": package})
        return subject.get("role") == "admin"


@pytest.fixture
def fake_authz_client() -> FakeAuthzClient:
    return FakeAuthzClient()


@pytest.fixture
async def client(fake_authz_client: FakeAuthzClient):
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        camera_base_url="http://mock-camera.invalid:8001",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory
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
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"x-internal-token": admin_token}
