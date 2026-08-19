from google import genai
from google.genai import types
from redis.asyncio import Redis

RATE_LIMIT_MESSAGE = "I've reached my response limit, switching to human support."


def _mode_key(room_id: str) -> str:
    return f"chat:{room_id}:mode"


def _count_key(room_id: str) -> str:
    return f"chat:{room_id}:ai_count"


async def get_mode(redis: Redis, room_id: str, default_mode: str) -> str:
    mode = await redis.get(_mode_key(room_id))
    return mode if mode is not None else default_mode


async def check_and_increment_rate_limit(redis: Redis, room_id: str, limit: int, window_seconds: int) -> bool:
    """Returns True if this response is still within budget. Increments
    first, then checks — so the response that pushes the count past `limit`
    is the one that triggers the rate-limit message, matching the ticket's
    "Max 10 AI responses per room per hour" (the 10th response still goes
    through; the 11th doesn't)."""
    key = _count_key(room_id)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    return count <= limit


async def generate_reply(
    client: genai.Client, model: str, system_instruction: str, contents: list[dict], max_tokens: int
) -> str:
    # STR-161b: contents come from context.build_messages as plain
    # {"role", "content"} dicts (role already mapped to Gemini's "user"/
    # "model" — see context._sender_role_to_map) — converted to
    # types.Content here rather than upstream, so build_messages stays
    # testable without importing the SDK's types.
    genai_contents = [
        types.Content(role=entry["role"], parts=[types.Part(text=entry["content"])]) for entry in contents
    ]
    response = await client.aio.models.generate_content(
        model=model,
        contents=genai_contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=max_tokens,
            temperature=0.3,  # low temperature for factual support responses
        ),
    )
    return response.text
