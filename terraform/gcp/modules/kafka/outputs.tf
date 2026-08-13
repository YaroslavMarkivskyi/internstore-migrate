output "bootstrap_address" {
  # The google_managed_kafka_cluster resource doesn't export a
  # bootstrap-address attribute directly (checked against the provider's own
  # schema, not assumed) — GCP's documented bootstrap address format is
  # `bootstrap.<cluster_id>.<region>.managedkafka.<project_id>.cloud.goog:9092`.
  # CONFIRM this against the real cluster's `gcloud managed-kafka clusters
  # describe` output before first use — construct, don't assume.
  description = "Bootstrap server address for KAFKA_BOOTSTRAP_SERVERS — reached via the Managed Kafka Private Service Connect endpoint in-cluster"
  value       = "bootstrap.${google_managed_kafka_cluster.this.cluster_id}.${var.region}.managedkafka.${var.project_id}.cloud.goog:9092"
}

output "cluster_id" {
  value = google_managed_kafka_cluster.this.cluster_id
}
