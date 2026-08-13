output "cluster_name" {
  value = google_container_cluster.autopilot.name
}

output "endpoint" {
  value     = google_container_cluster.autopilot.endpoint
  sensitive = true
}

output "ca_certificate" {
  value     = google_container_cluster.autopilot.master_auth[0].cluster_ca_certificate
  sensitive = true
}

# Autopilot's default node service account (used by the artifact-registry
# module to grant image-pull access). Autopilot always uses the project's
# default Compute Engine SA unless a custom one is wired in, which this
# demo module deliberately doesn't do (one less resource to manage/destroy).
output "node_service_account" {
  value = "${data.google_project.this.number}-compute@developer.gserviceaccount.com"
}
