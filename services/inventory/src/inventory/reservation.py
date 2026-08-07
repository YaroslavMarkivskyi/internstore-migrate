import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.models import Reservation, ReservationItem, ReservationStatus, StockItem


async def try_reserve(
    session: AsyncSession,
    order_id: uuid.UUID,
    items: list[dict],
    ttl_seconds: float,
) -> Reservation | None:
    """Attempts to reserve all requested (product_id, quantity) pairs across
    however many StockItem rows a product is split over (same multi-stock
    summing `check-availability` already does). All-or-nothing: if any
    product can't be fully covered, no `reserved_quantity` is touched and
    no rows are created — caller should not commit in that case.

    Single-partition topics (see ADR 0002) mean only one consumer instance
    ever processes order-events at a time, so there's no concurrent writer
    to race against here.
    """
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

    reservation = Reservation(
        order_id=order_id,
        status=ReservationStatus.RESERVED,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
    )
    session.add(reservation)
    await session.flush()  # populate reservation.id for the ReservationItem FK

    for stock_item, quantity in allocations:
        stock_item.reserved_quantity += quantity
        session.add(ReservationItem(reservation_id=reservation.id, stock_item_id=stock_item.id, quantity=quantity))

    return reservation


async def consume_reservation(session: AsyncSession, order_id: uuid.UUID) -> tuple[Reservation, list[uuid.UUID]] | None:
    """PaymentConfirmed: final decrement. Returns None (no-op) if there's no
    RESERVED reservation for this order — already consumed/released, so a
    redelivered PaymentConfirmed doesn't double-decrement. The returned
    product_ids are every product this decrement touched, for the caller to
    check against Catalog (see stock_sync.unpublish_if_out_of_stock) once
    this commits -- a product hitting zero stock across every stock is
    exactly what "consuming the last unit" looks like."""
    result = await session.execute(
        select(Reservation).where(Reservation.order_id == order_id, Reservation.status == ReservationStatus.RESERVED)
    )
    reservation = result.scalar_one_or_none()
    if reservation is None:
        return None

    await session.refresh(reservation, attribute_names=["items"])
    product_ids: set[uuid.UUID] = set()
    for reservation_item in reservation.items:
        stock_item = await session.get(StockItem, reservation_item.stock_item_id)
        stock_item.reserved_quantity -= reservation_item.quantity
        stock_item.quantity -= reservation_item.quantity
        product_ids.add(stock_item.product_id)

    reservation.status = ReservationStatus.CONSUMED
    return reservation, list(product_ids)


async def release_reservation(session: AsyncSession, reservation: Reservation) -> None:
    """TTL expiry: frees `reserved_quantity` without ever touching `quantity`
    — the stock was never actually removed, just held."""
    await session.refresh(reservation, attribute_names=["items"])
    for reservation_item in reservation.items:
        stock_item = await session.get(StockItem, reservation_item.stock_item_id)
        stock_item.reserved_quantity -= reservation_item.quantity

    reservation.status = ReservationStatus.RELEASED
