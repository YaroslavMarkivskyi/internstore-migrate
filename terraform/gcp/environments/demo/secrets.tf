# Every credential the ticket names (INTERNAL_TOKEN_SECRET, DB passwords,
# OPENAI_API_KEY, Stripe keys) plus the GCS HMAC keys, as Secret Manager
# secrets. (Keycloak's own creds used to live here too — removed by
# STR-192 along with Keycloak itself.) The k8s overlay's generated
# SecretProviderClasses reference these by name via Workload Identity — see
# k8s/overlays/gcp/generate-overlay.py. Cloud SQL Auth Proxy sidecars listen
# on 127.0.0.1, so every DATABASE_URL below points at localhost, not the
# instance's real address.

locals {
  # service-facing secret id -> value. One Secret Manager secret per entry.
  secrets = merge(
    {
      "internal-token-secret" = var.internal_token_secret
      "openai-api-key"        = var.openai_api_key
      "stripe-secret-key"     = var.stripe_secret_key
      "stripe-webhook-secret" = var.stripe_webhook_secret
      "temporal-db-password"  = random_password.db["temporal"].result
      "gcs-hmac-access-id"    = module.storage.hmac_access_id
      "gcs-hmac-secret"       = module.storage.hmac_secret
      # See databases.tf's comment: matches the value telemetry's own
      # Alembic migration (69ff8539f688) already creates the
      # telemetry_readonly role with, unchanged from base's local value —
      # rotate this for anything longer-lived than a demo.
      "telemetry-readonly-password" = "telemetry-readonly"
    },
    # DATABASE_URL per DB-backed service, proxied through 127.0.0.1:5432
    # (the Cloud SQL Auth Proxy sidecar's default local port).
    {
      for svc, dbkey in {
        catalog                = "catalog"
        inventory              = "inventory"
        orders                 = "orders"
        telemetry              = "telemetry"
        "telemetry-aggregates" = "telemetry-aggregates"
        security               = "security"
        chat                   = "chat"
        payments               = "payments"
        "ai-assistant"         = "ai"
        "mcp-gateway"          = "ai"
      } : "${svc}-database-url" => "postgresql+asyncpg://${local.databases[dbkey].user}:${random_password.db[dbkey].result}@127.0.0.1:5432/${local.databases[dbkey].db}"
    },
    {
      # telemetry-aggregates' second connection (TELEMETRY_DB_URL), proxied
      # on a second local port (5433) in the same sidecar — see the k8s
      # overlay generator's multi-instance proxy config for this service.
      "telemetry-aggregates-telemetry-db-url" = "postgresql+asyncpg://telemetry_readonly:telemetry-readonly@127.0.0.1:5433/telemetry"
    }
  )
}

resource "google_secret_manager_secret" "this" {
  for_each  = local.secrets
  project   = var.project_id
  secret_id = "${var.name_prefix}-${each.key}"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "this" {
  for_each    = local.secrets
  secret      = google_secret_manager_secret.this[each.key].id
  secret_data = each.value
}
