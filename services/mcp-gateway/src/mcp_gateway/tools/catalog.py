import httpx
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mcp_gateway.auth import mint_internal_token
from mcp_gateway.models import ProductEmbedding


class CatalogToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float, internal_token_secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._secret = internal_token_secret

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": mint_internal_token(self._secret)}

    async def get_product(self, product_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/products/{product_id}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def list_categories(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/categories", headers=self._headers())
        resp.raise_for_status()
        return resp.json()


class ProductSearchClient:
    """Semantic search over ai-assistant's product_embeddings table (see
    models.py) rather than a Catalog HTTP call — Catalog itself has no
    search endpoint, only exact-id lookups (see catalog/routers/products.py).
    Queries the pgvector index directly, same approach as ai-assistant's own
    embeddings.search_similar_products."""

    def __init__(self, session_factory: async_sessionmaker, openai_client: AsyncOpenAI, embedding_model: str) -> None:
        self._session_factory = session_factory
        self._openai_client = openai_client
        self._embedding_model = embedding_model

    async def search_products(self, query: str, limit: int = 5) -> list[dict]:
        response = await self._openai_client.embeddings.create(model=self._embedding_model, input=query)
        vector = response.data[0].embedding

        async with self._session_factory() as session:
            result = await session.execute(
                select(ProductEmbedding.product_id, ProductEmbedding.name, ProductEmbedding.description)
                .order_by(ProductEmbedding.embedding.l2_distance(vector))
                .limit(limit)
            )
            return [
                {"product_id": str(row.product_id), "name": row.name, "description": row.description}
                for row in result
            ]
