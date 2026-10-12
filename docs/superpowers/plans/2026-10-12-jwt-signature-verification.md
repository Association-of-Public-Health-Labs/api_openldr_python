# JWT Signature Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every reporting endpoint (TB GeneXpert, TB Cultura, HIV VL, HIV EID, including both patients modules) accepts only cryptographically verified bearer tokens. Anything else gets HTTP 401.

**Architecture:**
- All reporting controllers authenticate through `authenticate_request()` in `utilities/controller_helpers.py`. Today it decodes the JWT **without verifying the signature** (`get_unverified_payload`).
- We add one module, `utilities/token_verification.py`, that verifies the two token kinds the API actually receives:
  - **Clerk session tokens** (RS256, from the dashboards' `getToken()`), checked against Clerk's JWKS, issuer, expiry and optional authorized parties.
  - **This API's own `/auth` login tokens** (HS256, Flask-JWT-Extended), checked with the app's JWT secret.
- `authenticate_request()` switches to the new module and returns a fixed 401 body on failure. The unverified decoder and dead helpers are deleted.

**Tech Stack:** Python 3.12, Flask 3.1, Flask-RESTful, Flask-JWT-Extended 4.7.1, PyJWT 2.10.1, cryptography 45, requests 2.32, pytest.

**Spec:** `openldr-monorepo/docs/superpowers/specs/2026-10-12-vl-dashboard-migration-design.md`, section 3 "Piece 0 — JWT verification". It lives in the monorepo repo, branch `docs/vl-dashboard-migration-spec`.

## Global Constraints

- Branch `security/verify-jwt-signatures` off `dev`; the PR targets `dev`.
- **Accepted Clerk tokens:**
  - only `alg = RS256`, key chosen by `kid` from `CLERK_JWTS_URL`
  - `iss` must equal `CLERK_ISSUER`
  - `exp`, `iat`, `iss`, `sub` are required
  - 5-second clock leeway
- **Accepted API tokens:** only `alg = HS256`, verified by `flask_jwt_extended.decode_token`.
- **Any other algorithm** (including `none`) is rejected.
- **Fail closed:** if `CLERK_ISSUER` or `CLERK_JWTS_URL` is empty, every RS256 token is rejected.
- **JWKS fetch:**
  - 5-second timeout
  - cached in process
  - re-fetched on an unknown `kid` at most once every 60 seconds
  - a failed fetch keeps the previously cached keys
- **401 response body is exactly** `{"status": "error", "code": 401, "message": "Invalid or missing token"}`. No exception text. The reason goes to the log only.
- **New optional config** `CLERK_AUTHORIZED_PARTIES` (comma-separated origins). When set, a Clerk token's `azp` must be in it. When empty, no `azp` check.
  - Read via `get_config("Clerk", "clerk_authorized_parties", "CLERK_AUTHORIZED_PARTIES")`: `configs.ini` on Windows, environment variable on Linux.
- No new dependencies. `requirements.txt` already pins PyJWT, cryptography and requests.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Clerk JWKS endpoint down or slow.** Tokens whose `kid` is already cached keep working. Tokens with an unknown `kid` get 401 within about 5 seconds, never a 500 or a hang. *(Task 1: `test_jwks_unreachable_keeps_cached_keys`)*
2. **A burst of tokens carrying random `kid`s** (scanning or abuse). Clerk's JWKS URL is fetched at most once per 60 seconds, not once per request. *(Task 1: `test_unknown_kid_refetch_is_rate_limited`)*
3. **Algorithm tricks.** An unsigned `alg: none` token, or an HS256 token signed with a guessed secret, is rejected even though it carries an Admin `user_id`. *(Task 1: `test_alg_none_rejected`, `test_hs256_token_with_wrong_secret_rejected`)*
4. **Authorization header variants from real clients.** `bearer <t>` (lowercase), extra spaces, `Basic <x>`, `Bearer` with no token, and no header at all. Valid forms authenticate; the rest get 401 and never a 500. *(Task 2: `test_get_token_*`)*
5. **Error body leakage.** The 401 body is the fixed message on every path, with no PyJWT exception text or key ids. *(Task 2: `test_rejected_requests_return_fixed_401_body`)*

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `utilities/token_verification.py` | Create | `TokenVerificationError`, `JwksCache`, `verify_bearer_token(token) -> dict` |
| `configs/paths.py` | Modify (after line 80) | Add `CLERK_AUTHORIZED_PARTIES` |
| `utilities/utils.py` | Modify | Make `get_token` parse `Bearer` robustly. Delete `get_unverified_payload`, `get_public_key`, `verify_clerk_token` (lines ~704–760). |
| `utilities/controller_helpers.py` | Modify | `authenticate_request()` uses `verify_bearer_token`. Add `unauthorized_response()`. |
| `tb/gxpert/controllers/common.py` | Modify | Delete dead `execute_tb_service` and the imports only it used |
| `tools/check_clerk_token.py` | Create | Operator script: verify a real token against the configured issuer/JWKS before deploying |
| `tests/test_token_verification.py` | Create | Unit tests for the verifier |
| `tests/test_auth_enforcement.py` | Create | Endpoint-level 401/200 tests and `get_token` parsing tests |
| `tests/README.md`, `tests/hiv/test_vl_*.py`, `tests/hiv/test_eid_*.py`, `tests/tb/test_tb_facility.py` | Modify | Remove the stale "API does not enforce 401" notes |
| `CLAUDE.md` | Modify | Document the auth contract and the new config key |

---

### Task 1: Token verifier module

**Files:**
- Create: `utilities/token_verification.py`
- Modify: `configs/paths.py` (insert after line 80, `CLERK_PUBLIC_KEY = ...`)
- Test: `tests/test_token_verification.py`

**Interfaces:**
- Consumes: `configs.paths.CLERK_ISSUER`, `configs.paths.CLERK_JWTS_URL`, `configs.paths.CLERK_AUTHORIZED_PARTIES` (all read at call time, so tests can monkeypatch them); `flask_jwt_extended.decode_token` (needs an app context).
- Produces:
  - `class TokenVerificationError(Exception)`
  - `class JwksCache(fetch: Callable[[], dict], min_refresh_interval: float = 60, clock: Callable[[], float] = time.monotonic)` with method `get_key(kid: str) -> RSAPublicKey | None`
  - module attribute `_clerk_jwks: JwksCache` (replaced by tests)
  - `verify_bearer_token(token: str | None) -> dict`, which returns the verified claims or raises `TokenVerificationError`

- [ ] **Step 1: Add the config key**

In `configs/paths.py`, directly after `CLERK_PUBLIC_KEY = get_config("Clerk", "clerk_public_key", "CLERK_PUBLIC_KEY")`, add:

```python
# Optional comma-separated list of origins allowed in a Clerk token's ``azp``
# claim (e.g. "https://tb.openldr.org.mz,https://vl.openldr.org.mz").
# Empty means the azp claim is not checked.
CLERK_AUTHORIZED_PARTIES = get_config(
    "Clerk", "clerk_authorized_parties", "CLERK_AUTHORIZED_PARTIES"
)
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_token_verification.py`:

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_token_verification.py -q`
Expected: collection error `ImportError: cannot import name 'token_verification' from 'utilities'`.

- [ ] **Step 4: Implement the module**

Create `utilities/token_verification.py`:

```python
"""
Verification of bearer tokens presented to the reporting endpoints.

Two token kinds are accepted:

* Clerk session tokens (RS256) sent by the dashboards. They are verified
  against Clerk's JWKS (``CLERK_JWTS_URL``), the expected issuer
  (``CLERK_ISSUER``), expiry and, when configured, the authorized parties
  (``CLERK_AUTHORIZED_PARTIES``).
* Tokens issued by this API's ``/auth`` login (HS256, Flask-JWT-Extended),
  verified with the application's JWT secret.

Anything else raises :class:`TokenVerificationError`. Callers must turn that
into a generic 401 without echoing the exception text to the client.
"""

import json
import logging
import threading
import time

import jwt
import requests
from flask_jwt_extended import decode_token
from jwt.algorithms import RSAAlgorithm

from configs import paths

logger = logging.getLogger(__name__)

JWKS_FETCH_TIMEOUT_SECONDS = 5
JWKS_MIN_REFRESH_INTERVAL_SECONDS = 60
CLOCK_SKEW_LEEWAY_SECONDS = 5
REQUIRED_CLERK_CLAIMS = ["exp", "iat", "iss", "sub"]


class TokenVerificationError(Exception):
    """Raised when a bearer token is missing, malformed or not trusted."""


class JwksCache:
    """
    Thread-safe cache of RSA public keys indexed by ``kid``.

    The key set is fetched lazily. An unknown ``kid`` triggers a refetch,
    but at most once per ``min_refresh_interval`` seconds so that a flood of
    tokens with random key ids cannot hammer the JWKS endpoint. A failed
    fetch keeps the previously cached keys.
    """

    def __init__(
        self,
        fetch,
        min_refresh_interval=JWKS_MIN_REFRESH_INTERVAL_SECONDS,
        clock=time.monotonic,
    ):
        self._fetch = fetch
        self._min_refresh_interval = min_refresh_interval
        self._clock = clock
        self._keys = {}
        self._last_fetch = None
        self._lock = threading.Lock()

    def get_key(self, kid):
        with self._lock:
            key = self._keys.get(kid)
            if key is not None:
                return key
            if (
                self._last_fetch is not None
                and self._clock() - self._last_fetch < self._min_refresh_interval
            ):
                return None
            self._refresh()
            return self._keys.get(kid)

    def _refresh(self):
        self._last_fetch = self._clock()
        try:
            jwks = self._fetch()
        except Exception as exc:
            logger.error("Could not fetch Clerk JWKS: %s", exc)
            return

        keys = {}
        for jwk in jwks.get("keys", []):
            if jwk.get("kty") == "RSA" and jwk.get("kid"):
                keys[jwk["kid"]] = RSAAlgorithm.from_jwk(json.dumps(jwk))
        self._keys = keys


def _fetch_clerk_jwks():
    if not paths.CLERK_JWTS_URL:
        raise TokenVerificationError("CLERK_JWTS_URL is not configured")
    response = requests.get(paths.CLERK_JWTS_URL, timeout=JWKS_FETCH_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


_clerk_jwks = JwksCache(_fetch_clerk_jwks)


def verify_bearer_token(token):
    """
    Verify ``token`` and return its claims.

    Raises
    ------
    TokenVerificationError
        If the token is missing, malformed, expired, signed by an untrusted
        key or uses an unsupported algorithm.
    """
    if not token:
        raise TokenVerificationError("missing token")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise TokenVerificationError(f"malformed token: {exc}") from exc

    alg = header.get("alg")
    if alg == "RS256":
        return _verify_clerk_token(token, header.get("kid"))
    if alg == "HS256":
        return _verify_api_token(token)
    raise TokenVerificationError(f"unsupported token algorithm: {alg}")


def _verify_clerk_token(token, kid):
    issuer = paths.CLERK_ISSUER
    if not issuer:
        raise TokenVerificationError("CLERK_ISSUER is not configured")
    if not kid:
        raise TokenVerificationError("token has no kid")

    key = _clerk_jwks.get_key(kid)
    if key is None:
        raise TokenVerificationError(f"unknown signing key {kid}")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            leeway=CLOCK_SKEW_LEEWAY_SECONDS,
            options={"require": REQUIRED_CLERK_CLAIMS},
        )
    except jwt.PyJWTError as exc:
        raise TokenVerificationError(f"invalid Clerk token: {exc}") from exc

    _check_authorized_party(claims)
    return claims


def _check_authorized_party(claims):
    allowed = [
        party.strip()
        for party in (paths.CLERK_AUTHORIZED_PARTIES or "").split(",")
        if party.strip()
    ]
    if allowed and claims.get("azp") not in allowed:
        raise TokenVerificationError(f"unauthorized party {claims.get('azp')}")


def _verify_api_token(token):
    try:
        return decode_token(token)
    except Exception as exc:
        raise TokenVerificationError(f"invalid API token: {exc}") from exc
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_token_verification.py -q`
Expected: `19 passed` (16 test functions; the garbage-token one is parametrized four ways).

If `test_alg_none_rejected` errors inside `jwt.encode` (some PyJWT builds refuse `key=""` for `none`), use `key=None` instead. The assertion must stay unchanged.

- [ ] **Step 6: Run the whole suite**

Run: `python3 -m pytest -q`
Expected: `298 passed` (the 279 baseline + 19 new).

- [ ] **Step 7: Commit**

```bash
git add configs/paths.py utilities/token_verification.py tests/test_token_verification.py
git commit -m "feat(auth): add verified bearer-token decoding for Clerk and API tokens

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Enforce verification in `authenticate_request` and remove the unverified path

**Files:**
- Modify: `utilities/utils.py` (`get_token` around line 683; delete `get_unverified_payload`, `get_public_key`, `verify_clerk_token`, around lines 704–760)
- Modify: `utilities/controller_helpers.py:35-41` (imports) and `:102-121` (`authenticate_request`)
- Modify: `tb/gxpert/controllers/common.py` (delete `execute_tb_service` and its imports)
- Modify: stale notes in `tests/README.md:99-118`, `tests/hiv/test_vl_summary.py:8-10`, `tests/hiv/test_vl_facility.py:136-137`, `tests/hiv/test_vl_laboratory.py:142-144`, `tests/hiv/test_eid_facility.py:128-129`, `tests/hiv/test_eid_laboratory.py:109-110`, `tests/hiv/test_eid_summary.py:156-157`, `tests/tb/test_tb_facility.py:164-165`
- Test: `tests/test_auth_enforcement.py`

**Interfaces:**
- Consumes: `utilities.token_verification.verify_bearer_token`, `TokenVerificationError` (Task 1).
- Produces:
  - `utilities.controller_helpers.unauthorized_response() -> tuple[dict, int]`
  - `authenticate_request() -> tuple[str | None, tuple | None]` (same signature; its failure value is now a 401)
  - `utilities.utils.get_token(request) -> str | None`, which now accepts any case of `Bearer` and surrounding whitespace

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_enforcement.py`:

```python
"""
Endpoint-level authentication contract.

Every reporting endpoint must reject unverified tokens with a fixed 401 body
and accept valid API-issued tokens. One endpoint per module is enough because
all of them go through utilities.controller_helpers.authenticate_request.
"""
import time
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest

from utilities.utils import get_token

UNAUTHORIZED_BODY = {
    "status": "error",
    "code": 401,
    "message": "Invalid or missing token",
}

# (url, symbol patched in the controller module, mocked service result)
ENDPOINTS = [
    ("/hiv/vl/summary/tat_by_month/",
     "hiv.vl.controllers.vl_controller_summary.tat_service_by_month", []),
    ("/hiv/vl/patients/by_name/",
     "hiv.vl.controllers.vl_controller_patients.get_patients_by_name_service", []),
    ("/hiv/eid/laboratories/tested_samples_by_month/",
     "hiv.eid.controllers.eid_controller_laboratory.tested_samples_by_month_service", []),
    ("/tb/gx/laboratories/registered_samples/",
     "tb.gxpert.controllers.tb_gx_controller_laboratory.registered_samples_by_lab_service", []),
    ("/tb/gx/patients/by_name/",
     "tb.gxpert.controllers.tb_gx_controller_patients.get_patients_by_name_service", []),
]


def forged_admin_token():
    """Unsigned-by-us token claiming to be an Admin, the attack the fix closes."""
    now = int(time.time())
    return jwt.encode(
        {"sub": "admin", "user_id": "admin-1", "role": "Admin",
         "type": "access", "jti": "x", "fresh": False,
         "iat": now, "nbf": now, "exp": now + 600},
        "attacker-secret",
        algorithm="HS256",
    )


@pytest.mark.parametrize("url,service,result", ENDPOINTS)
def test_valid_api_token_is_accepted(client, auth_headers, url, service, result):
    with patch(service, return_value=result):
        response = client.get(url, headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.parametrize("url,service,result", ENDPOINTS)
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": f"Bearer {forged_admin_token()}"},
    ],
    ids=["no-header", "bearer-no-token", "basic", "garbage", "forged-admin"],
)
def test_rejected_requests_return_fixed_401_body(client, url, service, result, headers):
    with patch(service, return_value=result) as service_mock:
        response = client.get(url, headers=headers)
    assert response.status_code == 401
    assert response.get_json() == UNAUTHORIZED_BODY
    service_mock.assert_not_called()


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("bearer abc.def.ghi", "abc.def.ghi"),
        ("  Bearer   abc.def.ghi  ", "abc.def.ghi"),
        ("Basic dXNlcjpwYXNz", None),
        ("Bearer", None),
        ("Bearer    ", None),
        ("", None),
        (None, None),
    ],
)
def test_get_token_parses_authorization_header(header, expected):
    headers = {} if header is None else {"Authorization": header}
    assert get_token(SimpleNamespace(headers=headers)) == expected
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_auth_enforcement.py -q`
Expected: failures.
- `test_rejected_requests_return_fixed_401_body` gets 200 instead of 401, because unverified tokens are accepted today.
- Three `test_get_token_parses_authorization_header` cases fail (`bearer abc…`, the padded header, `Basic …`).

- [ ] **Step 3: Make `get_token` robust**

In `utilities/utils.py`, replace the body of `get_token` (keep the docstring, but change "space-separated token" to "Bearer token") with:

```python
    auth_header = (request.headers.get("Authorization") or "").strip()
    scheme, _, token = auth_header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token
