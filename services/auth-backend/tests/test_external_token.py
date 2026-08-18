import pytest
from firebase_admin import auth as firebase_auth

from auth_backend.auth.external_token import ExternalTokenVerifier
from tests.conftest import _fake_verify_id_token, mint_external_token


@pytest.fixture(autouse=True)
def _mock_firebase(monkeypatch):
    monkeypatch.setattr(firebase_auth, "verify_id_token", _fake_verify_id_token)


# Unit-level coverage of ExternalTokenVerifier itself, independent of the
# ASGI client — test_verify.py exercises the same scenarios through
# /auth/verify end-to-end; these assert the verifier's own claim mapping
# and error handling in isolation.
async def test_valid_token_extracts_correct_claims():
    token = mint_external_token(sub="user-123", email="admin@example.com", role="admin")

    claims = ExternalTokenVerifier().verify(token)

    assert claims.sub == "user-123"
    assert claims.email == "admin@example.com"
    assert claims.role == "admin"


# check_revoked=True is passed on every call, not opt-in — confirms the
# verifier always asks Firebase to check revocation, matching
# auth/revocation.py's retired fail-closed convention.
async def test_revoked_token_is_rejected():
    token = mint_external_token(revoked=True)

    with pytest.raises(firebase_auth.RevokedIdTokenError):
        ExternalTokenVerifier().verify(token)


async def test_expired_token_is_rejected():
    token = mint_external_token(expires_in=-10)

    with pytest.raises(firebase_auth.ExpiredIdTokenError):
        ExternalTokenVerifier().verify(token)


async def test_invalid_token_is_rejected():
    with pytest.raises(firebase_auth.InvalidIdTokenError):
        ExternalTokenVerifier().verify("not-a-real-firebase-token")


async def test_disabled_user_token_is_rejected():
    token = mint_external_token(disabled=True)

    with pytest.raises(firebase_auth.UserDisabledError):
        ExternalTokenVerifier().verify(token)


async def test_token_missing_role_claim_is_rejected():
    token = mint_external_token(role=None)

    with pytest.raises(ValueError, match="role"):
        ExternalTokenVerifier().verify(token)


async def test_token_with_unrecognized_role_is_rejected():
    token = mint_external_token(role="superadmin")

    with pytest.raises(ValueError, match="role"):
        ExternalTokenVerifier().verify(token)
