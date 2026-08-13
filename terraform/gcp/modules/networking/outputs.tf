output "network_id" {
  value = google_compute_network.main.id
}

output "network_name" {
  value = google_compute_network.main.name
}

output "subnetwork_id" {
  value = google_compute_subnetwork.gke.id
}

output "subnetwork_name" {
  value = google_compute_subnetwork.gke.name
}

output "pods_range_name" {
  value = "pods"
}

output "services_range_name" {
  value = "services"
}

output "private_service_connection" {
  description = "Used as a dependency by the memorystore module so Redis isn't created before peering exists"
  value       = google_service_networking_connection.private_service_connection.network
}

output "cloud_armor_policy_name" {
  value = google_compute_security_policy.default.name
}

output "lb_ip_address" {
  value = google_compute_global_address.lb_ip.address
}

output "lb_ip_name" {
  value = google_compute_global_address.lb_ip.name
}
