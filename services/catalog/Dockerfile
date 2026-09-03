# syntax=docker/dockerfile:1

# ---- Builder ---------------------------------------------------------------
# Pinned uv + Python base. uv is only needed to resolve/install deps, so it
# lives in the build stage and never ships in the runtime image.
FROM ghcr.io/astral-sh/uv:0.9-python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# 1. Install dependencies only, from the lockfile. This layer is cached until
#    pyproject.toml / uv.lock actually change. The cache mount keeps uv's
#    wheel cache across builds; the bind mounts avoid COPYing the manifests
#    into their own layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-install-project --no-dev

# 2. Install the project itself on top of the cached dependency layer.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ---- Runtime ------------------------------------------------------------------
FROM python:3.13-slim-bookworm

# Drop root.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

# Put the venv on PATH so `alembic` / `uvicorn` resolve without `uv run`.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

# The entrypoint runs preflight checks + migrations, then execs uvicorn as
# PID 1. Prod by default; set RELOAD=1 (see docker-compose.yml) for local dev.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
