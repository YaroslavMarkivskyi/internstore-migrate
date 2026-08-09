#!/usr/bin/env bash
# Re-mirrors the repo's real policies/*.rego into this directory — see the
# comment in kustomization.yaml for why this is a copy, not a live
# reference. Run after editing anything under /policies.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
cp ../../../policies/*.rego ./policies/
echo "Synced $(ls ./policies/*.rego | wc -l | tr -d ' ') policy files."
