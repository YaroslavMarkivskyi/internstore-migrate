"""Adapt ADK's `Runner.run_async` event stream to the `Delta`/`Reset` events
the rest of ai-assistant already speaks (see main.py `_stream_agent_reply`,
which fans them out to Chat as `message_delta` / `message_reset` frames).

`Delta`  — a chunk of the final answer, stream it to the customer now.
`Reset`  — the model streamed some answer text and then called a tool after
           all; discard what was shown and wait for the real answer.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

# Batch streamed deltas up to roughly this many characters before pushing one
# to Chat — the model streams word-by-word, and one HTTP round trip per word
# through Chat's gate is needless chatter for no perceptible UX gain.
_DELTA_FLUSH_CHARS = 40


@dataclass
class Delta:
    text: str


@dataclass
class Reset:
    pass


StreamEvent = Delta | Reset


def _event_text(event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "".join(part.text for part in event.content.parts if getattr(part, "text", None))


async def run_agent_stream(
    runner: Runner,
    *,
    user_id: str,
    session_id: str,
    message: str,
    author: str,
    max_llm_calls: int,
    fallback_reply: str,
) -> AsyncIterator[StreamEvent]:
    """Drive one agent turn and yield its answer as it streams. The request's
    internal token must already be set via
    `adk.token_context.set_request_token` — the MCP toolset's header provider
    reads it."""
    run_config = RunConfig(streaming_mode=StreamingMode.SSE, max_llm_calls=max_llm_calls)
    new_message = genai_types.Content(role="user", parts=[genai_types.Part(text=message)])

    streamed_any = False
    produced_final = False

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=new_message, run_config=run_config
    ):
        if event.author != runner.agent.name:
            continue

        if event.get_function_calls():
            # Text before a tool call is a preamble, not the answer.
            if streamed_any:
                streamed_any = False
                yield Reset()
            continue

        text = _event_text(event)
        if not text:
            continue

        if event.partial:
            streamed_any = True
            yield Delta(text)
        elif event.is_final_response():
            produced_final = True
            if not streamed_any:
                # Model answered in one non-streamed shot (or after a Reset).
                yield Delta(text)
            # else: partials already carried the whole answer.
            break

    if not produced_final and not streamed_any:
        logger.warning("Agent %s produced no answer, using fallback", runner.agent.name)
        yield Delta(fallback_reply)


async def stream_agent_reply(chat_client, room_id: str, events: AsyncIterator[StreamEvent], *, fallback: str) -> None:
    """Drain an agent's Delta/Reset stream into Chat: batched `message_delta`
    frames, a `message_reset` on Reset, one persisted `message_done` at the end.

    Always finishes with a `message_done` — if the agent stream raises partway
    through (a model error, an MCP hiccup), the customer gets the fallback
    text and the "typing…" indicator clears, instead of hanging forever."""
    stream_id = str(uuid.uuid4())
    full: list[str] = []
    pending: list[str] = []

    async def _flush() -> None:
        if pending:
            await chat_client.stream_delta(room_id, stream_id, "".join(pending))
            pending.clear()

    try:
        async for event in events:
            if isinstance(event, Reset):
                full.clear()
                pending.clear()
                await chat_client.stream_reset(room_id, stream_id)
                continue
            full.append(event.text)
            pending.append(event.text)
            if sum(len(part) for part in pending) >= _DELTA_FLUSH_CHARS:
                await _flush()
        await _flush()
    except Exception:
        logger.exception("Agent stream failed for room %s", room_id)
        if not full:
            await chat_client.stream_reset(room_id, stream_id)
            full = [fallback]

    await chat_client.stream_done(room_id, stream_id, "".join(full))
