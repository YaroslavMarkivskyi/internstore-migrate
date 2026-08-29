#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

REPO_URL="${1:?Usage: build-push-gcp.sh <artifact-registry-repository-url> [tag]}"
TAG="${2:-latest}"

gcloud auth configure-docker "$(echo "$REPO_URL" | cut -d/ -f1)" --quiet

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
  echo "==> Building and Pushing ${tag} from ${ctx}"
  docker buildx build --platform linux/amd64 -t "${tag}" --push "${ctx}"
done

echo "Done. Every internstore/* image is pushed to ${REPO_URL} at tag :${TAG}."