```

- [ ] **Step 4: Delete the unverified decoder and the unused Clerk helpers**

In `utilities/utils.py`, delete the three functions `get_unverified_payload`, `get_public_key` and `verify_clerk_token` completely. They sit between `get_token` and `get_user_token_info`. Then check that nothing else references them:

Run: `grep -rn "get_unverified_payload\|get_public_key\|verify_clerk_token" --include=*.py . | grep -v "^./tests/"`
Expected: only `utilities/controller_helpers.py` and `tb/gxpert/controllers/common.py`, which the next two steps fix.

Leave `RSAAlgorithm`, `requests` and `json` imported in `utils.py` if other code there uses them. Check with `grep -n "RSAAlgorithm\|requests\.\|json\." utilities/utils.py` and remove only imports with no remaining use.

- [ ] **Step 5: Rewire `authenticate_request`**

In `utilities/controller_helpers.py`, replace the import block:

```python
from utilities.utils import (
    get_token,
    get_unverified_payload,
    get_user_token_info,
)
```

with:

```python
import logging

from utilities.token_verification import TokenVerificationError, verify_bearer_token
from utilities.utils import get_token, get_user_token_info

logger = logging.getLogger(__name__)
```

Add this function directly after `error_response`:

```python
def unauthorized_response():
    """Fixed 401 payload. Never include the verification failure reason."""
    return (
        {
            "status": "error",
            "code": 401,
            "message": "Invalid or missing token",
        },
        401,
    )
