from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from security.authz import AuthzClient
from security.config import Settings, load_settings
from security.db import make_session_factory
from security.observability import setup_observability
from security.routers import hardware, users, visit_log, warehouses


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_observability("security")

    app = FastAPI(title="security")
    FastAPIInstrumentor.instrument_app(app)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.authz_client = AuthzClient(settings.opa_url)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(hardware.router)
    app.include_router(users.router)
    app.include_router(visit_log.router)
    app.include_router(warehouses.router)

    return app
