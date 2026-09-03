import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from ai_assistant.consumers.catalog_events import handle_product_deleted, handle_product_updated
from ai_assistant.embeddings import (
    build_embedding_text,
    delete_product_embedding,
    upsert_product_embedding,
)
from ai_assistant.models import ProcessedEvent, ProductEmbedding

FAKE_VECTOR = [0.1] * 1536
DIMENSIONS = 1536


def _fake_genai_client() -> AsyncMock:
    client = AsyncMock()
    client.aio.models.embed_content = AsyncMock(
        return_value=SimpleNamespace(embeddings=[SimpleNamespace(values=FAKE_VECTOR)])
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
    client = _fake_genai_client()
    product_id = uuid.uuid4()

    await upsert_product_embedding(
        session,
        client,
        "gemini-embedding-001",
        {"product_id": str(product_id), "name": "Frozen Peas", "description": "1kg bag"},
        DIMENSIONS,
    )

    client.aio.models.embed_content.assert_awaited_once()
    session.add.assert_called_once()
    added = session.add.call_args.args[0]
    assert isinstance(added, ProductEmbedding)
    assert added.product_id == product_id
    assert added.embedding == FAKE_VECTOR


async def test_upsert_stores_price_and_category_for_search_filters():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    client = _fake_genai_client()
    product_id = uuid.uuid4()

    await upsert_product_embedding(
        session,
        client,
        "gemini-embedding-001",
        {
            "product_id": str(product_id),
            "name": "Gouda",
            "description": "Aged cheese",
            "price": 12.5,
            "category_name": "Dairy",
        },
        DIMENSIONS,
    )

    added = session.add.call_args.args[0]
    assert added.price == 12.5
    assert added.category_name == "Dairy"


async def test_upsert_updates_existing_row_in_place():
    session = AsyncMock()
    existing = ProductEmbedding(
        product_id=uuid.uuid4(), name="Old name", description="old", embedding=[0.0] * 1536
    )
    session.get = AsyncMock(return_value=existing)
    session.add = MagicMock()
    client = _fake_genai_client()

    await upsert_product_embedding(
        session,
        client,
        "gemini-embedding-001",
        {"product_id": str(existing.product_id), "name": "New name", "description": "new"},
        DIMENSIONS,
    )

    session.add.assert_not_called()
    assert existing.name == "New name"
    assert existing.description == "new"
    assert existing.embedding == FAKE_VECTOR


async def test_embed_text_requests_the_configured_output_dimensionality():
    """STR-161b: gemini-embedding-001 natively outputs 3072 dims -- this is
    the one call site that actually keeps product_embeddings at 1536 (via
    Matryoshka truncation) rather than the model's native size, see
    config.py's embedding_dimensions."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    client = _fake_genai_client()

    await upsert_product_embedding(
        session, client, "gemini-embedding-001", {"product_id": str(uuid.uuid4()), "name": "x"}, DIMENSIONS
    )

    call_kwargs = client.aio.models.embed_content.call_args.kwargs
    assert call_kwargs["config"].output_dimensionality == DIMENSIONS


async def test_delete_product_embedding_removes_existing_row():
    session = AsyncMock()
    existing = ProductEmbedding(product_id=uuid.uuid4(), name="Gone", description=None, embedding=[0.0] * 1536)
    session.get = AsyncMock(return_value=existing)
    session.delete = AsyncMock()

    await delete_product_embedding(session, {"product_id": str(existing.product_id)})

    session.delete.assert_awaited_once_with(existing)


async def test_delete_product_embedding_is_a_noop_if_never_embedded():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.delete = AsyncMock()

    await delete_product_embedding(session, {"product_id": str(uuid.uuid4())})

    session.delete.assert_not_awaited()


async def test_handle_product_deleted_skips_already_processed_event():
    session = AsyncMock()
    session.get = AsyncMock(return_value=ProcessedEvent(event_id=uuid.uuid4()))
    session.delete = AsyncMock()
    session.add = MagicMock()

    await handle_product_deleted(session, uuid.uuid4(), {"product_id": str(uuid.uuid4())})

    session.delete.assert_not_awaited()
    session.add.assert_not_called()


async def test_handle_product_updated_skips_already_processed_event():
    session = AsyncMock()
    session.get = AsyncMock(return_value=ProcessedEvent(event_id=uuid.uuid4()))
    session.add = MagicMock()
    client = _fake_genai_client()

    await handle_product_updated(
        session, client, "gemini-embedding-001", DIMENSIONS, uuid.uuid4(), {"product_id": str(uuid.uuid4()), "name": "x"}
    )

    client.aio.models.embed_content.assert_not_awaited()
    session.add.assert_not_called()
