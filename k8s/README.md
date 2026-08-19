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
used to apply to Keycloak's `realm-export.json` mirror in `k8s/base/keycloak/config/` — removed
along with Keycloak itself (STR-192, see `docs/adr/0004-replace-keycloak-with-firebase.md`).

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

**(Historical, STR-192 removed Keycloak/postgres-keycloak entirely — see
`docs/adr/0004-replace-keycloak-with-firebase.md`.) Keycloak had no PVC of its own.** Verified
against compose at the time: the `keycloak` service's only mount was the read-only
`realm-export.json` import file — there was no volume for `/opt/keycloak/data`. All of
Keycloak's real state (realms, users, sessions) lived in `keycloak-db` via `KC_DB=postgres`. So
`postgres-keycloak`'s own PVC was the only persistence that mattered, and `start-dev
--import-realm` re-importing on every pod restart (idempotent, skip-if-exists per entity, same
as compose) reproduced compose's behavior exactly — no separate import Job/initContainer was
needed.

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

## STR-145: live verification — build images, run all sagas against a real kind cluster

Everything in "Still to run" above (the state this file was in before STR-145) has now
actually been run end-to-end against a real `kind` cluster on a 4-core host, images built
from this repo's own Dockerfiles, no shortcuts. This section is the record of that run: what
passed cleanly, what real bugs were found and fixed (manifest-only, per this ticket's own
scope — no architecture changes), and the two open questions ("does nginx's DNS parity claim
actually hold", "does chat cross-instance delivery actually work") that STR-142's README could
only flag as needing a live check.

### Result summary

- `k8s/build-images.sh` runs clean as written — all 14 `internstore/*:local` images (12 domain
  services + nginx + mock-camera) build and `kind load docker-image` successfully. No script
  changes needed; every image tag it builds matches exactly what the Deployment manifests
  reference.
- `kubectl apply -k k8s/overlays/local/` reaches **100% of pods Running/Ready** — all infra
  plus all 12 domain services — after the fixes below.
- All 6 in-scope saga scripts (`scripts/k8s/*.sh`, adapted copies — see below) **pass** against
  the live cluster.
- Chat cross-instance delivery (2 replicas): **confirmed working**, live proof below.
- Teardown: **no orphaned PVCs** — `kubectl delete -k` removes all 11 PVCs itself (they're
  declared as ordinary standalone resources in this kustomization, not left to a StatefulSet's
  own reclaim policy), and kind's default `local-path` StorageClass has `reclaimPolicy: Delete`,
  so the backing PV + on-node data directory are gone too. Every teardown is a full data wipe by
  default — worth knowing, not a bug: nothing here relies on data surviving a `kubectl delete`.

### Real bugs found and fixed (all manifest/script-scoped, per this ticket's mandate)

**1. Local-overlay CPU-request floor was too high for a 4-core host** (confirmed the STR-142
capacity finding, then fixed it). Base's per-container `resources.requests.cpu` (100m for most
domain services, up to 250m for Kafka/Keycloak/Temporal) summed to ~3.7 cores of *requests*
before any pod even starts using CPU — kube-system alone reserves ~0.85 core on a single-node
kind cluster, leaving ~3.15 allocatable, so several pods sat `Pending` ("Insufficient cpu").
Chose to **reduce requests via a new `k8s/overlays/local` patch**
(`patches/reduce-cpu-request.yaml`, blanket `containers/0` cpu request → `50m`) rather than
give the kind node more CPU, because kind nodes are containers sharing *this same host's* 4
cores — there's no separate allocation to bump on a single dev machine. This only touches the
scheduling floor (`requests`), not the actual ceiling (`limits`), so nothing loses real
throughput under load.

**2. `bump-memory-limit.yaml` was silently a *cut*, not a bump, for 3 services.** That existing
local-overlay patch blanket-replaces every container's memory *limit* to 768Mi — but base sets
keycloak/kafka/temporal's own limit to 1Gi, so 768Mi was actually lower than base for those
three. Caught via a live OOMKill on keycloak. Fixed by raising the patch's value to 1536Mi
(comfortably above every base limit, so it's now always a bump, never a cut, regardless of
what base sets per-service).

**3. Probe tolerance was too tight for ~30 services cold-starting on one 4-core node at once.**
Base's default `failureThreshold` (3) at typical `periodSeconds` (5-15s) gives each container
only 15-45s to become healthy — not enough when every pod is competing for the same 4 cores
simultaneously (each doing its own `uv sync`/`alembic upgrade`/JVM-boot dance). Added
`patches/loosen-probe-tolerance.yaml` (`failureThreshold: 10` on every readiness/liveness
probe, `containers/0` only — excludes `checkout-workflow-worker`, which has no probes at all).

**4. Kafka's `KAFKA_CONTROLLER_QUORUM_VOTERS` pointed at the Service DNS name, not `localhost`
— a real base-manifest bug, fixed there, not just in the local overlay.** With
`"1@kafka:9093"`, the single broker/controller registered with *itself* over the ClusterIP
Service's hairpin path instead of a same-pod loopback, and consistently failed its own internal
registration handshake ~60-70s after every start (`CancellationException`, "unable to register
with the controller quorum") — a fixed protocol-level timeout, not CPU contention (node-wide
CPU usage was ~34% at the time, confirmed via `docker stats`). Fixed by changing it to
`"1@localhost:9093"` in `k8s/base/kafka/statefulset.yaml` — there's only one node in this
quorum and it's always the pod talking to itself.

**5. Kafka's own readiness/liveness probes hit the same hairpin problem, independently.**
`kafka-topics.sh --bootstrap-server localhost:9092 --list` bootstraps via localhost fine, but
the admin client then reconnects using the *advertised* listener (`kafka:9092`, the Service
name) for the actual RPC — routing the probe back through the same broken self-Service path,
timing out even once the broker was genuinely up and accepting real connections. Fixed in
`k8s/base/kafka/statefulset.yaml` by replacing both probes with a plain `bash -c 'exec
3<>/dev/tcp/localhost/9092'` TCP-open check — sufficient for a single-broker dev cluster, and
it sidesteps the advertised-listener redirect entirely (real client pods, being genuinely
different pods from kafka-0, don't hit this hairpin path at all — only same-pod tooling does).

**6. `ai-assistant` and `mcp-gateway`'s `OPENAI_API_KEY: ""` crash-looped both pods.** The
OpenAI SDK's own client constructor (`AsyncOpenAI(api_key=...)`) raises `OpenAIError: Missing
credentials` for a falsy key — unlike Stripe's client, which only 401s lazily at call time
(the pattern compose's `${OPENAI_API_KEY:-}` comment was modeled on). Compose's "still boots
without it" claim only held in practice because local devs have a real value in their own
`.env`; this is the first time either service ran with no `.env` fallback at all. Fixed in
`k8s/base/ai-assistant/secret.yaml` and `k8s/base/mcp-gateway/secret.yaml` with a non-empty
placeholder (`sk-local-dev-placeholder-not-a-real-key`) — real AI-assistant calls still 401
without a genuine key, matching Stripe's documented behavior.

**STR-161b update:** `OPENAI_API_KEY` is gone entirely now — the Gemini migration replaced it
with IAM/Workload Identity, and `google-genai`'s `Client()` constructor (unlike `AsyncOpenAI`'s)
never raises on a missing/empty project at construction time, only at the first real call. The
placeholder workaround above no longer exists in either `secret.yaml`; see
`services/ai-assistant/README.md`'s "Gemini migration" section.

**7. nginx's `resolver` directive was hardcoded to `127.0.0.11`, Docker Compose's embedded DNS
— the STR-142 "no nginx.conf edits should be needed" claim did not hold.** Every proxied
request 500'd with `resolver: 127.0.0.11:53` connection-refused errors — that address doesn't
exist in Kubernetes (pods get CoreDNS's ClusterIP instead, e.g. `10.96.0.10` on this cluster,
but it's whatever the cluster assigns, not a value safe to hardcode either). **A second,
independent issue compounded it**: even with the right resolver IP, nginx's own DNS-resolution
mechanism (used for the `set $x_upstream "host:port"` request-time `proxy_pass` variables)
queries literally whatever hostname is in the variable — it does not consult
`/etc/resolv.conf`'s `search` list the way a normal libc resolver call (`curl`, `python`,
`getent`) does. Compose's embedded DNS resolves bare short names (`auth-backend`) natively;
CoreDNS only resolves them via the pod's search suffix, so the exact same bare names in
nginx.conf 500'd in-cluster even with a working resolver address. Both problems share one root
cause (nginx.conf assuming compose-only DNS semantics) and one fix, in `nginx/
docker-entrypoint-certs.sh`: at container start, read the container's *actual* nameserver and
`svc.cluster.local`-style search suffix from its own `/etc/resolv.conf`, and `sed`-patch
`nginx.conf`'s `resolver` directive and every bareword upstream hostname accordingly. Under
compose this is a no-op (127.0.0.11, no matching search suffix) — same nginx.conf, same image,
correct behavior in both environments without hardcoding either one. Confirmed live: `GET
/api/catalog/categories` through nginx went from `500` to `200` after this fix, and
`/api/orders/health` etc. correctly `401` instead of `502`/`500`.

**8. Several `scripts/*.sh` had real, pre-existing bugs of their own — not translation
mistakes, and not compose-vs-k8s differences — first surfaced because this is the first time
they were actually run.** All fixed in the `scripts/k8s/` copies with a comment explaining
each; flagging here that the compose originals carry the same bugs and would benefit from the
same fixes:
  - `verify-gateway.sh`'s probe-category name (`"gw-probe-$RANDOM-guest"`, ~20 chars) exceeds
    Catalog's `name` schema limit (`max_length=15`), 422ing instead of 403ing.
  - `verify-gateway.sh`'s "JWKS caching survives Keycloak down" assertion (expects `200`) is
    stale relative to `auth-backend`'s `RevocationChecker` (AUTH-05) — that does its own live
    Keycloak token-introspection call per token (30s cache) and deliberately fails closed
    (`401`) on an uncached token with Keycloak unreachable. Correct secure-by-default behavior,
    not a caching gap; the assertion needed updating, not the app.
  - `test-reservation-saga.sh` polls for reservation expiry with a 60s timeout and a comment
    claiming `RESERVATION_TTL_SECONDS=30`, but both compose and this manifest set actually set
    it to 300s (confirmed against the live inventory pod's own env) — the poll could never
    succeed as written. Bumping the timeout to match the real TTL then surfaced a *second*,
    compounding bug: the customer/admin tokens are minted once near the top of the script and
    reused for the whole run, but Keycloak's `accessTokenLifespan` is 300s — with a 330s+ poll
    plus everything before it, the token expires mid-poll and every subsequent check 401s
    (nginx's own non-JSON auth-rejection page, not the app's JSON) for the rest of the window,
    indistinguishable from a hung saga without inspecting the raw response. Fixed by
    re-logging-in on each poll attempt instead of reusing one long-lived token. Also hardened
    `poll_until` itself to not let a single transient non-JSON response (`set -e` + a `jq`
    parse error) silently kill the entire script mid-poll with no `FAIL` line.
  - `test-temporal-saga.sh` never actually registers `PRODUCT_A`/`PRODUCT_B` in Catalog —
    `checkout_v2.py`'s own price lookup (`catalog_client.get_product_price`, added specifically
    so prices are "never trusted from the client") means both need a real Catalog row with a
    known price, or checkout fails before ever reaching Payments. Fixed by seeding real
    products with prices chosen to hit the intended happy-path/failure outcomes deterministically
    (9.50 × 3, 12.99 × 1) instead of relying on undocumented demo seed data.
  - `test-temporal-saga.sh`'s `docker run temporalio/admin-tools:1.27.2-tctl-1.18.2-cli-1.1.1`
    tag no longer exists on Docker Hub (confirmed live 404). Switched to `:latest`.
  - `test-temporal-saga.sh`'s workflow-history assertion greps the CLI's default table output
    for activity names (`reserve_stock`, etc.) that table format never includes — only
    `--output json` surfaces the real `activityType.name` field the check actually needs.
  - (k8s-specific) `kubectl run ... -i --rm` silently truncated captured stdout when run
    non-interactively (no TTY) — dropped `-i` since nothing needs stdin here, only the one-shot
    command's own output.

None of the above needed second-guessing STR-142's architecture decisions (OPA sidecar model,
per-service Postgres, etc.) — every fix is either a probe/resource-tuning value, a genuine
config bug (Kafka's controller-quorum address, nginx's DNS assumptions, an empty secret), or a
pre-existing bug in a test script that had simply never been run before.

### Adapted saga scripts: `scripts/k8s/*.sh`

New copies, not edits to the originals (which remain the compose source of truth):
`verify-gateway.sh`, `test-reservation-saga.sh`, `test-telemetry-saga.sh`,
`test-security-saga.sh`, `test-chat-saga.sh`, `test-temporal-saga.sh` — all pass against the
live cluster. Translation pattern: `docker compose exec`/`restart`/`logs` calls become
`kubectl exec`/`scale`/`logs`; services with no NodePort (`auth-backend`) get a
`kubectl port-forward` for the script's duration; "hit a service directly, bypassing the
gateway" (`verify-gateway.sh`'s internal-token isolation checks) becomes a reusable
`kubectl run curlimages/curl` probe pod instead of one-shot `docker run --network` calls (too
slow to spin up fresh per call on a busy kind node); Temporal's workflow-history check becomes
a one-shot `kubectl run temporalio/admin-tools` pod instead of `docker run --network`.
`test-security-saga.sh` and `test-chat-saga.sh` needed no compose-specific translation at all
(pure HTTP/WebSocket through the gateway) — copied over anyway so every in-scope script has one
`scripts/k8s/` home, and so the real bugs found while running them (above) don't have to be
rediscovered by whoever reaches for these next.

`test-notifications-saga.sh` is **not** copied to `scripts/k8s/` (explicitly out of scope,
depends on Mailpit — see "Excluded from this manifest set" above). Its actual assertion was
verified manually instead: a real checkout → pay through the gateway, with a throwaway Mailpit
Deployment+Service standing in for the excluded compose service (see next section), produced a
real email — `PaymentConfirmed -> (real Kafka) -> Notifications -> (real SMTP) -> Payment
confirmed for order <id>` visible via Mailpit's REST API, correct recipient/subject/body. Same
flow that script would assert, confirmed working, without adding a permanent k8s script for an
explicitly-excluded dependency.

### Throwaway Mailpit

Used for `test-telemetry-saga.sh`, `test-chat-saga.sh`, and the manual notifications check
above — not part of the stack otherwise:

```bash
kubectl create deployment mailpit --image=axllent/mailpit:v1.20 --port=8025
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: mailpit
  labels: {app: mailpit}
spec:
  selector: {app: mailpit}
  ports:
  - {name: http, port: 8025, targetPort: 8025}
  - {name: smtp, port: 1025, targetPort: 1025}
EOF
kubectl rollout restart deployment/notifications   # picks up the now-resolvable "mailpit" host
kubectl port-forward svc/mailpit 8025:8025 &        # exposes Mailpit's REST API at localhost:8025
```

`notifications`' `SMTP_HOST`/`SMTP_PORT` ConfigMap values already point at `mailpit:1025`
(mirroring compose) even with nothing backing that hostname by default — this throwaway
Deployment+Service is the only thing missing, not a config change. Tear down when done:
`kubectl delete deployment,service mailpit` (and kill the port-forward). Confirmed this does
**not** need a Service `smtp` port name collision workaround or anything cluster-specific — a
single Service exposing both 8025 (REST/UI) and 1025 (SMTP) works as-is.

### Chat 2-replica cross-instance delivery: **confirmed working**

`kubectl scale deployment/chat --replicas=2`, then a live WebSocket round-trip with the
customer and admin connections opened independently through nginx (each gets its own
Service-routed backend pod — kube-proxy's default round-robin isn't perfectly alternating, so
this took 2 attempts, correlated against each pod's own access log, to land the two connections
on different pods deterministically):

```text
pod chat-79998dd944-66v2j: WebSocket /ws/room/room_65a2769a-... [accepted]   (customer)
pod chat-79998dd944-6cqvp: WebSocket /ws/room/room_65a2769a-... [accepted]   (admin)
```

Customer sent a message on its connection to pod `66v2j`; admin, connected to the *different*
pod `6cqvp`, received it. This is real proof that Chat's Redis pub/sub fan-out (STR-128's
mechanism — every pod subscribes to the same Redis channel per room, so a message published by
one pod's WebSocket handler reaches every other pod's subscribers, not just local in-process
delivery) works correctly across K8s's Service-based round-robin, which is a genuinely
different load-balancing mechanism than nginx's resolver-based routing in front of a single
compose container. STR-142 correctly flagged this as needing a live check rather than an
assumption — this ticket answers it: **pass**.

### Teardown: no orphaned PVCs

`kubectl delete -k k8s/overlays/local/` removed all 11 PVCs
(`kafka-data`, `minio-data`, 9× `postgres-*-data`) along with every other resource — they're
declared as ordinary standalone `PersistentVolumeClaim` resources inside this kustomization
(not StatefulSet `volumeClaimTemplates`, which `kubectl delete -k` would leave behind by
design), so they're deleted the same as any other resource the kustomization owns. `kubectl get
pvc,pv` after teardown: nothing left in either. kind's default `local-path` StorageClass has
`reclaimPolicy: Delete`, so the underlying PV and its on-node data directory are also gone, not
just the claim object. **Every `kubectl delete -k` here is a full data wipe by default** —
intentional for local dev (nothing in this manifest set is meant to survive a teardown), but
worth stating explicitly since compose's named volumes behave differently (they survive
`docker compose down` unless `-v` is passed) and someone coming from that habit might expect
the same here.

## STR-183: LGTM observability stack (Loki, Grafana, Tempo, Mimir) + Grafana Alloy

`k8s/base/observability/` — see `k8s/base/observability/README.md` for the full writeup
(storage-backend decision, Grafana trace↔log↔metric correlation config, a real Mimir
single-tenant-ring bug found and fixed via live verification, and the measured resource
footprint against STR-180's cost model). Summary:

- All four LGTM components + Alloy verified running and correctly correlating signals
  end-to-end on a scratch `kind` cluster — a synthetic OTLP trace and log pushed through Alloy
  were confirmed queryable back out through Grafana's own datasource-proxy endpoints for all
  three of Loki, Tempo, and Mimir (the last via Tempo's `metrics_generator` span-metrics).
- Storage stays filesystem/PVC-backed (not GCS) at this project's demo scale — confirmed with
  the ticket owner before building — so this directory needs **no** special `gcp` overlay
  handling; it flows through via `resources: [../../base]` same as everything else.
- Measured footprint: **250m CPU / 704Mi memory** of scheduling `requests` added to the
  cluster, **~20m CPU / 237Mi memory** actually used at idle/smoke-test load (`kubectl top`,
  no real service traffic yet — that's Phase 2's job).
- **Phase 2 (OTel SDK instrumentation across all 12+ services, incl. structured-logging
  migration — current logging is plain `logging.basicConfig()`, not JSON) is out of scope for
  this ticket** and tracked as its own follow-up: different risk profile (real application-code
  diffs vs. this ticket's purely-additive infra), confirmed with the ticket owner rather than
  force-fit in alongside Phase 1.
