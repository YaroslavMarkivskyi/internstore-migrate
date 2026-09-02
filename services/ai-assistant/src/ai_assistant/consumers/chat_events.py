import logging
from collections.abc import Awaitable, Callable

from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from redis.asyncio import Redis

from ai_assistant.adk.agents import GUEST_AGENT_NAME
from ai_assistant.adk.prompts import GUEST_FALLBACK_REPLY
from ai_assistant.adk.session import prepare_session
from ai_assistant.adk.streaming import run_agent_stream, stream_agent_reply
from ai_assistant.adk.token_context import reset_request_token, set_request_token
from ai_assistant.agent import RATE_LIMIT_MESSAGE, check_and_increment_rate_limit, get_mode
from ai_assistant.auth import mint_internal_token
from ai_assistant.chat_client import ChatClient
from ai_assistant.config import Settings

logger = logging.getLogger(__name__)

APP_NAME = "ai-assistant"
TOPIC = "chat-events"
GROUP_ID = "ai-assistant-chat-events"

Dispatch = Callable[[dict], Awaitable[None]]


async def handle_customer_message_sent(
    *,
    redis: Redis,
    session_service: BaseSessionService,
    guest_runner: Runner,
    chat_client: ChatClient,
    settings: Settings,
    payload: dict,
) -> None:
    room_id = payload["room_id"]
    sender_id = payload["sender_id"]
    # STR-148: this used to be guessed from sender_id's shape
    # (is_registered_customer) — broken, since guest session ids are
    # uuid4() same as a real customer's Firebase sub, so it misclassified
    # every guest as a customer and silently starved guests of any reply
    # at all (see chat/ws/room.py's staging of this field for the fuller
    # story). sender_role now comes straight from the event payload.
    sender_role = payload.get("sender_role")
    content = payload.get("content")
    if not content:
        return

    # STR-146: registered customers are handled synchronously instead, via
    # Chat calling POST /agent/shopping directly with the customer's own
    # internal-token (see main.py) — that's the only path that can propagate
    # a real per-customer identity into a cart-mutating tool call. This
    # Kafka-driven consumer has no inbound token to forward and keeps
    # handling guests only: it mints a guest-role token, so the Gateway pins
    # it to the read-only guest tool tier (mcp_gateway/authz._GUEST_TIER) —
    # catalogue lookups and the FAQ / policy corpus, no cart, no orders.
    if sender_role == "customer":
        return

    mode = await get_mode(redis, room_id, settings.ai_mode_default)
    if mode != "ai":
        return

    within_budget = await check_and_increment_rate_limit(
        redis, room_id, settings.ai_rate_limit, settings.ai_rate_limit_window_seconds
    )
    if not within_budget:
        await chat_client.post_message(room_id, RATE_LIMIT_MESSAGE)
        await chat_client.set_mode(room_id, "human")
        return

    history = await chat_client.get_recent_messages(room_id, settings.conversation_history_limit)
    session = await prepare_session(
        session_service,
        app_name=APP_NAME,
        user_id=sender_id,
        agent_name=GUEST_AGENT_NAME,
        history=history,
    )

    token = mint_internal_token(settings.internal_token_secret, sub=sender_id, role="guest")
    handle = set_request_token(token)
    try:
        await stream_agent_reply(
            chat_client,
            room_id,
            run_agent_stream(
                guest_runner,
                user_id=sender_id,
                session_id=session.id,
                message=content,
                author=GUEST_AGENT_NAME,
                max_llm_calls=settings.max_react_iterations * 2,
                fallback_reply=GUEST_FALLBACK_REPLY,
            ),
            fallback=GUEST_FALLBACK_REPLY,
        )
    finally:
        reset_request_token(handle)


def make_dispatch(
    *,
    redis: Redis,
    session_service: BaseSessionService,
    guest_runner: Runner,
    chat_client: ChatClient,
    settings: Settings,
) -> Dispatch:
    async def dispatch(envelope: dict) -> None:
        if envelope.get("event_type") != "CustomerMessageSent":
            # AdminRequested/AIModeEnabled/UnreadMessageReceived aren't ours
            # to react to — mode is read fresh from Redis on every message
            # instead of tracked from these events, so no handling is
            # needed for them here.
            return
        await handle_customer_message_sent(
            redis=redis,
            session_service=session_service,
            guest_runner=guest_runner,
            chat_client=chat_client,
            settings=settings,
            payload=envelope.get("payload", {}),
        )

    return dispatch
