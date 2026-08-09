#!/usr/bin/env bash
# Builds every service image this manifest set references (same build
# contexts as docker-compose.yml's `build:` blocks) and loads each into a
# running kind cluster. Usage: ./k8s/build-images.sh [kind-cluster-name]
#
# For minikube instead of kind, replace the `kind load docker-image` line
# with `minikube image load <tag>` (or point your shell's docker client at
# minikube's daemon via `eval $(minikube docker-env)` before this script's
# `docker build` calls, and skip the load step entirely).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

CLUSTER_NAME="${1:-internstore}"

# name -> build context (mirrors docker-compose.yml's `build:` paths)
declare -A IMAGES=(
  [auth-backend]="services/auth-backend"
  [catalog]="services/catalog"
  [inventory]="services/inventory"
  [orders]="services/orders"
  [payments]="services/payments"
  [checkout-workflow-worker]="services/checkout-workflow"
  [telemetry]="services/telemetry"
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
  tag="internstore/${name}:local"
  echo "==> Building ${tag} from ${ctx}"
  docker build -t "${tag}" "${ctx}"
  echo "==> Loading ${tag} into kind cluster '${CLUSTER_NAME}'"
  kind load docker-image "${tag}" --name "${CLUSTER_NAME}"
done

echo "Done. Every internstore/*:local image is built and loaded into '${CLUSTER_NAME}'."
