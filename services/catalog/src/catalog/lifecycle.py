"""Application wiring and start/stop logic, kept out of main.py so the entry
point stays a table of contents.

* build_state -- construct the long-lived clients and hang them off app.state
  (synchronous, runs inside create_app so tests get a fully wired app).
* startup / shutdown -- the async half: the boot-time dependency check, the
  Kafka producer, and the outbox worker task.
"""

import asyncio
import logging

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from catalog.config import Settings
from catalog.db import make_session_factory
from catalog.inventory_client import InventoryClient
from catalog.kafka import KafkaEventProducer
from catalog.object_storage_client import ObjectStorageClient
from catalog.outbox_worker import run_outbox_worker

logger = logging.getLogger(__name__)

# Bounds a single "is the database there?" probe -- both the fail-fast boot
# check and the /ready endpoint. Short enough that an unreachable host fails
# the pod quickly instead of hanging.
_DB_PROBE_TIMEOUT_SECONDS = 5.0


async def ping_database(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=_DB_PROBE_TIMEOUT_SECONDS)


def build_state(app: FastAPI, settings: Settings) -> None:
    FastAPIInstrumentor.instrument_app(app)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.object_storage_client = ObjectStorageClient(
        endpoint=settings.object_storage_endpoint,
        public_base_url=settings.object_storage_public_base_url,
        access_key=settings.object_storage_access_key,
        secret_key=settings.object_storage_secret_key,
        bucket=settings.object_storage_bucket,
        key_prefix=settings.object_storage_key_prefix,
        presigned_url_ttl_seconds=settings.object_storage_presigned_url_ttl_seconds,
    )
    app.state.inventory_client = InventoryClient(settings.inventory_base_url, settings.inventory_timeout_seconds)
    app.state.kafka_producer = None
    app.state.outbox_task = None


def _on_outbox_worker_done(task: asyncio.Task[None]) -> None:
    """The outbox worker should only ever stop by being cancelled at shutdown.
    Anything else means it died and events have silently stopped publishing."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("outbox worker exited unexpectedly", exc_info=exc)


async def startup(app: FastAPI) -> None:
    settings: Settings = app.state.settings

    # Fail fast (12-factor): if a backing service is unreachable at boot, crash
    # and let the orchestrator restart us rather than serve broken traffic.
    await ping_database(app.state.session_factory)

    producer = KafkaEventProducer(settings.kafka_bootstrap_servers)
    await producer.start()
    app.state.kafka_producer = producer

    task = asyncio.create_task(
        run_outbox_worker(app.state.session_factory, producer, settings.outbox_poll_interval_seconds)
    )
    task.add_done_callback(_on_outbox_worker_done)
    app.state.outbox_task = task


async def shutdown(app: FastAPI) -> None:
    task: asyncio.Task[None] | None = app.state.outbox_task
    if task is not None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    producer: KafkaEventProducer | None = app.state.kafka_producer
    if producer is not None:
        await producer.stop()