```

Replace the body of `authenticate_request` (keep its docstring, but change "Validate" to "Verify the signature of") with:

```python
    token = get_token(request)

    try:
        token_payload = verify_bearer_token(token)
    except TokenVerificationError as exc:
        logger.warning("Rejected token on %s: %s", request.path, exc)
        return None, unauthorized_response()

    session["user_info"] = get_user_token_info(token_payload)
    user_id = str(session["user_info"].get("user_id"))
    return user_id, None
```

- [ ] **Step 6: Delete the dead TB helper**

In `tb/gxpert/controllers/common.py`:
- Delete the function `execute_tb_service` (it has no callers).
- Delete the imports only it used:
  - `from flask import jsonify, request, session`
  - `from flask_jwt_extended import verify_jwt_in_request`
  - `from utilities.service_helpers import build_error_response`
  - `from utilities.utils import get_token, get_unverified_payload, get_user_token_info`
- `add_tb_common_args` needs none of them.

Run: `grep -rn "execute_tb_service" --include=*.py .`
Expected: no output.

- [ ] **Step 7: Run the new tests**

Run: `python3 -m pytest tests/test_auth_enforcement.py -q`
Expected: `38 passed` (5 accepted + 25 rejected + 8 header cases).

- [ ] **Step 8: Remove the stale "no 401" notes**

Delete the comment or docstring lines saying the API "does not enforce 401" / "never raises" in:
- `tests/hiv/test_vl_summary.py:8-10`
- `tests/hiv/test_vl_facility.py:136-137`
- `tests/hiv/test_vl_laboratory.py:142-144`
- `tests/hiv/test_eid_facility.py:128-129`
- `tests/hiv/test_eid_laboratory.py:109-110`
- `tests/hiv/test_eid_summary.py:156-157`
- `tests/tb/test_tb_facility.py:164-165`

In `tests/README.md`:
- Replace rule 2 ("The auth layer uses `get_unverified_payload`…") with: `2. Every reporting endpoint verifies the bearer token and returns 401 {"status": "error", "code": 401, "message": "Invalid or missing token"} when it is missing or untrusted. Use the auth_headers fixture for authenticated calls; tests/test_auth_enforcement.py covers the 401 contract.`
- Delete the troubleshooting bullet "Tests pass but you expected a 401".

Run: `grep -rn "get_unverified_payload\|does not enforce 401\|never raises" tests/`
Expected: no output.

- [ ] **Step 9: Run the whole suite**

Run: `python3 -m pytest -q`
Expected: `336 passed` (298 + 38). The existing endpoint tests still pass because `auth_headers` is a valid HS256 API token.

- [ ] **Step 10: Commit**

```bash
git add utilities/utils.py utilities/controller_helpers.py tb/gxpert/controllers/common.py tests/
git commit -m "fix(auth): reject unverified JWTs on all reporting endpoints

