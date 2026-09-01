"""PgVectorMemoryService — the parsing / best-effort behaviour that doesn't
need a live pgvector (the SQL paths are covered by the live stack)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from ai_assistant.adk.memory import PgVectorMemoryService, _transcript


def _service(genai_client=None) -> PgVectorMemoryService:
    return PgVectorMemoryService(
        session_factory=AsyncMock(),
        genai_client=genai_client or AsyncMock(),
        chat_model="gemini-2.5-flash",
        embedding_model="gemini-embedding-001",
        embedding_dimensions=1536,
    )


def _session(*turns: tuple[str, str]):
    events = [
        SimpleNamespace(
            author=author,
            content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
        )
        for author, text in turns
    ]
    return SimpleNamespace(app_name="ai-assistant", user_id="cust-1", events=events)


def test_transcript_labels_speakers():
    text = _transcript(_session(("user", "any brie?"), ("shopping_assistant", "Yes, we have Brie.")))
    assert text == "Customer: any brie?\nAssistant: Yes, we have Brie."


@pytest.mark.parametrize(
    ("model_reply", "expected"),
    [
        ("NONE", []),
        ("  none  ", []),
        ("Is lactose intolerant.\nShops for a family of four.", ["Is lactose intolerant.", "Shops for a family of four."]),
        ("- Likes aged cheddar\n* Budget around $30", ["Likes aged cheddar", "Budget around $30"]),
    ],
)
async def test_extract_facts_parses_the_model_reply(model_reply, expected):
    genai = AsyncMock()
    genai.aio.models.generate_content = AsyncMock(return_value=SimpleNamespace(text=model_reply))
    assert await _service(genai)._extract_facts("Customer: ...") == expected


async def test_extract_facts_skips_the_model_call_for_an_empty_transcript():
    genai = AsyncMock()
    assert await _service(genai)._extract_facts("   ") == []
    genai.aio.models.generate_content.assert_not_awaited()


async def test_search_memory_returns_empty_on_failure():
    genai = AsyncMock()
    genai.aio.models.embed_content = AsyncMock(side_effect=RuntimeError("quota"))
    result = await _service(genai).search_memory(app_name="ai-assistant", user_id="cust-1", query="brie")
    assert result.memories == []


async def test_add_session_to_memory_swallows_errors():
    genai = AsyncMock()
    genai.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("quota"))
    # Must not raise — the reply has already been sent by the time this runs.
    await _service(genai).add_session_to_memory(_session(("user", "hi")))
