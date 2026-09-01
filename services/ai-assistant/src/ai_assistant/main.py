import asyncio
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from ai_assistant.adk.agents import (
    OPS_AGENT_NAME,
    SHOPPING_AGENT_NAME,
    build_ops_agent,
    build_shopping_agent,
    close_toolsets,
)
from ai_assistant.adk.prompts import ADMIN_FALLBACK_REPLY, FALLBACK_REPLY
from ai_assistant.adk.session import prepare_session, viewing_context_note
from ai_assistant.adk.streaming import Reset, run_agent_stream
from ai_assistant.adk.token_context import make_header_provider, reset_request_token, set_request_token
from ai_assistant.agent import RATE_LIMIT_MESSAGE, check_and_increment_rate_limit, get_mode
from ai_assistant.auth import InternalClaims, get_raw_internal_token, verify_internal_token
from ai_assistant.auth_backend_client import AuthBackendClient
from ai_assistant.chat_client import ChatClient
from ai_assistant.config import Settings, load_settings
from ai_assistant.consumers import catalog_events, chat_events
from ai_assistant.db import make_session_factory
from ai_assistant.kafka import run_consumer_loop
from ai_assistant.observability import setup_observability
from ai_assistant.orders_client import OrdersClient
from ai_assistant.redis_client import make_redis_client

# Batch streamed deltas up to roughly this many characters before pushing
# one to Chat — the model streams word-by-word, and one HTTP round trip per
# word through Chat's gate is needless chatter for no perceptible UX gain.
_DELTA_FLUSH_CHARS = 40

