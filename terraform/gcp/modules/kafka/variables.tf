variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "cluster_id" {
  type    = string
  default = "internstore-demo-kafka"
}

variable "subnetwork_id" {
  type = string
}

variable "vcpu_count" {
  description = "Smallest documented Managed Kafka capacity unit — CONFIRM against `terraform plan`/pricing calculator before first apply (see main.tf's COST FLAG comment)"
  type        = number
  default     = 3
}

variable "memory_bytes" {
  type    = number
  default = 3221225472 # 3 GiB, matched 1:1 to vcpu_count per GCP's DCU ratio
}

variable "topics" {
  description = "Mirrors docs/EVENT_BROKER.md's topic list (base's kafka-topic-init Job, which the gcp overlay drops in favor of this)"
  type        = list(string)
  default = [
    "order-events",
    "inventory-events",
    "telemetry-events",
    "catalog-events",
    "chat-events",
    "ops-events",
  ]
}
