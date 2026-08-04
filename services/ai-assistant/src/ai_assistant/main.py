import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI

from ai_assistant.chat_client import ChatClient
from ai_assistant.config import Settings, load_settings
from ai_assistant.consumers import catalog_events, chat_events
from ai_assistant.db import make_session_factory
from ai_assistant.kafka import run_consumer_loop
from ai_assistant.orders_client import OrdersClient
from ai_assistant.redis_client import make_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    chat_dispatch = chat_events.make_dispatch(
        session_factory=app.state.session_factory,
        redis=app.state.redis,
        openai_client=app.state.openai_client,
        chat_client=app.state.chat_client,
        orders_client=app.state.orders_client,
        settings=settings,
    )
    catalog_dispatch = catalog_events.make_dispatch(
        app.state.session_factory, app.state.openai_client, settings.embedding_model
    )

    # Distinct consumer groups per topic — a rebalance/restart on one
    # doesn't perturb the other, same pattern as Notifications.
    tasks = [
        asyncio.create_task(
            run_consumer_loop(
                settings.kafka_bootstrap_servers, chat_events.TOPIC, chat_events.GROUP_ID, chat_dispatch
            )
        ),
        asyncio.create_task(
            run_consumer_loop(
                settings.kafka_bootstrap_servers, catalog_events.TOPIC, catalog_events.GROUP_ID, catalog_dispatch
            )
        ),
    ]

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await app.state.redis.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="ai-assistant", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.redis = make_redis_client(settings.redis_url)
    app.state.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    app.state.chat_client = ChatClient(settings.chat_service_url, 10.0, settings.internal_token_secret)
    app.state.orders_client = OrdersClient(settings.orders_service_url, 10.0, settings.internal_token_secret)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
