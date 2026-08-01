import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from inventory.config import Settings, load_settings
from inventory.consumers.order_events import GROUP_ID, TOPIC as ORDER_EVENTS_TOPIC, make_dispatch
from inventory.db import make_session_factory
from inventory.kafka import KafkaEventProducer, run_consumer_loop
from inventory.outbox_worker import run_outbox_worker
from inventory.reservation_expiry import run_reservation_expiry_checker
from inventory.routers import items, stocks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    producer = KafkaEventProducer(settings.kafka_bootstrap_servers)
    await producer.start()
    app.state.kafka_producer = producer

    outbox_task = asyncio.create_task(
        # Poll interval reuses the reservation-check cadence — no separate
        # setting needed for this dev-scale project.
        run_outbox_worker(app.state.session_factory, producer, settings.reservation_check_interval_seconds)
    )
    consumer_task = asyncio.create_task(
        run_consumer_loop(
            settings.kafka_bootstrap_servers,
            ORDER_EVENTS_TOPIC,
            GROUP_ID,
            make_dispatch(app.state.session_factory, settings.reservation_ttl_seconds),
        )
    )
    expiry_task = asyncio.create_task(
        run_reservation_expiry_checker(app.state.session_factory, settings.reservation_check_interval_seconds)
    )

    try:
        yield
    finally:
        for task in (outbox_task, consumer_task, expiry_task):
            task.cancel()
        await asyncio.gather(outbox_task, consumer_task, expiry_task, return_exceptions=True)
        await producer.stop()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="inventory", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(stocks.router)
    app.include_router(items.router)

    return app
