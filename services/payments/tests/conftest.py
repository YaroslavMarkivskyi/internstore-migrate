import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from payments.config import Settings
from payments.db import Base, make_session_factory
from payments.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
async def client():
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        payment_fail_on_amount_suffix="99",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app
        yield ac

    await engine.dispose()


@pytest.fixture
def admin_token() -> str:
    return mint_internal_token(sub="checkout-workflow", role="admin")
