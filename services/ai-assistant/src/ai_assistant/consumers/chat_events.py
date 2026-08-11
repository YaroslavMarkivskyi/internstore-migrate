import logging
from collections.abc import Awaitable, Callable

from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from ai_assistant.agent import RATE_LIMIT_MESSAGE, check_and_increment_rate_limit, generate_reply, get_mode
from ai_assistant.chat_client import ChatClient
from ai_assistant.config import Settings
from ai_assistant.context import build_messages, is_registered_customer
from ai_assistant.orders_client import OrdersClient

logger = logging.getLogger(__name__)

TOPIC = "chat-events"
GROUP_ID = "ai-assistant-chat-events"

Dispatch = Callable[[dict], Awaitable[None]]


async def handle_customer_message_sent(
    *,
    session_factory: async_sessionmaker,
    redis: Redis,
    openai_client: AsyncOpenAI,
    chat_client: ChatClient,
    orders_client: OrdersClient,
    settings: Settings,
    payload: dict,
) -> None:
    room_id = payload["room_id"]
    sender_id = payload["sender_id"]
    content = payload.get("content")
    if not content:
        return

    # STR-146: registered customers are handled synchronously instead, via
    # Chat calling POST /agent/shopping directly with the customer's own
    # internal-token (see main.py) — that's the only path that can
    # propagate a real per-customer identity into a cart-mutating tool
    # call. This Kafka-driven consumer has no inbound token to forward (see
    # ai_assistant/auth.py's own docstring) and keeps handling guests only,
    # with the original non-agentic, tool-less reply — guests get no
    # shopping-agent access per the ticket, and this path never touches
    # cart tools regardless.
    if is_registered_customer(sender_id):
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

    async with session_factory() as session:
        messages = await build_messages(
            session=session,
            openai_client=openai_client,
            embedding_model=settings.embedding_model,
            chat_client=chat_client,
            orders_client=orders_client,
            room_id=room_id,
            sender_id=sender_id,
            customer_message=content,
            conversation_history_limit=settings.conversation_history_limit,
            order_history_limit=settings.order_history_limit,
            product_context_limit=settings.product_context_limit,
        )

    reply = await generate_reply(openai_client, settings.chat_model, messages, settings.max_response_tokens)
    await chat_client.post_message(room_id, reply)


def make_dispatch(
    *,
    session_factory: async_sessionmaker,
    redis: Redis,
    openai_client: AsyncOpenAI,
    chat_client: ChatClient,
    orders_client: OrdersClient,
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
            session_factory=session_factory,
            redis=redis,
            openai_client=openai_client,
            chat_client=chat_client,
            orders_client=orders_client,
            settings=settings,
            payload=envelope.get("payload", {}),
        )

    return dispatch
