import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition

from telemetry.observability import record_kafka_lag

logger = logging.getLogger(__name__)

Dispatch = Callable[[dict], Awaitable[None]]


class KafkaEventProducer:
    def __init__(self, bootstrap_servers: str) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def send(self, topic: str, event_type: str, payload: dict, event_id: uuid.UUID | None = None) -> None:
        envelope = {
            "event_id": str(event_id or uuid.uuid4()),
            "event_type": event_type,
            "payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._producer.send_and_wait(topic, envelope)


async def run_consumer_loop(bootstrap_servers: str, topic: str, group_id: str, dispatch: Dispatch) -> None:
    """Generic at-least-once consumer loop: manual offset commit only after
    `dispatch` returns without raising, so a crash mid-handler redelivers
    the message rather than silently dropping it. `dispatch` is expected to
    itself be idempotent-safe for the events it handles.

    This task is created with `asyncio.create_task` and never awaited until
    shutdown (see main.py's lifespan), so an exception raised out of this
    function doesn't surface anywhere by default — the task just dies and
    the consumer group quietly stops advancing (see STR-133: a stray
    non-JSON message on order-events wedged Inventory's copy of this loop
    with no error in the logs and no recovery even across a service
    restart, since the next consumer hit the exact same unparseable
    message at the same offset).

    Deserialization is done here rather than via AIOKafkaConsumer's
    `value_deserializer` so a single malformed message doesn't blow up
    iteration itself. It's logged and skipped (committed past) rather than
    retried, since a message that isn't valid JSON can never become valid
    JSON on redelivery — retrying it would just wedge the consumer forever,
    which is exactly what happened. A `dispatch` failure on an
    otherwise-well-formed message is logged too, but still re-raised
    without committing, preserving the redeliver-on-restart behavior above
    for errors that might genuinely be transient — the difference is that
    it's now visible in `docker compose logs` instead of vanishing.
    """
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
