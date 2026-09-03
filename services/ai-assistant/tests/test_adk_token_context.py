"""The MCP toolset's header provider: refreshes the request's internal token
if it's near its 60s TTL, then hands it back as X-Internal-Token."""

import time
from unittest.mock import AsyncMock

import jwt
from ai_assistant.adk.token_context import (
    make_header_provider,
    reset_request_token,
    set_request_token,
)

SECRET = "test-secret"


def _mint(*, expires_in: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": "cust-1", "role": "customer", "iat": now, "exp": now + expires_in}, SECRET, "HS256")


async def test_returns_the_current_token_when_it_is_still_fresh():
    auth_backend = AsyncMock()
    provider = make_header_provider(auth_backend, refresh_margin_seconds=15)
    token = _mint(expires_in=300)
    handle = set_request_token(token)
    try:
        headers = await provider(None)
    finally:
        reset_request_token(handle)
    assert headers == {"X-Internal-Token": token}
    auth_backend.refresh.assert_not_awaited()


async def test_refreshes_a_token_close_to_expiry():
    fresh = _mint(expires_in=300)
    auth_backend = AsyncMock()
    auth_backend.refresh = AsyncMock(return_value=fresh)
    provider = make_header_provider(auth_backend, refresh_margin_seconds=15)
    handle = set_request_token(_mint(expires_in=5))
    try:
        headers = await provider(None)
    finally:
        reset_request_token(handle)
    auth_backend.refresh.assert_awaited_once()
    assert headers == {"X-Internal-Token": fresh}
