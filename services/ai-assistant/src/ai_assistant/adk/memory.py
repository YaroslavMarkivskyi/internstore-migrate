"""Cross-session memory for the shopping agent, backed by the same pgvector
store the product / help embeddings already live in.

`add_session_to_memory` distils durable customer facts from a finished
conversation with one Gemini call ("Is lactose intolerant.", "Shops for a
household of four."), embeds each and stores it scoped to (app_name,
user_id). ADK's `PreloadMemoryTool` calls `search_memory` on every turn and
injects the nearest few into the prompt, so the next conversation — days
later, a fresh session — already knows them.

A demo-scale implementation of ADK's `BaseMemoryService`: no summarisation
windows, no TTLs, exact-text dedup only. Everything here is best-effort —
memory never blocks or breaks a reply.
"""

import logging

from google import genai
from google.adk.memory.base_memory_service import (
    BaseMemoryService,
    SearchMemoryResponse,
)
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.sessions import Session
from google.genai import types as genai_types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ai_assistant.embeddings import embed_text
from ai_assistant.models import AgentMemory

logger = logging.getLogger(__name__)

_SEARCH_LIMIT = 5
# pgvector L2 distance over 1536-dim unit-ish embeddings — past this the
# "match" is noise. Same order of magnitude as the product search cutoff.
_MAX_DISTANCE = 0.85

_EXTRACT_PROMPT = """\
From the conversation below, extract durable facts about this customer that \
would help personalise future shopping conversations — dietary needs, \
allergies, household size, preferred categories or brands, budget habits. \
One fact per line, each a short standalone statement ("Is lactose \
intolerant.", "Usually shops for a family of four."). Only facts the \
customer stated or clearly implied about themselves. Do NOT include one-off \
requests, anything about a specific order, or anything the assistant said. \
If there are no such facts, reply with exactly: NONE"""


def _transcript(session: Session) -> str:
    lines: list[str] = []
    for event in session.events:
        if not event.content or not event.content.parts:
            continue
        text = "".join(p.text for p in event.content.parts if getattr(p, "text", None))
        if not text:
            continue
        who = "Customer" if event.author == "user" else "Assistant"
        lines.append(f"{who}: {text}")
    return "\n".join(lines)


class PgVectorMemoryService(BaseMemoryService):
    def __init__(
        self,
        session_factory: async_sessionmaker,
        genai_client: genai.Client,
        *,
        chat_model: str,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> None:
        self._session_factory = session_factory
        self._genai = genai_client
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._dimensions = embedding_dimensions

    async def _extract_facts(self, transcript: str) -> list[str]:
        if not transcript.strip():
            return []
        response = await self._genai.aio.models.generate_content(
            model=self._chat_model,
            contents=f"{_EXTRACT_PROMPT}\n\n---\n{transcript}\n---",
        )
        raw = (response.text or "").strip()
        if not raw or raw.upper() == "NONE":
            return []
        facts = [line.strip("-* \t") for line in raw.splitlines()]
        return [f for f in facts if f and f.upper() != "NONE"][:10]

    async def add_session_to_memory(self, session: Session) -> None:
        try:
            facts = await self._extract_facts(_transcript(session))
            if not facts:
                return
            async with self._session_factory() as db:
                existing = set(
                    (
                        await db.execute(
                            select(AgentMemory.text).where(
                                AgentMemory.app_name == session.app_name,
                                AgentMemory.user_id == session.user_id,
                            )
                        )
                    ).scalars()
                )
                for fact in facts:
                    if fact in existing:
                        continue
                    vector = await embed_text(self._genai, self._embedding_model, fact, self._dimensions)
                    db.add(
                        AgentMemory(
                            app_name=session.app_name,
                            user_id=session.user_id,
                            text=fact,
                            embedding=vector,
                        )
                    )
                await db.commit()
        except Exception:  # noqa: BLE001 - memory is best-effort, never break a reply
            logger.warning("add_session_to_memory failed for user %s", session.user_id, exc_info=True)

    async def search_memory(self, *, app_name: str, user_id: str, query: str) -> SearchMemoryResponse:
        try:
            vector = await embed_text(self._genai, self._embedding_model, query, self._dimensions)
            distance = AgentMemory.embedding.l2_distance(vector)
            async with self._session_factory() as db:
                rows = (
                    await db.execute(
                        select(AgentMemory.text, AgentMemory.created_at, distance.label("d"))
                        .where(AgentMemory.app_name == app_name, AgentMemory.user_id == user_id)
                        .where(distance < _MAX_DISTANCE)
                        .order_by(distance)
                        .limit(_SEARCH_LIMIT)
                    )
                ).all()
        except Exception:  # noqa: BLE001
            logger.warning("search_memory failed for user %s", user_id, exc_info=True)
            return SearchMemoryResponse()

        return SearchMemoryResponse(
            memories=[
                MemoryEntry(
                    author="memory",
                    timestamp=created_at.isoformat() if created_at else None,
                    content=genai_types.Content(role="user", parts=[genai_types.Part(text=text)]),
                )
                for text, created_at, _ in rows
            ]
        )
