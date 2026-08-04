from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import respx

from mcp_gateway.tools.catalog import CatalogToolsClient, ProductSearchClient

BASE_URL = "http://catalog.invalid"


def _client() -> CatalogToolsClient:
    return CatalogToolsClient(BASE_URL, timeout_seconds=5.0, internal_token_secret="test-secret")


@respx.mock
async def test_get_product_calls_catalog_by_id():
    route = respx.get(f"{BASE_URL}/products/prod-1").mock(
        return_value=httpx.Response(200, json={"id": "prod-1", "name": "Frozen Peas", "min_temperature": -18})
    )

    result = await _client().get_product("prod-1")

    assert route.called
    assert result["name"] == "Frozen Peas"


@respx.mock
async def test_list_categories_returns_catalog_response():
    respx.get(f"{BASE_URL}/categories").mock(
        return_value=httpx.Response(200, json=[{"id": "cat-1", "name": "Frozen"}])
    )

    result = await _client().list_categories()

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


def _fake_openai_client() -> AsyncMock:
    client = AsyncMock()
    client.embeddings.create = AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 1536)]))
    return client


async def test_search_products_embeds_query_and_returns_nearest_rows():
    rows = [SimpleNamespace(product_id="prod-1", name="Frozen Peas", description="1kg bag")]
    openai_client = _fake_openai_client()
    search_client = ProductSearchClient(_fake_session_factory(rows), openai_client, "text-embedding-3-small")

    result = await search_client.search_products("frozen vegetables", limit=5)

    openai_client.embeddings.create.assert_awaited_once_with(model="text-embedding-3-small", input="frozen vegetables")
    assert result == [{"product_id": "prod-1", "name": "Frozen Peas", "description": "1kg bag"}]
