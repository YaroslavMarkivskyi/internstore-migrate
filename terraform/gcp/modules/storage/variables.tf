variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "bucket_name" {
  description = "Globally unique — must include the project ID or a random suffix"
  type        = string
}
