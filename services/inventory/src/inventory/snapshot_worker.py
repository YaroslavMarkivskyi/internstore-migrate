import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from inventory.snapshots import find_aggregates_needing_snapshot, take_snapshot


async def take_pending_snapshots(session_factory: async_sessionmaker) -> int:
    async with session_factory() as session:
        aggregate_ids = await find_aggregates_needing_snapshot(session)
        for aggregate_id in aggregate_ids:
            await take_snapshot(session, aggregate_id)
        await session.commit()
        return len(aggregate_ids)


async def run_snapshot_worker(session_factory: async_sessionmaker, poll_interval: float) -> None:
    """Same lifespan-task shape as outbox_worker.run_outbox_worker /
    reservation_expiry.run_reservation_expiry_checker: a background
    asyncio.Task, cancelled on shutdown. Not on the hot path -- see
    snapshots.py's module docstring for why this can lag without
    affecting reservation correctness."""
    try:
        while True:
            await take_pending_snapshots(session_factory)
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        raise
