import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.models import ReservationStatus, Stock, StockItem
from inventory.reservation import consume_reservation, release_reservation, try_reserve

TTL_SECONDS = 3600


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def _make_stock_item(session: AsyncSession, quantity: int, product_id: uuid.UUID | None = None) -> StockItem:
    stock = Stock(name=f"Warehouse {uuid.uuid4()}")
    session.add(stock)
    await session.flush()
    item = StockItem(stock_id=stock.id, product_id=product_id or uuid.uuid4(), quantity=quantity)
    session.add(item)
    await session.flush()
    return item


async def test_try_reserve_single_stock_sufficient(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, quantity=10, product_id=product_id)
    order_id = uuid.uuid4()

    reservation = await try_reserve(session, order_id, [{"product_id": str(product_id), "quantity": 4}], TTL_SECONDS)
    await session.commit()

    assert reservation is not None
    assert reservation.status == ReservationStatus.RESERVED
    await session.refresh(item)
    assert item.reserved_quantity == 4
    assert item.quantity == 10  # unchanged until PaymentConfirmed


async def test_try_reserve_allocates_across_two_stocks(session):
    product_id = uuid.uuid4()
    item_a = await _make_stock_item(session, quantity=3, product_id=product_id)
    item_b = await _make_stock_item(session, quantity=5, product_id=product_id)
    order_id = uuid.uuid4()

    reservation = await try_reserve(session, order_id, [{"product_id": str(product_id), "quantity": 6}], TTL_SECONDS)
    await session.commit()

    assert reservation is not None
    await session.refresh(item_a)
    await session.refresh(item_b)
    # Allocation order across stock rows isn't guaranteed (StockItem.id is a
    # random UUID) — assert the invariants: total reserved matches the
    # request, and neither row is over-reserved.
    assert item_a.reserved_quantity + item_b.reserved_quantity == 6
    assert item_a.reserved_quantity <= item_a.quantity
    assert item_b.reserved_quantity <= item_b.quantity


async def test_try_reserve_insufficient_stock_returns_none_and_writes_nothing(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, quantity=2, product_id=product_id)
    order_id = uuid.uuid4()

    reservation = await try_reserve(session, order_id, [{"product_id": str(product_id), "quantity": 5}], TTL_SECONDS)

    assert reservation is None
    await session.refresh(item)
    assert item.reserved_quantity == 0


async def test_consume_reservation_decrements_quantity_and_marks_consumed(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, quantity=10, product_id=product_id)
    order_id = uuid.uuid4()
    await try_reserve(session, order_id, [{"product_id": str(product_id), "quantity": 4}], TTL_SECONDS)
    await session.commit()

    reservation = await consume_reservation(session, order_id)
    await session.commit()

    assert reservation is not None
    assert reservation.status == ReservationStatus.CONSUMED
    await session.refresh(item)
    assert item.reserved_quantity == 0
    assert item.quantity == 6


async def test_consume_reservation_is_a_no_op_when_nothing_reserved(session):
    result = await consume_reservation(session, uuid.uuid4())
    assert result is None


async def test_release_reservation_frees_reserved_quantity_without_touching_quantity(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, quantity=10, product_id=product_id)
    order_id = uuid.uuid4()
    reservation = await try_reserve(session, order_id, [{"product_id": str(product_id), "quantity": 4}], TTL_SECONDS)
    await session.commit()

    await release_reservation(session, reservation)
    await session.commit()

    assert reservation.status == ReservationStatus.RELEASED
    await session.refresh(item)
    assert item.reserved_quantity == 0
    assert item.quantity == 10
