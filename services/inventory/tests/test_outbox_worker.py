from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.models import OutboxEvent
from inventory.outbox_worker import publish_pending_events


class FakeProducer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict]] = []

    async def send(self, topic: str, event_type: str, payload: dict, event_id=None) -> None:
        self.sent.append((topic, event_type, payload))


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def test_publish_pending_events_publishes_and_marks_published(client, session):
    session.add(OutboxEvent(event_type="StockReserved", payload={"order_id": "abc"}))
    await session.commit()

    producer = FakeProducer()
    published_count = await publish_pending_events(client.app.state.session_factory, producer)

    assert published_count == 1
    assert producer.sent == [("inventory-events", "StockReserved", {"order_id": "abc"})]

    async with client.app.state.session_factory() as check_session:
        rows = (await check_session.execute(select(OutboxEvent))).scalars().all()
        assert len(rows) == 1
        assert rows[0].published_at is not None


async def test_publish_pending_events_skips_already_published(client, session):
    session.add(OutboxEvent(event_type="StockReserved", payload={}, published_at=datetime.now(timezone.utc)))
    await session.commit()

    producer = FakeProducer()
    published_count = await publish_pending_events(client.app.state.session_factory, producer)

    assert published_count == 0
    assert producer.sent == []
