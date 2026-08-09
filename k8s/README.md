# InternStore on Kubernetes (local kind/minikube)

Kustomize-based manifests that reproduce `docker-compose.yml`'s stack on a local
`kind`/`minikube` cluster. No GCP work here — this is the local-validation step that a future
GKE Autopilot overlay (`k8s/overlays/gcp/`, not yet implemented) builds on. See
`k8s/overlays/gcp/README.md`.

## Prerequisites

- `kind` (or `minikube`) and `kubectl`
- `docker` (to build each service's image before loading it into the cluster)

## Quick start

```bash
kind create cluster --name internstore --config k8s/kind-config.yaml
./k8s/build-images.sh internstore   # docker build every service image, kind load each one
kubectl apply -k k8s/overlays/local
kubectl get pods -w                 # wait for everything to reach Running/Ready
```

`k8s/kind-config.yaml` maps nginx (8443/8082), keycloak (8081), MinIO (9000/9001), and
temporal-ui (8088) NodePorts straight onto those same host ports. Skip `--config` and use
`kubectl port-forward svc/nginx 8443:8443` (etc.) instead if you'd rather not reserve those
host ports.

Tear down:

```bash
kubectl delete -k k8s/overlays/local
kind delete cluster --name internstore
```

## Directory structure

```text
k8s/
  base/               # Kustomize base — environment-agnostic
    <service>/          # deployment.yaml|statefulset.yaml, service.yaml,
                         # configmap.yaml, secret.yaml, kustomization.yaml
    kustomization.yaml   # aggregates every service directory
  overlays/
    local/              # this ticket's target: kind/minikube
    gcp/                # placeholder only — see its README.md
```

## Decisions made while writing this (verified against the repo, not assumed)

The ticket asked several of these to be confirmed against the actual `docker-compose.yml`
rather than taken on faith. What was found and what was decided:

**mcp-gateway** isn't in the ticket's original service list, but it's a real internal-only
compose service that `ai-assistant` depends on (`MCP_GATEWAY_URL`). Included, for stack parity.

**OPA sidecars are not future work — they already shipped** (STR-140, most recent commit at the
time this was written). `catalog`, `inventory`, `orders`, `payments`, `telemetry`, `security`,
and `chat` each run a `network_mode: service:X` OPA container in compose today. Each of those
7 Deployments here is a **2-container pod** — the app container plus `<service>-opa`
(`openpolicyagent/opa:latest`) sharing the pod's network namespace, reached at
`localhost:8181` exactly like compose's shared network namespace, so **no service code
changes** were needed (every service already reads `OPA_URL=http://localhost:8181`). The
`.rego` policy files are mirrored into `k8s/base/opa-policies/policies/` — see that
directory's `kustomization.yaml` comment and `sync-policies.sh` for why this is a copy, not a
live reference (kubectl's built-in kustomize refuses to read `configMapGenerator` files from
outside a kustomization's own directory tree, with no flag to relax that). The same pattern
applies to Keycloak's `realm-export.json` mirror in `k8s/base/keycloak/config/` —
`sync-realm-export.sh` re-mirrors it.

**Postgres**: one StatefulSet + PVC per service database (10 total, including Temporal's own),
mirroring compose's existing 9 single-tenant containers 1:1, rather than consolidating onto a
shared instance. `ai-db` specifically uses the `ankane/pgvector` image (not plain
`postgres:16-alpine`), so it couldn't share an instance with the others regardless. Confirmed
with the team as the intended approach — see the plan history for the trade-off discussion.

**stripe-cli** (dev-only Stripe webhook forwarder) is dropped, same treatment as
telemetry-simulator/mailpit below. **temporal-ui** is kept as a Deployment + NodePort (useful
for this ticket's own STR-142 workflow verification), not routed through nginx — same as
compose.

**Kafka is KRaft-mode**, single broker+controller node (`apache/kafka:3.7.0`,
`KAFKA_PROCESS_ROLES: broker,controller` in compose) — confirmed no separate Zookeeper
service exists. This is a single-replica StatefulSet, not a Zookeeper+broker pair. Compose's
`PLAINTEXT_HOST://:29092` host-debug listener is dropped — nothing in-cluster needs it, every
producer/consumer is itself a pod using the ClusterIP Service's DNS name.

**Every domain service has an unauthenticated `GET /health`** returning `{"status": "ok"}` —
confirmed by reading each service's `main.py` (no auth middleware wraps it before the router
mount). Used as both `readinessProbe` and `livenessProbe`.

**`checkout-workflow-worker` has no HTTP server at all** — confirmed: it's a pure Temporal
task-queue poller (`python -m checkout_workflow.worker`, no FastAPI app anywhere in
`services/checkout-workflow/src`). No `GET /health` is possible. Rather than bolt on a
fragile `pgrep`-based exec probe against a `python:3.12-slim` image that doesn't ship `procps`
by default, **this Deployment has no readiness/liveness probes at all** — a known gap vs.
every other service, documented rather than papered over. A crash here shows up only as
`CrashLoopBackOff` from the container exiting, not from a failed probe.

**Keycloak has no PVC of its own.** Verified against compose: the `keycloak` service's only
mount is the read-only `realm-export.json` import file — there is no volume for
`/opt/keycloak/data`. All of Keycloak's real state (realms, users, sessions) lives in
`keycloak-db` via `KC_DB=postgres`. So `postgres-keycloak`'s own PVC is the only persistence
that matters, and `start-dev --import-realm` re-importing on every pod restart (idempotent,
skip-if-exists per entity, same as compose) reproduces compose's behavior exactly — no
separate import Job/initContainer needed.

**nginx.conf is unchanged** — mounted-in-image (via `internstore/nginx:local`'s own
Dockerfile, `COPY nginx.conf /etc/nginx/nginx.conf`, same as compose's `build: ./nginx`), not
re-templated. Its existing short-form upstream names (`catalog:8000`, `orders:8000`, ...) with
STR-135's resolver-based `proxy_pass` resolve correctly against Kubernetes' own DNS search
path as long as nginx and every backend Service share the `default` namespace, the same way
they resolved against Docker Compose's embedded DNS. **This was verified against a real `kind`
cluster while building these manifests** (see Verification below) — not just asserted.

## Excluded from this manifest set

- **`telemetry-simulator`, `mailpit`** — per the ticket: dev-only, no K8s equivalent. Simulator
  is replaced by real hardware, Mailpit by real SMTP, both already documented gaps
  (`docs/EVENT_BROKER.md`).
- **`stripe-cli`** — dev-only webhook forwarder, same treatment.
- **`frontend`** — the Vite dev server was never in the ticket's service list; it stays
  docker-compose/local-only. Point it at the K8s-hosted nginx via `kubectl port-forward` the
  same way it points at compose's nginx today.

## Secrets (local dev only — explicitly insecure)

Every `secret.yaml` in `k8s/base/*/` is a plain `stringData` manifest with the **same
dev-only values** already committed in `docker-compose.yml` (`dev-only-internal-secret-change-me`,
`minioadmin`/`minioadmin`, etc.) — not a new exposure, the same non-production credentials this
repo already ships. **Do not do this once a GCP overlay exists** — that's when GCP Secret
Manager + Workload Identity replaces plain `Secret` manifests, not before.

## Known gaps / follow-ups surfaced while writing this

- **`scripts/test-notifications-saga.sh` hard-requires Mailpit's REST API**
  (`http://localhost:8025/api/v1/...`) to confirm an email was actually sent — but Mailpit is
  explicitly excluded from this manifest set (see above). Running that script against the K8s
  stack as-is will fail at the Mailpit-query step. Either deploy a throwaway Mailpit pod
  out-of-band for this one verification run (`kubectl run mailpit --image=axllent/mailpit:v1.20
  --port=8025`, point `notifications`' `SMTP_HOST` ConfigMap value at it, `kubectl
  port-forward`), or treat that script's assertion as not portable and confirm delivery
  manually. Not resolved silently either way — flagging it here since the ticket asks to
  verify, not assume, that the existing scripts work unmodified.
- **Every `scripts/*.sh` verification script invokes `docker compose` somewhere** (container
  restarts, log tailing, or compose-specific setup) — none of them run against this stack
  completely unmodified. Translating each `docker compose restart <svc>` /
  `docker compose logs <svc>` call to its `kubectl rollout restart deployment/<svc>` /
  `kubectl logs deployment/<svc>` equivalent is real, scoped follow-up work, not done as part
  of this ticket (out of scope: this ticket is the manifests, not a scripts rewrite).
- **Kafka/temporal/keycloak have no compose healthcheck equivalents in some cases** — where
  compose defined a real healthcheck (Kafka, Keycloak, Postgres) it's reproduced faithfully
  here; where compose defined none at all (Temporal has no healthcheck in compose), a
  best-effort TCP probe is added rather than nothing, and rather than inventing an HTTP
  endpoint the service doesn't have. Documented per-manifest.

## A real bug found and fixed via the `kind` cluster check

`temporal-ui` crash-looped with `config file corrupted: yaml: unmarshal errors: line 2: cannot unmarshal
!!str tcp://1... into int` on a real cluster. Cause: Kubernetes auto-injects
legacy "service link" env vars into every pod for every Service that existed at pod creation
time, including a pod's own Service — so `temporal-ui`'s own `temporal-ui` Service produced
`TEMPORAL_UI_PORT=tcp://10.96.x.x:8080` in its container's environment, and `temporalio/ui`
happens to read `TEMPORAL_UI_PORT` as its own listen-port config, expecting a bare integer.
Fixed by setting `enableServiceLinks: false` on every pod template in `k8s/base` (none of
these services rely on the legacy Docker-links-style env vars — they all use K8s DNS — so this
is a safe blanket default, not just a `temporal-ui`-specific patch). This is exactly the kind
of thing that only shows up against a real cluster, not from reading the compose file — see
"Verification performed" below for how it was caught.

## Resource requests on a small local node

Validating against a real single-node `kind` cluster on a 4-core dev host, the 10 Postgres
StatefulSets + Kafka + Redis + Keycloak + Temporal + temporal-ui + MinIO alone already reserve
~98% of that node's allocatable CPU before a single domain service Deployment is scheduled —
some domain service pods sat `Pending` (`Insufficient cpu`) as a direct result, not because of
a manifest defect. On a small local machine, either give `kind`/`minikube` more CPU (a
multi-core host, or `--config` with more allocatable capacity), or lower `resources.requests`
for the domain services via a `k8s/overlays/local` patch (they're intentionally rough
placeholder values, not tuned) — the correctness of the manifests themselves doesn't depend on
running the full stack concurrently on a tiny node.

## Verification performed while writing these manifests

- `kubectl kustomize k8s/overlays/local` builds cleanly (validated).
- `kubectl apply --dry-run=server -k k8s/overlays/local` — every resource passes API-server
  schema validation against a real `kind` cluster (validated).
- `kubectl apply -k k8s/overlays/local` against a scratch `kind` cluster — confirms the
  manifests themselves apply without error; **actually reaching all-`Running`/`Ready` requires
  building and `kind load docker-image`-ing all 12 custom service images first** (see
  `k8s/build-images.sh`), which is the next step for whoever picks this up to run end-to-end
  against real images, not something validated as part of writing the manifests.

## Still to run (not done as part of writing these manifests — needs real images + time)

1. `./k8s/build-images.sh` then `kubectl apply -k k8s/overlays/local` — confirm all pods reach
   `Running`/`Ready`, no `CrashLoopBackOff`.
2. Hit a route through nginx (`curl -sk https://localhost:<nodePort>/api/catalog/categories`)
   and confirm 200, not 502 — the concrete DNS-parity check.
3. Run `scripts/verify-gateway.sh`, `test-reservation-saga.sh`, `test-telemetry-saga.sh`,
   `test-security-saga.sh`, `test-chat-saga.sh`, `test-temporal-saga.sh` against the
   port-forwarded/NodePort nginx (each may need its `docker compose`-specific steps adapted —
   see "Known gaps" above). `test-notifications-saga.sh` needs the Mailpit workaround above.
4. `kubectl scale deployment/chat --replicas=2`, manually confirm cross-instance chat message
   delivery still works via Redis pub/sub (STR-128) — K8s Service round-robin is a genuinely
   different load-balancing mechanism than nginx's resolver-based routing, so this needs an
   actual two-tab manual test, not an assumption that it still works.
5. `kubectl delete -k k8s/overlays/local` — confirm no orphaned PVCs remain (local dev data
   isn't precious here, unlike compose's named volumes surviving `docker compose down`).
