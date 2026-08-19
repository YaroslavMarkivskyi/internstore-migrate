from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import respx

from mcp_gateway.tools.catalog import CatalogToolsClient, ProductSearchClient

BASE_URL = "http://catalog.invalid"


def _client() -> CatalogToolsClient:
    return CatalogToolsClient(BASE_URL, timeout_seconds=5.0)


@respx.mock
async def test_get_product_calls_catalog_by_id():
    route = respx.get(f"{BASE_URL}/products/prod-1").mock(
        return_value=httpx.Response(200, json={"id": "prod-1", "name": "Frozen Peas", "min_temperature": -18})
    )

    result = await _client().get_product("caller-token", "prod-1")

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"] == "caller-token"
    assert result["name"] == "Frozen Peas"


@respx.mock
async def test_list_categories_returns_catalog_response():
    respx.get(f"{BASE_URL}/categories").mock(
        return_value=httpx.Response(200, json=[{"id": "cat-1", "name": "Frozen"}])
    )

    result = await _client().list_categories("caller-token")

    assert result == [{"id": "cat-1", "name": "Frozen"}]


class _FakeSession:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def execute(self, _stmt: object) -> object:
        return iter(self._rows)


def _fake_session_factory(rows: list):
    return lambda: _FakeSession(rows)


def _fake_genai_client() -> AsyncMock:
    client = AsyncMock()
    client.aio.models.embed_content = AsyncMock(
        return_value=SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1] * 1536)])
    )
    return client


async def test_search_products_embeds_query_and_returns_nearest_rows():
    rows = [
        SimpleNamespace(
            product_id="prod-1", name="Frozen Peas", description="1kg bag", price=4.5, category_name="Frozen"
        )
    ]
    genai_client = _fake_genai_client()
    search_client = ProductSearchClient(_fake_session_factory(rows), genai_client, "gemini-embedding-001", 1536)

    result = await search_client.search_products("caller-token", "frozen vegetables", limit=5)

    genai_client.aio.models.embed_content.assert_awaited_once()
    call_kwargs = genai_client.aio.models.embed_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-embedding-001"
    assert call_kwargs["contents"] == "frozen vegetables"
    assert call_kwargs["config"].output_dimensionality == 1536
    assert result == [
        {"product_id": "prod-1", "name": "Frozen Peas", "description": "1kg bag", "price": 4.5, "category": "Frozen"}
    ]
