"""Test double for the ADK agent stream.

The endpoint tests care about what `/agent/{shopping,admin}` does *around* the
agent — mode/rate-limit guards, history fetch + seeding, streaming the reply
to Chat, persisting on done. They don't exercise a real model, so they patch
`ai_assistant.main.run_agent_stream` with `fake_agent_stream(...)`.
"""

from ai_assistant.adk.streaming import Delta, Reset


def fake_agent_stream(*events: str | Delta | Reset):
    """Build a stand-in for `run_agent_stream`: an async-generator function
    that ignores its arguments (beyond recording them on `.calls`) and yields
    the given events. Plain strings become `Delta`s."""
    calls: list[dict] = []

    async def _run(runner, **kwargs):
        calls.append(kwargs)
        for event in events:
            yield event if isinstance(event, (Delta, Reset)) else Delta(str(event))

    _run.calls = calls
    return _run
