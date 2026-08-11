"""Periodic snapshots, purely to bound replay cost -- see
`models.StockSnapshot`'s docstring and README.md. NOT on the hot path:
the live `stock_items` projection never reads a snapshot, since it's
already current by construction (folded synchronously with every event
append, see projector.py). This module is read by exactly two things: the
background `snapshot_worker`, and the `as-of` point-in-time endpoint.

Defaults: a snapshot is taken once an aggregate has accumulated >=100
events since its last snapshot, or its last snapshot is more than an hour
old (whichever comes first). 100 bounds worst-case replay for a hot SKU
(reserved/released/consumed repeatedly) to a small, fast fold; the 1-hour
ceiling guarantees low-traffic aggregates (most warehouse SKUs, which
might get one ItemReceived a week) still get a snapshot eventually for
disaster-recovery/as-of performance, rather than never crossing the count
threshold. Both numbers are pure operational tuning -- cheap to revise
later, no schema/contract implications.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.event_store import load_stream
from inventory.models import StockEvent, StockSnapshot
from inventory.projector import replay

SNAPSHOT_EVENT_THRESHOLD = 100
SNAPSHOT_MAX_AGE = timedelta(hours=1)


async def find_aggregates_needing_snapshot(session: AsyncSession) -> list[uuid.UUID]:
    """Aggregates whose event count since their last snapshot (or since
    the beginning of the stream, if they've never been snapshotted) has
    crossed SNAPSHOT_EVENT_THRESHOLD, or whose last snapshot predates
    SNAPSHOT_MAX_AGE. One query per poll, not per-aggregate -- cheap
    enough to run against every aggregate that has ever emitted an event.
    """
    all_aggregates = await session.execute(select(StockEvent.aggregate_id).distinct())
    aggregate_ids = [row[0] for row in all_aggregates.all()]

    cutoff = datetime.now(timezone.utc) - SNAPSHOT_MAX_AGE
    needing: list[uuid.UUID] = []
    for aggregate_id in aggregate_ids:
        latest_snapshot = await session.execute(
            select(StockSnapshot)
            .where(StockSnapshot.aggregate_id == aggregate_id)
            .order_by(StockSnapshot.sequence_number.desc())
            .limit(1)
        )
        snapshot = latest_snapshot.scalar_one_or_none()

        latest_seq = await session.execute(
            select(StockEvent.sequence_number)
            .where(StockEvent.aggregate_id == aggregate_id)
            .order_by(StockEvent.sequence_number.desc())
            .limit(1)
        )
        latest = latest_seq.scalar_one()

        if snapshot is None:
            needing.append(aggregate_id)
        elif latest - snapshot.sequence_number >= SNAPSHOT_EVENT_THRESHOLD:
            needing.append(aggregate_id)
        elif snapshot.created_at is not None:
            created_at = snapshot.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at < cutoff:
                needing.append(aggregate_id)
    return needing


async def take_snapshot(session: AsyncSession, aggregate_id: uuid.UUID) -> StockSnapshot | None:
    """Replays the full current stream for `aggregate_id` and writes a
    snapshot as of its latest sequence_number. Returns None if the
    aggregate somehow has no events (nothing to snapshot)."""
    stream = await load_stream(session, aggregate_id)
    if not stream:
        return None

    state = replay(stream)
    snapshot = StockSnapshot(
        aggregate_id=aggregate_id,
        sequence_number=stream[-1].sequence_number,
        state={
            "stock_id": str(state["stock_id"]) if state["stock_id"] else None,
            "product_id": str(state["product_id"]) if state["product_id"] else None,
            "quantity": state["quantity"],
            "reserved_quantity": state["reserved_quantity"],
            "is_unavailable": state["is_unavailable"],
            "exists": state["exists"],
        },
    )
    session.add(snapshot)
    return snapshot
