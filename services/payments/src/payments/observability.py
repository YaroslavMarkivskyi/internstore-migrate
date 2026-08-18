"""Structured JSON logging + OpenTelemetry SDK setup (STR-158b).

Duplicated per-service rather than a shared internal package — this repo has
no shared-library mechanism between services (every service is an
independent `uv` project with its own venv/lockfile; see the k8s manifests'
per-service duplication of things like `catalog_client.py`-style HTTP
clients for the same pattern already established elsewhere). A ~100-line
module is cheaper than introducing one for this.

Logging: hand-rolled JSON formatter, not structlog/python-json-logger (a
real decision, not a default — see k8s/base/observability/README.md's
"Phase 2 scope" note and this repo's consistent smallest-footprint
preference). Every line carries service_name (matches the label Loki's
queries expect, see k8s/base/observability/grafana/configmap-datasources.yaml's
derivedFields) and, inside a traced request, trace_id/span_id — that's what
makes Grafana's Tempo<->Loki click-through actually work.

Tracing: exports to the Phase 1 Alloy collector (k8s/base/observability/alloy)
over OTLP/gRPC. HTTPXClientInstrumentor patches httpx at the transport level,
so it propagates W3C traceparent into every outbound call this service makes
— including the ones that build their own `{"X-Internal-Token": ...}` headers
dict by hand (mcp_client.py, activities.py, etc.) — without touching those
call sites or their header dicts at all; traceparent and X-Internal-Token
are different header keys, added by two different layers, never colliding.

Metrics: a MeterProvider set before FastAPIInstrumentor.instrument_app(app)
runs (see main.py) makes that instrumentation emit standard
request-count/latency/error-rate metrics for free — no extra code here.
record_kafka_lag is this module's one domain-specific metric hook: any
service's kafka.py calls it from inside run_consumer_loop after each
commit, and the ObservableGauge below reports whatever it last recorded per
(topic, consumer_group) on Mimir's next scrape. Same registry lives in
every service's copy of this module — there's no cross-service aggregation
here, each service reports only the lag its own consumer(s) see.
"""

import json
import logging
import os
import sys
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class _JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "service_name": self._service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Correlate with the active span, if any — the log<->trace half of
        # Phase 1's tracesToLogsV2/derivedFields correlation config.
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(service_name: str) -> None:
    """Points the root logger at a single JSON-lines stdout handler,
    replacing whatever default/uvicorn-configured handlers were there.
    Call once, at process startup, before any other logging call."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter(service_name))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # uvicorn.error/uvicorn.access configure their own handlers by default
    # (bypassing root) — strip those too so access logs come out as JSON
    # the same as application logs, instead of uvicorn's plain-text default.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True


def configure_tracing(service_name: str) -> TracerProvider:
    """OTLP/gRPC export to Alloy (k8s/base/observability/alloy) — same env-
    var convention OTel's own SDK already defines
    (OTEL_EXPORTER_OTLP_ENDPOINT), defaulting to Alloy's in-cluster Service
    DNS name the way every other service already defaults its own
    *_BASE_URL. Also instruments httpx process-wide so every outbound call
    this service makes propagates trace context — see module docstring."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://alloy:4317")
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
    return provider


_kafka_lag: dict[tuple[str, str], int] = {}


def record_kafka_lag(topic: str, group_id: str, lag: int) -> None:
    """Called from run_consumer_loop after each commit — see kafka.py.
    Last-value-wins per (topic, group_id); the ObservableGauge callback
    below reports whatever's here whenever Mimir's next scrape happens."""
    _kafka_lag[(topic, group_id)] = lag


def _observe_kafka_lag(_options: metrics.CallbackOptions):
    for (topic, group_id), lag in _kafka_lag.items():
        yield metrics.Observation(lag, {"topic": topic, "consumer_group": group_id})


def configure_metrics(service_name: str) -> MeterProvider:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://alloy:4317")
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint, insecure=True))
    provider = MeterProvider(resource=Resource.create({SERVICE_NAME: service_name}), metric_readers=[reader])
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter(service_name)
    meter.create_observable_gauge(
        "kafka_consumer_lag",
        callbacks=[_observe_kafka_lag],
        description="Messages behind the partition's high-water mark, per consumer group (STR-134).",
    )
    return provider


def setup_observability(service_name: str) -> None:
    """One call, at process startup, before the app/worker is built."""
    configure_logging(service_name)
    configure_tracing(service_name)
    configure_metrics(service_name)
