import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ai_assistant.db import Base

# STR-161b: originally OpenAI text-embedding-3-small's native size; kept at
# 1536 after the Gemini migration as a deliberate choice, not a leftover
# default — gemini-embedding-001 natively outputs 3072 dims, truncated to
# 1536 via Matryoshka Representation Learning (see config.py's
# embedding_dimensions and embeddings.py's embed_text). Column width is
# unchanged, but every row still had to be re-embedded: OpenAI's and
# Gemini's embedding spaces aren't numerically compatible even at matching
# dimensionality (see README's "Gemini migration" section).
EMBEDDING_DIMENSIONS = 1536


class ProductEmbedding(Base):
    """One row per Catalog product, kept in sync by the catalog-events
    consumer (ProductUpdated). A separate database from Catalog's own —
    this service never touches Catalog's tables directly, only the
    event-driven copy of {name, description, price, temperatures, category}
    it needs for RAG."""

    __tablename__ = "product_embeddings"

    product_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # STR-146: added for the shopping agent's search_products price/category
    # filters (see mcp-gateway's ProductSearchClient, which mirrors this
    # table read-only) — not used for embedding text or RAG matching itself.
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(15), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HelpChunk(Base):
    """One retrievable chunk of customer-facing FAQ / policy text (see
    help/*.md). Rebuilt in place by ai_assistant.seed_help; read by
    mcp-gateway's search_help tool (same AI_DB_URL). `chunk_id` is
    uuid5(source + heading + ordinal) so re-seeding upserts."""

    __tablename__ = "help_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    heading: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcessedEvent(Base):
    """Dedup ledger for the catalog-events consumer's at-least-once
    delivery — same shape as Inventory's (see
    services/inventory/src/inventory/models.py). The chat-events consumer
    doesn't need one: a redelivered CustomerMessageSent just means the
    customer gets an extra AI reply, not a corrupted embedding row, and rate
    limiting bounds the damage — the same severity trade-off Notifications
    makes for its in-memory dedup, not Inventory's."""

    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
