import httpx
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mcp_gateway.models import ProductEmbedding


class CatalogToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"X-Internal-Token": token}

    async def get_product(self, token: str, product_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/products/{product_id}", headers=self._headers(token))
        resp.raise_for_status()
        return resp.json()

    async def list_categories(self, token: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/categories", headers=self._headers(token))
        resp.raise_for_status()
        return resp.json()


class ProductSearchClient:
    """Semantic search over ai-assistant's product_embeddings table (see
    models.py) rather than a Catalog HTTP call — Catalog itself has no
    search endpoint, only exact-id lookups (see catalog/routers/products.py).
    Queries the pgvector index directly, same approach as ai-assistant's own
    embeddings.search_similar_products. No downstream HTTP call, so nothing
    here actually needs the caller's token — search_products still accepts
    (and ignores) one, purely so router.call_tool can inject `token` into
    every tool call uniformly rather than special-casing this one."""

    def __init__(self, session_factory: async_sessionmaker, openai_client: AsyncOpenAI, embedding_model: str) -> None:
        self._session_factory = session_factory
        self._openai_client = openai_client
        self._embedding_model = embedding_model

    # STR-146: `filters` is optional and additive — {price_min, price_max,
    # category} — since shopping queries are more filter-heavy than the
    # original support-chat use case ("dinner party under $50"). Applied as
    # plain SQL predicates *after* the vector ordering, not folded into the
    # embedding itself: filtering by exact price/category needs to be exact,
    # not "semantically close to".
    async def search_products(
        self, token: str, query: str, limit: int = 5, filters: dict | None = None
    ) -> list[dict]:
        del token  # unused — see class docstring
        response = await self._openai_client.embeddings.create(model=self._embedding_model, input=query)
        vector = response.data[0].embedding

        stmt = select(
            ProductEmbedding.product_id,
            ProductEmbedding.name,
            ProductEmbedding.description,
            ProductEmbedding.price,
            ProductEmbedding.category_name,
        )
        filters = filters or {}
        if filters.get("price_min") is not None:
            stmt = stmt.where(ProductEmbedding.price >= filters["price_min"])
        if filters.get("price_max") is not None:
            stmt = stmt.where(ProductEmbedding.price <= filters["price_max"])
        if filters.get("category"):
            stmt = stmt.where(ProductEmbedding.category_name == filters["category"])
        stmt = stmt.order_by(ProductEmbedding.embedding.l2_distance(vector)).limit(limit)

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [
                {
                    "product_id": str(row.product_id),
                    "name": row.name,
                    "description": row.description,
                    "price": row.price,
                    "category": row.category_name,
                }
                for row in result
            ]
