"""Command layer: every write path that used to mutate `stock_items`
directly now goes through here. Each `build_*` function validates a
request against a given session and returns the `EventAppend` batch (one
entry per aggregate touched) plus whatever result value its caller wants
-- it does not append or commit anything itself, so it can be reused both
by the retrying convenience wrappers below (`receive_stock_item`,
`reserve`, ...) and directly by callers that already own a transaction
they need everything folded into (the Kafka consumers in `consumers/`,
which per ADR 0002's single-partition-topic guarantee have no concurrent
writer to race and so don't need their own retry loop).

`run_with_retry` is the optimistic-concurrency algorithm: it opens a fresh
session, calls a `build_*` function, appends events + updates the
projection, and commits -- all in one transaction. A `ConcurrencyConflict`
(another writer claimed a sequence number first) rolls the whole attempt
back and retries from scratch, since the stale sequence numbers `build_*`
read usually mean a stale business decision too (e.g. how much stock was
actually available). This is what "replaces row-level locking" means in
practice: nothing here ever takes a row lock, and the only place we retry
is at the command level, driven by a real fresh read.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from opentelemetry import metrics
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inventory import events as ev
from inventory.event_store import ConcurrencyConflict, EventAppend, append_events, load_last_sequence
from inventory.models import Reservation, ReservationItem, ReservationStatus, StockItem

# STR-158b/STR-150: every retry through run_with_retry's loop below is a
# real optimistic-concurrency conflict — this is the metric that would
# have made STR-150's manually-tested 5/5-runs-one-winner behavior visible
# on a dashboard instead of requiring a dedicated manual test pass.
_meter = metrics.get_meter(__name__)
_concurrency_conflicts = _meter.create_counter(
    "inventory_concurrency_conflicts_total",
    description="Optimistic-concurrency conflicts on aggregate append (retried, not necessarily fatal).",
)
from inventory.outbox import add_outbox_event
from inventory.projector import project_and_upsert

MAX_ATTEMPTS = 3

# What a build_* function returns: None for a business-level rejection
# that should NOT be retried (e.g. "insufficient stock", "reservation not
# found") -- distinct from a ConcurrencyConflict, which IS retried.
# Otherwise, the EventAppend batch (may be empty, e.g. an idempotent no-op
# that still needs its result committed) plus a caller-defined result value.
BuildOutcome = tuple[list[EventAppend], object] | None


class StockItemNotFound(Exception):
    pass


class InsufficientQuantity(Exception):
    pass


class ReservedQuantityHeld(Exception):
    pass


class SameStockError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def apply(session: AsyncSession, appends: list[EventAppend]) -> dict[uuid.UUID, StockItem | None]:
    """Appends every event in `appends` and folds each touched aggregate's
    new events into the projection -- no commit. Shared by
    `run_with_retry` and by callers (Kafka consumers) that own their own
    transaction and don't go through the retry wrapper."""
    stock_events = await append_events(session, appends)

    by_aggregate: dict[uuid.UUID, list] = {}
    for stock_event in stock_events:
        by_aggregate.setdefault(stock_event.aggregate_id, []).append(stock_event)

    projected: dict[uuid.UUID, StockItem | None] = {}
    for aggregate_id, agg_events in by_aggregate.items():
        agg_events.sort(key=lambda e: e.sequence_number)
        projected[aggregate_id] = await project_and_upsert(session, aggregate_id, agg_events)
    return projected


async def run_with_retry(
    session_factory: async_sessionmaker[AsyncSession],
    build: Callable[..., Awaitable[BuildOutcome]],
    *args: object,
    max_attempts: int = MAX_ATTEMPTS,
    **kwargs: object,
) -> tuple[object, dict[uuid.UUID, StockItem | None]] | None:
    last_error: ConcurrencyConflict | None = None
    for _ in range(max_attempts):
        async with session_factory() as session:
            outcome = await build(session, *args, **kwargs)
            if outcome is None:
                return None
            appends, result = outcome
            try:
                projected = await apply(session, appends)
            except ConcurrencyConflict as exc:
                await session.rollback()
                last_error = exc
                _concurrency_conflicts.add(1)
                continue

            await session.commit()
            return result, projected
    raise ConcurrencyConflict("exhausted retries") from last_error


