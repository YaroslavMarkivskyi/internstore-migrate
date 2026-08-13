variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "instance_name" {
  description = "Cloud SQL instance name, e.g. \"internstore-demo-catalog\""
  type        = string
}

variable "database_name" {
  type = string
}

variable "database_user" {
  type = string
}

variable "database_password" {
  type      = string
  sensitive = true
}

variable "tier" {
  description = "Shared-core by default — see module main.tf comment for the cost justification"
  type        = string
  default     = "db-f1-micro"
}

variable "database_version" {
  description = "POSTGRES_16 for the 9 uniform instances; postgres-ai (pgvector) should also use POSTGRES_16 or later — pgvector is a plain extension, not a special image, on Cloud SQL"
  type        = string
  default     = "POSTGRES_16"
}

variable "disk_size_gb" {
  type    = number
  default = 10 # Cloud SQL's minimum
}
