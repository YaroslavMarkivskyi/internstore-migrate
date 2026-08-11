import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from ai_assistant.react_loop import FALLBACK_REPLY, SHOPPING_TOOL_NAMES, run_shopping_agent
from ai_assistant.token_manager import RefreshableToken

TOOL_SPECS = [
    {"name": "search_products", "description": "search", "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_cart", "description": "cart", "input_schema": {"type": "object", "properties": {}}},
    {"name": "add_to_cart", "description": "add", "input_schema": {"type": "object", "properties": {}}},
    {"name": "remove_from_cart", "description": "remove", "input_schema": {"type": "object", "properties": {}}},
    # Not a shopping tool -- must never be offered to the model, even though
    # the Gateway's full catalog includes it.
    {"name": "get_visit_log", "description": "admin only", "input_schema": {"type": "object", "properties": {}}},
]


def _tool_call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def _response(content: str | None, tool_calls: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


def _fake_deps():
    mcp_client = AsyncMock()
    mcp_client.list_tools = AsyncMock(return_value=TOOL_SPECS)
    auth_backend_client = AsyncMock()
    openai_client = AsyncMock()
    return mcp_client, auth_backend_client, openai_client


async def test_returns_final_answer_when_model_makes_no_tool_call():
    mcp_client, auth_backend_client, openai_client = _fake_deps()
    openai_client.chat.completions.create = AsyncMock(return_value=_response("Here are some cheeses under $20."))

    reply = await run_shopping_agent(
        openai_client=openai_client,
        mcp_client=mcp_client,
        auth_backend_client=auth_backend_client,
        chat_model="gpt-4o",
        message="find me a gouda under $20",
        token=RefreshableToken(_no_exp_token()),
    )

    assert reply == "Here are some cheeses under $20."
    mcp_client.call_tool.assert_not_awaited()


def _no_exp_token() -> str:
    import jwt

    return jwt.encode({"sub": "customer-1", "role": "customer", "iss": "internstore-gateway"}, "secret")


async def test_only_shopping_tools_are_offered_to_the_model():
    mcp_client, auth_backend_client, openai_client = _fake_deps()
    openai_client.chat.completions.create = AsyncMock(return_value=_response("done"))

    await run_shopping_agent(
        openai_client=openai_client,
        mcp_client=mcp_client,
        auth_backend_client=auth_backend_client,
        chat_model="gpt-4o",
        message="hi",
        token=RefreshableToken(_no_exp_token()),
    )

    offered = {tool["function"]["name"] for tool in openai_client.chat.completions.create.call_args.kwargs["tools"]}
    assert offered == set(SHOPPING_TOOL_NAMES)
    assert "get_visit_log" not in offered


async def test_executes_tool_call_then_returns_models_follow_up_answer():
    mcp_client, auth_backend_client, openai_client = _fake_deps()
    mcp_client.call_tool = AsyncMock(return_value={"items": [{"product_id": "prod-1", "quantity": 2}]})
    openai_client.chat.completions.create = AsyncMock(
        side_effect=[
            _response(None, tool_calls=[_tool_call("call-1", "add_to_cart", {"product_id": "prod-1", "quantity": 2})]),
            _response("Added 2x Gouda to your cart."),
        ]
    )
    token = RefreshableToken(_no_exp_token())

    reply = await run_shopping_agent(
        openai_client=openai_client,
        mcp_client=mcp_client,
        auth_backend_client=auth_backend_client,
        chat_model="gpt-4o",
        message="add it to my cart",
        token=token,
    )

    assert reply == "Added 2x Gouda to your cart."
    mcp_client.call_tool.assert_awaited_once_with(token.value, "add_to_cart", {"product_id": "prod-1", "quantity": 2})


async def test_stops_after_max_iterations_and_returns_fallback():
    mcp_client, auth_backend_client, openai_client = _fake_deps()
    mcp_client.call_tool = AsyncMock(return_value={"items": []})
    # The model keeps calling a tool forever and never gives a final answer.
    openai_client.chat.completions.create = AsyncMock(
        return_value=_response(None, tool_calls=[_tool_call("call-x", "get_cart", {})])
    )

    reply = await run_shopping_agent(
        openai_client=openai_client,
        mcp_client=mcp_client,
        auth_backend_client=auth_backend_client,
        chat_model="gpt-4o",
        message="loop forever",
        token=RefreshableToken(_no_exp_token()),
        max_iterations=3,
    )

    assert reply == FALLBACK_REPLY
    assert openai_client.chat.completions.create.await_count == 3


async def test_tool_call_failure_is_surfaced_to_the_model_not_raised():
    mcp_client, auth_backend_client, openai_client = _fake_deps()
    mcp_client.call_tool = AsyncMock(side_effect=RuntimeError("Orders unavailable"))
    openai_client.chat.completions.create = AsyncMock(
        side_effect=[
            _response(None, tool_calls=[_tool_call("call-1", "get_cart", {})]),
            _response("Sorry, I couldn't check your cart right now."),
        ]
    )

    reply = await run_shopping_agent(
        openai_client=openai_client,
        mcp_client=mcp_client,
        auth_backend_client=auth_backend_client,
        chat_model="gpt-4o",
        message="what's in my cart?",
        token=RefreshableToken(_no_exp_token()),
    )

    assert reply == "Sorry, I couldn't check your cart right now."
    second_call_messages = openai_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    tool_message = next(m for m in second_call_messages if m["role"] == "tool")
    assert "Orders unavailable" in tool_message["content"]
