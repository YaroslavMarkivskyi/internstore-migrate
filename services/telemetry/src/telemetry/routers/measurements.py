from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from telemetry.db import get_session
from telemetry.models import StoreProductThreshold, TemperatureReading
from telemetry.outbox import add_outbox_event
from telemetry.schemas import MeasurementCreate, MeasurementRead
from telemetry.stores import get_or_create_store

router = APIRouter(prefix="/measurements", tags=["measurements"])


@router.post("", response_model=MeasurementRead, status_code=201)
async def create_measurement(
    payload: MeasurementCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TemperatureReading:
    # No auth dependency: called directly by the telemetry-simulator
    # container, not through a logged-in admin session — same trust model
    # as Inventory's check-availability (open within the docker network,
    # Gateway-routed like every other service's endpoints).
    await get_or_create_store(session, payload.store_id)

    reading = TemperatureReading(
        store_id=payload.store_id,
        temperature=payload.temperature,
        humidity=payload.humidity,
    )
    session.add(reading)
    await session.flush()

    # STR-147: this endpoint only ever carries {store_id, temperature,
    # humidity} — product association happens elsewhere, via
    # store_product_thresholds (see violations.py's own {store, product}
    # loop). A single reading is therefore not tied to one product; it
    # applies to every product this store currently tracks, so we stage one
    # TemperatureRecorded event per {store_id, product_id} pair. A store
    # tracking no products yet (no ItemAdded seen) stages nothing — nothing
    # in telemetry-aggregates' hourly_aggregates PK works without a
    # product_id, so there's no meaningful event to emit yet.
    product_ids = (
        await session.execute(
            select(StoreProductThreshold.product_id).where(StoreProductThreshold.store_id == payload.store_id)
        )
    ).scalars().all()
    for product_id in product_ids:
        add_outbox_event(
            session,
            "TemperatureRecorded",
            {
                "store_id": str(payload.store_id),
                "product_id": str(product_id),
                "temperature": float(reading.temperature),
                "humidity": float(reading.humidity) if reading.humidity is not None else None,
                "recorded_at": reading.recorded_at.isoformat(),
            },
        )

    await session.commit()
    await session.refresh(reading)
    return reading
