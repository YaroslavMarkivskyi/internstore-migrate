import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from telemetry.config import Settings, load_settings
from telemetry.consumers.catalog_events import (
    GROUP_ID as CATALOG_EVENTS_GROUP_ID,
    TOPIC as CATALOG_EVENTS_TOPIC,
    make_dispatch as make_catalog_dispatch,
)
from telemetry.consumers.inventory_events import (
    GROUP_ID as INVENTORY_EVENTS_GROUP_ID,
    TOPIC as INVENTORY_EVENTS_TOPIC,
    make_dispatch as make_inventory_dispatch,
)
from telemetry.db import make_session_factory
from telemetry.kafka import KafkaEventProducer, run_consumer_loop
from telemetry.observability import setup_observability
from telemetry.outbox_worker import run_outbox_worker
from telemetry.routers import measurements, stores
from telemetry.violations import run_violation_checker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    producer = KafkaEventProducer(settings.kafka_bootstrap_servers)
    await producer.start()
    app.state.kafka_producer = producer

    outbox_task = asyncio.create_task(
        run_outbox_worker(app.state.session_factory, producer, settings.outbox_poll_interval_seconds)
    )
    catalog_consumer_task = asyncio.create_task(
        run_consumer_loop(
            settings.kafka_bootstrap_servers,
            CATALOG_EVENTS_TOPIC,
            CATALOG_EVENTS_GROUP_ID,
            make_catalog_dispatch(app.state.session_factory),
        )
    )
    inventory_consumer_task = asyncio.create_task(
        run_consumer_loop(
            settings.kafka_bootstrap_servers,
            INVENTORY_EVENTS_TOPIC,
            INVENTORY_EVENTS_GROUP_ID,
            make_inventory_dispatch(app.state.session_factory),
        )
    )
    violation_task = asyncio.create_task(
        run_violation_checker(
            app.state.session_factory,
            settings.violation_check_interval_seconds,
            window=timedelta(seconds=settings.violation_window_seconds),
        )
    )

    tasks = (outbox_task, catalog_consumer_task, inventory_consumer_task, violation_task)
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await producer.stop()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_observability("telemetry")

    app = FastAPI(title="telemetry", lifespan=lifespan)
    FastAPIInstrumentor.instrument_app(app)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(measurements.router)
    app.include_router(stores.router)

    return app
