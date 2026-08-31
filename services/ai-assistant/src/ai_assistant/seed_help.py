"""One-shot: (re)build the `help_chunks` table from `help/*.md`.

Run after `docker compose up -d` (and after `alembic upgrade head` has
created the table), or any time the FAQ / policy docs change:

    docker compose exec ai-assistant uv run python -m ai_assistant.seed_help

No event pipeline backs this table (policies change rarely) — this script
is the whole update path. See scripts/seed-help-docs.sh for the wrapper.
"""

import asyncio
import logging
from pathlib import Path

from google import genai

from ai_assistant.config import load_settings
from ai_assistant.db import make_session_factory
from ai_assistant.help import reindex_help_docs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_assistant.seed_help")

_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "help"


async def _main() -> None:
    settings = load_settings()
    session_factory = make_session_factory(settings.database_url)
    client = genai.Client(
        enterprise=True, project=settings.gcp_project, location=settings.gcp_location
    )

    async with session_factory() as session:
        count = await reindex_help_docs(
            session,
            client,
            settings.embedding_model,
            settings.embedding_dimensions,
            _DOCS_DIR,
        )
        await session.commit()

    logger.info("Reindexed %d help chunk(s) from %s", count, _DOCS_DIR)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
