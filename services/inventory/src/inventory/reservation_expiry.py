import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from inventory import commands
from inventory.models import Reservation, ReservationStatus


async def expire_reservations(session_factory: async_sessionmaker) -> int:
    async with session_factory() as session:
        result = await session.execute(
            select(Reservation.order_id).where(
                Reservation.status == ReservationStatus.RESERVED,
                Reservation.expires_at < datetime.now(timezone.utc),
            )
        )
        expired_order_ids = [row[0] for row in result.all()]

    count = 0
    for order_id in expired_order_ids:
        # extra_outbox_event lands in the SAME transaction as the
        # StockReleased event append + projection update (see
        # commands.build_release) -- preserves the outbox pattern's
        # guarantee that the notification and the domain change it
        # announces are durable together.
        status = await commands.release(
            session_factory, order_id, extra_outbox_event=("ReservationExpired", {"order_id": str(order_id)})
        )
        if status == "released":
            count += 1
    return count


async def run_reservation_expiry_checker(session_factory: async_sessionmaker, check_interval: float) -> None:
    try:
        while True:
            await expire_reservations(session_factory)
            await asyncio.sleep(check_interval)
    except asyncio.CancelledError:
        raise
