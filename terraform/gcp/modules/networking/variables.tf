variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the subnet"
  type        = string
}

variable "name_prefix" {
  description = "Prefix applied to all networking resource names (e.g. \"internstore-demo\")"
  type        = string
}

variable "subnet_cidr" {
  description = "Primary CIDR range for the GKE subnet (nodes)"
  type        = string
  default     = "10.10.0.0/20"
}

variable "pods_cidr" {
  description = "Secondary range for GKE pod IPs"
  type        = string
  default     = "10.20.0.0/14"
}

variable "services_cidr" {
  description = "Secondary range for GKE service IPs"
  type        = string
  default     = "10.30.0.0/20"
}

variable "private_service_range_cidr" {
  description = "Reserved range for VPC peering used by Memorystore private services access"
  type        = string
  default     = "10.40.0.0/20"
}
