import fakeredis

from ai_assistant.agent import check_and_increment_rate_limit, get_mode

ROOM_ID = "room_11111111-1111-1111-1111-111111111111"


async def test_get_mode_defaults_when_key_missing():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    assert await get_mode(redis, ROOM_ID, "ai") == "ai"


async def test_get_mode_reads_redis_value():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(f"chat:{ROOM_ID}:mode", "human")
    assert await get_mode(redis, ROOM_ID, "ai") == "human"


async def test_rate_limit_allows_up_to_limit():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for _ in range(10):
        assert await check_and_increment_rate_limit(redis, ROOM_ID, limit=10, window_seconds=3600) is True


async def test_rate_limit_blocks_after_limit():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for _ in range(10):
        await check_and_increment_rate_limit(redis, ROOM_ID, limit=10, window_seconds=3600)

    assert await check_and_increment_rate_limit(redis, ROOM_ID, limit=10, window_seconds=3600) is False
