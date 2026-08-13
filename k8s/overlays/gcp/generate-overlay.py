#!/usr/bin/env python3
"""Generate the per-service GCP overlay pieces STR-154 needs: one
ServiceAccount (Workload Identity), one SecretProviderClass (Secret
Manager -> synced-as-Kubernetes-Secret, same name/keys base's plaintext
secret.yaml used), and — for DB-backed services — a Cloud SQL Auth Proxy
sidecar patch, per service.

keycloak and temporal are NOT covered here — their DB config is inline
`env: value:` in base rather than `envFrom: secretRef`, so they're
hand-written (keycloak-patch.yaml/keycloak-secrets.yaml,
temporal-patch.yaml/temporal-secrets.yaml) instead. notifications has no
secret.yaml in base at all and needs nothing here either.

Deliberately stdlib-only (json + string templates, no PyYAML) — this repo's
CLAUDE.md says not to add dependencies without asking, and the YAML this
script emits is simple enough not to need a templating library.

The SERVICE_SECRETS/SERVICE_DB_KEYS tables below mirror
terraform/gcp/environments/demo/workload-identity.tf's
local.service_secrets/local.service_db_keys — kept in sync by hand (two
small tables, not worth wiring a shared source of truth for STR-154's
scope). If you add a secret to a service's k8s/base/*/secret.yaml, update
both places.
"""
import argparse
import json
import sys
from pathlib import Path

# service -> [(k8s Secret key, Secret Manager secret-id suffix), ...]
# matches each service's k8s/base/*/secret.yaml stringData keys 1:1.
SERVICE_SECRET_KEYS = {
    "catalog": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("DATABASE_URL", "catalog-database-url"),
        ("MINIO_ACCESS_KEY", "gcs-hmac-access-id"),
        ("MINIO_SECRET_KEY", "gcs-hmac-secret"),
    ],
    "inventory": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("DATABASE_URL", "inventory-database-url"),
    ],
    "orders": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("DATABASE_URL", "orders-database-url"),
        ("STRIPE_SECRET_KEY", "stripe-secret-key"),
        ("STRIPE_WEBHOOK_SECRET", "stripe-webhook-secret"),
    ],
    "telemetry": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("DATABASE_URL", "telemetry-database-url"),
    ],
    "telemetry-aggregates": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("DATABASE_URL", "telemetry-aggregates-database-url"),
        ("TELEMETRY_DB_URL", "telemetry-aggregates-telemetry-db-url"),
    ],
    "security": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("DATABASE_URL", "security-database-url"),
    ],
    "chat": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("DATABASE_URL", "chat-database-url"),
        ("MINIO_ACCESS_KEY", "gcs-hmac-access-id"),
        ("MINIO_SECRET_KEY", "gcs-hmac-secret"),
    ],
    "payments": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("DATABASE_URL", "payments-database-url"),
    ],
    "ai-assistant": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("DATABASE_URL", "ai-assistant-database-url"),
        ("OPENAI_API_KEY", "openai-api-key"),
    ],
    "mcp-gateway": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("AI_DB_URL", "mcp-gateway-database-url"),
        ("OPENAI_API_KEY", "openai-api-key"),
    ],
    "auth-backend": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
        ("KEYCLOAK_CLIENT_SECRET", "keycloak-client-secret"),
    ],
    "checkout-workflow-worker": [
        ("INTERNAL_TOKEN_SECRET", "internal-token-secret"),
    ],
}

# service -> [(db key, local proxy port), ...]. db key indexes into
# terraform output cloudsql_connection_names. Absent = no DB, no sidecar.
SERVICE_DB_KEYS = {
    "catalog": [("catalog", 5432)],
    "inventory": [("inventory", 5432)],
    "orders": [("orders", 5432)],
    "telemetry": [("telemetry", 5432)],
    "telemetry-aggregates": [("telemetry-aggregates", 5432), ("telemetry", 5433)],
    "security": [("security", 5432)],
    "chat": [("chat", 5432)],
    "payments": [("payments", 5432)],
    "ai-assistant": [("ai", 5432)],
    "mcp-gateway": [("ai", 5432)],
}

CLOUDSQL_PROXY_IMAGE = "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.14.0"