# ---------------------------------------------------------------------------
# receive_stock_item / move_stock_item / set_stock_item_quantity /
# remove_stock_item / mark_unavailable / mark_available
#
# Admin CRUD-ish paths. Low contention in practice (one admin acting on one
# item at a time), but still go through the same append+retry mechanism as
# reserve/release for a single reason worth documenting: it's the only
# correct way to know "the next sequence_number" without a row lock, not
# because these paths are expected to race often.
# ---------------------------------------------------------------------------


async def build_receive_stock_item(
    session: AsyncSession, stock_id: uuid.UUID, product_id: uuid.UUID, quantity: int
) -> BuildOutcome:
    aggregate_id = ev.compute_aggregate_id(stock_id, product_id)
    existing = await session.execute(
        select(StockItem).where(StockItem.stock_id == stock_id, StockItem.product_id == product_id)
    )
    item = existing.scalar_one_or_none()
    next_seq = await load_last_sequence(session, aggregate_id) + 1

    if item is None:
        event = (
            ev.STOCK_ITEM_CREATED,
            {
                "aggregate_id": str(aggregate_id),
                "stock_id": str(stock_id),
                "product_id": str(product_id),
                "initial_quantity": quantity,
                "created_at": _now(),
            },
        )
    else:
        event = (
            ev.ITEM_RECEIVED,
            {
                "aggregate_id": str(aggregate_id),
                "stock_id": str(stock_id),
                "product_id": str(product_id),
                "quantity_delta": quantity,
                "source": "admin_receive",
                "received_at": _now(),
            },
        )

    appends = [EventAppend(aggregate_id=aggregate_id, expected_next_sequence=next_seq, events=[event])]

    # STR-152: the event-sourcing migration (STR-149/150) moved this whole
    # path onto stock_events, which is Inventory's own internal audit log
    # and is never published to Kafka (see event_store.py) -- it dropped
    # the `add_outbox_event(session, "ItemAdded", ...)` call this route used
    # to make directly, silently breaking Telemetry's inventory-events
    # consumer (telemetry/consumers/inventory_events.py's handle_item_added,
    # the only thing that creates a store_product_thresholds row for a
    # {store, product} pair). Found live: scripts/test-telemetry-saga.sh's
    # violation-detection step polled forever because Telemetry never
    # learned this store carries this product. Re-staged here, unconditional
    # on create vs. replenish exactly like the pre-migration code, into the
    # same transaction as the stock_events append (both commit or roll back
    # together under run_with_retry).
    add_outbox_event(session, "ItemAdded", {"stock_id": str(stock_id), "product_id": str(product_id)})

    return appends, aggregate_id


async def receive_stock_item(
    session_factory: async_sessionmaker[AsyncSession], stock_id: uuid.UUID, product_id: uuid.UUID, quantity: int
) -> StockItem:
    outcome = await run_with_retry(session_factory, build_receive_stock_item, stock_id, product_id, quantity)
    assert outcome is not None  # build_receive_stock_item never returns None
    aggregate_id, projected = outcome
    item = projected[aggregate_id]
    assert item is not None
    return item


