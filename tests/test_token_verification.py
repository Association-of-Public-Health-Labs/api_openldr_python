"""
Unit tests for utilities.token_verification.

Clerk tokens are simulated with a locally generated RSA key and a fake JWKS
fetcher, so no network access is needed. API tokens are created with
Flask-JWT-Extended inside the shared ``app`` fixture from conftest.py.
"""
import json
import time
from datetime import timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from flask_jwt_extended import create_access_token
from jwt.algorithms import RSAAlgorithm

from configs import paths
from utilities import token_verification as tv

ISSUER = "https://clerk.test.openldr.org.mz"
KID = "test-kid-1"
TB_ORIGIN = "https://tb.openldr.org.mz"

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_jwks(private_key=SIGNING_KEY, kid=KID):
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


def make_clerk_token(private_key=SIGNING_KEY, kid=KID, **overrides):
    now = int(time.time())
    claims = {
        "sub": "user_abc",
        "iss": ISSUER,
        "iat": now,
        "nbf": now,
        "exp": now + 60,
        "azp": TB_ORIGIN,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def jwks_fetches(monkeypatch):
    """Configure Clerk settings and a fake JWKS fetcher; return the call log."""
    calls = []

    def fake_fetch():
        calls.append(1)
        return make_jwks()

    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", None)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(fake_fetch))
    return calls


# --- Clerk (RS256) tokens --------------------------------------------------

def test_valid_clerk_token_returns_claims(jwks_fetches):
    claims = tv.verify_bearer_token(make_clerk_token())
    assert claims["sub"] == "user_abc"
    assert claims["iss"] == ISSUER


def test_expired_clerk_token_rejected(jwks_fetches):
    now = int(time.time())
    token = make_clerk_token(iat=now - 120, nbf=now - 120, exp=now - 60)
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(token)


def test_wrong_issuer_rejected(jwks_fetches):
    token = make_clerk_token(iss="https://evil.example.com")
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(token)


def test_forged_signature_rejected(jwks_fetches):
    token = make_clerk_token(private_key=OTHER_KEY)  # same kid, wrong key
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(token)


def test_missing_sub_rejected(jwks_fetches):
    token = make_clerk_token(sub=None)
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(token)


def test_unknown_kid_rejected(jwks_fetches):
    token = make_clerk_token(kid="rotated-away")
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(token)


def test_jwks_fetched_once_for_repeated_valid_tokens(jwks_fetches):
    tv.verify_bearer_token(make_clerk_token())
    tv.verify_bearer_token(make_clerk_token())
    assert len(jwks_fetches) == 1


def test_unknown_kid_refetch_is_rate_limited(monkeypatch):
    calls = []
    clock = FakeClock()

    def fake_fetch():
        calls.append(1)
        return make_jwks()

    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", None)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(fake_fetch, clock=clock))

    for i in range(20):
        with pytest.raises(tv.TokenVerificationError):
            tv.verify_bearer_token(make_clerk_token(kid=f"random-{i}"))
    assert len(calls) == 1

    clock.now += 61
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(make_clerk_token(kid="random-after-window"))
    assert len(calls) == 2


def test_jwks_unreachable_keeps_cached_keys(monkeypatch):
    clock = FakeClock()
    responses = [make_jwks()]

    def flaky_fetch():
        if responses:
            return responses.pop()
        raise ConnectionError("clerk down")

    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", None)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(flaky_fetch, clock=clock))

    assert tv.verify_bearer_token(make_clerk_token())["sub"] == "user_abc"

    clock.now += 61
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(make_clerk_token(kid="new-kid"))  # fetch fails
    # The previously cached key still verifies.
    assert tv.verify_bearer_token(make_clerk_token())["sub"] == "user_abc"


def test_missing_issuer_config_fails_closed(jwks_fetches, monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", "")
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(make_clerk_token())


def test_authorized_party_enforced_when_configured(jwks_fetches, monkeypatch):
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", "https://vl.openldr.org.mz")
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(make_clerk_token())

    monkeypatch.setattr(
        paths,
        "CLERK_AUTHORIZED_PARTIES",
        " https://tb.openldr.org.mz , https://vl.openldr.org.mz ",
    )
    assert tv.verify_bearer_token(make_clerk_token())["azp"] == TB_ORIGIN


# --- Algorithm and format abuse --------------------------------------------

def test_alg_none_rejected(jwks_fetches):
    now = int(time.time())
    token = jwt.encode(
        {"sub": "admin", "user_id": "admin", "iss": ISSUER, "iat": now, "exp": now + 60},
        key="",
        algorithm="none",
    )
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(token)


@pytest.mark.parametrize("token", [None, "", "not-a-jwt", "a.b.c"])
def test_missing_or_garbage_token_rejected(jwks_fetches, token):
    with pytest.raises(tv.TokenVerificationError):
        tv.verify_bearer_token(token)


# --- API-issued (HS256) tokens ---------------------------------------------

def test_valid_api_token_returns_claims(app):
    with app.app_context():
        token = create_access_token(identity="u1", additional_claims={"user_id": "u1"})
        claims = tv.verify_bearer_token(token)
    assert claims["user_id"] == "u1"


def test_expired_api_token_rejected(app):
    with app.app_context():
        token = create_access_token(identity="u1", expires_delta=timedelta(seconds=-1))
        with pytest.raises(tv.TokenVerificationError):
            tv.verify_bearer_token(token)


def test_hs256_token_with_wrong_secret_rejected(app):
    now = int(time.time())
    forged = jwt.encode(
        {"sub": "admin", "user_id": "admin", "type": "access", "fresh": False,
         "jti": "x", "iat": now, "nbf": now, "exp": now + 600},
        "guessed-secret",
        algorithm="HS256",
    )
    with app.app_context():
        with pytest.raises(tv.TokenVerificationError):
            tv.verify_bearer_token(forged)
