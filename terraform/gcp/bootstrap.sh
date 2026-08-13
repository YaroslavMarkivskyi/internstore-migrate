#!/usr/bin/env bash
# One-time prerequisite, run BEFORE the first `terraform init` in
# environments/demo. Not part of the Terraform-managed stack — this bucket
# and these API enablements are not touched by `terraform destroy`, since
# state has to live somewhere Terraform doesn't manage. Safe to leave
# enabled/existing between demo apply/destroy cycles.
set -euo pipefail

PROJECT_ID="${1:?Usage: bootstrap.sh <project-id> [region]}"
REGION="${2:-us-central1}"
STATE_BUCKET="${PROJECT_ID}-internstore-tfstate"

gcloud config set project "$PROJECT_ID"

gcloud services enable \
  compute.googleapis.com \
  container.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  managedkafka.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  servicenetworking.googleapis.com \
  iam.googleapis.com

if ! gcloud storage buckets describe "gs://${STATE_BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${STATE_BUCKET}" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --uniform-bucket-level-access
  gcloud storage buckets update "gs://${STATE_BUCKET}" --versioning
fi

echo
echo "Bootstrap complete. Initialize Terraform with:"
echo "  terraform -chdir=terraform/gcp/environments/demo init -backend-config=\"bucket=${STATE_BUCKET}\""
