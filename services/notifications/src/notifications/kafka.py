import json
import logging
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger(__name__)

Dispatch = Callable[[dict], Awaitable[None]]


async def run_consumer_loop(bootstrap_servers: str, topic: str, group_id: str, dispatch: Dispatch) -> None:
    """Generic at-least-once consumer loop: manual offset commit only after
    `dispatch` returns without raising, so a crash mid-handler (or a failed
    SMTP send that exhausts its own retries) redelivers the message rather
    than silently dropping it. Same shape as
    services/orders/src/orders/kafka.py and
    services/inventory/src/inventory/kafka.py — duplicated rather than
    shared, matching this repo's existing convention (see e.g. each
    service's own internal-token verification).

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
    finally:
        await consumer.stop()
