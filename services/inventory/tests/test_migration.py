"""STR-149's data-backfill migration (migrations/versions/85cc420998d1_
backfill_stock_events.py) converts existing stock_items rows -- including
outstanding in-flight reservations -- into an equivalent event sequence.
This test exercises the migration's row-to-event transform directly
(inventory.migration_support.build_backfill_events, the plain function the
Alembic script calls) and asserts that replaying its output reproduces
the pre-migration quantity/reserved_quantity exactly. Real Alembic
machinery (`op.get_bind()`) only works inside an actual `alembic upgrade`
run, so the migration script itself is a thin, untested-here wrapper
around this function -- see its docstring.
"""

import uuid

from inventory.event_store import EventAppend
from inventory.migration_support import build_backfill_events
from inventory.models import StockEvent
from inventory.projector import replay


def _make_event_objects(rows: list[dict]) -> list[StockEvent]:
    """Turns build_backfill_events' plain dicts into StockEvent instances
    so they can go through projector.replay the same way a real read from
    stock_events would."""
    return [
        StockEvent(
            id=row["id"],
            aggregate_id=row["aggregate_id"],
            event_type=row["event_type"],
            payload=row["payload"],
            sequence_number=row["sequence_number"],
        )
        for row in rows
    ]


def test_backfill_reproduces_a_plain_item_with_no_reservations():
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()
    item_id = uuid.uuid4()
    items = [{"id": item_id, "stock_id": stock_id, "product_id": product_id, "quantity": 17}]

    rows = build_backfill_events(items, outstanding_reservations_by_item_id={})

    assert [row["event_type"] for row in rows] == ["StockItemCreated"]
    assert rows[0]["sequence_number"] == 1

    state = replay(_make_event_objects(rows))
    assert state["exists"] is True
    assert state["quantity"] == 17
    assert state["reserved_quantity"] == 0
    assert state["is_unavailable"] is False


def test_backfill_reproduces_outstanding_reservations_as_stock_reserved_events():
    stock_id, product_id = uuid.uuid4(), uuid.uuid4()
    item_id = uuid.uuid4()
    order_a, order_b = uuid.uuid4(), uuid.uuid4()
    items = [{"id": item_id, "stock_id": stock_id, "product_id": product_id, "quantity": 30}]
    outstanding = {item_id: [(5, order_a), (7, order_b)]}

    rows = build_backfill_events(items, outstanding)

    assert [row["event_type"] for row in rows] == ["StockItemCreated", "StockReserved", "StockReserved"]
    assert [row["sequence_number"] for row in rows] == [1, 2, 3]
    # Same aggregate for every row -- one stream per (stock_id, product_id).
    assert len({row["aggregate_id"] for row in rows}) == 1

    state = replay(_make_event_objects(rows))
    assert state["quantity"] == 30  # quantity itself is untouched by a hold
    assert state["reserved_quantity"] == 12  # 5 + 7


def test_backfill_keeps_separate_streams_per_aggregate():
    stock_a, stock_b = uuid.uuid4(), uuid.uuid4()
    product_id = uuid.uuid4()
    item_a, item_b = uuid.uuid4(), uuid.uuid4()
    items = [
        {"id": item_a, "stock_id": stock_a, "product_id": product_id, "quantity": 10},
        {"id": item_b, "stock_id": stock_b, "product_id": product_id, "quantity": 4},
    ]
    outstanding = {item_a: [(2, uuid.uuid4())]}

    rows = build_backfill_events(items, outstanding)
    events = _make_event_objects(rows)

    from inventory.events import compute_aggregate_id

    aggregate_a = compute_aggregate_id(stock_a, product_id)
    aggregate_b = compute_aggregate_id(stock_b, product_id)

    state_a = replay([e for e in events if e.aggregate_id == aggregate_a])
    state_b = replay([e for e in events if e.aggregate_id == aggregate_b])

    assert state_a["quantity"] == 10
    assert state_a["reserved_quantity"] == 2
    assert state_b["quantity"] == 4
    assert state_b["reserved_quantity"] == 0


def test_backfill_is_empty_for_no_stock_items():
    assert build_backfill_events([], {}) == []


async def test_migration_end_to_end_against_real_rows(client):
    """Runs build_backfill_events (the migration's core transform) against
    real stock_items/reservations rows created the same way the
    pre-STR-149 app would have, inserts its output the same way
    event_store.append_events does, and asserts the resulting stream
    replays to exactly the pre-migration quantity/reserved_quantity --
    including the outstanding in-flight reservation."""
    from inventory.event_store import append_events, load_stream
    from inventory.events import compute_aggregate_id
    from inventory.models import Reservation, ReservationItem, ReservationStatus, Stock, StockItem
    from datetime import datetime, timedelta, timezone

    session_factory = client.app.state.session_factory
    async with session_factory() as session:
        stock = Stock(name=f"Warehouse {uuid.uuid4()}")
        session.add(stock)
        await session.flush()
        item = StockItem(stock_id=stock.id, product_id=uuid.uuid4(), quantity=25, reserved_quantity=6)
        session.add(item)
        await session.flush()

        reservation = Reservation(
            order_id=uuid.uuid4(),
            status=ReservationStatus.RESERVED,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(reservation)
        await session.flush()
        session.add(ReservationItem(reservation_id=reservation.id, stock_item_id=item.id, quantity=6))
        await session.commit()

        stock_items_rows = [
            {"id": item.id, "stock_id": item.stock_id, "product_id": item.product_id, "quantity": item.quantity}
        ]
        outstanding = {item.id: [(6, reservation.order_id)]}

        event_rows = build_backfill_events(stock_items_rows, outstanding)
        await append_events(
            session,
            [
                EventAppend(row["aggregate_id"], row["sequence_number"], [(row["event_type"], row["payload"])])
                for row in event_rows
            ],
        )
        await session.commit()

        aggregate_id = compute_aggregate_id(item.stock_id, item.product_id)
        stream = await load_stream(session, aggregate_id)
        state = replay(stream)

        assert state["quantity"] == item.quantity
        assert state["reserved_quantity"] == item.reserved_quantity
