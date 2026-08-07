import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from notifications.config import Settings, load_settings
from notifications.consumers.handlers import make_dispatch
from notifications.dedup import DedupCache
from notifications.kafka import run_consumer_loop
from notifications.mailer import Mailer

# One topic per bounded context (see docs/EVENT_BROKER.md) — dispatch keys
# off event_type, not topic, so a topic with no producer yet
# (telemetry-events, chat-events) just never yields a message. That's the
# "gracefully idle" behavior this service needs until Telemetry/Chat exist.
# ops-events (STR-139) is checkout-workflow's escalation channel — same
# "gracefully idle" reasoning applies until a workflow actually escalates.
TOPICS = ["order-events", "inventory-events", "telemetry-events", "chat-events", "ops-events"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    mailer = Mailer(settings.smtp_host, settings.smtp_port, settings.smtp_from_address)
    dedup = DedupCache(settings.dedup_ttl_seconds, settings.dedup_max_size)
    dispatch = make_dispatch(mailer, dedup)

    # A distinct group per topic — not one shared group across all four —
    # so each topic's consumer rebalances independently instead of a
    # restart/rebalance on one topic's consumer perturbing the others.
    tasks = [
        asyncio.create_task(
            run_consumer_loop(settings.kafka_bootstrap_servers, topic, f"notifications-{topic}", dispatch)
        )
        for topic in TOPICS
    ]

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="notifications", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
