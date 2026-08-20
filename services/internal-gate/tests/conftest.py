import pytest
from httpx import ASGITransport, AsyncClient

from internal_gate.config import Settings
from internal_gate.main import create_app


@pytest.fixture
async def client():
    settings = Settings(opa_url="http://opa.invalid", opa_package="catalog")
    app = create_app(settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
