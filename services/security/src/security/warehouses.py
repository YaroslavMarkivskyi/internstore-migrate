import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from security.models import Warehouse


async def get_or_create_warehouse(session: AsyncSession, warehouse_id: uuid.UUID) -> Warehouse:
    """Security's `warehouses.id` is always Inventory's `Stock.id` — there
    is no "warehouse created" sync from Inventory, so a row here is lazily
    upserted the first time an auth attempt names a given id. `name`
    defaults to the id itself until an admin renames it via
    `PATCH /warehouses/{id}` — same pattern as Telemetry's
    `stores.get_or_create_store`."""
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        warehouse = Warehouse(id=warehouse_id, name=str(warehouse_id))
        session.add(warehouse)
        await session.flush()
    return warehouse
