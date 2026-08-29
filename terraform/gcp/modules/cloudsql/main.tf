# Reusable per-service Postgres instance. environments/demo instantiates
# this once per service (10 uniform instances + postgres-ai), per STR-154's
# "confirm before assuming" resolution: at db-f1-micro/shared-core pricing
# and this stack's apply->demo->destroy lifecycle, 10 separate instances
# costs on the order of $0.13/hr total — not the always-on ~$80-100/mo the
# ticket was worried about. See environments/demo/README.md for the math.

resource "google_sql_database_instance" "this" {
  project             = var.project_id
  name                = var.instance_name
  region              = var.region
  database_version    = var.database_version
  deletion_protection = false # mandatory for a stack that must `terraform destroy` cleanly

  settings {
    edition = "ENTERPRISE"
    tier              = var.tier
    availability_type = "ZONAL" # no HA — demo only, halves the (already tiny) cost
    disk_size         = var.disk_size_gb
    disk_type         = "PD_SSD"
    disk_autoresize   = false

    backup_configuration {
      enabled = false # nothing here needs to survive past `terraform destroy`
    }

    ip_configuration {
      ipv4_enabled = true # public IP + Cloud SQL Auth Proxy sidecar, see k8s/overlays/gcp
    }
  }
}

resource "google_sql_database" "db" {
  project  = var.project_id
  name     = var.database_name
  instance = google_sql_database_instance.this.name
}

resource "google_sql_user" "app" {
  project  = var.project_id
  name     = var.database_user
  instance = google_sql_database_instance.this.name
  password = var.database_password
}
