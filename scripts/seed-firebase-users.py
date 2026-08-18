#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["firebase-admin>=6.5.0"]
# ///
"""STR-192: Firebase equivalent of keycloak/realm-export.json's pre-seeded
dev users (removed by this ticket along with Keycloak itself). Creates the
two standard dev test users this project's verification scripts assume
exist, each with a {"role": ...} custom claim (STR-181's replacement for
Keycloak's realm_access.roles):

  customer@example.com / Customer123    -> {"role": "customer"}
  admin@example.com    / Admin123456    -> {"role": "admin"}

Idempotent: safe to re-run against an already-seeded emulator — existing
users are left alone (password unchanged) but have their custom claims
reconciled to the values above, in case they drifted.

Targets the Firebase Auth emulator by default (FIREBASE_AUTH_EMULATOR_HOST
defaults to localhost:9099, matching docker-compose.yml's published port —
override it to point elsewhere). Run after `docker compose up -d`:

    uv run scripts/seed-firebase-users.py

Not for the real GCP Firebase project: STR-181 flagged that as needing its
own idempotent admin-side script (this one could be parameterized to target
either, per that ticket's "nice-to-have, not a requirement" note, but isn't
today — it always talks to whatever FIREBASE_AUTH_EMULATOR_HOST points at).
"""
import os
import sys

os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")

import firebase_admin  # noqa: E402
from firebase_admin import auth, credentials  # noqa: E402

PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "internstore-dev")

DEV_USERS = [
    {"email": "customer@example.com", "password": "Customer123", "role": "customer"},
    {"email": "admin@example.com", "password": "Admin123456", "role": "admin"},
]


def seed_user(email: str, password: str, role: str) -> None:
    try:
        user = auth.get_user_by_email(email)
        print(f"{email}: already exists (uid={user.uid}), leaving password as-is")
    except auth.UserNotFoundError:
        user = auth.create_user(email=email, password=password, email_verified=True)
        print(f"{email}: created (uid={user.uid})")

    if user.custom_claims != {"role": role}:
        auth.set_custom_user_claims(user.uid, {"role": role})
        print(f"{email}: set custom claim role={role}")
    else:
        print(f"{email}: custom claim role={role} already correct")


def main() -> None:
    if "FIREBASE_AUTH_EMULATOR_HOST" not in os.environ:
        # setdefault above always sets it, so this can't actually happen —
        # kept as a guard in case that line is ever removed, since running
        # create_user/set_custom_user_claims against a *real* Firebase
        # project by accident would be a real, hard-to-undo mistake.
        print("Refusing to run without FIREBASE_AUTH_EMULATOR_HOST set.", file=sys.stderr)
        sys.exit(1)

    firebase_admin.initialize_app(credentials.ApplicationDefault(), {"projectId": PROJECT_ID})

    for u in DEV_USERS:
        seed_user(u["email"], u["password"], u["role"])


if __name__ == "__main__":
    main()
