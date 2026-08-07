import json
import uuid
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer


# Same envelope shape as every other producer in this codebase (see
# services/orders/src/orders/kafka.py) — Notifications and any other
# order-events/ops-events consumer dispatch on `event_type` regardless of
# which service produced the message.
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

    async def send(self, topic: str, event_type: str, payload: dict) -> None:
        envelope = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._producer.send_and_wait(topic, envelope)
