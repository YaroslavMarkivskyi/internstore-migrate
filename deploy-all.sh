#!/usr/bin/env bash
set -euo pipefail

echo "==> 1. Initializing Terraform"
terraform -chdir=terraform/gcp/environments/demo init -backend-config="bucket=internstore-taij26-internstore-tfstate"

echo "==> 2. Applying Terraform (this will take 10-15 mins)..."
terraform -chdir=terraform/gcp/environments/demo apply -auto-approve

echo "==> 3. Getting TF outputs"
REPO_URL=$(terraform -chdir=terraform/gcp/environments/demo output -raw artifact_registry_repository_url)
CLUSTER_NAME=$(terraform -chdir=terraform/gcp/environments/demo output -raw gke_cluster_name)

echo "==> 4. Building and pushing Docker images to ${REPO_URL}..."
./k8s/build-push-gcp.sh "$REPO_URL"

echo "==> 5. Generating K8s overlay..."
python3 k8s/overlays/gcp/generate-overlay.py \
  --outputs <(terraform -chdir=terraform/gcp/environments/demo output -json) \
  --out k8s/overlays/gcp/generated

echo "==> 6. Authenticating with GKE..."
gcloud container clusters get-credentials "$CLUSTER_NAME" --region us-central1 --project internstore-taij26

echo "==> 7. Applying K8s manifests..."
kubectl apply -k k8s/overlays/gcp/

echo "==> ALL DONE! <=="
