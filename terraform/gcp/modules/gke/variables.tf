variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "cluster_name" {
  type    = string
  default = "internstore-demo"
}

variable "network_id" {
  type = string
}

variable "subnetwork_id" {
  type = string
}

variable "pods_range_name" {
  type = string
}

variable "services_range_name" {
  type = string
}
