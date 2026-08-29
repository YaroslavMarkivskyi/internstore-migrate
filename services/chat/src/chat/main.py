import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from chat.ai_assistant_client import AIAssistantClient
from chat.config import Settings, load_settings
from chat.db import make_session_factory
from chat.kafka import KafkaEventProducer
from chat.object_storage_client import ObjectStorageClient
from chat.observability import setup_observability
from chat.outbox_worker import run_outbox_worker
from chat.pubsub import PubSubRouter
from chat.redis_client import make_redis_client
from chat.routers import attachments, internal_messages, mode, rooms
from chat.ws import room as ws_room
from chat.ws_manager import WebSocketManager


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
        await app.state.pubsub.close()
        await app.state.redis.aclose()
        await producer.stop()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_observability("chat")

    app = FastAPI(title="chat", lifespan=lifespan)
    FastAPIInstrumentor.instrument_app(app)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.redis = make_redis_client(settings.redis_url)
    app.state.ws_manager = WebSocketManager()
    app.state.pubsub = PubSubRouter(app.state.redis, app.state.ws_manager)
    app.state.object_storage_client = ObjectStorageClient(
        endpoint=settings.object_storage_endpoint,
        public_base_url=settings.object_storage_public_base_url,
        access_key=settings.object_storage_access_key,
        secret_key=settings.object_storage_secret_key,
        bucket=settings.object_storage_bucket,
        key_prefix=settings.object_storage_key_prefix,
        presigned_url_ttl_seconds=settings.object_storage_presigned_url_ttl_seconds,
    )
    # One id per process, used as the member value in the
    # chat:{room_id}:connections presence set — not tied to any external
    # identity, just a way to tell instances apart.
    app.state.instance_id = str(uuid.uuid4())
    app.state.admin_local_refcounts = {}
    app.state.ai_assistant_client = AIAssistantClient(settings.ai_assistant_service_url, 10.0)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(rooms.router)
    app.include_router(attachments.router)
    app.include_router(mode.router)
    app.include_router(internal_messages.router)
    app.include_router(ws_room.router)

    return app
