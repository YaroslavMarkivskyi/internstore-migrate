import uuid

from redis.asyncio import Redis

# 7 days. Not sliding — a guest's identity expires 7 days after it was
# first created, regardless of activity in between (see plan doc, "TTL
# sliding on reuse" decision point: kept simple by design).
GUEST_SESSION_TTL_SECONDS = 60 * 60 * 24 * 7

KEY_PREFIX = "guest_session:"


# Separate from revocation.py's Redis usage (a denylist, different concern)
# — its own key prefix so the two never collide.
class GuestSessionStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def lookup(self, guest_id: str) -> bool:
        value = await self._redis.get(KEY_PREFIX + guest_id)
        return value is not None

    async def create(self) -> str:
        guest_id = str(uuid.uuid4())
        await self._redis.set(KEY_PREFIX + guest_id, "1", ex=GUEST_SESSION_TTL_SECONDS)
        return guest_id