authenticate_request() decoded tokens without checking the signature, so any
caller could forge a token with an Admin user_id and read patient data.
It now verifies Clerk RS256 tokens against the JWKS/issuer and API HS256
tokens with the app secret, and returns a fixed 401 otherwise.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Pre-deploy token check tool and auth docs

The fix locks every dashboard user out if production's `CLERK_ISSUER` / `CLERK_JWTS_URL` do not match the Clerk instance the dashboards use. This task gives the operator a one-command check to run with the production config before deploying, and documents the contract.

**Files:**
- Create: `tools/check_clerk_token.py`
- Modify: `CLAUDE.md` (the "Authentication" section, lines ~140–150 of the first section)
- Test: `tests/test_check_clerk_token.py`

**Interfaces:**
- Consumes: `utilities.token_verification.verify_bearer_token`, `TokenVerificationError` (Task 1).
- Produces: `tools/check_clerk_token.py`, with `main(argv: list[str] | None = None, stdin=sys.stdin) -> int` returning exit code 0 on a verified token and 1 otherwise.

- [ ] **Step 1: Write the failing test**

Create `tests/test_check_clerk_token.py`:

```python
"""The operator tool must report success/failure without printing the token."""
import io

from tests.test_token_verification import ISSUER, make_clerk_token, make_jwks
from configs import paths
from tools import check_clerk_token
from utilities import token_verification as tv


def _configure(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", None)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))


def test_valid_token_exits_zero_and_prints_claims(monkeypatch, capsys):
    _configure(monkeypatch)
    token = make_clerk_token()
    code = check_clerk_token.main([], stdin=io.StringIO(token + "\n"))
    out = capsys.readouterr().out
    assert code == 0
    assert "VERIFIED" in out
    assert "user_abc" in out
    assert token not in out


def test_bad_token_exits_one_with_reason(monkeypatch, capsys):
    _configure(monkeypatch)
    code = check_clerk_token.main([], stdin=io.StringIO("not-a-jwt\n"))
    out = capsys.readouterr().out
    assert code == 1
    assert "REJECTED" in out
    assert "malformed token" in out
```

