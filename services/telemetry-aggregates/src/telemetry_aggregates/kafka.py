import json
import logging
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer, TopicPartition

from telemetry_aggregates.observability import record_kafka_lag

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
            # STR-158b/STR-134: lag = how far this partition's high-water
            # mark has moved past what we've now committed — one extra
            # Kafka round-trip per message is fine at this project's demo
            # scale; the ObservableGauge callback in observability.py just
            # reports whatever was last recorded here on Mimir's next scrape.
            try:
                tp = TopicPartition(topic, message.partition)
                end_offsets = await consumer.end_offsets([tp])
                record_kafka_lag(topic, group_id, max(0, end_offsets[tp] - (message.offset + 1)))
            except Exception:
                logger.debug("Failed to compute consumer lag for %s/%s", topic, group_id, exc_info=True)
    finally:
        await consumer.stop()
