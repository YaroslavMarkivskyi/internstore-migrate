from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from payments.authz import AuthzClient
from payments.config import Settings, load_settings
from payments.db import make_session_factory
from payments.observability import setup_observability
from payments.routers import payments


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_observability("payments")

    app = FastAPI(title="payments", lifespan=None)
    FastAPIInstrumentor.instrument_app(app)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.authz_client = AuthzClient(settings.opa_url)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(payments.router)

    return app