Note: `tests/` must be importable as a package for `from tests.test_token_verification import …`. `tests/__init__.py` already exists on `dev`, and `tools/` needs an `__init__.py` (created in step 3).

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_check_clerk_token.py -q`
Expected: `ModuleNotFoundError: No module named 'tools'` (or `cannot import name 'check_clerk_token'` if a `tools` package already exists).

- [ ] **Step 3: Implement the tool**

First check whether `tools/` exists:

Run: `ls tools 2>/dev/null; ls tools/__init__.py 2>/dev/null`

If `tools/__init__.py` is missing, create it empty. Then create `tools/check_clerk_token.py`:

```python
"""
Verify a real Clerk session token against this API's configured
CLERK_ISSUER / CLERK_JWTS_URL / CLERK_AUTHORIZED_PARTIES.

Run it on the API host (or with the production environment loaded) BEFORE
deploying the JWT-verification change, using a token copied from a signed-in
dashboard tab (browser console: ``await window.Clerk.session.getToken()``):

    python -m tools.check_clerk_token < token.txt

The token is read from stdin so it does not end up in shell history, and it
is never printed. Exit code 0 = verified, 1 = rejected.
"""

import sys

from configs import paths
from utilities.token_verification import TokenVerificationError, verify_bearer_token

SHOWN_CLAIMS = ["iss", "sub", "azp", "iat", "exp"]