async def build_move_stock_item(
    session: AsyncSession, stock_id: uuid.UUID, item_id: uuid.UUID, to_stock_id: uuid.UUID, quantity: int
) -> BuildOutcome:
    if to_stock_id == stock_id:
        raise SameStockError()

    source_item = await session.get(StockItem, item_id)
    if source_item is None or source_item.stock_id != stock_id:
        raise StockItemNotFound()
    if source_item.quantity < quantity:
        raise InsufficientQuantity()

    product_id = source_item.product_id
    source_aggregate = ev.compute_aggregate_id(stock_id, product_id)
    dest_aggregate = ev.compute_aggregate_id(to_stock_id, product_id)
    move_id = str(uuid.uuid4())
    now = _now()

    source_next = await load_last_sequence(session, source_aggregate) + 1
    dest_next = await load_last_sequence(session, dest_aggregate) + 1

    appends = [
        EventAppend(
            aggregate_id=source_aggregate,
            expected_next_sequence=source_next,
            events=[
                (
                    ev.ITEM_MOVED_OUT,
                    {
                        "aggregate_id": str(source_aggregate),
                        "stock_id": str(stock_id),
                        "product_id": str(product_id),
                        "quantity": quantity,
                        "to_stock_id": str(to_stock_id),
                        "move_id": move_id,
                        "moved_at": now,
                    },
                )
            ],
        ),
        EventAppend(
            aggregate_id=dest_aggregate,
            expected_next_sequence=dest_next,
            events=[
                (
                    ev.ITEM_MOVED_IN,
                    {
                        "aggregate_id": str(dest_aggregate),
                        "stock_id": str(to_stock_id),
                        "product_id": str(product_id),
                        "quantity": quantity,
                        "from_stock_id": str(stock_id),
                        "move_id": move_id,
                        "moved_at": now,
                    },
                )
            ],
        ),
    ]

    # STR-153: same gap as build_receive_stock_item's ItemAdded above --
    # the pre-STR-149 move_stock_item route staged ItemAdded for the
    # *destination* stock (source stock isn't newly carrying the product,
    # only the destination is), which the STR-149 rewrite dropped since
    # ItemAdded wasn't in that ticket's own event taxonomy. Telemetry's
    # handle_item_added is what lazily creates the destination
    # {store, product} threshold row, so without this a moved-in item at a
    # stock that had never directly received it stays outside temperature
    # monitoring. Re-staged here, into the same transaction as both
    # ItemMovedOut/ItemMovedIn appends.
    add_outbox_event(session, "ItemAdded", {"stock_id": str(to_stock_id), "product_id": str(product_id)})

    return appends, dest_aggregate


async def move_stock_item(
    session_factory: async_sessionmaker[AsyncSession],
    stock_id: uuid.UUID,
    item_id: uuid.UUID,
    to_stock_id: uuid.UUID,
    quantity: int,
) -> StockItem:
    outcome = await run_with_retry(session_factory, build_move_stock_item, stock_id, item_id, to_stock_id, quantity)
    assert outcome is not None
    dest_aggregate, projected = outcome
    item = projected[dest_aggregate]
    assert item is not None
    return item


async def build_set_stock_item_quantity(
    session: AsyncSession, stock_id: uuid.UUID, item_id: uuid.UUID, quantity: int
) -> BuildOutcome:
    item = await session.get(StockItem, item_id)
    if item is None or item.stock_id != stock_id:
        raise StockItemNotFound()

    aggregate_id = ev.compute_aggregate_id(stock_id, item.product_id)
    next_seq = await load_last_sequence(session, aggregate_id) + 1
    event = (
        ev.STOCK_ITEM_QUANTITY_SET,
        {
            "aggregate_id": str(aggregate_id),
            "stock_id": str(stock_id),
            "product_id": str(item.product_id),
            "quantity": quantity,
            "previous_quantity": item.quantity,
            "set_at": _now(),
        },
    )
    appends = [EventAppend(aggregate_id=aggregate_id, expected_next_sequence=next_seq, events=[event])]
    return appends, aggregate_id


async def set_stock_item_quantity(
    session_factory: async_sessionmaker[AsyncSession], stock_id: uuid.UUID, item_id: uuid.UUID, quantity: int
) -> StockItem:
    outcome = await run_with_retry(session_factory, build_set_stock_item_quantity, stock_id, item_id, quantity)
    assert outcome is not None
    aggregate_id, projected = outcome
    item = projected[aggregate_id]
    assert item is not None
    return item


