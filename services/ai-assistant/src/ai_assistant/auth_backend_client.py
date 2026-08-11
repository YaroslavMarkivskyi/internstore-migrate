import httpx


class TokenRefreshError(Exception):
    """Raised when auth-backend rejects a refresh attempt (token already
    expired, bad signature, etc.) — the ReAct loop treats this as fatal for
    the in-flight request rather than retrying, since a rejected refresh
    means the customer's session is no longer valid, not that this call
    happened to fail transiently."""


class AuthBackendClient:
    """STR-146: re-mints a still-valid internal token with a fresh exp, so a
    shopping ReAct loop that outlives the 60s internal-token TTL doesn't
    fail mid-sequence with a stale-token 401 (see auth-backend's new
    POST /auth/refresh)."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def refresh(self, token: str) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/auth/refresh", headers={"X-Internal-Token": token})
        if resp.status_code != 200:
            raise TokenRefreshError(f"auth-backend rejected refresh: {resp.status_code}")
        return resp.json()["internalToken"]
