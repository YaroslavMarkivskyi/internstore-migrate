#!/usr/bin/env bash
# Same build matrix as build-images.sh, but tags + pushes to the
# Terraform-provisioned Artifact Registry repo instead of loading into a
# local kind cluster. Usage:
#   ./k8s/build-push-gcp.sh <artifact-registry-repository-url> [tag]
# repository-url is terraform/gcp/environments/demo's
# artifact_registry_repository_url output, e.g.
#   us-central1-docker.pkg.dev/my-project/internstore
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

REPO_URL="${1:?Usage: build-push-gcp.sh <artifact-registry-repository-url> [tag]}"
TAG="${2:-latest}"

gcloud auth configure-docker "$(echo "$REPO_URL" | cut -d/ -f1)" --quiet

# name -> build context — identical to build-images.sh's map, kept in sync
# by hand (same reasoning as k8s/overlays/gcp/generate-overlay.py's tables:
# small enough not to be worth a shared source of truth for this ticket).
declare -A IMAGES=(
  [auth-backend]="services/auth-backend"
  [catalog]="services/catalog"
  [inventory]="services/inventory"
  [orders]="services/orders"
  [payments]="services/payments"
  [checkout-workflow-worker]="services/checkout-workflow"
  [telemetry]="services/telemetry"
  [telemetry-aggregates]="services/telemetry-aggregates"
  [mock-camera]="services/security/mock-camera"
  [security]="services/security"
  [notifications]="services/notifications"
  [chat]="services/chat"
  [ai-assistant]="services/ai-assistant"
  [mcp-gateway]="services/mcp-gateway"
  [nginx]="nginx"
)

for name in "${!IMAGES[@]}"; do
  ctx="${IMAGES[$name]}"
  tag="${REPO_URL}/${name}:${TAG}"
  echo "==> Building ${tag} from ${ctx}"
  docker build -t "${tag}" "${ctx}"
  echo "==> Pushing ${tag}"
  docker push "${tag}"
done

echo "Done. Every internstore/* image is pushed to ${REPO_URL} at tag :${TAG}."
echo "Point k8s/overlays/gcp/kustomization.yaml's images[].newTag at '${TAG}' if it isn't already."
