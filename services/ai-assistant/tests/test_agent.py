from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis

from ai_assistant.agent import (
    RATE_LIMIT_MESSAGE,
    check_and_increment_rate_limit,
    generate_reply,
    get_mode,
)
from ai_assistant.consumers.chat_events import handle_customer_message_sent

ROOM_ID = "room_11111111-1111-1111-1111-111111111111"


def _fake_genai_client(text: str = "Your order shipped yesterday.") -> AsyncMock:
    client = AsyncMock()
    client.aio.models.generate_content = AsyncMock(return_value=SimpleNamespace(text=text))
    return client


async def test_get_mode_defaults_when_key_missing():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    assert await get_mode(redis, ROOM_ID, "ai") == "ai"


async def test_get_mode_reads_redis_value():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(f"chat:{ROOM_ID}:mode", "human")
    assert await get_mode(redis, ROOM_ID, "ai") == "human"


async def test_generate_reply_uses_expected_system_instruction_and_params():
    client = _fake_genai_client("Hi there!")
    contents = [{"role": "user", "content": "hi"}]

    reply = await generate_reply(client, "gemini-3-flash", "sys", contents, max_tokens=500)

    assert reply == "Hi there!"
    call_kwargs = client.aio.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3-flash"
    assert [c.role for c in call_kwargs["contents"]] == ["user"]
    assert call_kwargs["contents"][0].parts[0].text == "hi"
    assert call_kwargs["config"].system_instruction == "sys"
    assert call_kwargs["config"].max_output_tokens == 500
    assert call_kwargs["config"].temperature == 0.3


async def test_rate_limit_allows_up_to_limit():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for _ in range(10):
        assert await check_and_increment_rate_limit(redis, ROOM_ID, limit=10, window_seconds=3600) is True


async def test_rate_limit_blocks_after_limit():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for _ in range(10):
        await check_and_increment_rate_limit(redis, ROOM_ID, limit=10, window_seconds=3600)

    assert await check_and_increment_rate_limit(redis, ROOM_ID, limit=10, window_seconds=3600) is False


class _Settings:
    ai_mode_default = "ai"
    ai_rate_limit = 10
    ai_rate_limit_window_seconds = 3600
    embedding_model = "gemini-embedding-001"
    embedding_dimensions = 1536
    chat_model = "gemini-3-flash"
    max_response_tokens = 500
    conversation_history_limit = 20
    order_history_limit = 5
    product_context_limit = 5


async def test_mode_human_skips_response():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(f"chat:{ROOM_ID}:mode", "human")
    chat_client = AsyncMock()
    orders_client = AsyncMock()
    genai_client = _fake_genai_client()

    await handle_customer_message_sent(
        session_factory=AsyncMock(),
        redis=redis,
        genai_client=genai_client,
        chat_client=chat_client,
        orders_client=orders_client,
        settings=_Settings(),
        payload={"room_id": ROOM_ID, "sender_id": "guest-session-1", "content": "hi"},
    )

    genai_client.aio.models.generate_content.assert_not_awaited()
    chat_client.post_message.assert_not_awaited()


async def test_rate_limit_hit_sends_final_message_and_switches_to_human():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(f"chat:{ROOM_ID}:mode", "ai")
    await redis.set(f"chat:{ROOM_ID}:ai_count", 10)
    chat_client = AsyncMock()
    orders_client = AsyncMock()
    genai_client = _fake_genai_client()

    await handle_customer_message_sent(
        session_factory=AsyncMock(),
        redis=redis,
        genai_client=genai_client,
        chat_client=chat_client,
        orders_client=orders_client,
        settings=_Settings(),
        payload={"room_id": ROOM_ID, "sender_id": "guest-session-1", "content": "hi"},
    )

    chat_client.post_message.assert_awaited_once_with(ROOM_ID, RATE_LIMIT_MESSAGE)
    chat_client.set_mode.assert_awaited_once_with(ROOM_ID, "human")
    genai_client.aio.models.generate_content.assert_not_awaited()
