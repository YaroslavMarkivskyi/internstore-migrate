resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  format        = "DOCKER"
  description   = "InternStore service images (demo environment) — see k8s/build-push-gcp.sh"

  # Keeps the repo from silently growing across repeated demo cycles; not
  # required for teardown (the repo itself is destroyed with the rest of
  # the stack), just avoids storage cost creep for anyone leaving it up
  # briefly between apply/destroy cycles during iteration.
  cleanup_policies {
    id     = "keep-last-3-per-image"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }
}

resource "google_artifact_registry_repository_iam_member" "gke_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${var.gke_node_service_account}"
}
