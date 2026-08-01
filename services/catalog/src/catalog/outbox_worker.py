import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from catalog.kafka import KafkaEventProducer
from catalog.models import OutboxEvent

TOPIC = "catalog-events"
BATCH_SIZE = 50


async def publish_pending_events(session_factory: async_sessionmaker, producer: KafkaEventProducer) -> int:
    async with session_factory() as session:
        result = await session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(BATCH_SIZE)
        )
        rows = list(result.scalars().all())
        for row in rows:
            await producer.send(TOPIC, row.event_type, row.payload, event_id=row.id)
            row.published_at = datetime.now(timezone.utc)
        await session.commit()
        return len(rows)


async def run_outbox_worker(
    session_factory: async_sessionmaker, producer: KafkaEventProducer, poll_interval: float
) -> None:
    try:
        while True:
            await publish_pending_events(session_factory, producer)
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        raise
