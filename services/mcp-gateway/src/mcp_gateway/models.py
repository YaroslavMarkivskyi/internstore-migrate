import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mcp_gateway.db import Base

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
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
