import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel

from ai_assistant.agent import RATE_LIMIT_MESSAGE, check_and_increment_rate_limit, get_mode
from ai_assistant.auth import InternalClaims, get_raw_internal_token, verify_internal_token
from ai_assistant.auth_backend_client import AuthBackendClient
from ai_assistant.chat_client import ChatClient
from ai_assistant.config import Settings, load_settings
from ai_assistant.consumers import catalog_events, chat_events
from ai_assistant.db import make_session_factory
from ai_assistant.kafka import run_consumer_loop
from ai_assistant.mcp_client import MCPGatewayClient
from ai_assistant.orders_client import OrdersClient
from ai_assistant.react_loop import run_shopping_agent
from ai_assistant.redis_client import make_redis_client
from ai_assistant.token_manager import RefreshableToken

logger = logging.getLogger(__name__)


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


class ShoppingAgentRequest(BaseModel):
    room_id: str
    sender_id: str
    message: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="ai-assistant", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.redis = make_redis_client(settings.redis_url)
    app.state.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    app.state.chat_client = ChatClient(settings.chat_service_url, 10.0, settings.internal_token_secret)
    app.state.orders_client = OrdersClient(settings.orders_service_url, 10.0, settings.internal_token_secret)
    # STR-146: this service's first actual MCP Gateway caller, and its first
    # caller of auth-backend's refresh path — both only ever exercised by
    # POST /agent/shopping below.
    app.state.mcp_client = MCPGatewayClient(settings.mcp_gateway_url, 10.0)
    app.state.auth_backend_client = AuthBackendClient(settings.auth_backend_url, 10.0)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # STR-146: this service's only real inbound REST route. Called
    # synchronously by Chat (see services/chat/src/chat/ws/room.py) with the
    # customer's own internal-token forwarded in X-Internal-Token — not via
    # the chat-events Kafka topic, which has no token to carry (see
    # chat_events.py's own guard skipping registered customers). Guests
    # never reach this: Chat only calls it for role=="customer" senders, and
    # this endpoint independently rejects anything else below as a second,
    # fail-closed check.
    @app.post("/agent/shopping")
    async def shopping_agent(
        payload: ShoppingAgentRequest,
        token: Annotated[str, Depends(get_raw_internal_token)],
    ) -> dict[str, str]:
        try:
            claims: InternalClaims = verify_internal_token(token, settings.internal_token_secret)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid internal token") from exc

        if claims.role != "customer":
            raise HTTPException(status_code=403, detail="Shopping agent is customer-only")
        if claims.sub != payload.sender_id:
            # Chat sends sender_id alongside the token as a sanity check —
            # the token's own sub is what actually governs cart ownership
            # downstream, this just catches a mismatched/stale caller early
            # with a clearer error than a confusing cart result later.
            logger.warning("Shopping agent token/sender_id mismatch for room %s", payload.room_id)
            raise HTTPException(status_code=401, detail="Token does not match sender_id")

        redis = app.state.redis
        mode = await get_mode(redis, payload.room_id, settings.ai_mode_default)
        if mode != "ai":
            return {"status": "skipped"}

        within_budget = await check_and_increment_rate_limit(
            redis, payload.room_id, settings.ai_rate_limit, settings.ai_rate_limit_window_seconds
        )
        if not within_budget:
            await app.state.chat_client.post_message(payload.room_id, RATE_LIMIT_MESSAGE)
            await app.state.chat_client.set_mode(payload.room_id, "human")
            return {"status": "rate_limited"}

        reply = await run_shopping_agent(
            openai_client=app.state.openai_client,
            mcp_client=app.state.mcp_client,
            auth_backend_client=app.state.auth_backend_client,
            chat_model=settings.chat_model,
            message=payload.message,
            token=RefreshableToken(token),
            max_iterations=settings.max_react_iterations,
            refresh_margin_seconds=settings.token_refresh_margin_seconds,
        )
        await app.state.chat_client.post_message(payload.room_id, reply)
        return {"status": "ok"}

    return app
