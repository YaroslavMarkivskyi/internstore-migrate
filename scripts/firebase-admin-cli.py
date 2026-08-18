#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["firebase-admin>=6.5.0"]
# ///
"""STR-192: thin Firebase Admin SDK CLI for the handful of operations the
saga/verify scripts need that have no REST equivalent reachable from plain
curl/jq (unlike login, which uses the Identity Toolkit REST API directly —
see e.g. test-auth-flows.sh's login()). Firebase's client REST API has no
"revoke this user's tokens" call at all (that's deliberately admin-only,
unlike Keycloak's client-facing /logout endpoint which did double duty as
revocation) — only the Admin SDK can do it.

Targets the Firebase Auth emulator by default (FIREBASE_AUTH_EMULATOR_HOST
defaults to localhost:9099), same as scripts/seed-firebase-users.py.

Usage:
    uv run scripts/firebase-admin-cli.py revoke-refresh-tokens <uid>
    uv run scripts/firebase-admin-cli.py update-password <uid> <new-password>
"""
import os
import sys

os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")

import firebase_admin  # noqa: E402
from firebase_admin import auth, credentials  # noqa: E402

PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "internstore-dev")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    command, uid = sys.argv[1], sys.argv[2]
    firebase_admin.initialize_app(credentials.ApplicationDefault(), {"projectId": PROJECT_ID})

    if command == "revoke-refresh-tokens":
        auth.revoke_refresh_tokens(uid)
        print(f"{uid}: refresh tokens revoked")
    elif command == "update-password":
        if len(sys.argv) < 4:
            print("update-password requires <uid> <new-password>", file=sys.stderr)
            sys.exit(1)
        auth.update_user(uid, password=sys.argv[3])
        print(f"{uid}: password updated")
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
