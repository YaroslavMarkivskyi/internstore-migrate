import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inventory.models import Reservation, ReservationStatus
from inventory.outbox import add_outbox_event
from inventory.reservation import release_reservation


async def expire_reservations(session: AsyncSession) -> int:
    result = await session.execute(
        select(Reservation).where(
            Reservation.status == ReservationStatus.RESERVED,
            Reservation.expires_at < datetime.now(timezone.utc),
        )
    )
    reservations = list(result.scalars().all())
    for reservation in reservations:
        await release_reservation(session, reservation)
        add_outbox_event(session, "ReservationExpired", {"order_id": str(reservation.order_id)})
    return len(reservations)


async def run_reservation_expiry_checker(session_factory: async_sessionmaker, check_interval: float) -> None:
    try:
        while True:
            async with session_factory() as session:
                await expire_reservations(session)
                await session.commit()
            await asyncio.sleep(check_interval)
    except asyncio.CancelledError:
        raise