def serviceaccount_yaml(service: str, gsa_email: str) -> str:
    return f"""apiVersion: v1
kind: ServiceAccount
metadata:
  name: {service}
  annotations:
    iam.gke.io/gcp-service-account: "{gsa_email}"
"""


def secretproviderclass_yaml(service: str, project_id: str, secret_ids: dict, keys: list) -> str:
    secrets_lines = "\n".join(
        f'      - resourceName: "projects/{project_id}/secrets/{secret_ids[secret_suffix]}/versions/latest"\n'
        f'        fileName: "{k8s_key}"'
        for k8s_key, secret_suffix in keys
    )
    data_lines = "\n".join(
        f'    - objectName: "{k8s_key}"\n      key: "{k8s_key}"' for k8s_key, _ in keys
    )
    return f"""apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: {service}-secrets
spec:
  provider: gcp
  parameters:
    secrets: |
{secrets_lines}
  secretObjects:
  - secretName: {service}-secret
    type: Opaque
    data:
{data_lines}
"""


def deployment_patch_yaml(service: str, db_keys, connection_names: dict) -> str:
    # cloud-sql-proxy v2 takes one positional INSTANCE_CONNECTION_NAME per
    # DB, each with an explicit `?port=N` query suffix — telemetry-aggregates
    # is the one service with two (its own DB on 5432, plus a read-only
    # connection to postgres-telemetry on 5433).
    sidecar = ""
    if db_keys:
        instance_args = "\n".join(
            f'          - "{connection_names.get(dbkey, "PROJECT:REGION:INSTANCE_" + dbkey)}?port={port}"'
            for dbkey, port in db_keys
        )
        sidecar = f"""      - name: cloudsql-proxy
        image: {CLOUDSQL_PROXY_IMAGE}
        args:
{instance_args}
        resources:
          requests:
            cpu: "50m"
            memory: "64Mi"
          limits:
            cpu: "200m"
            memory: "128Mi"
"""
    return f"""# Assumes the base Deployment's main container is named "{service}"
# (true for every service this generator covers — checked against
# k8s/base/{service}/deployment.yaml) — the CSI volumeMount patches onto it.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service}
spec:
  template:
    spec:
      serviceAccountName: {service}
      containers:
      - name: {service}
        volumeMounts:
        - name: secrets-store
          mountPath: /mnt/secrets-store
          readOnly: true
{sidecar}      volumes:
      - name: secrets-store
        csi:
          driver: secrets-store.csi.k8s.io
          readOnly: true
          volumeAttributes:
            secretProviderClass: {service}-secrets
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", required=True, help="Path to `terraform output -json` output (or a process-substitution fd)")
    parser.add_argument("--out", required=True, help="Output directory for generated manifests")
    args = parser.parse_args()

    outputs = json.loads(Path(args.outputs).read_text())
    project_id = outputs["project_id"]["value"]
    secret_ids = outputs["secret_manager_secret_ids"]["value"]
    gsa_emails = outputs["workload_identity_gsa_emails"]["value"]
    connection_names = outputs["cloudsql_connection_names"]["value"]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    generated_resources = []
    generated_patches = []

    for service, keys in SERVICE_SECRET_KEYS.items():
        sa_path = out_dir / f"{service}-serviceaccount.yaml"
        sa_path.write_text(serviceaccount_yaml(service, gsa_emails[service]))
        generated_resources.append(sa_path.name)

        spc_path = out_dir / f"{service}-secretproviderclass.yaml"
        spc_path.write_text(secretproviderclass_yaml(service, project_id, secret_ids, keys))
        generated_resources.append(spc_path.name)

        patch_path = out_dir / f"{service}-deployment-patch.yaml"
        patch_path.write_text(deployment_patch_yaml(service, SERVICE_DB_KEYS.get(service, []), connection_names))
        generated_patches.append(patch_path.name)

    # manifest.json isn't consumed by kustomization.yaml (Kustomize has no
    # way to read a file list at build time) — kustomization.yaml's
    # resources/patches entries are the static, spelled-out list of these
    # same filenames. This is just a record of what got generated, useful
    # for a diff/review pass.
    manifest = {"resources": generated_resources, "patches": generated_patches}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Wrote {len(generated_resources)} resources + {len(generated_patches)} patches to {out_dir}/", file=sys.stderr)


if __name__ == "__main__":
    main()
