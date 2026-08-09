# GCP overlay — not yet implemented

See STR-\<future\> for the GKE Autopilot overlay (Cloud SQL, Memorystore,
Managed Kafka, Secret Manager + Workload Identity, Terraform). This
directory is a placeholder only.

`k8s/base/` is written to be reusable as-is: swap each service's
`DATABASE_URL`/`KAFKA_BOOTSTRAP_SERVERS`/etc. Secret and ConfigMap values
for managed-service connection strings, replace the dev-only plaintext
Secrets with Secret Manager–backed ones, and this overlay becomes
`kubectl apply -k k8s/overlays/gcp/` — not a rewrite.
