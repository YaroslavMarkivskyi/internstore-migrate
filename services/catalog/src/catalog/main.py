from fastapi import FastAPI

from catalog.config import Settings, load_settings
from catalog.db import make_session_factory
from catalog.routers import categories, products


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="catalog")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(categories.router)
    app.include_router(products.router)

    return app
