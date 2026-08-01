import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from inventory.config import Settings
from inventory.db import Base, make_session_factory
from inventory.main import create_app
from inventory.models import Stock

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
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.session_factory = session_factory
        yield ac

    await engine.dispose()


@pytest.fixture
def admin_token() -> str:
    return mint_internal_token(sub="admin-1", role="admin")


@pytest.fixture
def customer_token() -> str:
    return mint_internal_token(sub="customer-1", role="customer")


# Stocks have no create/write API by design in this ticket (they're
# provisioned out-of-band, not through Inventory's HTTP surface), so tests
# seed them directly through the session factory instead of the API.
async def create_stock(client, name: str = "Warehouse A") -> str:
    async with client.session_factory() as session:
        stock = Stock(name=name)
        session.add(stock)
        await session.commit()
        await session.refresh(stock)
        return str(stock.id)
