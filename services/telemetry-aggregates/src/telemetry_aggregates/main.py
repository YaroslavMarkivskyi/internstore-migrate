import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from telemetry_aggregates.backfill import run_backfill_loop
from telemetry_aggregates.config import Settings, load_settings
from telemetry_aggregates.consumers.telemetry_events import (
    GROUP_ID as TELEMETRY_EVENTS_GROUP_ID,
    TOPIC as TELEMETRY_EVENTS_TOPIC,
    make_dispatch as make_telemetry_events_dispatch,
)
from telemetry_aggregates.db import make_session_factory
from telemetry_aggregates.kafka import run_consumer_loop
from telemetry_aggregates.observability import setup_observability
from telemetry_aggregates.routers import aggregates


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    consumer_task = asyncio.create_task(
        run_consumer_loop(
            settings.kafka_bootstrap_servers,
            TELEMETRY_EVENTS_TOPIC,
            TELEMETRY_EVENTS_GROUP_ID,
            make_telemetry_events_dispatch(app.state.session_factory),
        )
    )
    backfill_task = asyncio.create_task(
        run_backfill_loop(
            app.state.session_factory,
            app.state.telemetry_session_factory,
            settings.backfill_interval_minutes,
        )
    )

    tasks = (consumer_task, backfill_task)
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_observability("telemetry-aggregates")

    app = FastAPI(title="telemetry-aggregates", lifespan=lifespan)
    FastAPIInstrumentor.instrument_app(app)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    # Connects as the telemetry_readonly Postgres role in real deployments
    # (see README's "Backfill job" section) — enforced at the DB level via
    # GRANT, not by anything in this client code; SQLite in tests has no
    # such concept, so this stays a plain session factory either way.
    app.state.telemetry_session_factory = make_session_factory(settings.telemetry_db_url)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(aggregates.router)

    return app
