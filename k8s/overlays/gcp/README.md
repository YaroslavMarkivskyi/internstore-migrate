# GCP overlay (STR-154)

Populates the STR-142 placeholder with the actual GKE Autopilot overlay:
Artifact Registry image references, Cloud SQL (via Auth Proxy sidecars),
Memorystore, Managed Kafka, and GCS — all wired from
`terraform/gcp/environments/demo`'s outputs, with every credential coming
from Secret Manager via Workload Identity instead of `k8s/base`'s plaintext
`secret.yaml` files.

`k8s/base/` itself needed **zero changes** — everything below is additive
resources plus Kustomize patches over the same base STR-142/157 already
verified against `kind`.

**Autopilot resource billing note**: base's per-container `requests` (e.g.
`catalog`'s `100m`/`256Mi`) are below Autopilot's per-pod floor (`250m`
vCPU / `0.5Gi` memory total). Autopilot silently rounds a pod's effective
billed request up to that floor rather than rejecting it — base's manifests
are deliberately left as-is rather than patched to "match" that floor,
since the floor is enforced (and billed) by GKE regardless of what the
manifest states; patching every container's request across 23 differently
shaped Deployments to cosmetically match a platform-enforced minimum
wouldn't change what's actually billed. Reflected in the cost doc, not
silently absorbed.

## How to render and apply

```bash
cd terraform/gcp/environments/demo && terraform apply   # provisions everything, see that dir's README for cost math

# From repo root:
python3 k8s/overlays/gcp/generate-overlay.py \
  --outputs <(terraform -chdir=terraform/gcp/environments/demo output -json) \
  --out k8s/overlays/gcp/generated

kubectl apply -k k8s/overlays/gcp/
```

`generate-overlay.py` writes one `ServiceAccount` + `SecretProviderClass` +
Deployment/StatefulSet patch per service into `k8s/overlays/gcp/generated/`
(gitignored — it embeds this session's Secret Manager secret *names* and
Cloud SQL connection names, which are only meaningful against the Terraform
state that produced them). `generated-example/` is a checked-in sample,
produced by running the same generator against
`terraform-outputs.example.json`, so the mechanism is reviewable without a
live GCP project.

## What's static vs. generated

**Static** (hand-written, in this directory):

- `kustomization.yaml` — glues everything together
- `components/delete-infra/` — a Kustomize Component that drops base's
  in-cluster `postgres-*`, `redis`, `minio`/`minio-init`,
  `kafka`/`kafka-topic-init` (replaced by Cloud SQL, Memorystore, GCS,
  Managed Kafka respectively)
- `temporal-patch.yaml` — special-cased: reads its DB config from inline
  `env: value:` entries in `k8s/base`, not an `envFrom: secretRef`, so it
  needs its own strategic-merge patch rather than the generic generator
  (see its header comment).
- `ingress.yaml`, `nginx-service-patch.yaml`, `backendconfig.yaml` — GCLB
  Ingress in front of the existing `nginx` Service, with Cloud Armor
  attached via `BackendConfig`
- `kustomization.yaml`'s `images:` transformer — repoints all 15
  `internstore/*:local` images at Artifact Registry (values filled from
  `terraform output` — see the `# TF:` markers)

**Generated** (`generate-overlay.py`, one set of files per service that had
a `secret.yaml` in base): `ServiceAccount` (Workload Identity-annotated),
`SecretProviderClass` (Secret Manager -> synced-as-Kubernetes-Secret, same
Secret name base already used so `envFrom` in every Deployment is
byte-identical to local), and — for DB-backed services — a Cloud SQL Auth
Proxy sidecar patch.

## Mechanism: Secret Manager -> pod env, no app code changes

1. `SecretProviderClass` pulls named Secret Manager secrets and declares
   `secretObjects`, which tells the driver to also materialize them as a
   native `v1/Secret` with the **same name and keys** the plaintext
   `secret.yaml` used (e.g. `catalog-secret` / `DATABASE_URL`,
   `INTERNAL_TOKEN_SECRET`, ...).
2. Each service's Deployment/StatefulSet is patched to run as a dedicated
   `ServiceAccount` (Workload Identity-bound to a GSA scoped to only that
   service's secrets — see `terraform/gcp/environments/demo/workload-identity.tf`)
   and to mount the CSI volume somewhere (triggers the sync — the driver
   only creates the Secret once its volume is actually mounted by a pod).
3. `envFrom: secretRef: <service>-secret` in `k8s/base/<service>/deployment.yaml`
   is untouched — it now resolves against the CSI-driver-created Secret
   instead of the deleted plaintext one, invisibly to the app.

## Mechanism: Cloud SQL

Every DB-backed service gets a `cloudsql-proxy` sidecar container
(`gcr.io/cloud-sql-connectors/cloud-sql-proxy`) listening on
`127.0.0.1:5432` (a second port, `5433`, for `telemetry-aggregates`'s extra
read-only connection to `postgres-telemetry`). `DATABASE_URL` in the synced
Secret already points at `127.0.0.1:5432` (set by Terraform in
`environments/demo/secrets.tf`), so base's Deployment YAML doesn't change —
only the new sidecar and the Secret Manager-backed DB password do.

## GCS instead of MinIO

`catalog` and `chat`'s `MINIO_ENDPOINT` config value becomes the GCS
S3-compatible XML endpoint, and their `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`
secrets become the HMAC key pair Terraform's `storage` module creates —
`services/catalog` and `services/chat`'s boto3 client
(`minio_client.py`) needs no code change, per its own docstring.
