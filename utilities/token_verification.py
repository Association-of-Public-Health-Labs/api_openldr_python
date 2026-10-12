"""
Verification of bearer tokens presented to the reporting endpoints.

Two token kinds are accepted:

* Clerk session tokens (RS256) sent by the dashboards. They are verified
  against Clerk's JWKS (``CLERK_JWTS_URL``), the expected issuer
  (``CLERK_ISSUER``), expiry and, when configured, the authorized parties
  (``CLERK_AUTHORIZED_PARTIES``).
* Tokens issued by this API's ``/auth`` login (HS256, Flask-JWT-Extended),
  verified with the application's JWT secret. If that secret is unset, the
  public default ``"default-secret-key"`` or shorter than 32 bytes, every API
  token is rejected (fail closed).

Anything else raises :class:`TokenVerificationError`. Callers must turn that
into a generic 401 without echoing the exception text to the client.
"""

import json
import logging
import threading
import time

import jwt
import requests
from flask import current_app
from flask_jwt_extended import decode_token
from jwt.algorithms import RSAAlgorithm

from configs import paths

logger = logging.getLogger(__name__)

JWKS_FETCH_TIMEOUT_SECONDS = 5
JWKS_MIN_REFRESH_INTERVAL_SECONDS = 60
CLOCK_SKEW_LEEWAY_SECONDS = 5
REQUIRED_CLERK_CLAIMS = ["exp", "iat", "iss", "sub"]
DEFAULT_SECRET_KEY = "default-secret-key"
MIN_API_SECRET_BYTES = 32


class TokenVerificationError(Exception):
    """Raised when a bearer token is missing, malformed or not trusted."""


class JwksCache:
    """
    Thread-safe cache of RSA public keys indexed by ``kid``.

    The key set is fetched lazily. An unknown ``kid`` triggers a refetch,
    but at most once per ``min_refresh_interval`` seconds so that a flood of
    tokens with random key ids cannot hammer the JWKS endpoint. A failed
    fetch, an empty key list or a list with no usable keys keeps the
    previously cached keys.
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

        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
            logger.error("Clerk JWKS response is not a valid key set")
            return

        entries = jwks["keys"]
        keys = {}
        for jwk in entries:
            kid = jwk.get("kid") if isinstance(jwk, dict) else None
            try:
                if isinstance(jwk, dict) and jwk.get("kty") == "RSA" and kid:
                    keys[kid] = RSAAlgorithm.from_jwk(json.dumps(jwk))
            except Exception as exc:
                logger.warning("Skipping unusable JWK %r: %s", kid, exc)
        if not entries and self._keys:
            logger.warning("Clerk JWKS returned an empty key list; keeping cached keys")
            return
        if entries and not keys:
            logger.error("Clerk JWKS contained no usable keys; keeping cached keys")
            return
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

    try:
        key = _clerk_jwks.get_key(kid)
    except Exception as exc:
        raise TokenVerificationError("could not load signing keys") from exc
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


def _api_secret_is_weak():
    config = current_app.config
    secret = config.get("JWT_SECRET_KEY") or config.get("SECRET_KEY")
    if not secret or secret == DEFAULT_SECRET_KEY:
        return True
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return len(secret) < MIN_API_SECRET_BYTES


def _verify_api_token(token):
    if _api_secret_is_weak():
        logger.error(
            "Rejecting API token: JWT_SECRET_KEY/SECRET_KEY is unset, the "
            "default, or shorter than %d bytes", MIN_API_SECRET_BYTES
        )
        raise TokenVerificationError("API token secret is weak or unset")
    try:
        return decode_token(token)
    except Exception as exc:
        raise TokenVerificationError(f"invalid API token: {exc}") from exc
