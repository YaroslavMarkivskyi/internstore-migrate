import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from telemetry.auth import require_admin
from telemetry.db import get_session
from telemetry.models import Incident, Store, TemperatureReading
from telemetry.schemas import IncidentRead, MeasurementRead, StoreRead, StoreUpdate

router = APIRouter(prefix="/stores", tags=["stores"])

Period = Literal["week", "month", "3months", "all"]

PERIOD_DELTAS: dict[str, timedelta] = {
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
    "3months": timedelta(days=90),
}

OPEN_VIOLATION_WINDOW = timedelta(hours=1)


async def _get_store_or_404(session: AsyncSession, store_id: uuid.UUID) -> Store:
    store = await session.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("", response_model=list[StoreRead])
async def list_stores(session: Annotated[AsyncSession, Depends(get_session)]) -> list[StoreRead]:
    stores = list((await session.execute(select(Store).order_by(Store.name))).scalars().all())
    window_start = datetime.now(timezone.utc) - OPEN_VIOLATION_WINDOW

    results: list[StoreRead] = []
    for store in stores:
        latest_temperature = (
            await session.execute(
                select(TemperatureReading.temperature)
                .where(TemperatureReading.store_id == store.id)
                .order_by(TemperatureReading.recorded_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        has_open_violation = (
            await session.execute(
                select(Incident.id)
                .where(Incident.store_id == store.id, Incident.started_at >= window_start)
                .limit(1)
            )
        ).scalar_one_or_none() is not None

        results.append(
            StoreRead(
                id=store.id,
                name=store.name,
                threshold_temp=store.threshold_temp,
                current_temperature=latest_temperature,
                has_open_violation=has_open_violation,
            )
        )

    return results


@router.patch("/{store_id}", response_model=StoreRead, dependencies=[Depends(require_admin)])
async def update_store(
    store_id: uuid.UUID,
    payload: StoreUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StoreRead:
    store = await _get_store_or_404(session, store_id)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(store, field, value)

    await session.commit()
    await session.refresh(store)
    return StoreRead(id=store.id, name=store.name, threshold_temp=store.threshold_temp)


@router.get("/{store_id}/readings", response_model=list[MeasurementRead], dependencies=[Depends(require_admin)])
async def list_readings(
    store_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    period: Period = "all",
) -> list[TemperatureReading]:
    await _get_store_or_404(session, store_id)

    stmt = select(TemperatureReading).where(TemperatureReading.store_id == store_id)
    delta = PERIOD_DELTAS.get(period)
    if delta is not None:
        stmt = stmt.where(TemperatureReading.recorded_at >= datetime.now(timezone.utc) - delta)
    stmt = stmt.order_by(TemperatureReading.recorded_at)

    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.delete("/{store_id}/readings", status_code=204, dependencies=[Depends(require_admin)])
async def delete_readings(
    store_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await _get_store_or_404(session, store_id)
    await session.execute(delete(TemperatureReading).where(TemperatureReading.store_id == store_id))
    await session.commit()


@router.get("/{store_id}/incidents", response_model=list[IncidentRead], dependencies=[Depends(require_admin)])
async def list_incidents(
    store_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Incident]:
    await _get_store_or_404(session, store_id)
    result = await session.execute(
        select(Incident).where(Incident.store_id == store_id).order_by(Incident.started_at)
    )
    return list(result.scalars().all())


@router.delete("/{store_id}/incidents/last", status_code=204, dependencies=[Depends(require_admin)])
async def delete_last_incident(
    store_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await _get_store_or_404(session, store_id)
    last = (
        await session.execute(
            select(Incident).where(Incident.store_id == store_id).order_by(Incident.started_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if last is not None:
        await session.delete(last)
        await session.commit()


@router.delete("/{store_id}/incidents", status_code=204, dependencies=[Depends(require_admin)])
async def delete_incidents(
    store_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await _get_store_or_404(session, store_id)
    await session.execute(delete(Incident).where(Incident.store_id == store_id))
    await session.commit()
