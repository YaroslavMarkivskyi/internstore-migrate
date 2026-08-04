import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orders.catalog_client import CatalogClient
from orders.config import Settings, load_settings
from orders.consumers.inventory_events import GROUP_ID, TOPIC as INVENTORY_EVENTS_TOPIC, make_dispatch
from orders.db import make_session_factory
from orders.inventory_client import InventoryClient
from orders.kafka import KafkaEventProducer, run_consumer_loop
from orders.outbox_worker import run_outbox_worker
from orders.routers import cart, checkout, orders, orders_admin, pay, payments
from orders.stripe_client import StripeClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    producer = KafkaEventProducer(settings.kafka_bootstrap_servers)
    await producer.start()
    app.state.kafka_producer = producer

    outbox_task = asyncio.create_task(
        run_outbox_worker(app.state.session_factory, producer, settings.outbox_poll_interval_seconds)
    )
    consumer_task = asyncio.create_task(
        run_consumer_loop(
            settings.kafka_bootstrap_servers,
            INVENTORY_EVENTS_TOPIC,
            GROUP_ID,
            make_dispatch(app.state.session_factory),
        )
    )

    try:
        yield
    finally:
        for task in (outbox_task, consumer_task):
            task.cancel()
        await asyncio.gather(outbox_task, consumer_task, return_exceptions=True)
        await producer.stop()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="orders", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.inventory_client = InventoryClient(settings.inventory_base_url, settings.inventory_timeout_seconds)
    app.state.catalog_client = CatalogClient(settings.catalog_base_url, settings.catalog_timeout_seconds)
    app.state.stripe_client = StripeClient(settings.stripe_secret_key, settings.stripe_webhook_secret)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(cart.router)
    app.include_router(checkout.router)
    app.include_router(orders_admin.router)
    app.include_router(orders.router)
    app.include_router(pay.router)
    app.include_router(payments.router)
    app.include_router(payments.webhook_router)

    return app
