import json
import logging
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger(__name__)

Dispatch = Callable[[dict], Awaitable[None]]


async def run_consumer_loop(bootstrap_servers: str, topic: str, group_id: str, dispatch: Dispatch) -> None:
    """Same generic at-least-once consumer loop as telemetry's
    kafka.run_consumer_loop (see that module's docstring for the full
    rationale, including STR-133): manual offset commit only after
    `dispatch` returns without raising, a malformed message is logged and
    skipped rather than retried, and a genuine dispatch failure is logged
    and re-raised without committing so it redelivers on restart. This
    service never produces events (no outbox — it's a pure read model), so
    unlike telemetry's copy there's no KafkaEventProducer here."""
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    try:
        async for message in consumer:
            try:
                value = json.loads(message.value.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.error(
                    "Skipping unparseable message on topic=%s partition=%s offset=%s: %r",
                    topic,
                    message.partition,
                    message.offset,
                    message.value[:200],
                )
                await consumer.commit()
                continue

            try:
                await dispatch(value)
            except Exception:
                logger.exception(
                    "dispatch failed on topic=%s partition=%s offset=%s event_type=%s "
                    "— not committing, will redeliver on restart",
                    topic,
                    message.partition,
                    message.offset,
                    value.get("event_type"),
                )
                raise
            await consumer.commit()
    finally:
        await consumer.stop()
