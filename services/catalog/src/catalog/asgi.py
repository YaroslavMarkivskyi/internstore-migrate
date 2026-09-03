"""uvicorn entrypoint: `uvicorn catalog.asgi:app`.

This module owns the process-wide setup that must happen exactly once — JSON
logging and the OpenTelemetry providers — before building the app. Keeping it
out of catalog.main.create_app is what lets the test suite call that factory
per-test without re-registering global providers.
"""

from catalog.main import create_app
from catalog.observability import setup_observability

setup_observability("catalog")

app = create_app()