APP_NAME = "ai-assistant"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    chat_dispatch = chat_events.make_dispatch(
        session_factory=app.state.session_factory,
        redis=app.state.redis,
        genai_client=app.state.genai_client,
        chat_client=app.state.chat_client,
        orders_client=app.state.orders_client,
        settings=settings,
    )
    catalog_dispatch = catalog_events.make_dispatch(
        app.state.session_factory, app.state.genai_client, settings.embedding_model, settings.embedding_dimensions
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
        await close_toolsets(app.state.shopping_agent)
        await close_toolsets(app.state.ops_agent)
        await app.state.redis.aclose()


class ShoppingAgentRequest(BaseModel):
    room_id: str
    sender_id: str
    message: str
    # The product / category page the customer had open when they sent this,
    # if any — lets the agent resolve "this" / "here" without them naming it.
    # UUID strings; Chat validates the shape before forwarding (see
    # chat/ws/room.py), so a client can't smuggle prose into the prompt
    # through these fields.
    viewing_product_id: str | None = None
    viewing_category_id: str | None = None


class AdminAgentRequest(BaseModel):
    room_id: str
    sender_id: str
    message: str


async def _stream_agent_reply(chat_client, room_id: str, events) -> None:
    """Drain a react_loop stream into Chat: batched `message_delta` frames,
    a `message_reset` on Reset, one persisted `message_done` at the end."""
    stream_id = str(uuid.uuid4())
    full: list[str] = []
    pending: list[str] = []

    async def _flush() -> None:
        if pending:
            await chat_client.stream_delta(room_id, stream_id, "".join(pending))
            pending.clear()

    async for event in events:
        if isinstance(event, Reset):
            full.clear()
            pending.clear()
            await chat_client.stream_reset(room_id, stream_id)
            continue
        full.append(event.text)
        pending.append(event.text)
        if sum(len(part) for part in pending) >= _DELTA_FLUSH_CHARS:
            await _flush()

    await _flush()
    await chat_client.stream_done(room_id, stream_id, "".join(full))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_observability("ai-assistant")

    app = FastAPI(title="ai-assistant", lifespan=lifespan)
    FastAPIInstrumentor.instrument_app(app)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.redis = make_redis_client(settings.redis_url)
    # STR-161b: `enterprise=True` targets the Gemini Enterprise Agent
    # Platform (Vertex AI's Cloud Next 2026 rebrand) rather than the Gemini
    # Developer API — auth is IAM/Workload Identity via ADC, no API key.
    # `vertexai=True` is still accepted as an alias by the SDK but
    # `enterprise` is the current name post-rebrand.
    app.state.genai_client = genai.Client(
        enterprise=True, project=settings.gcp_project, location=settings.gcp_location
    )
    app.state.chat_client = ChatClient(settings.chat_service_url, 10.0, settings.internal_token_secret)
    app.state.orders_client = OrdersClient(settings.orders_service_url, 10.0, settings.internal_token_secret)
    app.state.auth_backend_client = AuthBackendClient(settings.auth_backend_url, 10.0)

    # ADK talks to Gemini through google-genai; point it at the same Vertex
    # project/location as app.state.genai_client (ADC auth, no key).
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.gcp_project)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.gcp_location)

    # The shopping + ops agents (ADK LlmAgent). Their tools are the MCP
    # Gateway's, reached over the real MCP protocol; the header provider mints
    # a fresh X-Internal-Token per MCP session from the ContextVar the agent
    # endpoints set (see adk/token_context.py).
    header_provider = make_header_provider(
        app.state.auth_backend_client, settings.token_refresh_margin_seconds
    )
    app.state.shopping_agent = build_shopping_agent(
        model=settings.chat_model, mcp_gateway_url=settings.mcp_gateway_url, header_provider=header_provider
    )
    app.state.ops_agent = build_ops_agent(
        model=settings.chat_model, mcp_gateway_url=settings.mcp_gateway_url, header_provider=header_provider
    )
    app.state.adk_session_service = InMemorySessionService()
    app.state.shopping_runner = Runner(
        app_name=APP_NAME, agent=app.state.shopping_agent, session_service=app.state.adk_session_service
    )
    app.state.ops_runner = Runner(
        app_name=APP_NAME, agent=app.state.ops_agent, session_service=app.state.adk_session_service
    )

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

        # STR-148: without this, every message was handled as a completely
        # isolated turn — see react_loop.py's own docstring for the bug
        # this caused ("add it to my cart" right after a search had no
        # antecedent for "it"), found via live verification, not any unit
        # test (they all mock a single self-contained turn).
        history = await app.state.chat_client.get_recent_messages(
            payload.room_id, settings.conversation_history_limit
        )

        session = await prepare_session(
            app.state.adk_session_service,
            app_name=APP_NAME,
            user_id=claims.sub,
            agent_name=SHOPPING_AGENT_NAME,
            history=history,
            context_note=viewing_context_note(
                viewing_product_id=payload.viewing_product_id,
                viewing_category_id=payload.viewing_category_id,
            ),
        )

        # Stream the reply to Chat (and on to the customer's WebSocket) as the
        # model produces it — see _stream_agent_reply.
        token_handle = set_request_token(token)
        try:
            await _stream_agent_reply(
                app.state.chat_client,
                payload.room_id,
                run_agent_stream(
                    app.state.shopping_runner,
                    user_id=claims.sub,
                    session_id=session.id,
                    message=payload.message,
                    author=SHOPPING_AGENT_NAME,
                    max_llm_calls=settings.max_react_iterations * 2,
                    fallback_reply=FALLBACK_REPLY,
                ),
            )
        finally:
            reset_request_token(token_handle)
        return {"status": "ok"}

    # STR-XXX: the internal ops assistant. Called by Chat (ws/room.py) only
    # when an admin sends a message in their own ops room (room_ops_<sub>),
    # forwarding the admin's own internal token. Read-only tools only (see
    # react_loop.ADMIN_TOOL_NAMES); this handler independently rejects any
    # non-admin token as a fail-closed second check.
    @app.post("/agent/admin")
    async def admin_agent(
        payload: AdminAgentRequest,
        token: Annotated[str, Depends(get_raw_internal_token)],
    ) -> dict[str, str]:
        try:
            claims: InternalClaims = verify_internal_token(token, settings.internal_token_secret)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid internal token") from exc

        if claims.role != "admin":
            raise HTTPException(status_code=403, detail="Ops assistant is admin-only")
        if claims.sub != payload.sender_id:
            logger.warning("Ops assistant token/sender_id mismatch for room %s", payload.room_id)
            raise HTTPException(status_code=401, detail="Token does not match sender_id")

        history = await app.state.chat_client.get_recent_messages(
            payload.room_id, settings.conversation_history_limit
        )
        session = await prepare_session(
            app.state.adk_session_service,
            app_name=APP_NAME,
            user_id=claims.sub,
            agent_name=OPS_AGENT_NAME,
            history=history,
        )
        token_handle = set_request_token(token)
        try:
            await _stream_agent_reply(
                app.state.chat_client,
                payload.room_id,
                run_agent_stream(
                    app.state.ops_runner,
                    user_id=claims.sub,
                    session_id=session.id,
                    message=payload.message,
                    author=OPS_AGENT_NAME,
                    max_llm_calls=settings.max_react_iterations * 2,
                    fallback_reply=ADMIN_FALLBACK_REPLY,
                ),
            )
        finally:
            reset_request_token(token_handle)
        return {"status": "ok"}

    return app
