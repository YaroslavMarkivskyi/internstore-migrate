"""The event-sourcing log's storage primitive.

`stock_events` is append-only and its `UNIQUE(aggregate_id,
sequence_number)` constraint is the *sole* concurrency-control mechanism
for the `(stock_id, product_id)` aggregate -- it replaces the row-level
locking a directly-mutated `stock_items` table would otherwise need.
Writing a new event requires knowing the aggregate's current last
sequence_number and inserting at `+1`; a conflict there means a concurrent
writer already claimed that slot, and the caller must re-read fresh state
and retry the whole command (see commands.run_with_retry). No
`SELECT ... FOR UPDATE` is used anywhere in this design.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.models import StockEvent


class ConcurrencyConflict(Exception):
    """Raised when an append's `expected_next_sequence` lost a race against
    another writer for the same aggregate. Never retried inside
    `append_events` itself -- the caller (commands.run_with_retry) is
    responsible for re-reading current state and retrying the whole
    command, since a stale sequence number usually means a stale business
    decision too (e.g. how much stock was actually available)."""


@dataclass
class EventAppend:
    """One aggregate's contribution to a multi-aggregate command (e.g. a
    move touches two aggregates, a multi-product reservation touches one
    per allocated stock_item). `events` is applied starting at
    `expected_next_sequence`, incrementing by one per event in the list."""

    aggregate_id: uuid.UUID
    expected_next_sequence: int
    events: list[tuple[str, dict]] = field(default_factory=list)  # (event_type, payload)


async def load_last_sequence(session: AsyncSession, aggregate_id: uuid.UUID) -> int:
    """0 if the aggregate has no events yet -- the next sequence_number to
    write is always this value + 1."""
    result = await session.execute(
        select(func.coalesce(func.max(StockEvent.sequence_number), 0)).where(
            StockEvent.aggregate_id == aggregate_id
        )
    )
    return result.scalar_one()


async def load_stream(session: AsyncSession, aggregate_id: uuid.UUID) -> list[StockEvent]:
    """The full event stream for one aggregate, in sequence order -- what a
    from-scratch replay (history API, test_projection_consistency, disaster
    recovery) folds over."""
    result = await session.execute(
        select(StockEvent).where(StockEvent.aggregate_id == aggregate_id).order_by(StockEvent.sequence_number)
    )
    return list(result.scalars().all())


async def append_events(session: AsyncSession, appends: list[EventAppend]) -> list[StockEvent]:
    """Stages every event across every aggregate in `appends` and flushes
    them in the caller's current transaction. Flushing (not just adding) is
    what actually sends the INSERTs and triggers the
    UNIQUE(aggregate_id, sequence_number) check against the database -- a
    conflict raises ConcurrencyConflict here, before any projection write,
    so a caller that rolls back on this exception never leaves a partial
    projection update committed for any of the touched aggregates.
    """
    rows: list[StockEvent] = []
    for append in appends:
        for offset, (event_type, payload) in enumerate(append.events):
            rows.append(
                StockEvent(
                    aggregate_id=append.aggregate_id,
                    event_type=event_type,
                    payload=payload,
                    sequence_number=append.expected_next_sequence + offset,
                )
            )
    session.add_all(rows)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConcurrencyConflict("aggregate sequence_number conflict") from exc
    return rows
