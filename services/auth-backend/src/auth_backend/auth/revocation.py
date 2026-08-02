from redis.asyncio import Redis


# Placeholder for the token-denylist check that ships with /logout
# (AUTH-05). Not wired to Redis yet — always reports "not revoked" so the
# call site in external-token verification is already in place and doesn't
# need to change when the real check lands.
class RevocationChecker:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def is_revoked(self, sub: str) -> bool:
        del sub
        return False
