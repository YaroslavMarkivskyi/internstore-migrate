"""Adapt ADK's `Runner.run_async` event stream to the `Delta`/`Reset` events
the rest of ai-assistant already speaks (see main.py `_stream_agent_reply`,
which fans them out to Chat as `message_delta` / `message_reset` frames).

`Delta`  — a chunk of the final answer, stream it to the customer now.
`Reset`  — the model streamed some answer text and then called a tool after
           all; discard what was shown and wait for the real answer.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.genai import types as genai_types

logger = logging.getLogger(__name__)


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
