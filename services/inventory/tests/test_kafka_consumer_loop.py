import pytest

import inventory.kafka as kafka_module
from inventory.kafka import run_consumer_loop


class FakeMessage:
    def __init__(self, value: bytes, offset: int, partition: int = 0) -> None:
        self.value = value
        self.offset = offset
        self.partition = partition


class FakeConsumer:
    """Stands in for AIOKafkaConsumer: replays a fixed message list via
    async iteration and records committed offsets, without touching a real
    broker."""

    def __init__(self, messages: list[FakeMessage]) -> None:
        self._messages = iter(messages)
        self.committed_offsets: list[int] = []

    def __call__(self, *args, **kwargs):
        return self

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed_offsets.append(self._last_offset)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            message = next(self._messages)
        except StopIteration as exc:
            raise StopAsyncIteration from exc
        self._last_offset = message.offset
        return message


async def test_unparseable_message_is_skipped_and_committed(monkeypatch):
    messages = [
        FakeMessage(b"not-json", offset=0),
        FakeMessage(b'{"event_type": "OrderCreated", "payload": {}}', offset=1),
    ]
    fake_consumer = FakeConsumer(messages)
    monkeypatch.setattr(kafka_module, "AIOKafkaConsumer", fake_consumer)

    dispatched = []

    async def dispatch(value: dict) -> None:
        dispatched.append(value)

    await run_consumer_loop("kafka:9092", "order-events", "test-group", dispatch)

    assert dispatched == [{"event_type": "OrderCreated", "payload": {}}]
    assert fake_consumer.committed_offsets == [0, 1]


async def test_dispatch_failure_is_not_committed_and_reraises(monkeypatch):
    messages = [FakeMessage(b'{"event_type": "OrderCreated", "payload": {}}', offset=0)]
    fake_consumer = FakeConsumer(messages)
    monkeypatch.setattr(kafka_module, "AIOKafkaConsumer", fake_consumer)

    async def dispatch(value: dict) -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await run_consumer_loop("kafka:9092", "order-events", "test-group", dispatch)

    assert fake_consumer.committed_offsets == []
