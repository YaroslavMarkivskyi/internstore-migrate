#!/usr/bin/env bash
# (Re)builds the FAQ / policy embeddings the shopping agent's `search_help`
# tool retrieves from.
#
# Source of truth is services/ai-assistant/help/*.md — one `##` section per
# retrievable chunk. Unlike product embeddings there is no Kafka event
# backing this table (policies change rarely), so this script is the whole
# update path: run it once after `docker compose up -d`, and again any time
# the help docs change. Deterministic chunk ids mean re-runs upsert in
# place; removed sections are deleted.
#
# Requires: docker compose, with the ai-assistant service up and its
# `alembic upgrade head` (which creates help_chunks) already applied.
set -euo pipefail

docker compose exec -T ai-assistant uv run python -m ai_assistant.seed_help
