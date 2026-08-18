import logging

from fastapi import Request
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor

logger = logging.getLogger(__name__)


async def connect_temporal_client(temporal_host: str) -> Client | None:
    """Best-effort connect, same reasoning as Orders' other peer-service
    clients (inventory_client, catalog_client) having no `depends_on` —
    Orders should still boot and serve the existing /checkout fine even if
    Temporal is briefly unavailable. Unlike an HTTP client, temporalio's
    Client.connect actually dials on connect rather than lazily on first
    call, so a startup failure here is caught and turned into `None` —
    routers/checkout_v2.py 503s on a None client instead of the whole app
    failing to start.

    STR-158b: TracingInterceptor here covers this client's own
    start_workflow span (the checkout-saga trace's root hop into Temporal).
    checkout-workflow-worker needs the same interceptor registered
    separately on its own Client.connect (see its worker.py) — that's a
    different process with its own client, not this one.
    """
    try:
        return await Client.connect(temporal_host, interceptors=[TracingInterceptor()])
    except Exception:
        logger.exception("Failed to connect to Temporal at %s — /checkout/v2 will 503 until it's reachable", temporal_host)
        return None


def get_temporal_client(request: Request) -> Client | None:
    # getattr, not a plain attribute access: tests build the app without
    # running FastAPI's lifespan (httpx's ASGITransport doesn't invoke it,
    # same reason fake_inventory_client/fake_catalog_client are wired via
    # app.dependency_overrides instead) — routers/checkout_v2.py's tests
    # override this dependency directly rather than relying on app.state.
    return getattr(request.app.state, "temporal_client", None)
