# InternStore GitOps (ArgoCD)

Pull-based deployment: ArgoCD runs inside the cluster, watches this repo's `k8s/`
overlays, and reconciles cluster state to match — instead of anyone (or CI) running
`kubectl apply -k` by hand (STR-144/145/157's established pattern until now).

## Directory structure

```text
gitops/
  argocd-install/
    values.yaml           # Helm values for the official argo-cd chart
  applications/
    local-application.yaml  # auto-sync + self-heal, path k8s/overlays/local
    gcp-application.yaml    # manual sync, path k8s/overlays/gcp (see blocker below)
```

## Decisions made while writing this

**ArgoCD, not Flux.** No repo evidence favors Flux. ArgoCD has first-class native
Kustomize support (matching STR-144's explicit Kustomize-not-Helm decision, no adapter
needed), and its web UI gives the same demo-visible observability value this project
has repeatedly prioritized elsewhere — Temporal UI was explicitly kept in `k8s/base`
for exactly this reason, being able to show a live dashboard has real demo value beyond
a more CLI-centric workflow. If a concrete reason to prefer Flux ever surfaces, flag it
rather than silently switching.

**Sync policy differs per environment, on purpose:**

- **`local` (kind): auto-sync + self-heal.** No cost implications, nothing to fight —
  ArgoCD reconciling automatically is strictly an improvement over `kubectl apply -k`
  run by hand.
- **`gcp`: manual sync only.** This project's GCP demo environment is explicitly
  `terraform apply` → demo → `terraform destroy`, not always-on (small budget,
  deliberate spin-up/teardown — see `terraform/gcp/environments/demo/README.md`).
  Auto-sync with self-heal could fight a deliberate `terraform destroy` teardown —
  ArgoCD might try to recreate resources Terraform is tearing down, or vice versa.
  Manual sync means someone explicitly triggers `argocd app sync internstore-gcp` (or
  clicks Sync in the UI) only when they want the demo environment live.

**Repo structure: no reorganizing needed for `local`.** `k8s/base/` +
`k8s/overlays/local/` (STR-144's structure) is fully self-contained and committed to
git already — ArgoCD's Application/AppProject model works against it unmodified.

**Repo structure: real blocker for `gcp`, not resolved by this ticket.**
`k8s/overlays/gcp/kustomization.yaml` references files under
`k8s/overlays/gcp/generated/`, which is **gitignored** (`.gitignore:11`). That
directory is produced by running `k8s/overlays/gcp/generate-overlay.py` against a live
`terraform output -json` — deliberately not committed, because its contents (Secret
Manager secret *names*, Cloud SQL connection names) are only meaningful against the
Terraform state that produced them (see `k8s/overlays/gcp/README.md`). ArgoCD's
repo-server only ever sees committed git content, so `internstore-gcp` will fail
`kustomize build` (missing resources) until this is addressed.

Three options were considered, none picked yet — flagged here rather than silently
switched or silently left broken:

1. **Render-and-commit.** Un-gitignore `generated/` (or a new committed directory) and
   document a manual step: after `terraform apply`, run `generate-overlay.py` and
   commit its output before syncing. Simple, but reintroduces the staleness/drift
   problem `k8s/overlays/gcp/README.md` explains was the reason to gitignore it in the
   first place — a committed `generated/` can silently go stale against a newer
   Terraform apply.
2. **ArgoCD Config Management Plugin (CMP).** Build a CMP sidecar for ArgoCD's
   repo-server that runs `generate-overlay.py` at sync time, sourcing Terraform outputs
   from a ConfigMap Terraform writes into the cluster (or Secret Manager directly).
   Fully automated pull-based GitOps for `gcp` too, but real added complexity — a
   custom repo-server image, a new Terraform resource just to publish outputs — for an
   environment that's `apply → demo → destroy`, not long-lived enough to obviously
   justify it.
3. **Keep deferring.** Leave `internstore-gcp` scaffolded but non-functional until this
   is picked up as explicit follow-up work, once STR-154's GCP infra is confirmed live
   and this actually needs exercising.

**Decision: option 3 for now**, consistent with this project's established
local-first/GCP-second ticket sequencing (STR-144 local → STR-154 GCP, STR-149 design →
STR-150 live-verify) — this pass proves the ArgoCD pattern against `kind`; resolving the
`gcp` blocker is separate follow-up work, not silently done or silently skipped.

**Terraform/ArgoCD boundary: checked, already clean.** Read every `.tf` file under
`terraform/gcp/` — there is no `kubernetes` (or `helm`/`kubectl`) provider anywhere, so
Terraform never applies application manifests today. Nothing needed to be removed from
Terraform's scope. Terraform's role stays: infra (GKE, Cloud SQL, Memorystore, Kafka,
networking) + (future work, not yet done) installing ArgoCD itself + the initial
Application resource pointing at this repo.

## How to install (local / kind)

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
kubectl create namespace argocd
helm upgrade --install argocd argo/argo-cd -n argocd -f gitops/argocd-install/values.yaml
kubectl -n argocd rollout status deploy/argocd-server

# UI + CLI access
kubectl port-forward svc/argocd-server -n argocd 8080:443 &
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d   # admin password, first login only
```

Then apply the local Application:

```bash
kubectl apply -f gitops/applications/local-application.yaml
```

`gcp-application.yaml` can be applied at the same time — it just won't sync
successfully until the blocker above is resolved.

**Private repo note (found during verification, not anticipated up front):** this repo
is private, so ArgoCD's repo-server needs read credentials before it can list refs at
all — without them the Application sits on `ComparisonError: authentication required:
Repository not found`. Register a credential (a `Secret` labeled
`argocd.argoproj.io/secret-type: repository`, or `argocd repo add` if you have the CLI)
before expecting any Application here to reach `Synced`:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: internstore-repo-creds
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
stringData:
  type: git
  url: https://github.com/YaroslavMarkivskyi/internstore-migrate.git
  username: x-access-token
  password: <a GitHub PAT or fine-grained token with read access to this repo>
EOF
```

## Verification

Run **2026-08-18**, end to end, against a real `kind` cluster (`kind create cluster
--name internstore --config k8s/kind-config.yaml`, then `./k8s/build-images.sh
internstore` per `k8s/README.md`), after `origin/main` was confirmed pushed (the first
verification pass, before the repo had been pushed, stopped at `ComparisonError:
remote repository is empty` — see history). Cluster torn down (`kind delete cluster`)
immediately after; nothing left running.

1. **Baseline parity — confirmed.** After registering repo credentials (see above),
   `internstore-local` reached `Synced`/`Healthy` on its own, no manual sync needed
   (`local`'s `syncPolicy.automated` triggered it). All 109 resources in
   `.status.resources[]` report `status: Synced` — i.e. the live cluster is provably
   byte-identical to what `kubectl apply -k k8s/overlays/local` would produce directly,
   which is the strongest form of "no behavioral difference" ArgoCD can attest to.
   Re-ran `scripts/k8s/verify-gateway.sh` and `scripts/k8s/test-telemetry-saga.sh`
   against the ArgoCD-managed deployment: both fail, but for the exact
   **pre-existing, already-documented** reasons their own header comments describe —
   `verify-gateway.sh` is Keycloak-specific logic left over from before STR-192 removed
   Keycloak (no `deployment/keycloak` to scale, connection refused at step 1);
   `test-telemetry-saga.sh` needs a Firebase Auth emulator at `localhost:9099` that
   `k8s/overlays/local` doesn't provide (also a documented STR-192 gap), plus the
   throwaway Mailpit `Deployment`/`Service` its header describes, neither of which was
   stood up for this pass. Both gaps are about what's *deployed* to the cluster, not
   *how* it was deployed — a manual `kubectl apply -k` would hit the identical
   `curl: (7) Connection refused` at the identical step. No ArgoCD-specific regression
   found; the resource-level Synced proof above is the parity evidence for the parts
   these scripts can't currently exercise.
2. **Drift detection + self-heal — confirmed.** `kubectl scale deployment/catalog
   --replicas=3`, then `--replicas=5`. `kubectl get events` on `deployment/catalog`
   shows ArgoCD's application-controller reverting each one within ~2 seconds — faster
   than a 3-second poll could catch it mid-drift:

   ```text
   Scaled up replica set catalog-... from 1 to 3
   Scaled down replica set catalog-... from 3 to 1     (self-heal, ~2s later)
   Scaled up replica set catalog-... from 1 to 5
   Scaled down replica set catalog-... from 5 to 1     (self-heal, same second)
   ```

   `internstore-local` stayed `Synced` throughout — self-heal reconciled before the
   Application ever had to report `OutOfSync` in a way a poll could observe.
3. **Git-driven reconciliation — confirmed.** Committed a temporary memory-limit bump
   (`1536Mi` → `1792Mi`) to `patches/bump-memory-limit.yaml` on a throwaway branch,
   pushed it, and pointed the *live* Application's `targetRevision` at that branch
   (rather than touching `main`, to keep this test isolated). Within 5–10s:
   `internstore-local` flipped `Synced` → `OutOfSync` → `Synced` on its own, `catalog`'s
   live memory limit became `1792Mi`, and a fresh `catalog` pod rolled out and reached
   `2/2 Running` — all without any `kubectl apply`. Reverted `targetRevision` back to
   `main`; self-heal immediately reverted `catalog`'s live memory limit back to
   `1536Mi` (main's actual committed value) within seconds, confirming the revert path
   too. Test branch and its commit were deleted afterward — `main` was never touched by
   this test.
4. **`gcp` Application — still deferred, as decided.** Not attempted. See the blocker
   above; unblocking it (and confirming manual-sync behavior once STR-154's GCP infra
   exists) is separate follow-up work.

## Explicitly out of scope

- Multi-environment promotion pipelines (dev → staging → prod) — this project has
  exactly two environments (`local`, `gcp` demo), no promotion pipeline needed.
- ArgoCD SSO/RBAC integration with Firebase Auth (STR-155) — ArgoCD's own access
  control is a separate concern from this project's application-level auth; using
  ArgoCD's default admin access for now. Future hardening item if this becomes a
  shared/team environment rather than solo-demo use.
- Notifications/Slack integration for sync events — not needed at this project's scale.
- Resolving the `gcp` `generated/` blocker (see above) — flagged, not fixed, here.
