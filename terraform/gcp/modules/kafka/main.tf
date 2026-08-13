# GCP Managed Service for Apache Kafka. Topic creation moves from base's
# `kafka-topic-init` Job (which the gcp overlay drops) into Terraform here,
# since Managed Kafka topics are a GCP resource in their own right —
# one fewer moving part inside the cluster.
#
# COST FLAG (see environments/demo/README.md): this is the least-pinned-down
# price in the whole stack. Confirm the real `terraform plan` cost estimate
# (or the pricing calculator) against the vcpu_count/memory_bytes below
# BEFORE the first real apply — do not assume the smallest DCU config is
# actually cheap without checking.

resource "google_managed_kafka_cluster" "this" {
  project    = var.project_id
  cluster_id = var.cluster_id
  location   = var.region
  capacity_config {
    vcpu_count   = var.vcpu_count
    memory_bytes = var.memory_bytes
  }
  gcp_config {
    access_config {
      network_configs {
        subnet = var.subnetwork_id
      }
    }
  }
}

resource "google_managed_kafka_topic" "topics" {
  for_each = toset(var.topics)

  project            = var.project_id
  topic_id           = each.value
  cluster            = google_managed_kafka_cluster.this.cluster_id
  location           = var.region
  partition_count    = 1 # matches base's kafka-topic-init — see docs/EVENT_BROKER.md
  replication_factor = 3 # Managed Kafka's minimum; base's single-broker RF1 doesn't carry over
}
