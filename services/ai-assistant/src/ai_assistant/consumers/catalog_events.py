import uuid
from collections.abc import Awaitable, Callable

from google import genai
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_assistant.embeddings import delete_product_embedding, upsert_product_embedding
from ai_assistant.models import ProcessedEvent

TOPIC = "catalog-events"
GROUP_ID = "ai-assistant-catalog-events"

Dispatch = Callable[[dict], Awaitable[None]]


async def _already_processed(session: AsyncSession, event_id: uuid.UUID) -> bool:
    return await session.get(ProcessedEvent, event_id) is not None


async def handle_product_updated(
    session: AsyncSession,
    genai_client: genai.Client,
    embedding_model: str,
    embedding_dimensions: int,
    event_id: uuid.UUID,
    payload: dict,
) -> None:
    if await _already_processed(session, event_id):
        return
    session.add(ProcessedEvent(event_id=event_id))
    await upsert_product_embedding(session, genai_client, embedding_model, payload, embedding_dimensions)


async def handle_product_deleted(session: AsyncSession, event_id: uuid.UUID, payload: dict) -> None:
    """STR-148: keeps product_embeddings from outliving the Catalog product
    it was built from — see embeddings.delete_product_embedding."""
    if await _already_processed(session, event_id):
        return
    session.add(ProcessedEvent(event_id=event_id))
    await delete_product_embedding(session, payload)


def make_dispatch(
    session_factory: async_sessionmaker, genai_client: genai.Client, embedding_model: str, embedding_dimensions: int
) -> Dispatch:
    async def dispatch(envelope: dict) -> None:
        event_type = envelope.get("event_type")
        event_id = uuid.UUID(envelope["event_id"])
        payload = envelope.get("payload", {})

        if event_type == "ProductUpdated":
            async with session_factory() as session:
                await handle_product_updated(
                    session, genai_client, embedding_model, embedding_dimensions, event_id, payload
                )
                await session.commit()
        elif event_type == "ProductDeleted":
            async with session_factory() as session:
                await handle_product_deleted(session, event_id, payload)
                await session.commit()

    return dispatch
