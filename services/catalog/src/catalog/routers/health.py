from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from catalog.lifecycle import ping_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up. No dependency checks -- a failing
    dependency should not get the pod killed and restarted."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    """Readiness: the service can actually serve requests. Returns 503 when the
    database is unreachable, so the orchestrator pulls this instance out of
    rotation instead of routing 500s to it."""
    try:
        await ping_database(request.app.state.session_factory)
    except (TimeoutError, OSError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
