import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.models import OutboxEvent, Reservation, ReservationItem, ReservationStatus, Stock, StockItem
from inventory.reservation_expiry import expire_reservations


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def _make_reservation(session: AsyncSession, expires_at: datetime, quantity: int = 3) -> tuple[Reservation, StockItem]:
    stock = Stock(name=f"Warehouse {uuid.uuid4()}")
    session.add(stock)
    await session.flush()
    item = StockItem(stock_id=stock.id, product_id=uuid.uuid4(), quantity=10, reserved_quantity=quantity)
    session.add(item)
    await session.flush()

    reservation = Reservation(order_id=uuid.uuid4(), status=ReservationStatus.RESERVED, expires_at=expires_at)
    session.add(reservation)
    await session.flush()
    session.add(ReservationItem(reservation_id=reservation.id, stock_item_id=item.id, quantity=quantity))
    await session.commit()
    return reservation, item


async def test_expired_reservation_is_released_and_publishes_reservation_expired(session):
    reservation, item = await _make_reservation(session, datetime.now(timezone.utc) - timedelta(seconds=1))

    count = await expire_reservations(session)
    await session.commit()

    assert count == 1
    await session.refresh(reservation)
    await session.refresh(item)
    assert reservation.status == ReservationStatus.RELEASED
    assert item.reserved_quantity == 0

    outbox = (await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "ReservationExpired"))).scalars().all()
    assert len(outbox) == 1
    assert outbox[0].payload["order_id"] == str(reservation.order_id)


async def test_non_expired_reservation_is_left_alone(session):
    reservation, item = await _make_reservation(session, datetime.now(timezone.utc) + timedelta(hours=1))

    count = await expire_reservations(session)
    await session.commit()

    assert count == 0
    await session.refresh(reservation)
    await session.refresh(item)
    assert reservation.status == ReservationStatus.RESERVED
    assert item.reserved_quantity == 3
