#!/bin/sh
# Process launcher for the catalog service. Deploy-target agnostic (Kubernetes,
# docker-compose, plain `docker run`, PaaS).
#
# 12-factor: starts one web process, nothing else.
#   * No waiting for backing services -- the app fails fast in
#     catalog.main.lifespan (and /ready reports it) and the orchestrator
#     restarts / depools it.
#   * No migrations -- that is a separate release-phase admin process:
#         <run-image> alembic upgrade head
#
# Concurrency is one uvicorn process per container; scale out with replicas
# (HPA), not with in-container workers.
#
# Any argument is exec'd as-is instead of the server (the migration command
# above, `sh` for debugging, ...).
set -eu

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

# RELOAD=1 => hot reload against the src bind mount (local dev only).
reload=
[ "${RELOAD:-0}" = "1" ] && reload=--reload

exec uvicorn catalog.asgi:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
    $reload
