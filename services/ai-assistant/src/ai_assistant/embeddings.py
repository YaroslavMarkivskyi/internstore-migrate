import uuid

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_assistant.models import ProductEmbedding


def build_embedding_text(payload: dict) -> str:
    """Assembles the text embedded for a product, from the exact fields the
    ticket specifies: {name, description, min_temperature, max_temperature,
    category}."""
    parts = [payload["name"]]
    if payload.get("description"):
        parts.append(payload["description"])
    if payload.get("category_name"):
        parts.append(f"Category: {payload['category_name']}")
    min_temp = payload.get("min_temperature")
    max_temp = payload.get("max_temperature")
    if min_temp is not None or max_temp is not None:
        parts.append(f"Temperature range: {min_temp} to {max_temp}")
    return "\n".join(parts)


async def embed_text(client: AsyncOpenAI, model: str, text: str) -> list[float]:
    response = await client.embeddings.create(model=model, input=text)
    return response.data[0].embedding


async def upsert_product_embedding(
    session: AsyncSession, client: AsyncOpenAI, model: str, payload: dict
) -> None:
    vector = await embed_text(client, model, build_embedding_text(payload))
    product_id = uuid.UUID(payload["product_id"])

    existing = await session.get(ProductEmbedding, product_id)
    if existing is None:
        session.add(
            ProductEmbedding(
                product_id=product_id,
                name=payload["name"],
                description=payload.get("description"),
                embedding=vector,
            )
        )
    else:
        existing.name = payload["name"]
        existing.description = payload.get("description")
        existing.embedding = vector


async def search_similar_products(
    session: AsyncSession, client: AsyncOpenAI, model: str, query_text: str, limit: int
) -> list[dict]:
    vector = await embed_text(client, model, query_text)
    result = await session.execute(
        select(ProductEmbedding.product_id, ProductEmbedding.name, ProductEmbedding.description)
        # pgvector's <-> operator (Euclidean/L2 distance) — nearest first.
        .order_by(ProductEmbedding.embedding.l2_distance(vector)).limit(limit)
    )
    return [
        {"product_id": str(row.product_id), "name": row.name, "description": row.description}
        for row in result
    ]
