variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "repository_id" {
  type    = string
  default = "internstore"
}

variable "gke_node_service_account" {
  description = "Email of the service account GKE nodes pull images with (Autopilot's default compute SA unless overridden)"
  type        = string
}
