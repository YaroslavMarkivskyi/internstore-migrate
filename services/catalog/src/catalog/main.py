import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from catalog.config import Settings, load_settings
from catalog.db import make_session_factory
from catalog.inventory_client import InventoryClient
from catalog.kafka import KafkaEventProducer
from catalog.object_storage_client import ObjectStorageClient
from catalog.observability import setup_observability
from catalog.outbox_worker import run_outbox_worker
from catalog.routers import categories, product_images, products


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    producer = KafkaEventProducer(settings.kafka_bootstrap_servers)
    await producer.start()
    app.state.kafka_producer = producer

    outbox_task = asyncio.create_task(
        run_outbox_worker(app.state.session_factory, producer, settings.outbox_poll_interval_seconds)
    )

    try:
        yield
    finally:
        outbox_task.cancel()
        await asyncio.gather(outbox_task, return_exceptions=True)
        await producer.stop()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_observability("catalog")

    app = FastAPI(title="catalog", lifespan=lifespan)
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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(categories.router)
    app.include_router(products.router)
    app.include_router(product_images.router)

    return app
