# Observability (STR-183 Phase 1): LGTM stack + Grafana Alloy

Loki (logs), Grafana (dashboards), Tempo (traces), Mimir (metrics) — the "LGTM" stack — plus
Grafana Alloy as the single OTLP collector every service's OpenTelemetry SDK will export to
once Phase 2 (service instrumentation, tracked as a separate follow-up ticket — see
"Phase 2 scope" below) lands. Follows the same per-component directory pattern STR-144
established for the rest of `k8s/base/`: one directory per component, each with its own
`kustomization.yaml`.

```text
observability/
  loki/        # log storage — filesystem-backed, single-binary mode
  tempo/       # trace storage — filesystem-backed, single-binary mode
  mimir/       # metrics storage — filesystem-backed, monolithic mode
  grafana/     # dashboards + datasources (Loki/Tempo/Mimir pre-wired with correlation)
  alloy/       # OTLP collector (traces/metrics) — grpc :4317, http :4318
  alloy-logs/  # log collector — DaemonSet, see its own section below
```

## Logs: a separate collector, not the OTLP one

`alloy/configmap.yaml`'s pipeline has a `logs = [otelcol.exporter.loki...]` route wired up, but
nothing ever feeds it: every service's `observability.py` (Phase 2, STR-158b) only ever
configures a stdout JSON handler, never an OTLP log exporter. Rather than touching all 12+
services' `observability.py` to add one, `alloy-logs` collects the exact same JSON lines every
service already writes to stdout, from outside the app entirely — the same way
`kubectl logs`/`docker logs` already do — via a `DaemonSet` (one collector per node) using
Alloy's `loki.source.kubernetes` component, which reads container logs through the Kubernetes
API rather than tailing node-local log files, so it needs no `hostPath` mount or privileged
access — just a read-only `ClusterRole` scoped to `pods`/`pods/log` (see `alloy-logs/rbac.yaml`).

A `DaemonSet`, not a sidecar added to each of the 12+ domain-service `Deployment`s: one
collector per node discovers every Pod via the Kubernetes API and reads all of them, instead of
duplicating a log-shipping container into every service's pod spec — same centralization
argument the OTLP `alloy` Deployment already makes for traces/metrics.

## Storage backend: filesystem/PVC, not GCS

