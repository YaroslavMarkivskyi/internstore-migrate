from types import SimpleNamespace
from unittest.mock import AsyncMock

from mcp_gateway.tools.help import HelpSearchClient


class _FakeSession:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def execute(self, _stmt: object) -> object:
        return iter(self._rows)


def _fake_session_factory(rows: list):
    return lambda: _FakeSession(rows)


def _fake_genai_client() -> AsyncMock:
    client = AsyncMock()
    client.aio.models.embed_content = AsyncMock(
        return_value=SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1] * 1536)])
    )
    return client


async def test_search_help_embeds_query_and_returns_nearest_chunks():
    rows = [
        SimpleNamespace(
            source="faq.md",
            heading="Returns and refunds",
            content="Non-perishable items can be returned within 14 days.",
        )
    ]
    genai_client = _fake_genai_client()
    client = HelpSearchClient(_fake_session_factory(rows), genai_client, "gemini-embedding-001", 1536)

    result = await client.search_help("caller-token", "can I return this?", limit=3)

    call_kwargs = genai_client.aio.models.embed_content.call_args.kwargs
    assert call_kwargs["contents"] == "can I return this?"
    assert call_kwargs["config"].output_dimensionality == 1536
    assert result == [
        {
            "source": "faq.md",
            "heading": "Returns and refunds",
            "content": "Non-perishable items can be returned within 14 days.",
        }
    ]