async def build_remove_stock_item(session: AsyncSession, stock_id: uuid.UUID, item_id: uuid.UUID) -> BuildOutcome:
    item = await session.get(StockItem, item_id)
    if item is None or item.stock_id != stock_id:
        raise StockItemNotFound()
    if item.reserved_quantity > 0:
        raise ReservedQuantityHeld()

    # reserved_quantity == 0 means no *active* RESERVED reservation holds
    # this item, but ReservationItem rows from past RELEASED/CONSUMED
    # reservations still FK-reference it as history -- removed here first
    # since the FK has no ON DELETE CASCADE (unchanged from pre-STR-149
    # behavior, see the original delete_stock_item).
    await session.execute(delete(ReservationItem).where(ReservationItem.stock_item_id == item_id))

    aggregate_id = ev.compute_aggregate_id(stock_id, item.product_id)
    next_seq = await load_last_sequence(session, aggregate_id) + 1
    event = (
        ev.STOCK_ITEM_REMOVED,
        {
            "aggregate_id": str(aggregate_id),
            "stock_id": str(stock_id),
            "product_id": str(item.product_id),
            "removed_at": _now(),
        },
    )
    appends = [EventAppend(aggregate_id=aggregate_id, expected_next_sequence=next_seq, events=[event])]
    return appends, item.product_id


async def remove_stock_item(session_factory: async_sessionmaker[AsyncSession], stock_id: uuid.UUID, item_id: uuid.UUID) -> uuid.UUID:
    """Returns the removed item's product_id, for the router's post-commit
    unpublish-if-out-of-stock check (same as pre-STR-149 behavior)."""
    outcome = await run_with_retry(session_factory, build_remove_stock_item, stock_id, item_id)
    assert outcome is not None
    product_id, _projected = outcome
    return product_id


async def build_mark_unavailable(
    session: AsyncSession, stock_id: uuid.UUID, product_id: uuid.UUID, reason: str
) -> BuildOutcome:
    # Mirrors the pre-STR-149 telemetry consumer's "if item is None:
    # return" -- a TemperatureThresholdViolated for a (stock_id,
    # product_id) with no stock_items row is a no-op, not an error. Checked
    # via the projection row (like receive_stock_item/set_stock_item_
    # quantity/remove_stock_item), not the event stream, so this behaves
    # the same whether or not the aggregate's history happens to include a
    # StockItemCreated event.
    existing = await session.execute(
        select(StockItem).where(StockItem.stock_id == stock_id, StockItem.product_id == product_id)
    )
    if existing.scalar_one_or_none() is None:
        return None

    aggregate_id = ev.compute_aggregate_id(stock_id, product_id)
    last_seq = await load_last_sequence(session, aggregate_id)
    event = (
        ev.MARKED_UNAVAILABLE,
        {
            "aggregate_id": str(aggregate_id),
            "stock_id": str(stock_id),
            "product_id": str(product_id),
            "reason": reason,
            "marked_at": _now(),
        },
    )
    appends = [EventAppend(aggregate_id=aggregate_id, expected_next_sequence=last_seq + 1, events=[event])]
    return appends, aggregate_id


async def mark_unavailable(
    session_factory: async_sessionmaker[AsyncSession], stock_id: uuid.UUID, product_id: uuid.UUID, reason: str
) -> StockItem | None:
    outcome = await run_with_retry(session_factory, build_mark_unavailable, stock_id, product_id, reason)
    if outcome is None:
        return None
    aggregate_id, projected = outcome
    return projected[aggregate_id]


async def build_mark_available(session: AsyncSession, stock_id: uuid.UUID, product_id: uuid.UUID) -> BuildOutcome:
    existing = await session.execute(
        select(StockItem).where(StockItem.stock_id == stock_id, StockItem.product_id == product_id)
    )
    if existing.scalar_one_or_none() is None:
        raise StockItemNotFound()

    aggregate_id = ev.compute_aggregate_id(stock_id, product_id)
    last_seq = await load_last_sequence(session, aggregate_id)
    event = (
        ev.MARKED_AVAILABLE,
        {
            "aggregate_id": str(aggregate_id),
            "stock_id": str(stock_id),
            "product_id": str(product_id),
            "marked_at": _now(),
        },
    )
    appends = [EventAppend(aggregate_id=aggregate_id, expected_next_sequence=last_seq + 1, events=[event])]
    return appends, aggregate_id


async def mark_available(
    session_factory: async_sessionmaker[AsyncSession], stock_id: uuid.UUID, product_id: uuid.UUID
) -> StockItem:
    outcome = await run_with_retry(session_factory, build_mark_available, stock_id, product_id)
    assert outcome is not None
    aggregate_id, projected = outcome
    item = projected[aggregate_id]
    assert item is not None
    return item


