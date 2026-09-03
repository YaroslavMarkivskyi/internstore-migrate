import asyncio
import uuid
from collections import OrderedDict

import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mcp_gateway.models import ProductEmbedding

# The local Vertex project's gemini-embedding quota is tiny (5 req/min) and
# not raisable without a support case. Every search_products call embeds its
# query string, so: cache by normalised query text (demo queries repeat and
# are few), and retry once on a 429 instead of failing the tool outright.
_EMBED_CACHE_MAX = 256
_EMBED_RETRY_DELAY_SECONDS = 3.0


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

    def __init__(
        self,
        session_factory: async_sessionmaker,
        genai_client: genai.Client,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> None:
        self._session_factory = session_factory
        self._genai_client = genai_client
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions
        self._embed_cache: OrderedDict[str, list[float]] = OrderedDict()

    async def _embed_query(self, query: str) -> list[float]:
        """Embed `query`, from an LRU cache when possible; one retry on a
        transient Vertex quota (429) before giving up."""
        key = " ".join(query.split()).casefold()
        cached = self._embed_cache.get(key)
        if cached is not None:
            self._embed_cache.move_to_end(key)
            return cached

        for attempt in (1, 2):
            try:
                response = await self._genai_client.aio.models.embed_content(
                    model=self._embedding_model,
                    contents=query,
                    config=types.EmbedContentConfig(output_dimensionality=self._embedding_dimensions),
                )
                break
            except APIError as exc:
                if attempt == 1 and getattr(exc, "code", None) == 429:
                    await asyncio.sleep(_EMBED_RETRY_DELAY_SECONDS)
                    continue
                raise

        vector = response.embeddings[0].values
        self._embed_cache[key] = vector
        self._embed_cache.move_to_end(key)
        if len(self._embed_cache) > _EMBED_CACHE_MAX:
            self._embed_cache.popitem(last=False)
        return vector

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
        # STR-161b: output_dimensionality (inside _embed_query) must match
        # models.EMBEDDING_DIMENSIONS — this pgvector column is
        # dimension-fixed, and ai-assistant's own upsert path (embeddings.py)
        # embeds with the same truncated size.
        vector = await self._embed_query(query)

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
            return [_row_to_dict(row) for row in result]

    async def get_similar_products(self, token: str, product_id: str, limit: int = 3) -> list[dict]:
        """Nearest neighbours to an existing product by its *stored*
        embedding — for "no <X>, what's like it?" / substitutions. No
        Gemini call (the vector is already in the row), and the product
        itself is excluded from its own results. 404-shaped (empty) if the
        product isn't embedded."""
        del token  # unused — see class docstring
        try:
            pid = uuid.UUID(product_id)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"product_id must be a UUID from a search_products / get_cart result, got {product_id!r}"
            ) from exc

        async with self._session_factory() as session:
            anchor = await session.get(ProductEmbedding, pid)
            if anchor is None:
                return []
            stmt = (
                select(
                    ProductEmbedding.product_id,
                    ProductEmbedding.name,
                    ProductEmbedding.description,
                    ProductEmbedding.price,
                    ProductEmbedding.category_name,
                )
                .where(ProductEmbedding.product_id != pid)
                .order_by(ProductEmbedding.embedding.l2_distance(anchor.embedding))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_row_to_dict(row) for row in result]


def _row_to_dict(row) -> dict:
    return {
        "product_id": str(row.product_id),
        "name": row.name,
        "description": row.description,
        "price": row.price,
        "category": row.category_name,
    }
