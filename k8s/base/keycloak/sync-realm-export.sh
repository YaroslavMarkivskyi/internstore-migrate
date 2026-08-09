#!/usr/bin/env bash
# Re-mirrors /keycloak/realm-export.json into config/ — see the comment in
# kustomization.yaml. Run after editing the real realm-export.json.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
cp ../../../keycloak/realm-export.json ./config/realm-export.json
echo "Synced realm-export.json."
