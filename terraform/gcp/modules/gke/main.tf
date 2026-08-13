data "google_project" "this" {
  project_id = var.project_id
}

# GKE Autopilot cluster. deletion_protection is explicitly false — this
# stack is torn down after every demo (STR-154's cost model), a protected
# cluster would break `terraform destroy`.

resource "google_container_cluster" "autopilot" {
  project  = var.project_id
  name     = var.cluster_name
  location = var.region

  enable_autopilot    = true
  deletion_protection = false

  network    = var.network_id
  subnetwork = var.subnetwork_id

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  release_channel {
    channel = "REGULAR"
  }

  # Workload Identity is on by default for Autopilot, declared explicitly
  # so it can't silently regress if Autopilot's defaults ever change.
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Autopilot manages node config; the only thing worth setting here vs.
  # accepting Autopilot defaults is keeping cost predictable — no extra
  # add-ons (Istio, config sync, etc.) are enabled.
  vertical_pod_autoscaling {
    enabled = true
  }
}
