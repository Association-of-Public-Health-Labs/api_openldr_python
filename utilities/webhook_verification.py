"""
Verification of Svix-signed webhooks (used by Clerk for ``POST /auth/clerk``).

Svix signs ``"{svix-id}.{svix-timestamp}.{raw body}"`` with HMAC-SHA256 using
the endpoint's signing secret (``whsec_<base64 key>``) and sends one or more
``v1,<base64 signature>`` entries, space separated, in ``svix-signature``.

Stdlib only. Any failure raises :class:`WebhookVerificationError`; callers
must answer with a fixed 401 body and log the reason, never return it.
"""

import base64
import binascii
import hashlib
import hmac
import time

SVIX_TOLERANCE_SECONDS = 5 * 60
_SECRET_PREFIX = "whsec_"


class WebhookVerificationError(Exception):
    """Raised when a webhook request is not provably from the configured sender."""


def _header(headers, name):
    value = headers.get(name)
    if not value:
        raise WebhookVerificationError(f"missing {name} header")
    return value


def _signing_key(secret):
    if not secret:
        raise WebhookVerificationError("webhook secret is not configured")
    encoded = secret[len(_SECRET_PREFIX):] if secret.startswith(_SECRET_PREFIX) else secret
    try:
        key = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WebhookVerificationError("webhook secret is not valid base64") from exc
    if not key:
        raise WebhookVerificationError("webhook secret is empty")
    return key


def verify_svix_signature(headers, raw_body, secret, now=None):
    """
    Verify a Svix webhook request.

    Parameters
    ----------
    headers : mapping with ``.get`` (Flask request headers or a dict)
    raw_body : bytes, the exact request body as received
    secret : the ``whsec_...`` signing secret
    now : optional current Unix time, for tests

    Raises
    ------
    WebhookVerificationError
        If the secret is unset/invalid, a header is missing, the timestamp is
        not an integer or is more than five minutes from ``now``, or no
        ``v1`` signature matches.
    """
    key = _signing_key(secret)
    msg_id = _header(headers, "svix-id")
    timestamp_text = _header(headers, "svix-timestamp")
    signature_header = _header(headers, "svix-signature")

    if not (timestamp_text.isascii() and timestamp_text.isdigit()):
        raise WebhookVerificationError("svix-timestamp is not an integer")
    timestamp = int(timestamp_text)

    current = int(time.time()) if now is None else int(now)
    if timestamp < current - SVIX_TOLERANCE_SECONDS:
        raise WebhookVerificationError("svix-timestamp is too old")
    if timestamp > current + SVIX_TOLERANCE_SECONDS:
        raise WebhookVerificationError("svix-timestamp is too far in the future")

    try:
        body_text = raw_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WebhookVerificationError("body is not valid UTF-8") from exc

    content = f"{msg_id}.{timestamp_text}.{body_text}".encode("utf-8")
    expected = base64.b64encode(hmac.new(key, content, hashlib.sha256).digest()).decode("ascii")

    matched = False
    for entry in signature_header.split():
        version, _, signature = entry.partition(",")
        if version == "v1" and signature and hmac.compare_digest(signature, expected):
            matched = True
    if not matched:
        raise WebhookVerificationError("no matching v1 signature")
