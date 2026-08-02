import hashlib
import time

import httpx

from auth_backend.config import Settings

# Bounds the worst-case revocation-propagation window: a token revoked in
# Keycloak is accepted by /auth/verify for at most this long afterwards.
CACHE_TTL_SECONDS = 30.0


# AUTH-05: verifies a Keycloak access token is still active via RFC 7662
# token introspection before /auth/verify trusts it. Introspection failures
# fail closed (treated as revoked) — an unreachable or erroring Keycloak
# must not silently fall back to trusting the token.
#
# Introspection results are cached in-memory for CACHE_TTL_SECONDS, keyed by
# sha256(token) so raw tokens are never retained past the request that
# carried them. This avoids a Keycloak round trip on every /auth/verify call
# for the same token, at the cost of a bounded revocation-propagation delay.
class RevocationChecker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, tuple[bool, float]] = {}  # token_hash -> (revoked, expires_at)

    def _evict_expired(self, now: float) -> None:
        expired = [key for key, (_, expires_at) in self._cache.items() if expires_at <= now]
        for key in expired:
            del self._cache[key]

    async def is_revoked(self, token: str) -> bool:
        now = time.monotonic()
        self._evict_expired(now)

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        cached = self._cache.get(token_hash)
        if cached is not None:
            revoked, _ = cached
            return revoked

        revoked = await self._introspect(token)
        self._cache[token_hash] = (revoked, now + CACHE_TTL_SECONDS)
        return revoked

    async def _introspect(self, token: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._settings.keycloak_issuer}/protocol/openid-connect/token/introspect",
                    data={
                        "token": token,
                        "client_id": self._settings.keycloak_client_id,
                        "client_secret": self._settings.keycloak_client_secret,
                    },
                )
        except httpx.HTTPError:
            return True  # fail closed — Keycloak unreachable

        if resp.status_code != 200:
            return True  # fail closed — introspection error

        return not resp.json().get("active", False)
