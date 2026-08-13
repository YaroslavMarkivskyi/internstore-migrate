# Single shared Redis instance (base's `redis` Deployment served every
# service alike — no per-service split here either). Basic tier: no HA,
# cheapest per-GB rate, fine for a torn-down-same-day demo.

resource "google_redis_instance" "this" {
  project        = var.project_id
  name           = var.instance_name
  region         = var.region
  tier           = "BASIC"
  memory_size_gb = 1 # Memorystore's minimum
  redis_version  = "REDIS_7_0"

  authorized_network      = var.network_id
  connect_mode            = "PRIVATE_SERVICE_ACCESS"
  transit_encryption_mode = "DISABLED" # demo-only, keeps the client config identical to compose's plain redis://
}
