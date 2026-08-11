"""The single implementation of event semantics for the `(stock_id,
product_id)` aggregate: `apply_event` is a pure fold function, reused by
every consumer of that semantics -- the live synchronous projection
(`project_and_upsert`), the `as-of` point-in-time endpoint, snapshot
rebuilding, and `test_projection_consistency.py`'s from-scratch replay
check. There is deliberately no second implementation anywhere of what an
event "means".

`project_and_upsert` is the synchronous-projection half of this design:
called inside the *same* DB transaction as the event append (see
event_store.append_events / commands.run_with_retry), so a caller's very
next read of `stock_items` sees consistent state immediately. This is a
deliberate deviation from services/telemetry-aggregates' async-Kafka
-consumer CQRS pattern -- see README.md for why that pattern is wrong for
this projection.
"""

import uuid
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory import events as ev
from inventory.models import StockEvent, StockItem


class ProjectionState(TypedDict):
    stock_id: uuid.UUID | None
    product_id: uuid.UUID | None
    quantity: int
    reserved_quantity: int
    is_unavailable: bool
    # False for an aggregate that has never had a StockItemCreated event
    # yet, or whose stock_items row was removed by a StockItemRemoved event
    # and never re-received since. A later ItemReceived/StockItemCreated on
    # the same (stock_id, product_id) flips this back to True and reopens
    # the same aggregate stream -- identity is the pair, for life,
    # independent of whether a projection row currently exists.
    exists: bool


def initial_state() -> ProjectionState:
    return ProjectionState(stock_id=None, product_id=None, quantity=0, reserved_quantity=0, is_unavailable=False, exists=False)


def state_from_stock_item(item: StockItem) -> ProjectionState:
    return ProjectionState(
        stock_id=item.stock_id,
        product_id=item.product_id,
        quantity=item.quantity,
        reserved_quantity=item.reserved_quantity,
        is_unavailable=item.is_unavailable,
        exists=True,
    )


def apply_event(state: ProjectionState, event: StockEvent) -> ProjectionState:
    """Folds one event into `state`, returning a new state (never mutates
    its input) -- the exhaustive branch set for `events.ALL_EVENT_TYPES`."""
    payload = event.payload
    state = dict(state)  # type: ignore[assignment]

    if event.event_type == ev.STOCK_ITEM_CREATED:
        state["stock_id"] = uuid.UUID(payload["stock_id"])
        state["product_id"] = uuid.UUID(payload["product_id"])
        state["quantity"] = payload["initial_quantity"]
        state["reserved_quantity"] = 0
        state["is_unavailable"] = False
        state["exists"] = True
    elif event.event_type == ev.ITEM_RECEIVED:
        state["quantity"] += payload["quantity_delta"]
    elif event.event_type == ev.ITEM_MOVED_OUT:
        state["quantity"] -= payload["quantity"]
    elif event.event_type == ev.ITEM_MOVED_IN:
        if not state["exists"]:
            state["stock_id"] = uuid.UUID(payload["stock_id"])
            state["product_id"] = uuid.UUID(payload["product_id"])
            state["quantity"] = payload["quantity"]
            state["reserved_quantity"] = 0
            state["is_unavailable"] = False
            state["exists"] = True
        else:
            state["quantity"] += payload["quantity"]
    elif event.event_type == ev.STOCK_RESERVED:
        state["reserved_quantity"] += payload["quantity"]
    elif event.event_type == ev.STOCK_RELEASED:
        state["reserved_quantity"] -= payload["quantity"]
    elif event.event_type == ev.STOCK_CONSUMED:
        state["reserved_quantity"] -= payload["quantity"]
        state["quantity"] -= payload["quantity"]
    elif event.event_type == ev.STOCK_ITEM_QUANTITY_SET:
        state["quantity"] = payload["quantity"]
    elif event.event_type == ev.STOCK_ITEM_REMOVED:
        state["exists"] = False
    elif event.event_type == ev.MARKED_UNAVAILABLE:
        state["is_unavailable"] = True
    elif event.event_type == ev.MARKED_AVAILABLE:
        state["is_unavailable"] = False
    else:
        raise ValueError(f"Unknown event_type: {event.event_type!r}")

    return state  # type: ignore[return-value]


def replay(events: list[StockEvent], state: ProjectionState | None = None) -> ProjectionState:
    """Folds a whole (ordered) stream -- or a snapshot's state plus the
    events after it -- into a final ProjectionState. `state` defaults to
    the empty aggregate."""
    state = state if state is not None else initial_state()
    for event in events:
        state = apply_event(state, event)
    return state


async def project_and_upsert(
    session: AsyncSession, aggregate_id: uuid.UUID, new_events: list[StockEvent]
) -> StockItem | None:
    """Applies `new_events` (already appended to stock_events, in sequence
    order, all for the same aggregate) on top of the current `stock_items`
    row (if any) and writes the result back -- in the caller's still-open
    transaction, never a separate commit. Returns the resulting row, or
    None if the fold ended in a "removed" state (in which case any existing
    row is deleted).

    stock_items keeps the id of whatever row already existed for this
    (stock_id, product_id) pair -- a fresh id is only minted the first time
    an aggregate gets a row, so existing callers holding a stock_item id
    (PATCH/DELETE/move endpoints) keep working across every subsequent
    projection update.
    """
    if not new_events:
        return None

    stock_id = uuid.UUID(new_events[0].payload["stock_id"])
    product_id = uuid.UUID(new_events[0].payload["product_id"])

    result = await session.execute(select(StockItem).where(StockItem.stock_id == stock_id, StockItem.product_id == product_id))
    item = result.scalar_one_or_none()

    state = state_from_stock_item(item) if item is not None else initial_state()
    for event in new_events:
        state = apply_event(state, event)

    if not state["exists"]:
        if item is not None:
            await session.delete(item)
            await session.flush()
        return None

    if item is None:
        item = StockItem(stock_id=stock_id, product_id=product_id)
        session.add(item)

    item.quantity = state["quantity"]
    item.reserved_quantity = state["reserved_quantity"]
    item.is_unavailable = state["is_unavailable"]

    await session.flush()
    return item
