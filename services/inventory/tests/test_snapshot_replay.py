"""Snapshots exist purely to bound replay cost (see snapshots.py) --
never needed for the live projection's correctness, since that's always
current by construction. What must hold is: replaying from a snapshot
plus the events after it produces exactly the same state as replaying
from event zero. Also covers the snapshot-worker's eligibility thresholds
(N events, or a stale snapshot's age)."""

import uuid
from datetime import datetime, timedelta, timezone

from inventory import commands
from inventory.event_store import EventAppend, append_events, load_stream
from inventory.events import ITEM_RECEIVED, STOCK_ITEM_CREATED, compute_aggregate_id
from inventory.models import StockSnapshot
from inventory.projector import replay
from inventory.snapshots import SNAPSHOT_EVENT_THRESHOLD, find_aggregates_needing_snapshot, take_snapshot


def _payload(stock_id: uuid.UUID, product_id: uuid.UUID, **extra) -> dict:
    return {"stock_id": str(stock_id), "product_id": str(product_id), **extra}


async def _seed_stream(session_factory, aggregate_id: uuid.UUID, stock_id: uuid.UUID, product_id: uuid.UUID, n_receives: int) -> None:
    async with session_factory() as session:
        await append_events(
            session,
            [EventAppend(aggregate_id, 1, [(STOCK_ITEM_CREATED, _payload(stock_id, product_id, initial_quantity=0, created_at="2026-08-11T00:00:00+00:00"))])],
        )
        for i in range(n_receives):
            await append_events(
                session,
                [EventAppend(aggregate_id, 2 + i, [(ITEM_RECEIVED, _payload(stock_id, product_id, quantity_delta=1, source="test", received_at="2026-08-11T00:00:00+00:00"))])],
            )
        await session.commit()


async def test_replay_from_snapshot_matches_replay_from_zero(client):
    session_factory = client.app.state.session_factory
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()
    aggregate_id = compute_aggregate_id(stock_id, product_id)

    await _seed_stream(session_factory, aggregate_id, stock_id, product_id, n_receives=10)

    async with session_factory() as session:
        stream = await load_stream(session, aggregate_id)
        full_replay = replay(stream)

        # Snapshot as of halfway through the stream.
        halfway = stream[: len(stream) // 2]
        snapshot_state = replay(halfway)
        snapshot = StockSnapshot(
            aggregate_id=aggregate_id,
            sequence_number=halfway[-1].sequence_number,
            state={
                "stock_id": str(snapshot_state["stock_id"]),
                "product_id": str(snapshot_state["product_id"]),
                "quantity": snapshot_state["quantity"],
                "reserved_quantity": snapshot_state["reserved_quantity"],
                "is_unavailable": snapshot_state["is_unavailable"],
                "exists": snapshot_state["exists"],
            },
        )
        session.add(snapshot)
        await session.commit()

        remaining = [e for e in stream if e.sequence_number > snapshot.sequence_number]
        base_state = {
            "stock_id": uuid.UUID(snapshot.state["stock_id"]),
            "product_id": uuid.UUID(snapshot.state["product_id"]),
            "quantity": snapshot.state["quantity"],
            "reserved_quantity": snapshot.state["reserved_quantity"],
            "is_unavailable": snapshot.state["is_unavailable"],
            "exists": snapshot.state["exists"],
        }
        from_snapshot = replay(remaining, base_state)

    assert from_snapshot == full_replay


async def test_take_snapshot_writes_state_as_of_the_latest_sequence(client):
    session_factory = client.app.state.session_factory
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()
    aggregate_id = compute_aggregate_id(stock_id, product_id)
    await _seed_stream(session_factory, aggregate_id, stock_id, product_id, n_receives=3)

    async with session_factory() as session:
        stream = await load_stream(session, aggregate_id)
        snapshot = await take_snapshot(session, aggregate_id)
        await session.commit()

        assert snapshot is not None
        assert snapshot.sequence_number == stream[-1].sequence_number
        assert snapshot.state["quantity"] == replay(stream)["quantity"]


async def test_find_aggregates_needing_snapshot_by_event_count(client):
    session_factory = client.app.state.session_factory
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()
    aggregate_id = compute_aggregate_id(stock_id, product_id)

    # Below threshold: never snapshotted, but few events -- shouldn't be
    # picked up by the count rule (only the "never snapshotted" rule, which
    # always fires for any aggregate that has events -- see below).
    await _seed_stream(session_factory, aggregate_id, stock_id, product_id, n_receives=5)

    async with session_factory() as session:
        needing = await find_aggregates_needing_snapshot(session)
        # Never-snapshotted aggregates are always eligible (a first
        # snapshot is cheap and unblocks future incremental ones).
        assert aggregate_id in needing

        await take_snapshot(session, aggregate_id)
        await session.commit()

    # Fewer than SNAPSHOT_EVENT_THRESHOLD new events since that snapshot --
    # no longer eligible on the count rule, and the snapshot is fresh.
    async with session_factory() as session:
        needing = await find_aggregates_needing_snapshot(session)
        assert aggregate_id not in needing

    # Cross the threshold.
    other_stock_id, other_product_id = uuid.uuid4(), uuid.uuid4()
    other_aggregate = compute_aggregate_id(other_stock_id, other_product_id)
    await _seed_stream(session_factory, other_aggregate, other_stock_id, other_product_id, n_receives=SNAPSHOT_EVENT_THRESHOLD)

    async with session_factory() as session:
        await take_snapshot(session, other_aggregate)
        await session.commit()

    async with session_factory() as session:
        # Add enough events since that snapshot to cross the threshold.
        last = (await load_stream(session, other_aggregate))[-1].sequence_number
        for i in range(SNAPSHOT_EVENT_THRESHOLD):
            await append_events(
                session,
                [
                    EventAppend(
                        other_aggregate,
                        last + 1 + i,
                        [(ITEM_RECEIVED, _payload(other_stock_id, other_product_id, quantity_delta=1, source="test", received_at="2026-08-11T00:00:00+00:00"))],
                    )
                ],
            )
        await session.commit()

    async with session_factory() as session:
        needing = await find_aggregates_needing_snapshot(session)
        assert other_aggregate in needing


async def test_find_aggregates_needing_snapshot_by_age(client):
    session_factory = client.app.state.session_factory
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()
    aggregate_id = compute_aggregate_id(stock_id, product_id)
    await _seed_stream(session_factory, aggregate_id, stock_id, product_id, n_receives=1)

    async with session_factory() as session:
        snapshot = await take_snapshot(session, aggregate_id)
        # Backdate the snapshot past SNAPSHOT_MAX_AGE.
        snapshot.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        await session.commit()

    async with session_factory() as session:
        needing = await find_aggregates_needing_snapshot(session)
        assert aggregate_id in needing
