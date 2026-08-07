from fastapi import FastAPI

from payments.config import Settings, load_settings
from payments.db import make_session_factory
from payments.routers import payments


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="payments", lifespan=None)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(payments.router)

    return app
