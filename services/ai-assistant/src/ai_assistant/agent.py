from redis.asyncio import Redis

RATE_LIMIT_MESSAGE = "I've reached my response limit, switching to human support."


def _mode_key(room_id: str) -> str:
    return f"chat:{room_id}:mode"


def _count_key(room_id: str) -> str:
    return f"chat:{room_id}:ai_count"


async def get_mode(redis: Redis, room_id: str, default_mode: str) -> str:
    mode = await redis.get(_mode_key(room_id))
    return mode if mode is not None else default_mode


async def check_and_increment_rate_limit(redis: Redis, room_id: str, limit: int, window_seconds: int) -> bool:
    """Returns True if this response is still within budget. Increments
    first, then checks — so the response that pushes the count past `limit`
    is the one that triggers the rate-limit message, matching the ticket's
    "Max 10 AI responses per room per hour" (the 10th response still goes
    through; the 11th doesn't)."""
    key = _count_key(room_id)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    return count <= limit
