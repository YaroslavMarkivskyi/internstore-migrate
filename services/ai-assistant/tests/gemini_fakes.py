"""Shared fakes for google-genai's streaming API (generate_content_stream).

The shopping ReAct loop (react_loop.run_shopping_agent_stream) drives the
model with `generate_content_stream`, which is a coroutine returning an
async iterator of response chunks (each with `.text` and `.function_calls`).
These helpers build that shape for the unit tests without a real model.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock


def chunk(text: str | None = None, function_calls: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(text=text, function_calls=function_calls or [])


def function_call(name: str, args: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(name=name, args=args or {})


def turn(*chunks: SimpleNamespace):
    """One model turn = an async iterator of chunks."""

    async def _agen():
        for one in chunks:
            yield one

    return _agen()


def set_stream(genai_client, *turns) -> None:
    """Wire `genai_client.aio.models.generate_content_stream` to yield each
    given turn in order. A turn is a single chunk or a sequence of chunks."""
    streams = [turn(*(t if isinstance(t, (list, tuple)) else (t,))) for t in turns]
    if len(streams) == 1:
        genai_client.aio.models.generate_content_stream = AsyncMock(return_value=streams[0])
    else:
        genai_client.aio.models.generate_content_stream = AsyncMock(side_effect=streams)
