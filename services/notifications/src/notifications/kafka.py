import json
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer

Dispatch = Callable[[dict], Awaitable[None]]


async def run_consumer_loop(bootstrap_servers: str, topic: str, group_id: str, dispatch: Dispatch) -> None:
    """Generic at-least-once consumer loop: manual offset commit only after
    `dispatch` returns without raising, so a crash mid-handler (or a failed
    SMTP send that exhausts its own retries) redelivers the message rather
    than silently dropping it. Same shape as
    services/orders/src/orders/kafka.py and
    services/inventory/src/inventory/kafka.py — duplicated rather than
    shared, matching this repo's existing convention (see e.g. each
    service's own internal-token verification)."""
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    await consumer.start()
    try:
        async for message in consumer:
            await dispatch(message.value)
            await consumer.commit()
    finally:
        await consumer.stop()
