output "repository_url" {
  description = "e.g. us-central1-docker.pkg.dev/PROJECT/internstore — prefix each service image with this"
  value       = "${google_artifact_registry_repository.images.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
