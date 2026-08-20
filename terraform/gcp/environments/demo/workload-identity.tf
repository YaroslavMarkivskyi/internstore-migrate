# One GSA per k8s service that needs Secret Manager access, bound to a KSA
# of the *same name* in the `default` namespace (the k8s overlay's
# SecretProviderClasses + Deployment patches set
# `serviceAccountName: <service>` to match) via Workload Identity. Each GSA
# only gets `secretAccessor` on the secrets that service actually reads —
# not a single shared GSA — so a compromised pod can't read every
# credential in the stack.

locals {
  service_secrets = {
    catalog = [
      "internal-token-secret", "catalog-database-url",
      "gcs-hmac-access-id", "gcs-hmac-secret",
    ]
    inventory = ["internal-token-secret", "inventory-database-url"]
    orders = [
      "internal-token-secret", "orders-database-url",
      "stripe-secret-key", "stripe-webhook-secret",
    ]
    telemetry = ["internal-token-secret", "telemetry-database-url"]
    "telemetry-aggregates" = [
      "internal-token-secret", "telemetry-aggregates-database-url",
      "telemetry-aggregates-telemetry-db-url",
    ]
    security = ["internal-token-secret", "security-database-url"]
    chat = [
      "internal-token-secret", "chat-database-url",
      "gcs-hmac-access-id", "gcs-hmac-secret",
    ]
    payments       = ["internal-token-secret", "payments-database-url"]
    "ai-assistant" = ["internal-token-secret", "ai-assistant-database-url", "openai-api-key"]
    "mcp-gateway"  = ["internal-token-secret", "mcp-gateway-database-url", "openai-api-key"]
    # FIREBASE_PROJECT_ID isn't a Secret Manager secret (not sensitive) and
    # wiring the real GCP Firebase project id into auth-backend's config is
    # a separate follow-up — see generate-overlay.py's matching comment.
    "auth-backend"             = ["internal-token-secret"]
    "checkout-workflow-worker" = ["internal-token-secret"]
    temporal                   = ["temporal-db-password"]
    # notifications has no secret.yaml in base — no GSA/WI binding needed.
  }

  service_secret_pairs = flatten([
    for svc, secret_ids in local.service_secrets : [
      for sid in secret_ids : { service = svc, secret_id = sid }
    ]
  ])
}

resource "google_service_account" "workload" {
  for_each     = local.service_secrets
  project      = var.project_id
  account_id   = "${var.name_prefix}-${each.key}"
  display_name = "Workload Identity GSA for the ${each.key} k8s service (STR-154)"
}

resource "google_service_account_iam_member" "workload_identity_binding" {
  for_each           = local.service_secrets
  service_account_id = google_service_account.workload[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[default/${each.key}]"
}

resource "google_secret_manager_secret_iam_member" "access" {
  for_each  = { for pair in local.service_secret_pairs : "${pair.service}/${pair.secret_id}" => pair }
  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value.secret_id].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workload[each.value.service].email}"
}

# Cloud SQL Auth Proxy sidecar access — every service with a database
# connection also needs roles/cloudsql.client on its GSA.
locals {
  service_db_keys = {
    catalog                = ["catalog"]
    inventory              = ["inventory"]
    orders                 = ["orders"]
    telemetry              = ["telemetry"]
    "telemetry-aggregates" = ["telemetry-aggregates", "telemetry"]
    security               = ["security"]
    chat                   = ["chat"]
    payments               = ["payments"]
    "ai-assistant"         = ["ai"]
    "mcp-gateway"          = ["ai"]
    temporal               = ["temporal"]
  }
}

resource "google_project_iam_member" "cloudsql_client" {
  for_each = local.service_db_keys
  project  = var.project_id
  role     = "roles/cloudsql.client"
  member   = "serviceAccount:${google_service_account.workload[each.key].email}"
}
