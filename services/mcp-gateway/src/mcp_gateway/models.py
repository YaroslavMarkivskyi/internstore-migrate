import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mcp_gateway.db import Base

# STR-161b: must match ai-assistant's own EMBEDDING_DIMENSIONS exactly —
# see that module for the full rationale (Gemini's gemini-embedding-001
# truncated from its native 3072 dims down to 1536 via Matryoshka
# Representation Learning, kept at 1536 deliberately rather than resized).
EMBEDDING_DIMENSIONS = 1536


class ProductEmbedding(Base):
    """Read-only mirror of ai-assistant's own product_embeddings table (see
    services/ai-assistant/src/ai_assistant/models.py) — same database
    (AI_DB_URL), same schema, kept in sync by ai-assistant's catalog-events
    consumer. The Gateway never writes here; search_products just reuses
    the pgvector index ai-assistant already maintains instead of standing up
    a second embedding store."""

    __tablename__ = "product_embeddings"

    product_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # STR-146: added for search_products' price/category filters — populated
    # from ProductUpdated's own `price`/`category_name` fields (see
    # ai-assistant's embeddings.upsert_product_embedding).
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(15), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
