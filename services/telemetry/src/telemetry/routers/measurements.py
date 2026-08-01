from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from telemetry.db import get_session
from telemetry.models import TemperatureReading
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
    await session.commit()
    await session.refresh(reading)
    return reading