# ---------------------------------------------------------------------------
# reserve / release / consume
#
# The concurrency-sensitive paths: reserve_stock's REST endpoint (Temporal
# saga) can genuinely race (retries, concurrent orders for the same
# product), which is exactly the scenario UNIQUE(aggregate_id,
# sequence_number) + retry-the-whole-command exists for. The Kafka
# choreography saga's handlers (consumers/order_events.py) call
# build_reserve/build_consume directly against their own dispatch-owned
# session instead of these retrying wrappers -- ADR 0002's single-partition
# topics mean there is no concurrent writer to race there (same reasoning
# the pre-STR-149 try_reserve docstring already documented).
#
# `Reservation`/`ReservationItem` are NOT event-sourced -- they're
# order-level bookkeeping ("what did order X hold, from which stock_item
# rows") outside this ticket's scope (the (stock_id, product_id) quantity
# aggregate is what's event-sourced). They're created/updated directly,
# in the same transaction as the stock_events append + projection update,
# so "a Reservation row exists" and "its StockReserved events exist" can
# never disagree.
# ---------------------------------------------------------------------------


async def _allocate(session: AsyncSession, items: list[dict]) -> list[tuple[StockItem, int]] | None:
    """Identical decision logic to the pre-STR-149 `try_reserve`: for each
    requested (product_id, quantity), sum `quantity - reserved_quantity`
    across every StockItem row for that product; if any product can't be
    fully covered, the whole batch fails (all-or-nothing) and returns None.
    Otherwise greedily allocates across rows. Extracted here so `build_
    reserve` emits events off of this instead of directly mutating
    `reserved_quantity` the way the original did."""
    allocations: list[tuple[StockItem, int]] = []

    for requested in items:
        product_id = uuid.UUID(str(requested["product_id"]))
        quantity_needed = int(requested["quantity"])

        result = await session.execute(
            select(StockItem).where(StockItem.product_id == product_id).order_by(StockItem.id)
        )
        stock_items = list(result.scalars().all())

        total_available = sum(item.quantity - item.reserved_quantity for item in stock_items)
        if total_available < quantity_needed:
            return None

        remaining = quantity_needed
        for stock_item in stock_items:
            if remaining <= 0:
                break
            available = stock_item.quantity - stock_item.reserved_quantity
            if available <= 0:
                continue
            take = min(available, remaining)
            allocations.append((stock_item, take))
            remaining -= take

    return allocations


async def build_reserve(
    session: AsyncSession, order_id: uuid.UUID, items: list[dict], ttl_seconds: float
) -> BuildOutcome:
    # Idempotent by order_id, same as pre-STR-149: a retried call (Temporal
    # activity retry, or a redelivered OrderCreated) for an order_id that
    # already has a Reservation is a no-op that reports success again,
    # never a second reservation.
    existing = await session.execute(select(Reservation).where(Reservation.order_id == order_id))
    if existing.scalar_one_or_none() is not None:
        return [], "reserved"

    allocations = await _allocate(session, items)
    if allocations is None:
        return None  # insufficient_stock

    reservation = Reservation(
        order_id=order_id,
        status=ReservationStatus.RESERVED,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
    )
    session.add(reservation)
    await session.flush()  # populate reservation.id for the ReservationItem FK

    appends: list[EventAppend] = []
    now = _now()
    for stock_item, quantity in allocations:
        session.add(ReservationItem(reservation_id=reservation.id, stock_item_id=stock_item.id, quantity=quantity))
        aggregate_id = ev.compute_aggregate_id(stock_item.stock_id, stock_item.product_id)
        next_seq = await load_last_sequence(session, aggregate_id) + 1
        appends.append(
            EventAppend(
                aggregate_id=aggregate_id,
                expected_next_sequence=next_seq,
                events=[
                    (
                        ev.STOCK_RESERVED,
                        {
                            "aggregate_id": str(aggregate_id),
                            "stock_id": str(stock_item.stock_id),
                            "product_id": str(stock_item.product_id),
                            "quantity": quantity,
                            "order_id": str(order_id),
                            "reserved_at": now,
                        },
                    )
                ],
            )
        )

    return appends, "reserved"


