import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from telemetry.models import Store


async def get_or_create_store(session: AsyncSession, store_id: uuid.UUID) -> Store:
    """Telemetry's `stores.id` is always Inventory's `Stock.id` — there is
    no separate "store created" event to sync from, so a row here is
    lazily upserted the first time Telemetry sees a given store_id, via
    either `POST /measurements` or an inventory-events message. `name`
    defaults to the id itself until an admin renames it via
    `PATCH /stores/{id}`."""
    store = await session.get(Store, store_id)
    if store is None:
        store = Store(id=store_id, name=str(store_id))
        session.add(store)
        await session.flush()
    return store