def main(argv=None, stdin=sys.stdin):
    token = stdin.read().strip()
    print(f"CLERK_ISSUER             = {paths.CLERK_ISSUER!r}")
    print(f"CLERK_JWTS_URL           = {paths.CLERK_JWTS_URL!r}")
    print(f"CLERK_AUTHORIZED_PARTIES = {paths.CLERK_AUTHORIZED_PARTIES!r}")

    try:
        claims = verify_bearer_token(token)
    except TokenVerificationError as exc:
        print(f"REJECTED: {exc}")
        return 1

    print("VERIFIED")
    for name in SHOWN_CLAIMS:
        print(f"  {name}: {claims.get(name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_check_clerk_token.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Document the auth contract**

In `CLAUDE.md`, replace the bullet list under the first `## Authentication` heading with:

```markdown
- Every reporting endpoint authenticates through
  `utilities.controller_helpers.authenticate_request()`, which calls
  `utilities.token_verification.verify_bearer_token()`. Accepted tokens:
  - **Clerk session tokens** (RS256) from the dashboards — verified against
    `CLERK_JWTS_URL` (JWKS, cached; unknown `kid` refetched at most every 60 s),
    `CLERK_ISSUER`, expiry, and `CLERK_AUTHORIZED_PARTIES` (`azp`) when set.
  - **API login tokens** (HS256) from `POST /auth/login` — verified with the
    Flask/JWT secret; 60 min expiry.
- Anything else → HTTP 401 `{"status": "error", "code": 401, "message": "Invalid or missing token"}`.
  The reason is logged, never returned.
- If `CLERK_ISSUER` or `CLERK_JWTS_URL` is empty, all Clerk tokens are rejected
  (fail closed). Before changing Clerk config, run
  `python -m tools.check_clerk_token < token.txt` with the target config.
- Role-based access: Admin and User roles (`utilities/auth_helpers.py`).
```

In the second `### Authentication` section (lower in the file), replace the bullet "Token user info extracted in services using `get_user_token_info()`…" with "Verified token claims are mapped to `session['user_info']` by `get_user_token_info()` in `authenticate_request()`; see the Authentication section above." In the Windows `configs.ini` notes, if any, mention the new `[Clerk] clerk_authorized_parties` key.

- [ ] **Step 6: Run the whole suite**

Run: `python3 -m pytest -q`
Expected: `338 passed`.

- [ ] **Step 7: Commit**

```bash
git add tools/ tests/test_check_clerk_token.py CLAUDE.md
git commit -m "chore(auth): add pre-deploy Clerk token check and document auth contract

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Production-config check with the user, then PR

This task changes no code. It is the go/no-go gate the spec requires before the change can reach production. **Do not skip or simulate it. The user runs the commands that touch production.**

- [ ] **Step 1: Push the branch**

```bash
git push -u origin security/verify-jwt-signatures
```

- [ ] **Step 2: Ask the user to capture a real dashboard token**

Ask the user to:
1. Sign in to `https://tb.openldr.org.mz`.
2. Run `await window.Clerk.session.getToken()` in the browser console.
3. Save the output, without quotes, to a file such as `token.txt` on the machine that has the production API config.

The token is valid for about 60 seconds, so the next step must be run immediately afterwards.

- [ ] **Step 3: User runs the check with the production config**

On the production API host (Windows/Waitress, `configs/configs.ini`) or with identical settings, from a checkout of this branch. PowerShell does not support `<` redirection, so pass the file as an argument:

```powershell
python -m tools.check_clerk_token token.txt
# or: Get-Content token.txt | python -m tools.check_clerk_token
```

(bash equivalent: `python -m tools.check_clerk_token < token.txt`.)

Expected: `VERIFIED`, with `iss` equal to the printed `CLERK_ISSUER` and `azp` equal to `https://tb.openldr.org.mz`.
- **If `REJECTED: invalid Clerk token: Invalid issuer`:** production `CLERK_ISSUER` does not match the Clerk instance the dashboards use. Fix `configs.ini` (`[Clerk] clerk_issuer`, `clerk_jwts_url`) to the dashboard's instance, then re-run. **Do not merge until this prints VERIFIED.**
- **If `REJECTED: unknown signing key`:** `CLERK_JWTS_URL` points at a different instance; fix it the same way.
- Note the `diagnostic (unverified): clock offset ... = N s` line; it is used in Step 5.
- Delete `token.txt` afterwards.

- [ ] **Step 4: Decide on `CLERK_AUTHORIZED_PARTIES`**

Recommend the production value `https://tb.openldr.org.mz` (add `https://vl.openldr.org.mz` once piece 3 deploys the VL app), set under `[Clerk] clerk_authorized_parties` in `configs.ini`. Re-run step 3 after setting it. Leaving it empty is acceptable but weaker.

- [ ] **Step 5: Confirm production secrets and host clock (gate)**

All three must hold before opening the PR. The user checks them on the production host; never paste secret values into the chat.

1. **API/JWT secret:** the production Flask secret (`[Flask] secret_key` / `FLASK_SECRET_KEY`, which becomes `SECRET_KEY`; `JWT_SECRET_KEY` if set takes precedence) is set, is **not** `default-secret-key`, and is at least 32 bytes. Otherwise every `/auth/login` token is rejected after deploy (fail closed). Changing it invalidates outstanding API tokens.
2. **Clerk webhook secret:** `[Clerk] clerk_webhook_secret` / `CLERK_WEBHOOK_SECRET_KEY` equals the signing secret (`whsec_...`) of the Clerk webhook endpoint that points at `/auth/clerk` (Clerk dashboard → Webhooks → endpoint → Signing Secret). If it is empty or wrong, every webhook delivery gets 401. After deploy, check that Clerk's webhook dashboard shows 2xx deliveries for that endpoint.
3. **Host clock:** run `w32tm /query /status` on the production host and confirm it is synchronised; the clock offset printed by the tool in Step 3 should be within a few seconds (Clerk tokens live ~60 s and verification allows only 5 s leeway; the webhook allows 5 min).

- [ ] **Step 6: Open the PR against `dev`**

```bash
gh pr create --repo Association-of-Public-Health-Labs/api_openldr_python \
  --base dev --head security/verify-jwt-signatures \
  --title "fix(auth): verify JWT signatures on all reporting endpoints" \
  --body "$(cat <<'EOF'
## Summary
- `authenticate_request()` decoded bearer tokens **without verifying the signature**, so a forged token with an Admin `user_id` could read patient data (TB and VL patients) and all reporting endpoints.
- New `utilities/token_verification.py` verifies Clerk RS256 tokens (JWKS cache, issuer, expiry, optional `azp`) and API HS256 tokens; everything else returns a fixed 401.
- Removes the unverified decoder, unused Clerk helpers and the dead `execute_tb_service`.
- `POST /auth/clerk` (Clerk webhook) had **no signature verification** and returned a real API access token to any caller on `session.created` (and let anyone update/delete users). It now verifies the Svix signature (`utilities/webhook_verification.py`, stdlib HMAC, 5 min tolerance, fail closed without `CLERK_WEBHOOK_SECRET_KEY`) and never returns a token; API tokens come only from `POST /auth/login`.
- API HS256 tokens are rejected if the JWT/Flask secret is unset, the public default, or shorter than 32 bytes.
- Adds `tools/check_clerk_token.py` for a pre-deploy check (file argument for PowerShell, clock-offset diagnostic), plus docs.

## Deploy checklist
- [ ] `python -m tools.check_clerk_token token.txt` prints VERIFIED on the production config (token from tb.openldr.org.mz); clock offset within a few seconds (`w32tm /query /status`)
- [ ] Production Flask/JWT secret set, not `default-secret-key`, ≥ 32 bytes
- [ ] `[Clerk] clerk_webhook_secret` equals the signing secret of the Clerk webhook endpoint for `/auth/clerk`; after deploy, Clerk's webhook dashboard shows 2xx deliveries
- [ ] `[Clerk] clerk_authorized_parties` set (recommended: `https://tb.openldr.org.mz`)
- [ ] After deploy: tb.openldr.org.mz loads all pages; a request without a token returns 401
- Rollback: redeploy the previous commit of `dev`.

## Test plan
- [x] `python3 -m pytest -q`: 402 passed (123 new: token verifier, endpoint 401 contract and Clerk acceptance, header parsing, weak-secret rejection, Svix webhook verification and no-token responses, check tool)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

If `gh pr create` fails with "Head sha can't be blank" (a stale remote URL after a repo transfer), use:
`gh api -X POST repos/Association-of-Public-Health-Labs/api_openldr_python/pulls -f head=security/verify-jwt-signatures -f base=dev -f title="…" -f body="…"`.

- [ ] **Step 7: Report back to the user**

Report:
- the PR URL
- the test count
- the token-check result and the Step 5 gate results (secret strength, webhook secret, clock offset)
- the remaining deploy-checklist items, which are the user's to tick off after merging and deploying (production is the Windows Waitress service managed by NSSM)
