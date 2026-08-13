# Consumed by k8s/overlays/gcp/generate-overlay.py via
# `terraform output -json` — this is the "Terraform outputs feeding into
# Kustomize" mechanism the ticket asks for. Nothing sensitive is exposed
# here: secret *values* stay in Secret Manager, only structural data
# (hosts, instance/connection names, GSA emails) crosses this boundary.

output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "gke_cluster_name" {
  value = module.gke.cluster_name
}

output "artifact_registry_repository_url" {
  value = module.artifact_registry.repository_url
}

output "load_balancer_ip" {
  value = module.networking.lb_ip_address
}

output "cloud_armor_policy_name" {
  value = module.networking.cloud_armor_policy_name
}

output "kafka_bootstrap_address" {
  value = module.kafka.bootstrap_address
}

output "redis_host" {
  value = module.memorystore.host
}

output "redis_port" {
  value = module.memorystore.port
}

output "gcs_bucket_name" {
  value = module.storage.bucket_name
}

output "gcs_s3_compatible_endpoint" {
  value = module.storage.s3_compatible_endpoint
}

output "cloudsql_connection_names" {
  description = "db key -> PROJECT:REGION:INSTANCE, for the Cloud SQL Auth Proxy sidecar patch args"
  value       = { for k, m in module.cloudsql : k => m.connection_name }
}

output "workload_identity_gsa_emails" {
  description = "k8s service name -> GSA email, for the SecretProviderClass Workload Identity annotation"
  value       = { for k, sa in google_service_account.workload : k => sa.email }
}

output "secret_manager_secret_ids" {
  description = "secret key -> full Secret Manager secret_id, for SecretProviderClass secret refs"
  value       = { for k, s in google_secret_manager_secret.this : k => s.secret_id }
}
