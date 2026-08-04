import uuid
from collections.abc import Awaitable, Callable

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_assistant.embeddings import upsert_product_embedding
from ai_assistant.models import ProcessedEvent

TOPIC = "catalog-events"
GROUP_ID = "ai-assistant-catalog-events"

Dispatch = Callable[[dict], Awaitable[None]]


async def _already_processed(session: AsyncSession, event_id: uuid.UUID) -> bool:
    return await session.get(ProcessedEvent, event_id) is not None


async def handle_product_updated(
    session: AsyncSession, openai_client: AsyncOpenAI, embedding_model: str, event_id: uuid.UUID, payload: dict
) -> None:
    if await _already_processed(session, event_id):
        return
    session.add(ProcessedEvent(event_id=event_id))
    await upsert_product_embedding(session, openai_client, embedding_model, payload)


def make_dispatch(
    session_factory: async_sessionmaker, openai_client: AsyncOpenAI, embedding_model: str
) -> Dispatch:
    async def dispatch(envelope: dict) -> None:
        if envelope.get("event_type") != "ProductUpdated":
            return
        async with session_factory() as session:
            await handle_product_updated(
                session,
                openai_client,
                embedding_model,
                uuid.UUID(envelope["event_id"]),
                envelope.get("payload", {}),
            )
            await session.commit()

    return dispatch
