import time

import jwt

from ai_assistant.auth_backend_client import AuthBackendClient


class RefreshableToken:
    """Wraps the customer's forwarded internal-token for the lifetime of a
    single shopping ReAct loop, refreshing it via auth-backend when it's
    close to the 60s TTL expiring mid-sequence (STR-146). The token was
    already verified once by this service's own inbound auth dependency
    (see main.py's POST /agent/shopping) — decoding here without checking
    the signature again is just to read `exp` and decide whether a refresh
    is due, not a trust decision."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._exp = self._peek_exp(token)

    @staticmethod
    def _peek_exp(token: str) -> int | None:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
        except jwt.InvalidTokenError:
            return None
        return payload.get("exp")

    @property
    def value(self) -> str:
        return self._token

    def expires_within(self, margin_seconds: int) -> bool:
        # No exp claim at all (e.g. a self-minted admin/assistant token,
        # see mcp_gateway/auth.py's old behavior) means it never expires —
        # nothing to refresh.
        if self._exp is None:
            return False
        return time.time() + margin_seconds >= self._exp

    async def ensure_fresh(self, auth_backend_client: AuthBackendClient, margin_seconds: int) -> None:
        if not self.expires_within(margin_seconds):
            return
        self._token = await auth_backend_client.refresh(self._token)
        self._exp = self._peek_exp(self._token)
