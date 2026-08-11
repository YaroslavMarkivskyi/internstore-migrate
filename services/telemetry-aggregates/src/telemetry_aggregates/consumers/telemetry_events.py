import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from telemetry_aggregates.aggregation import incremental_merge, truncate_to_hour
from telemetry_aggregates.models import HourlyAggregate, ProcessedEvent

TOPIC = "telemetry-events"
GROUP_ID = "telemetry-aggregates-events"

Handler = Callable[[AsyncSession, uuid.UUID, dict], Awaitable[None]]


async def _already_processed(session: AsyncSession, event_id: uuid.UUID) -> bool:
    return await session.get(ProcessedEvent, event_id) is not None


async def handle_temperature_recorded(session: AsyncSession, event_id: uuid.UUID, payload: dict) -> None:
    """Incremental running-average update using only the event payload — no
    read-back to telemetry-db (see README's "Incremental update path"
    section for why this is the deliberate choice over a cross-database
    join). Dedup via `processed_events` guards against double-applying the
    *same* Kafka message on redelivery; it is not, on its own, a guarantee
    against double-counting relative to backfill after a consumer outage —
    that's backfill.py's job. A new hour_bucket always creates a new row
    rather than merging into the previous one, since the composite PK
    includes hour_bucket."""
    if await _already_processed(session, event_id):
        return
    session.add(ProcessedEvent(event_id=event_id))

    store_id = payload.get("store_id")
    product_id = payload.get("product_id")
    temperature = payload.get("temperature")
    recorded_at = payload.get("recorded_at")
    if store_id is None or product_id is None or temperature is None or recorded_at is None:
        return

    store_id = uuid.UUID(store_id)
    product_id = uuid.UUID(product_id)
    temperature = float(temperature)
    bucket = truncate_to_hour(datetime.fromisoformat(recorded_at))

    row = await session.get(HourlyAggregate, (store_id, product_id, bucket))
    if row is None:
        session.add(
            HourlyAggregate(
                store_id=store_id,
                product_id=product_id,
                hour_bucket=bucket,
                avg_temperature=temperature,
                min_temperature=temperature,
                max_temperature=temperature,
                reading_count=1,
            )
        )
        return

    new_avg, new_min, new_max, new_count = incremental_merge(
        float(row.avg_temperature),
        float(row.min_temperature),
        float(row.max_temperature),
        row.reading_count,
        temperature,
    )
    row.avg_temperature = new_avg
    row.min_temperature = new_min
    row.max_temperature = new_max
    row.reading_count = new_count


HANDLERS: dict[str, Handler] = {
    "TemperatureRecorded": handle_temperature_recorded,
}


def make_dispatch(session_factory: async_sessionmaker) -> Callable[[dict], Awaitable[None]]:
    async def dispatch(envelope: dict) -> None:
        handler = HANDLERS.get(envelope.get("event_type", ""))
        if handler is None:
            return
        async with session_factory() as session:
            await handler(session, uuid.UUID(envelope["event_id"]), envelope.get("payload", {}))
            await session.commit()

    return dispatch
