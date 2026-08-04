import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from ai_assistant.consumers.catalog_events import handle_product_updated
from ai_assistant.embeddings import build_embedding_text, search_similar_products, upsert_product_embedding
from ai_assistant.models import ProcessedEvent, ProductEmbedding

FAKE_VECTOR = [0.1] * 1536


def _fake_openai_client() -> AsyncMock:
    client = AsyncMock()
    client.embeddings.create = AsyncMock(
        return_value=SimpleNamespace(data=[SimpleNamespace(embedding=FAKE_VECTOR)])
    )
    return client


def test_build_embedding_text_includes_all_ticket_fields():
    text = build_embedding_text(
        {
            "name": "Frozen Peas",
            "description": "1kg bag",
            "min_temperature": -18,
            "max_temperature": -15,
            "category_name": "Frozen",
        }
    )

    assert "Frozen Peas" in text
    assert "1kg bag" in text
    assert "Frozen" in text
    assert "-18" in text and "-15" in text


async def test_upsert_creates_new_row_when_none_exists():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    client = _fake_openai_client()
    product_id = uuid.uuid4()

    await upsert_product_embedding(
        session,
        client,
        "text-embedding-3-small",
        {"product_id": str(product_id), "name": "Frozen Peas", "description": "1kg bag"},
    )

    client.embeddings.create.assert_awaited_once()
    session.add.assert_called_once()
    added = session.add.call_args.args[0]
    assert isinstance(added, ProductEmbedding)
    assert added.product_id == product_id
    assert added.embedding == FAKE_VECTOR


async def test_upsert_updates_existing_row_in_place():
    session = AsyncMock()
    existing = ProductEmbedding(
        product_id=uuid.uuid4(), name="Old name", description="old", embedding=[0.0] * 1536
    )
    session.get = AsyncMock(return_value=existing)
    session.add = MagicMock()
    client = _fake_openai_client()

    await upsert_product_embedding(
        session,
        client,
        "text-embedding-3-small",
        {"product_id": str(existing.product_id), "name": "New name", "description": "new"},
    )

    session.add.assert_not_called()
    assert existing.name == "New name"
    assert existing.description == "new"
    assert existing.embedding == FAKE_VECTOR


async def test_search_similar_products_returns_top_results():
    session = AsyncMock()
    rows = [
        SimpleNamespace(product_id=uuid.uuid4(), name="Frozen Peas", description="1kg bag"),
        SimpleNamespace(product_id=uuid.uuid4(), name="Frozen Corn", description="1kg bag"),
    ]
    session.execute = AsyncMock(return_value=iter(rows))
    client = _fake_openai_client()

    results = await search_similar_products(session, client, "text-embedding-3-small", "peas", limit=5)

    assert len(results) == 2
    assert results[0]["name"] == "Frozen Peas"
    assert all("product_id" in r and "description" in r for r in results)


async def test_handle_product_updated_skips_already_processed_event():
    session = AsyncMock()
    session.get = AsyncMock(return_value=ProcessedEvent(event_id=uuid.uuid4()))
    session.add = MagicMock()
    client = _fake_openai_client()

    await handle_product_updated(
        session, client, "text-embedding-3-small", uuid.uuid4(), {"product_id": str(uuid.uuid4()), "name": "x"}
    )

    client.embeddings.create.assert_not_awaited()
    session.add.assert_not_called()
