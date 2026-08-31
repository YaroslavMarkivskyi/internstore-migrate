from google import genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mcp_gateway.models import HelpChunk


class HelpSearchClient:
    """Semantic search over ai-assistant's `help_chunks` table (customer-facing
    FAQ / policy text — delivery, returns, payment, cold chain, accounts).
    Same approach as ProductSearchClient (see tools/catalog.py): queries the
    shared pgvector index directly, no downstream HTTP call, so the forwarded
    token is accepted and ignored purely so router.call_tool can inject it
    uniformly."""

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

    async def search_help(self, token: str, query: str, limit: int = 3) -> list[dict]:
        del token  # unused — see class docstring
        response = await self._genai_client.aio.models.embed_content(
            model=self._embedding_model,
            contents=query,
            config=types.EmbedContentConfig(output_dimensionality=self._embedding_dimensions),
        )
        vector = response.embeddings[0].values

        stmt = (
            select(HelpChunk.source, HelpChunk.heading, HelpChunk.content)
            .order_by(HelpChunk.embedding.l2_distance(vector))
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [
                {"source": row.source, "heading": row.heading, "content": row.content}
                for row in result
            ]
