import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from telemetry_aggregates.auth import require_admin
from telemetry_aggregates.db import get_session
from telemetry_aggregates.models import HourlyAggregate
from telemetry_aggregates.schemas import HourlyAggregateRead

router = APIRouter(prefix="/aggregates", tags=["aggregates"])

Period = Literal["week", "month", "3months", "all"]

# Same period vocabulary as telemetry's GET /stores/{id}/readings — this
# endpoint is a net-new, directly-consumed replacement for chart/reporting
# queries over that period range, not a proxy target of telemetry's
# existing endpoint. See README's "API" section for that integration
# decision.
PERIOD_DELTAS: dict[str, timedelta] = {
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
    "3months": timedelta(days=90),
}


@router.get("/{store_id}/{product_id}", response_model=list[HourlyAggregateRead], dependencies=[Depends(require_admin)])
async def get_aggregates(
    store_id: uuid.UUID,
    product_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    period: Period = "all",
) -> list[HourlyAggregate]:
    stmt = select(HourlyAggregate).where(
        HourlyAggregate.store_id == store_id, HourlyAggregate.product_id == product_id
    )
    delta = PERIOD_DELTAS.get(period)
    if delta is not None:
        stmt = stmt.where(HourlyAggregate.hour_bucket >= datetime.now(timezone.utc) - delta)
    stmt = stmt.order_by(HourlyAggregate.hour_bucket)

    result = await session.execute(stmt)
    return list(result.scalars().all())
