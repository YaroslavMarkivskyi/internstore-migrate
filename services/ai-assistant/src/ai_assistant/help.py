"""Customer-facing FAQ / policy retrieval for the shopping agent.

`help/*.md` is the source of truth (delivery, returns, payment, cold chain,
accounts). Each `##` section is one self-contained retrievable chunk; a very
long section is sub-split on paragraph boundaries so no single chunk blows
the embedding input budget. Chunks land in the `help_chunks` table in
ai-db (see models.HelpChunk), embedded with the same model/dimensions as
product_embeddings so mcp-gateway's `search_help` tool can query the same
pgvector index (it mirrors the table read-only).

Unlike product embeddings there is no event pipeline — policies change
rarely, so `ai_assistant.seed_help` (a one-shot script, same spirit as
scripts/seed-embeddings.sh) rebuilds the table in place on demand.
"""

import uuid
from pathlib import Path

from google import genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_assistant.embeddings import embed_text
from ai_assistant.models import HelpChunk

# Deterministic chunk ids: uuid5(source + heading + ordinal) so re-seeding an
# edited doc upserts the same rows instead of churning them.
_CHUNK_NAMESPACE = uuid.UUID("6f4d1c2e-8a3b-5f7d-9e1a-2c4b6d8f0a11")

# Character budget for one chunk's text before it is split further. Well
# above any current section; a guard, not a tuning knob.
_CHUNK_CHAR_BUDGET = 1500


def _chunk_id(source: str, heading: str, ordinal: int) -> uuid.UUID:
    return uuid.uuid5(_CHUNK_NAMESPACE, f"{source}::{heading}::{ordinal}")


def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split one markdown doc into retrievable chunks — one per `##` section,
    sub-split by paragraph when a section exceeds `_CHUNK_CHAR_BUDGET`. The
    `# ` title and any preamble before the first `##` are dropped. Returns
    dicts of {chunk_id, source, heading, content, ordinal}."""
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_heading is not None:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_heading, body))

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_heading = line[3:].strip()
            current_lines = []
        elif line.startswith("# "):
            continue
        else:
            current_lines.append(line)
    flush()

    chunks: list[dict] = []
    for heading, body in sections:
        parts = _split_to_budget(body)
        for ordinal, part in enumerate(parts):
            chunks.append(
                {
                    "chunk_id": _chunk_id(source, heading, ordinal),
                    "source": source,
                    "heading": heading,
                    "content": part,
                    "ordinal": ordinal,
                }
            )
    return chunks


def _split_to_budget(body: str) -> list[str]:
    if len(body) <= _CHUNK_CHAR_BUDGET:
        return [_normalise(body)]
    parts: list[str] = []
    buffer: list[str] = []
    for paragraph in body.split("\n\n"):
        candidate = "\n\n".join([*buffer, paragraph])
        if buffer and len(candidate) > _CHUNK_CHAR_BUDGET:
            parts.append(_normalise("\n\n".join(buffer)))
            buffer = [paragraph]
        else:
            buffer.append(paragraph)
    if buffer:
        parts.append(_normalise("\n\n".join(buffer)))
    return parts


def _normalise(text: str) -> str:
    """Collapse the markdown source's hard-wrapped lines back into flowing
    paragraphs — the embedding and the model both read prose, not the 72-col
    wrapping the .md file is authored in."""
    paragraphs = [" ".join(block.split()) for block in text.split("\n\n")]
    return "\n\n".join(p for p in paragraphs if p)


async def reindex_help_docs(
    session: AsyncSession,
    client: genai.Client,
    model: str,
    dimensions: int,
    docs_dir: Path,
) -> int:
    """Rebuild `help_chunks` in place from every `*.md` under `docs_dir`:
    upsert the current chunks, delete any row whose chunk_id is no longer
    produced (a removed or renamed section). Returns the chunk count."""
    seen: set[uuid.UUID] = set()
    for path in sorted(docs_dir.glob("*.md")):
        chunks = chunk_markdown(path.read_text(encoding="utf-8"), path.name)
        for chunk in chunks:
            seen.add(chunk["chunk_id"])
            vector = await embed_text(
                client, model, f"{chunk['heading']}\n{chunk['content']}", dimensions
            )
            existing = await session.get(HelpChunk, chunk["chunk_id"])
            if existing is None:
                session.add(
                    HelpChunk(
                        chunk_id=chunk["chunk_id"],
                        source=chunk["source"],
                        heading=chunk["heading"],
                        content=chunk["content"],
                        embedding=vector,
                    )
                )
            else:
                existing.source = chunk["source"]
                existing.heading = chunk["heading"]
                existing.content = chunk["content"]
                existing.embedding = vector

    stale = await session.execute(select(HelpChunk).where(HelpChunk.chunk_id.notin_(seen)))
    for row in stale.scalars():
        await session.delete(row)

    return len(seen)


async def search_help(
    session: AsyncSession,
    client: genai.Client,
    model: str,
    dimensions: int,
    query: str,
    limit: int,
) -> list[dict]:
    vector = await embed_text(client, model, query, dimensions)
    result = await session.execute(
        select(HelpChunk.source, HelpChunk.heading, HelpChunk.content)
        .order_by(HelpChunk.embedding.l2_distance(vector))
        .limit(limit)
    )
    return [{"source": row.source, "heading": row.heading, "content": row.content} for row in result]