async def reserve(
    session_factory: async_sessionmaker[AsyncSession], order_id: uuid.UUID, items: list[dict], ttl_seconds: float
) -> str:
    outcome = await run_with_retry(session_factory, build_reserve, order_id, items, ttl_seconds)
    if outcome is None:
        return "insufficient_stock"
    result, _projected = outcome
    return result  # "reserved"


async def build_release(
    session: AsyncSession, order_id: uuid.UUID, extra_outbox_event: tuple[str, dict] | None = None
) -> BuildOutcome:
    result = await session.execute(
        select(Reservation).where(Reservation.order_id == order_id, Reservation.status == ReservationStatus.RESERVED)
    )
    reservation = result.scalar_one_or_none()
    if reservation is None:
        return None  # not_found -- already released/consumed, or never existed

    await session.refresh(reservation, attribute_names=["items"])
    appends: list[EventAppend] = []
    now = _now()
    for reservation_item in reservation.items:
        stock_item = await session.get(StockItem, reservation_item.stock_item_id)
        aggregate_id = ev.compute_aggregate_id(stock_item.stock_id, stock_item.product_id)
        next_seq = await load_last_sequence(session, aggregate_id) + 1
        appends.append(
            EventAppend(
                aggregate_id=aggregate_id,
                expected_next_sequence=next_seq,
                events=[
                    (
                        ev.STOCK_RELEASED,
                        {
                            "aggregate_id": str(aggregate_id),
                            "stock_id": str(stock_item.stock_id),
                            "product_id": str(stock_item.product_id),
                            "quantity": reservation_item.quantity,
                            "order_id": str(order_id),
                            "released_at": now,
                        },
                    )
                ],
            )
        )

    reservation.status = ReservationStatus.RELEASED
    if extra_outbox_event is not None:
        event_type, payload = extra_outbox_event
        add_outbox_event(session, event_type, payload)

    return appends, "released"


async def release(
    session_factory: async_sessionmaker[AsyncSession],
    order_id: uuid.UUID,
    extra_outbox_event: tuple[str, dict] | None = None,
) -> str:
    outcome = await run_with_retry(session_factory, build_release, order_id, extra_outbox_event)
    if outcome is None:
        return "not_found"
    result, _projected = outcome
    return result  # "released"


async def build_consume(session: AsyncSession, order_id: uuid.UUID) -> BuildOutcome:
    result = await session.execute(
        select(Reservation).where(Reservation.order_id == order_id, Reservation.status == ReservationStatus.RESERVED)
    )
    reservation = result.scalar_one_or_none()
    if reservation is None:
        return None

    await session.refresh(reservation, attribute_names=["items"])
    appends: list[EventAppend] = []
    product_ids: set[uuid.UUID] = set()
    now = _now()
    for reservation_item in reservation.items:
        stock_item = await session.get(StockItem, reservation_item.stock_item_id)
        product_ids.add(stock_item.product_id)
        aggregate_id = ev.compute_aggregate_id(stock_item.stock_id, stock_item.product_id)
        next_seq = await load_last_sequence(session, aggregate_id) + 1
        appends.append(
            EventAppend(
                aggregate_id=aggregate_id,
                expected_next_sequence=next_seq,
                events=[
                    (
                        ev.STOCK_CONSUMED,
                        {
                            "aggregate_id": str(aggregate_id),
                            "stock_id": str(stock_item.stock_id),
                            "product_id": str(stock_item.product_id),
                            "quantity": reservation_item.quantity,
                            "order_id": str(order_id),
                            "consumed_at": now,
                        },
                    )
                ],
            )
        )

    reservation.status = ReservationStatus.CONSUMED
    return appends, list(product_ids)


async def consume(session_factory: async_sessionmaker[AsyncSession], order_id: uuid.UUID) -> list[uuid.UUID] | None:
    outcome = await run_with_retry(session_factory, build_consume, order_id)
    if outcome is None:
        return None
    result, _projected = outcome
    return result
