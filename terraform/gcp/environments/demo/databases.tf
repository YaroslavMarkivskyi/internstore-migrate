# One Cloud SQL instance per k8s/base/postgres-* directory (mirrors that
# topology 1:1, including postgres-ai's pgvector requirement). This is 10
# instances, matching the ticket's "10, including Temporal's" estimate.
# (It was briefly 11 — k8s/base used to also have postgres-keycloak, one
# more than the ticket's original estimate — until STR-192 removed
# Keycloak entirely in favor of Firebase, STR-181/STR-192.) See README.md
# for the cost math this count is based on.

locals {
  databases = {
    catalog                = { db = "catalog", user = "catalog" }
    inventory              = { db = "inventory", user = "inventory" }
    orders                 = { db = "orders", user = "orders" }
    telemetry              = { db = "telemetry", user = "telemetry" }
    "telemetry-aggregates" = { db = "telemetry-aggregates", user = "telemetry-aggregates" }
    security               = { db = "security", user = "security" }
    chat                   = { db = "chat", user = "chat" }
    payments               = { db = "payments", user = "payments" }
    temporal               = { db = "temporal", user = "temporal" }
    ai                     = { db = "ai", user = "ai" } # pgvector — see module cloudsql's database_version comment
  }
}

resource "random_password" "db" {
  for_each = local.databases
  length   = 24
  special  = false # keeps generated passwords URL-safe for DATABASE_URL without extra escaping
}

module "cloudsql" {
  for_each = local.databases
  source   = "../../modules/cloudsql"

  project_id        = var.project_id
  region            = var.region
  instance_name     = "${var.name_prefix}-${each.key}"
  database_name     = each.value.db
  database_user     = each.value.user
  database_password = random_password.db[each.key].result
}

# telemetry-aggregates' backfill job reads postgres-telemetry read-only (see
# k8s/base/telemetry/secret.yaml comment on the telemetry_readonly role,
# created by telemetry's own Alembic migration 69ff8539f688). That
# migration runs against telemetry's own DB regardless of host, so this
# instance doesn't need a Terraform-managed extra user — just a second
# Cloud SQL Auth Proxy connection wired up in the k8s overlay pointed at
# postgres-telemetry's connection_name, using the same telemetry_readonly
# credentials the migration already created.
