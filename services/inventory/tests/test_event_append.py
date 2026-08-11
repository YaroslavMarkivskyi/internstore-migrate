"""STR-149: UNIQUE(aggregate_id, sequence_number) is the sole concurrency-
control mechanism for the (stock_id, product_id) aggregate -- this is the
test that proves it actually rejects a second writer racing for the same
slot, and that commands.run_with_retry recovers by re-reading and
retrying the whole command rather than silently corrupting state."""

import uuid

import pytest

from inventory import commands
from inventory.event_store import ConcurrencyConflict, EventAppend, append_events, load_last_sequence
from inventory.events import STOCK_ITEM_CREATED


def _created_event(stock_id: uuid.UUID, product_id: uuid.UUID, quantity: int = 1) -> tuple[str, dict]:
    return (
        STOCK_ITEM_CREATED,
        {
            "aggregate_id": "unused-in-this-test",
            "stock_id": str(stock_id),
            "product_id": str(product_id),
            "initial_quantity": quantity,
            "created_at": "2026-08-11T00:00:00+00:00",
        },
    )


@pytest.fixture
async def session_factory(client):
    return client.app.state.session_factory


async def test_second_writer_at_same_sequence_number_conflicts(session_factory):
    aggregate_id = uuid.uuid4()
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()

    async with session_factory() as first:
        await append_events(first, [EventAppend(aggregate_id, 1, [_created_event(stock_id, product_id)])])
        await first.commit()

    async with session_factory() as second:
        with pytest.raises(ConcurrencyConflict):
            await append_events(second, [EventAppend(aggregate_id, 1, [_created_event(stock_id, product_id, 2)])])


async def test_writer_at_the_correct_next_sequence_succeeds(session_factory):
    aggregate_id = uuid.uuid4()
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()

    async with session_factory() as session:
        await append_events(session, [EventAppend(aggregate_id, 1, [_created_event(stock_id, product_id)])])
        await session.commit()

    async with session_factory() as session:
        last_seq = await load_last_sequence(session, aggregate_id)
        assert last_seq == 1
        events = await append_events(session, [EventAppend(aggregate_id, last_seq + 1, [_created_event(stock_id, product_id)])])
        await session.commit()

    assert events[0].sequence_number == 2


async def test_run_with_retry_recovers_from_a_conflicting_first_attempt(session_factory):
    """Simulates a genuine race: a concurrent writer claims sequence 1
    between when a command starts and when it tries to append. The first
    attempt's stale expected_next_sequence must conflict; run_with_retry
    must re-read fresh state and succeed on the second attempt -- not
    silently double-apply, not give up after one failure."""
    aggregate_id = uuid.uuid4()
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()

    # The "concurrent writer" that gets there first.
    async with session_factory() as seeder:
        await append_events(seeder, [EventAppend(aggregate_id, 1, [_created_event(stock_id, product_id)])])
        await seeder.commit()

    calls = {"count": 0}

    async def build(session):
        calls["count"] += 1
        if calls["count"] == 1:
            # Stale: this attempt's read happened (in the simulated
            # timeline) before the seeder above committed.
            next_seq = 1
        else:
            next_seq = await load_last_sequence(session, aggregate_id) + 1
        return [EventAppend(aggregate_id, next_seq, [_created_event(stock_id, product_id, 5)])], calls["count"]

    result, projected = await commands.run_with_retry(session_factory, build)

    assert calls["count"] == 2  # first attempt conflicted and rolled back, second succeeded
    assert result == 2
    item = projected[aggregate_id]
    assert item is not None
    assert item.quantity == 5


async def test_run_with_retry_raises_after_exhausting_attempts(session_factory):
    aggregate_id = uuid.uuid4()
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()

    async with session_factory() as seeder:
        await append_events(seeder, [EventAppend(aggregate_id, 1, [_created_event(stock_id, product_id)])])
        await seeder.commit()

    async def always_stale_build(session):
        return [EventAppend(aggregate_id, 1, [_created_event(stock_id, product_id)])], "unused"

    with pytest.raises(ConcurrencyConflict):
        await commands.run_with_retry(session_factory, always_stale_build, max_attempts=2)
