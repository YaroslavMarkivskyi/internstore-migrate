# InternStore GCP demo environment

`apply → demo → destroy`, not always-on. Every resource in this module defaults
to the smallest viable GCP size and nothing sets `deletion_protection = true`
— see the checklist at the bottom before trusting a `terraform destroy`.

## First-time setup

```bash
./../../bootstrap.sh <your-project-id> us-central1   # one-time: APIs + tfstate bucket, NOT Terraform-managed
cp terraform.tfvars.example terraform.tfvars          # fill in project_id + real secret values
terraform init -backend-config="bucket=<project-id>-internstore-tfstate"
terraform plan
terraform apply
```

Then build/push images and render the k8s overlay — see repo root `k8s/build-push-gcp.sh`
and `k8s/overlays/gcp/generate-overlay.py`.

## Cost math (resolves STR-154's "confirm before assuming" ask)

### Cloud SQL: 10 instances, not consolidated

Cloud SQL for PostgreSQL: **10** instances (9 uniform domain DBs +
`postgres-temporal` + `postgres-ai`), matching the ticket's "10, including
Temporal's" estimate.

Real Cloud SQL for PostgreSQL pricing (`us-central1`, checked against
`cloud.google.com/sql/pricing` and Google's own docs, not the ticket's
earlier estimate):

| Item | Rate |
|---|---|
| `db-f1-micro` (shared-core, supported for Postgres) | ≈ $0.0105/hr compute |
| Minimum SSD storage (10 GB) | ≈ $0.17/GB-mo ≈ $0.0023/hr |
| Single-zone, no HA, no automated backups | no extra multiplier |

10 instances × (~$0.0105 + ~$0.0023)/hr ≈ **$0.13/hr for all 10 Cloud SQL
instances combined** — under $1 for a multi-hour demo session, negligible
against the rest of the stack.

**Decision: keep 10 separate instances**, one per service, matching
`k8s/base`'s existing StatefulSet-per-service topology. The "per-instance
minimum cost" concern the ticket raised only bites at *always-on* pricing
(~$77-86/mo for 10 `db-f1-micro` instances run continuously) — this
environment is never left running that way. Consolidating onto fewer
instances would save cents per demo session at the cost of real
architectural complexity (shared instances can't isolate `postgres-ai`'s
pgvector requirement from the rest, and cross-service DB access defeats the
per-service-database isolation the topology exists for) — not a trade worth
making here.

### Other components (order-of-magnitude — replace with real numbers after a live apply/destroy cycle)

| Component | Rate | Notes |
|---|---|---|
| GKE Autopilot | ~$0.0445/vCPU-hr + $0.0049/GiB-hr (pod billing) + $0.10/hr cluster fee | Often absorbed by the $74.40/mo Autopilot credit. Autopilot bills each pod's *effective* request, rounded up to its 0.25 vCPU / 0.5Gi floor — several `k8s/base` containers request less than that, so real billed vCPU/memory across ~23 pods will run somewhat above a naive sum of `k8s/base`'s stated requests. See `k8s/overlays/gcp/README.md`'s "Autopilot resource billing note". |
| Memorystore Redis, Basic, 1GB | ~$0.03-0.05/hr | Smallest size, no HA |
| GCP Managed Kafka | ~$0.09/vCPU-hr + $0.02/GiB-hr (DCU-based), 3 vCPU minimum config here | **Least-pinned-down number in this doc — the ticket's own biggest cost risk.** Confirm the real `terraform plan` cost estimate against this before the first apply against a billed project; the smallest DCU config's true floor (and any multi-zone/broker minimum) wasn't fully verifiable from public pricing pages alone. |
| GCS storage | ~$0.02/GB-mo (Standard) | Trivial at demo data volumes |

### Post-demo: fill in actual measured cost here

_Not yet run against a real billed project. After the first live
`apply → demo → destroy` cycle, replace this section with the actual cost
pulled from Cloud Billing Reports (scoped to this project/label) for that
session — per the ticket's verification requirement, not the estimate above._

## Deviations from the ticket, documented not silent

- **`backend.tf` lives here, not at `terraform/gcp/` root.** A Terraform
  backend block only works in the root module actually applied
  (`environments/demo`); the ticket's tree diagram shows it a level up.
- **Cloud SQL connectivity is via Cloud SQL Auth Proxy sidecar + public IP**,
  not private-IP-only via Private Service Access peering. Chosen for a
  stack that lives a few hours per demo — one less piece of peering
  infrastructure to provision and tear down cleanly. Memorystore still uses
  private IP (it has no other supported mode).
- **GCS is accessed via its S3-compatible XML API + HMAC keys**, not the
  native `google-cloud-storage` SDK — required to keep `services/catalog`
  and `services/chat`'s existing boto3 client unchanged, since STR-154 puts
  application code changes out of scope.
- **Kafka topic creation moved into Terraform** (`modules/kafka`'s
  `google_managed_kafka_topic` resources), replacing `k8s/base`'s
  `kafka-topic-init` Job, which the gcp overlay drops entirely.
- **GKE nodes are public** (no Cloud NAT/bastion) — acceptable for a
  short-lived demo, would need revisiting for anything longer-lived.

## Teardown checklist

`terraform destroy` should remove everything below. Confirm via `gcloud`/Console
after every destroy, not just a clean `terraform destroy` exit code:

- [ ] All 10 Cloud SQL instances gone (`gcloud sql instances list`)
- [ ] GKE Autopilot cluster gone (`gcloud container clusters list`)
- [ ] Memorystore instance gone (`gcloud redis instances list`)
- [ ] Managed Kafka cluster + topics gone (`gcloud managed-kafka clusters list`)
- [ ] GCS bucket gone (`gcloud storage buckets list`) — `force_destroy = true` handles non-empty buckets
- [ ] Artifact Registry repo + images gone (`gcloud artifacts repositories list`)
- [ ] Load balancer forwarding rules / static IP gone (`gcloud compute forwarding-rules list`, `gcloud compute addresses list`)
- [ ] VPC + subnet + Cloud Armor policy gone (`gcloud compute networks list`)
- [ ] Secret Manager secrets gone (`gcloud secrets list`)
- [ ] Service accounts gone (`gcloud iam service-accounts list`)
- [ ] **Not** gone, and correctly so: the `bootstrap.sh`-created tfstate GCS bucket — that one is intentionally outside the Terraform-managed stack.
