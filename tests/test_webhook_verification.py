"""Unit tests for utilities.webhook_verification (Svix signatures, stdlib only)."""
import base64
import hashlib
import hmac

import pytest

from utilities.webhook_verification import (
    SVIX_TOLERANCE_SECONDS,
    WebhookVerificationError,
    verify_svix_signature,
)

KEY = b"openldr-test-webhook-signing-key!"
SECRET = "whsec_" + base64.b64encode(KEY).decode()
OTHER_SECRET = "whsec_" + base64.b64encode(b"some-other-signing-key-0123456789").decode()
NOW = 1_760_000_000
MSG_ID = "msg_2abc"
BODY = b'{"type":"session.created","data":{"user_id":"user_abc"}}'


def sign(msg_id, timestamp, body, key=KEY):
    content = f"{msg_id}.{timestamp}.{body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(key, content, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def svix_headers(body=BODY, msg_id=MSG_ID, timestamp=NOW, key=KEY, signature=None):
    return {
        "svix-id": msg_id,
        "svix-timestamp": str(timestamp),
        "svix-signature": signature if signature is not None else sign(msg_id, timestamp, body, key),
    }


def test_valid_signature_passes():
    assert verify_svix_signature(svix_headers(), BODY, SECRET, now=NOW) is None


def test_secret_without_prefix_is_accepted():
    raw = base64.b64encode(KEY).decode()
    verify_svix_signature(svix_headers(), BODY, raw, now=NOW)


def test_tampered_body_rejected():
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(svix_headers(), BODY.replace(b"user_abc", b"user_evil"), SECRET, now=NOW)


def test_wrong_secret_rejected():
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(svix_headers(), BODY, OTHER_SECRET, now=NOW)


@pytest.mark.parametrize("missing", ["svix-id", "svix-timestamp", "svix-signature"])
def test_missing_header_rejected(missing):
    headers = svix_headers()
    del headers[missing]
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(headers, BODY, SECRET, now=NOW)


@pytest.mark.parametrize("missing", ["svix-id", "svix-timestamp", "svix-signature"])
def test_empty_header_rejected(missing):
    headers = svix_headers()
    headers[missing] = ""
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(headers, BODY, SECRET, now=NOW)


def test_stale_timestamp_rejected():
    ts = NOW - SVIX_TOLERANCE_SECONDS - 1
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(svix_headers(timestamp=ts), BODY, SECRET, now=NOW)


def test_future_timestamp_rejected():
    ts = NOW + SVIX_TOLERANCE_SECONDS + 1
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(svix_headers(timestamp=ts), BODY, SECRET, now=NOW)


def test_timestamp_within_tolerance_accepted():
    for ts in (NOW - SVIX_TOLERANCE_SECONDS + 1, NOW + SVIX_TOLERANCE_SECONDS - 1):
        verify_svix_signature(svix_headers(timestamp=ts), BODY, SECRET, now=NOW)


def test_tolerance_is_five_minutes():
    assert SVIX_TOLERANCE_SECONDS == 300


@pytest.mark.parametrize("ts", ["abc", "1.5", "", " "])
def test_non_integer_timestamp_rejected(ts):
    headers = svix_headers()
    headers["svix-timestamp"] = ts
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(headers, BODY, SECRET, now=NOW)


def test_second_v1_entry_matching_is_accepted():
    good = sign(MSG_ID, NOW, BODY)
    bad = sign(MSG_ID, NOW, BODY, key=b"rotated-out-old-key-0123456789ab")
    headers = svix_headers(signature=f"{bad} {good}")
    verify_svix_signature(headers, BODY, SECRET, now=NOW)


def test_non_v1_entries_are_ignored():
    good_sig = sign(MSG_ID, NOW, BODY).split(",", 1)[1]
    headers = svix_headers(signature=f"v2,{good_sig} garbage")
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(headers, BODY, SECRET, now=NOW)


@pytest.mark.parametrize("secret", [None, "", "whsec_", "whsec_!!!not-base64!!!"])
def test_empty_or_invalid_secret_fails_closed(secret):
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(svix_headers(), BODY, secret, now=NOW)


def test_non_utf8_body_rejected():
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(svix_headers(), b"\xff\xfe", SECRET, now=NOW)


def test_uses_current_time_by_default():
    import time
    now = int(time.time())
    verify_svix_signature(svix_headers(timestamp=now), BODY, SECRET)
    with pytest.raises(WebhookVerificationError):
        verify_svix_signature(svix_headers(timestamp=NOW - 10_000_000), BODY, SECRET)
