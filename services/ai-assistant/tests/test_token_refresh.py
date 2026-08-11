"""STR-146: internal-tokens are minted with a 60s TTL (see auth-backend's
Settings.internal_token_ttl_seconds). A shopping ReAct loop spanning several
tool-calling round trips can easily outlive that — this proves the loop
refreshes proactively via auth-backend rather than failing partway through
with a stale-token 401."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt

from ai_assistant.react_loop import run_shopping_agent
from ai_assistant.token_manager import RefreshableToken

SECRET = "test-secret"
ISSUER = "internstore-gateway"

TOOL_SPECS = [
    {"name": "get_cart", "description": "cart", "input_schema": {"type": "object", "properties": {}}},
]


def _mint(sub: str, role: str, *, expires_in: int) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER, "iat": now, "exp": now + expires_in}, SECRET, algorithm="HS256"
    )


def _response(content: str | None, tool_calls: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


def _tool_call(call_id: str, name: str) -> SimpleNamespace:
    import json

    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps({})))


async def test_loop_refreshes_a_soon_to_expire_token_before_the_next_tool_call():
    about_to_expire = _mint("customer-1", "customer", expires_in=10)
    fresh_token = _mint("customer-1", "customer", expires_in=60)

    mcp_client = AsyncMock()
    mcp_client.list_tools = AsyncMock(return_value=TOOL_SPECS)
    mcp_client.call_tool = AsyncMock(return_value={"items": []})

    auth_backend_client = AsyncMock()
    auth_backend_client.refresh = AsyncMock(return_value=fresh_token)

    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(
        side_effect=[
            _response(None, tool_calls=[_tool_call("call-1", "get_cart")]),
            _response("Your cart is empty."),
        ]
    )

    token = RefreshableToken(about_to_expire)

    reply = await run_shopping_agent(
        openai_client=openai_client,
        mcp_client=mcp_client,
        auth_backend_client=auth_backend_client,
        chat_model="gpt-4o",
        message="what's in my cart?",
        token=token,
        refresh_margin_seconds=15,  # 10s left < 15s margin -- must refresh
    )

    assert reply == "Your cart is empty."
    auth_backend_client.refresh.assert_awaited_once_with(about_to_expire)
    # The refreshed token, not the near-expiry one, is what actually reaches
    # the Gateway for the tool call -- this is the part that would otherwise
    # 401 partway through a longer loop.
    mcp_client.call_tool.assert_awaited_once_with(fresh_token, "get_cart", {})


async def test_loop_does_not_refresh_a_token_with_plenty_of_time_left():
    plenty_of_time = _mint("customer-1", "customer", expires_in=60)

    mcp_client = AsyncMock()
    mcp_client.list_tools = AsyncMock(return_value=TOOL_SPECS)

    auth_backend_client = AsyncMock()
    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(return_value=_response("All good."))

    await run_shopping_agent(
        openai_client=openai_client,
        mcp_client=mcp_client,
        auth_backend_client=auth_backend_client,
        chat_model="gpt-4o",
        message="hi",
        token=RefreshableToken(plenty_of_time),
        refresh_margin_seconds=15,
    )

    auth_backend_client.refresh.assert_not_awaited()


async def test_loop_refreshes_again_across_iterations_if_still_close_to_expiry():
    # A loop that runs many iterations refreshes each time it's still close
    # to expiry -- not just once -- since auth-backend re-mints with a fresh
    # 60s TTL each call, and a slow enough sequence could approach it again.
    near_expiry = _mint("customer-1", "customer", expires_in=5)

    mcp_client = AsyncMock()
    mcp_client.list_tools = AsyncMock(return_value=TOOL_SPECS)
    mcp_client.call_tool = AsyncMock(return_value={"items": []})

    auth_backend_client = AsyncMock()
    # auth-backend's refresh always re-mints with the *same* short fixed
    # window in this test, so every iteration is still within the margin --
    # proving refresh isn't a one-shot "do it once at the start" thing.
    auth_backend_client.refresh = AsyncMock(side_effect=lambda _t: _mint("customer-1", "customer", expires_in=5))

    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(
        side_effect=[
            _response(None, tool_calls=[_tool_call("call-1", "get_cart")]),
            _response(None, tool_calls=[_tool_call("call-2", "get_cart")]),
            _response("done"),
        ]
    )

    await run_shopping_agent(
        openai_client=openai_client,
        mcp_client=mcp_client,
        auth_backend_client=auth_backend_client,
        chat_model="gpt-4o",
        message="check my cart twice",
        token=RefreshableToken(near_expiry),
        refresh_margin_seconds=15,
    )

    assert auth_backend_client.refresh.await_count == 3
