from fastapi import FastAPI

from orders.config import Settings, load_settings
from orders.db import make_session_factory
from orders.inventory_client import InventoryClient
from orders.routers import cart, checkout, orders


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="orders")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.inventory_client = InventoryClient(settings.inventory_base_url, settings.inventory_timeout_seconds)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(cart.router)
    app.include_router(checkout.router)
    app.include_router(orders.router)

    return app
