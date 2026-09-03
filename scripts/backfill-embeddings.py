"""Throttled backfill of ai-assistant's product_embeddings table.

The catalog-events consumer embeds each ProductUpdated as it arrives; a bulk
catalogue seed floods that and trips the Vertex embedding quota (429), which
kills the consumer. This script walks the current catalogue and (re)embeds
every product one at a time with a pause between calls, so a demo seed lands
without needing the live event pipeline.

Run inside the ai-assistant container:
    docker compose exec -T ai-assistant sh -c \
      'cd /app && .venv/bin/python /app/../scripts/backfill-embeddings.py'
or, simpler, pipe it in:
    docker compose exec -T ai-assistant /app/.venv/bin/python - < scripts/backfill-embeddings.py

Env:
  CATALOG_URL   default http://catalog:8000
  EMBED_SLEEP   seconds between embed calls, default 5
  FORCE=1       re-embed every product, not just the missing ones
  PRUNE=1       first delete embedding rows for products no longer in catalog
"""

import asyncio
import os

import httpx
from sqlalchemy import delete, select

from ai_assistant.config import load_settings
from ai_assistant.db import make_session_factory
from ai_assistant.embeddings import upsert_product_embedding
from ai_assistant.models import ProductEmbedding
from google import genai

FORCE = os.environ.get("FORCE") == "1"
PRUNE = os.environ.get("PRUNE") == "1"

CATALOG_URL = os.environ.get("CATALOG_URL", "http://catalog:8000").rstrip("/")
SLEEP = float(os.environ.get("EMBED_SLEEP", "5"))


async def main() -> None:
    s = load_settings()
    genai_client = genai.Client(enterprise=True, project=s.gcp_project, location=s.gcp_location)
    session_factory = make_session_factory(s.database_url)

    async with httpx.AsyncClient(timeout=15) as http:
        cats = {c["id"]: c["name"] for c in (await http.get(f"{CATALOG_URL}/categories")).json()}
        products = (await http.get(f"{CATALOG_URL}/products")).json()

    live_ids = {p["id"] for p in products}
    async with session_factory() as db:
        done = {str(d) for d in (await db.execute(select(ProductEmbedding.product_id))).scalars()}
        if PRUNE:
            stale = [d for d in done if d not in live_ids]
            if stale:
                await db.execute(delete(ProductEmbedding).where(ProductEmbedding.product_id.in_(stale)))
                await db.commit()
                print(f"pruned {len(stale)} embedding row(s) for products no longer in the catalogue")
    if not FORCE:
        products = [p for p in products if p["id"] not in done]

    print(f"{len(products)} products to embed; {SLEEP}s between calls")
    ok = fail = 0
    for i, p in enumerate(products, 1):
        payload = {
            "product_id": p["id"],
            "name": p["name"],
            "description": p.get("description"),
            "price": p.get("price"),
            "min_temperature": p.get("min_temperature"),
            "max_temperature": p.get("max_temperature"),
            "category_name": cats.get(p["category_id"]),
        }
        try:
            async with session_factory() as db:
                await upsert_product_embedding(db, genai_client, s.embedding_model, payload, s.embedding_dimensions)
                await db.commit()
            ok += 1
            print(f"  [{i}/{len(products)}] ok   {p['name']}")
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"  [{i}/{len(products)}] FAIL {p['name']}: {type(exc).__name__} {str(exc)[:120]}")
            await asyncio.sleep(SLEEP * 3)  # back off harder on error (usually 429)
        await asyncio.sleep(SLEEP)

    print(f"\ndone: {ok} embedded, {fail} failed")


if __name__ == "__main__":
    asyncio.run(main())
