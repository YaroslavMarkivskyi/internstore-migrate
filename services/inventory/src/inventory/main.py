from fastapi import FastAPI

from inventory.config import Settings, load_settings
from inventory.db import make_session_factory
from inventory.routers import items, stocks


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="inventory")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(stocks.router)
    app.include_router(items.router)

    return app