Confirmed with the ticket owner before building: every component uses local filesystem storage
on a PVC (`local-path` on kind, GKE's default `standard-rwo` StorageClass once this lands in the
`gcp` overlay), not a GCS object-storage backend. This matches the project's established
demo-scale pattern (STR-144's capacity findings, STR-149/150's cost constraints) — GCS backends
for all three of Loki/Tempo/Mimir would mean three sets of bucket + IAM + service-account wiring
for a stack that only needs to survive a single demo session. Each component gets a 5Gi PVC
(1Gi for Grafana's own SQLite state), retention pinned to 7 days across the board
(`limits_config.retention_period` in Loki, `compactor.compaction.block_retention` in Tempo,
`compactor_blocks_retention_period` in Mimir) — comfortably past any single demo, cheap to
re-provision from empty otherwise.

**Documented future upgrade**: if this stack ever needs to outlive a demo-session teardown (e.g.
an always-on staging environment), swap each component's `filesystem`/`local` storage block for
its GCS backend equivalent (`common.storage.backend: gcs` for Mimir, `storage.trace.backend: gcs`
for Tempo, `storage_config.gcs` for Loki) and drop the PVCs — no other manifest here changes
shape.

## Local (kind) first, then GCP

Built and verified against a local `kind` cluster before anything was added to the `gcp`
overlay — same sequencing as STR-144→154, STR-149→150, STR-156→182. Because storage stays
filesystem/PVC-backed (not GCS) per the decision above, the `gcp` overlay needs **no** special
handling for this directory: it's pulled in automatically via `resources: [../../base]`, runs as
an ordinary in-cluster StatefulSet/PVC set on GKE exactly like it does on kind. This is unlike
`postgres-*`/`redis`/`kafka`/`minio`, which the `gcp` overlay's `delete-infra` component strips
in favor of managed GCP services — observability isn't migrated to a managed equivalent (no
Cloud-managed Loki/Tempo/Mimir/Grafana in this project's GCP footprint) and doesn't need to be
at this scale.

## Grafana correlation (tracesToLogsV2 / tracesToMetrics)

`grafana/configmap-datasources.yaml` pre-provisions all three datasources wired together per
Grafana's own correlation config, verified live end-to-end against a real OTLP trace/log pushed
through Alloy on a scratch kind cluster:

- **Loki → Tempo**: `derivedFields` on the Loki datasource matches `trace_id=<hex>` in a log
  line's body and turns it into a clickable link to that trace in Tempo.
- **Tempo → Loki**: `tracesToLogsV2` on the Tempo datasource jumps from a selected span to its
  service's Loki logs in the span's time window (±5m).
- **Tempo → Mimir**: `tracesToMetrics` + `serviceMap` jump from a span to Tempo's own
  span-metrics (RED rate/error/duration, generated by Tempo's `metrics_generator` — see below)
  and the derived service graph, both stored in Mimir.

All three legs were confirmed working by hand: pushed a synthetic OTLP trace + log through
Alloy, queried each hop back out through Grafana's own datasource-proxy endpoints (not just the
components directly) — `Loki → derivedFields regex match`, `Tempo → trace fetch`,
`Mimir → traces_spanmetrics_calls_total` all returned the expected data.

## A real bug found and fixed via live verification

**Mimir's per-tenant ring, even single-instance**: `blocks_storage`/`ingester`/`store_gateway`
all default to `replication_factor: 3`, which a lone Mimir pod can never satisfy — every query
failed with `"too many unhealthy instances in the ring"` until `ingester.ring.replication_factor`
and `store_gateway.sharding_ring.replication_factor` were pinned to `1` in
`mimir/configmap.yaml` (the `ruler` ring has no such setting — its ring doesn't support a
configurable replication factor at all, unlike the other two).

**Mimir tenant routing survives `multitenancy_enabled: false`**: that flag disables *auth
enforcement*, not tenant routing — a request with no `X-Scope-OrgID` header lands in a default
"anonymous" tenant, but Tempo's `metrics_generator` always sends its remote-write with
`X-Scope-OrgID: single-tenant` (Tempo requires *some* tenant ID internally even outside real
multi-tenancy). The two landed in different tenants, so Grafana's Mimir datasource could see
neither the app's future OTel metrics (pushed by Alloy under "anonymous") nor Tempo's
span-metrics (under "single-tenant"). Fixed by pinning both writers to the same explicit tenant:
`alloy/configmap.yaml`'s `prometheus.remote_write` sends `X-Scope-OrgID: single-tenant`, and
`grafana/configmap-datasources.yaml`'s Mimir datasource sends the same header on every query via
`httpHeaderName1`/`secureJsonData.httpHeaderValue1`.

## Resource footprint (measured, not estimated)

Per the ticket's explicit ask — this stack's cost has to be measured against STR-180's demo-
session cost model, not left as a guess. Measured on a scratch single-node `kind` cluster
(`kindest/node:v1.36.1`, this environment's Docker host), applying only this directory plus the
same `local` overlay resource patches every other workload gets (`reduce-cpu-request.yaml`,
`bump-memory-limit.yaml`), with `metrics-server` installed for `kubectl top`.

**Scheduling footprint** (`requests` — what the cluster must have free to schedule this stack;
`limits` — the ceiling under load, after `bump-memory-limit.yaml`'s blanket 1536Mi patch, which
is a bump for every component here same as it is everywhere else in this repo):

| Component | CPU request | Mem request | CPU limit | Mem limit (local-patched) |
|---|---|---|---|---|
| Loki      | 50m | 128Mi | 500m | 1536Mi |
| Tempo     | 50m | 128Mi | 500m | 1536Mi |
| Mimir     | 50m | 256Mi | 750m | 1536Mi |
| Grafana   | 50m | 128Mi | 250m | 1536Mi |
| Alloy     | 50m |  64Mi | 250m | 1536Mi |
| **Total** | **250m** | **704Mi** | **2250m** | **7680Mi** |

(Base, pre-local-overlay-patch requests are higher per-component — 100-150m CPU each — but the
same blanket `reduce-cpu-request.yaml` patch that already applies to every other Deployment/
StatefulSet in this repo cuts main-container CPU requests to 50m so the stack schedules on a
small kind node; see `k8s/README.md`'s "Resource requests on a small local node" for why that
patch exists at all.)

**Actual usage** — two measurement points, both on a scratch single-node `kind` cluster with
`kubectl top`:

| Component | Idle/smoke-test (Phase 1) | Under instrumented load (STR-158b) |
|---|---|---|
| Loki      | 4m / 45Mi | 5m / 45Mi |
| Tempo     | 5m / 61Mi | 5m / 56Mi |
| Mimir     | 3m / 35Mi | 4m / 51Mi |
| Grafana   | 3m / 53Mi | 1m / 54Mi |
| Alloy     | 5m / 43Mi | 7m / 62Mi |
| **Total** | **20m / 237Mi** | **22m / 268Mi** |

The "under load" column (STR-158b) replays ~2 minutes of steady OTLP traffic through Alloy —
600 traces (5 spans each, matching the real checkout-saga trace's shape), 1,800 JSON log lines,
and a metrics batch across all 13 instrumented services every 2s — roughly what 12+ services
each handling a few requests/second would generate at this project's demo scale. Node-level:
`kubectl top node` read **137m CPU / 1006Mi memory** total (stack + kube-system) at the end of
that run, essentially unchanged from Phase 1's 144m/1097Mi idle reading.

**Reading these numbers against STR-180's cost model**: the *scheduling* floor this stack adds
is still 250m CPU / 704Mi memory of `requests` — unchanged by instrumentation, since that floor
was always sized for the collector infra itself, not the traffic through it. *Actual* usage
under a realistic demo-scale instrumented load (22m CPU / 268Mi memory) is barely above the
idle/smoke-test baseline (20m CPU / 237Mi memory) — the LGTM stack's per-signal ingest cost at
this project's traffic volume is small enough that it doesn't meaningfully move the needle
against the 250m/704Mi `requests` floor already budgeted. Disk grows with retention (7 days
configured, see Storage backend section above) rather than with this snapshot's few minutes of
traffic, so it isn't re-measured here — the 5Gi/5Gi/5Gi/1Gi PVC sizing already accounts for
sustained demo-session volume, not a 2-minute burst.

## Ports

| Service | Port(s) | Purpose |
|---|---|---|
| `alloy`   | 4317 (grpc), 4318 (http), 12345 (own UI/health) | OTLP ingest — point every service's OTel SDK here |
| `tempo`   | 3200 (http/query), 4317/4318 (OTLP, used by Alloy's trace exporter) | trace storage/query |
| `loki`    | 3100 (http), 9096 (grpc) | log storage/query |
| `mimir`   | 9009 (http) | metrics storage/query, `/prometheus` sub-path for PromQL |
| `grafana` | 3000 (http), NodePort 30030 → host 3000 via `k8s/kind-config.yaml` | dashboards |
| `alloy-logs` (DaemonSet) | 12345 (own UI/health) — no OTLP ports, it's a log collector, not a receiver | reads every Pod's stdout via the Kubernetes API, pushes to `loki` |

## Phase 2 (STR-158b): service instrumentation — delivered as its own ticket

Checked before scoping Phase 1: current logging across services was plain stdlib
`logging.basicConfig()`, not structured JSON — no `structlog` or JSON formatter anywhere in
`services/`. That meant Phase 2 wasn't "add a Loki shipper on top of existing structured logs" —
it was a structured-logging migration across 12+ services *plus* OTel SDK traces/metrics
instrumentation *plus* the two named cross-service trace chains. That's a different risk
profile from Phase 1's purely-additive infra deployment (touches real application code in every
service), which is why it shipped as its own ticket (STR-158b) rather than being force-fit into
this one — confirmed with the ticket owner at the time.

STR-158b delivered: a hand-rolled JSON logging + OTel SDK setup module (`observability.py`,
duplicated per-service — this repo has no shared internal Python package) across all 12 domain
services + checkout-workflow-worker; FastAPI + httpx auto-instrumentation everywhere; manual
spans for the shopping-agent chain (`chat.notify_shopping_agent` as the trace root, since a
WebSocket message has no ASGI span of its own; `mcp.tool.<name>` in MCP Gateway's tool
dispatcher) and the checkout-saga chain (`temporalio.contrib.opentelemetry.TracingInterceptor`,
confirmed to capture the compensation path's `release_stock`/`mark_order_rejected` as distinct
spans); the three named domain metrics (Kafka consumer lag, Temporal workflow outcomes,
Inventory concurrency-conflict rate); and three Grafana dashboards (shopping-agent chain,
checkout-saga chain, cross-service overview) provisioned the same way as this Phase's own
LGTM Pipeline Health dashboard. Both priority trace chains were live-verified end-to-end against
a real docker-compose stack + a scratch Tempo container — not assumed from code alone — which is
what caught this Phase's `derivedFields` regex bug (see above).

## STR-159b: live verification of the three domain metrics against real Mimir

STR-158b's three domain metrics were built against documented OTel→Prometheus naming
conventions but never confirmed against a real running Mimir (the implementing agent flagged
this explicitly as the most likely first failure point). This ticket closes that gap: the merged
Phase 2 stack was deployed to a scratch `kind` cluster (`k8s/build-images.sh` + `kubectl apply -k
k8s/overlays/local`, all 33 pods reaching Running/Ready), all three metric-producing conditions
were triggered for real, and each metric was queried directly out of Mimir via PromQL — not just
asserted from the exporter code.

**No naming mismatch found for any of the three metrics** — every name and label set Mimir
actually stores matches what the dashboards' panel queries (`grafana/configmap-dashboards.yaml`)
expect, exactly:

- `kafka_consumer_lag{topic, consumer_group}` — induced a real backlog by scaling
  `telemetry` to 0 replicas, producing ~8,000 real-shaped `ItemAdded` envelopes directly onto
  `inventory-events` (`kafka-console-producer` inside `kafka-0`, sized so draining would outlast
  the OTel SDK's 60s default metric-export interval — a smaller first attempt at 60/3000 messages
  fully drained before the next export tick and produced a false "still zero" read), then scaling
  `telemetry` back to 1. Confirmed both the real broker-side lag (`kafka-consumer-groups.sh
  --describe`) and Mimir's exported gauge moving together, e.g. broker lag 5226 next to
  `kafka_consumer_lag{topic="inventory-events",consumer_group="telemetry-inventory-events"} =
  6672` moments later (gauge is last-value-wins per commit, not a live tick, so the two don't
  match to the message — same behavior documented in `observability.py`).
- `checkout_workflow_outcomes_total{outcome}` — ran `scripts/k8s/test-temporal-saga.sh` (already
  adapted for this cluster by STR-145) against a throwaway in-cluster Firebase Auth emulator (this
  overlay has none of its own — same documented gap as `k8s/README.md`'s Mailpit workaround;
  stood up via `andreysenov/firebase-tools`, wired to `auth-backend` via a `FIREBASE_AUTH_EMULATOR_HOST`
  patch, torn down after). Both the happy path (`outcome="confirmed"`) and the payment-failure
  compensation path (`outcome="compensation_triggered"`) landed in Mimir under those exact label
  values, matching the dashboards' `sum(rate(checkout_workflow_outcomes_total[5m])) by (outcome)`.
- `inventory_concurrency_conflicts_total` — mirrored STR-150's manual 5-run concurrent-reservation
  test, but needed real concurrency, not 5 sequential-ish requests: 5 truly parallel
  `POST /stocks/reserve` calls against the same product (via `asyncio.gather`, minting the same
  internal HMAC token every service already trusts) didn't overlap enough to race; ~30 concurrent
  calls reliably did. Confirmed the counter increasing (58 → 101 across two bursts) and matching
  real `ConcurrencyConflict` retries in `inventory`'s own logs one-for-one.

**Dashboard panels confirmed rendering real data, not empty/no-data**: queried all three panel
expressions through Grafana's own datasource-proxy endpoint (`/api/datasources/proxy/uid/mimir/...`
— the same path a rendered panel hits, not a shortcut around it) immediately after each trigger.
All three returned non-empty vectors with the real values above once fresh events were within the
`rate()` queries' 5m windows.

**A real bug found, but out of this ticket's scope to fix**: `inventory`'s optimistic-concurrency
retry loop (`commands.run_with_retry`, `MAX_ATTEMPTS = 3`) correctly increments
`inventory_concurrency_conflicts_total` on every retry — including the ones that exhaust all 3
attempts — but the final `raise ConcurrencyConflict("exhausted retries")` on exhaustion has no
FastAPI exception handler, so it surfaces as an uncaught `500` instead of a handled `409`/`503`.
Confirmed live: heavier concurrency bursts (25-30 parallel reserves against one product) reliably
produced a mix of `200`s and `500`s, with the metric incrementing correctly on every one of them
regardless of the eventual HTTP status. This is an app-level error-handling gap in already-shipped
STR-150 code, not a metrics-naming or dashboard-query defect — flagged here rather than fixed,
per this ticket's explicit scope (verify the three metrics, don't redo STR-158b's or STR-150's
work).

**Also observed, not a defect**: under this verification's synthetic load (the ~8,000-message
Kafka burst and the 25-30-way concurrent-reservation bursts, run back to back on a single 4-core
kind node already hosting all 33 pods), Alloy's `prometheus.remote_write` queue to Mimir backed
up by several minutes at least once (`mimir-0` returned `500 context deadline exceeded` under the
combined load; Alloy retried per its own backoff policy). Every sample eventually landed intact
and under the correct name/labels — nothing was lost — but a burst this synthetically concentrated
produced longer end-to-end delivery latency than the stack sees under normal demo traffic. Worth
knowing if someone reproduces this verification and sees a metric appear to "stick" for a few
minutes before jumping to its real value — that's ingest backpressure on a small shared node, not
a broken exporter.
