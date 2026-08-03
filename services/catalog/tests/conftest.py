import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from catalog.config import Settings
from catalog.db import Base, make_session_factory
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


@pytest.fixture
async def client(fake_minio_client: FakeMinioClient):
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        kafka_bootstrap_servers="kafka.invalid:9092",
        minio_endpoint="http://minio.invalid:9000",
        minio_public_base_url="http://minio.invalid:9000",
        minio_access_key="test",
        minio_secret_key="test",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory
    app.dependency_overrides[get_minio_client] = lambda: fake_minio_client

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
