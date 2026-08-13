variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "instance_name" {
  type    = string
  default = "internstore-demo-redis"
}

variable "network_id" {
  type = string
}

# No private_service_connection input here — the ordering dependency on the
# VPC peering existing before Redis is created is expressed as a module-level
# `depends_on` on the calling side (environments/demo/main.tf), not a fake
# resource-shaped variable.
