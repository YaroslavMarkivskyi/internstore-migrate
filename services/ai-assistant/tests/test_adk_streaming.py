"""run_agent_stream: ADK Event stream -> Delta / Reset."""

from types import SimpleNamespace

from ai_assistant.adk.streaming import Delta, Reset, run_agent_stream

AGENT = "shopping_assistant"


def _event(*, text=None, partial=False, final=False, function_calls=(), author=AGENT):
    parts = [SimpleNamespace(text=text, function_call=None)] if text is not None else []
    parts += [SimpleNamespace(text=None, function_call=fc) for fc in function_calls]
    return SimpleNamespace(
        author=author,
        content=SimpleNamespace(parts=parts) if parts else None,
        partial=partial,
        get_function_calls=lambda: list(function_calls),
        is_final_response=lambda: final,
    )


def _runner(*events):
    async def _run_async(**_kwargs):
        for e in events:
            yield e

    return SimpleNamespace(agent=SimpleNamespace(name=AGENT), run_async=_run_async)


async def _collect(runner, **overrides):
    kwargs = {
        "user_id": "u",
        "session_id": "s",
        "message": "hi",
        "author": AGENT,
        "max_llm_calls": 10,
        "fallback_reply": "FB",
        **overrides,
    }
    return [e async for e in run_agent_stream(runner, **kwargs)]


async def test_streams_partial_text_as_deltas():
    runner = _runner(
        _event(text="Hello ", partial=True),
        _event(text="world", partial=True),
        _event(text="Hello world", final=True),
    )
    out = await _collect(runner)
    assert out == [Delta("Hello "), Delta("world")]


async def test_non_streamed_final_answer_is_emitted_once():
    runner = _runner(_event(text="The answer.", final=True))
    assert await _collect(runner) == [Delta("The answer.")]


async def test_tool_call_after_streamed_preamble_emits_reset():
    runner = _runner(
        _event(text="Let me check", partial=True),
        _event(function_calls=[SimpleNamespace(name="get_cart", args={})]),
        _event(text="You have 2 items.", final=True),
    )
    assert await _collect(runner) == [Delta("Let me check"), Reset(), Delta("You have 2 items.")]


async def test_tool_call_with_no_preamble_emits_no_reset():
    runner = _runner(
        _event(function_calls=[SimpleNamespace(name="search_products", args={})]),
        _event(text="Found it.", final=True),
    )
    assert await _collect(runner) == [Delta("Found it.")]


async def test_fallback_when_the_agent_produces_nothing():
    assert await _collect(_runner()) == [Delta("FB")]


async def test_events_from_other_authors_are_ignored():
    runner = _runner(
        _event(text="internal", partial=True, author="some_subagent"),
        _event(text="Real answer.", final=True),
    )
    assert await _collect(runner) == [Delta("Real answer.")]
