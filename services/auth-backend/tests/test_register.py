"""POST /auth/register — self-service customer sign-up. The frontend can't
set the `role: customer` custom claim itself (external_token.py rejects a
token without it), so auth-backend creates the Firebase user and sets the
claim server-side."""

import uuid
from types import SimpleNamespace

import pytest
from firebase_admin import auth as firebase_auth


@pytest.fixture
def firebase_stub(monkeypatch):
    created: list[dict] = []
    claims: dict[str, dict] = {}

    def _create_user(*, uid, email, password, display_name=None):
        if any(u["email"] == email for u in created):
            raise firebase_auth.EmailAlreadyExistsError("exists", cause=None, http_response=None)
        created.append({"uid": uid, "email": email, "password": password, "display_name": display_name})
        return SimpleNamespace(uid=uid)

    def _set_claims(uid, value):
        claims[uid] = value

    monkeypatch.setattr(firebase_auth, "create_user", _create_user)
    monkeypatch.setattr(firebase_auth, "set_custom_user_claims", _set_claims)
    return SimpleNamespace(created=created, claims=claims)


_BODY = {
    "email": "new.customer@example.com",
    "password": "Secret123!",
    "first_name": "New",
    "last_name": "Customer",
}


async def test_register_creates_user_and_sets_customer_claim(client, firebase_stub):
    resp = await client.post("/auth/register", json=_BODY)

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ok"
    uid = body["uid"]
    # chat's Room.customer_id is a UUID column — the uid must parse as one.
    assert uuid.UUID(uid)
    assert firebase_stub.created[0]["email"] == "new.customer@example.com"
    assert firebase_stub.created[0]["display_name"] == "New Customer"
    assert firebase_stub.claims[uid] == {"role": "customer"}


async def test_register_rejects_a_duplicate_email(client, firebase_stub):
    await client.post("/auth/register", json=_BODY)
    resp = await client.post("/auth/register", json=_BODY)

    assert resp.status_code == 409


async def test_register_validates_email_and_password(client, firebase_stub):
    bad_email = await client.post("/auth/register", json={**_BODY, "email": "not-an-email"})
    assert bad_email.status_code == 422

    short_pw = await client.post("/auth/register", json={**_BODY, "password": "short"})
    assert short_pw.status_code == 422

    assert firebase_stub.created == []
