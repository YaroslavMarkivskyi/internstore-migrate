from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from catalog.config import Settings, load_settings
from catalog.lifecycle import build_state, shutdown, startup
from catalog.routers import categories, health, product_images, products


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await startup(app)
    try:
        yield
    finally:
        await shutdown(app)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application. Pure: no global/process-wide side effects, so
    tests can call it freely with their own Settings. Process-wide setup
    (logging, OpenTelemetry) lives in catalog.asgi, the uvicorn entrypoint."""
    app = FastAPI(title="catalog", lifespan=lifespan)
    build_state(app, settings or load_settings())
    for router in (health.router, categories.router, products.router, product_images.router):
        app.include_router(router)
    return app
