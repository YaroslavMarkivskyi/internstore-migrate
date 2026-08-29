# Single VPC-native network for the whole demo stack. No Cloud NAT / bastion:
# GKE Autopilot nodes get public IPs here (a deliberate simplification for a
# stack that lives a few hours per STR-154's cost model — see
# environments/demo/README.md "Deviations from the ticket's networking spec").

resource "google_compute_network" "main" {
  project                 = var.project_id
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false
  # Nothing here survives `terraform destroy` — no manual routes/peerings
  # created outside Terraform that would orphan the network deletion.
}

resource "google_compute_subnetwork" "gke" {
  project       = var.project_id
  name          = "${var.name_prefix}-gke-subnet"
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = var.subnet_cidr

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }
}

# --- Private Services Access, required by Memorystore's private-IP-only mode ---

resource "google_compute_global_address" "private_service_range" {
  project       = var.project_id
  name          = "${var.name_prefix}-psa-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  address       = split("/", var.private_service_range_cidr)[0]
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_service_connection" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_range.name]
}

# --- Cloud Armor, attached to the GCLB Ingress via BackendConfig in the k8s overlay ---


# --- Static external IP for the GCLB Ingress ---

resource "google_compute_global_address" "lb_ip" {
  project = var.project_id
  name    = "${var.name_prefix}-lb-ip"
}
