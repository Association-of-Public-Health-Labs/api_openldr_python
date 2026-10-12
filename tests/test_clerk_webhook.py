"""
Endpoint tests for POST /auth/clerk (Clerk webhook via Svix).

The webhook must reject any request without a valid Svix signature before
touching the user database, and must never return an API access token.
"""
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from configs import paths
from tests.test_webhook_verification import KEY, OTHER_SECRET, SECRET, sign

URL = "/auth/clerk"
UNAUTHORIZED_BODY = {"status": 401, "error": "Unauthorized", "message": "Invalid webhook signature"}

CLERK_USER = {
    "id": "user_abc",
    "first_name": "Ana",
    "last_name": "Silva",
    "email_addresses": [{"email_address": "ana@openldr.org.mz"}],
}
DB_USER = SimpleNamespace(
    user_id="user_abc", user_name="Ana_Silva", first_name="Ana",
    last_name="Silva", email="ana@openldr.org.mz", role="Admin",
)


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", SECRET)
    return SECRET


def signed_post(client, payload, timestamp=None, key=KEY, msg_id="msg_1", headers=None):
    body = json.dumps(payload).encode("utf-8")
    timestamp = int(time.time()) if timestamp is None else timestamp
    signed = {
        "svix-id": msg_id,
        "svix-timestamp": str(timestamp),
        "svix-signature": sign(msg_id, timestamp, body, key),
        "Content-Type": "application/json",
    }
    if headers is not None:
        signed = headers
    return client.post(URL, data=body, headers=signed)


def _contains_token(value):
    if isinstance(value, dict):
        return any(
            "token" in str(k).lower() or _contains_token(v) for k, v in value.items()
        )
    if isinstance(value, list):
        return any(_contains_token(v) for v in value)
    return isinstance(value, str) and value.startswith("eyJ")


SESSION_CREATED = {"type": "session.created", "data": {"id": "sess_1", "user_id": "user_abc"}}
USER_DELETED = {"type": "user.deleted", "data": {"id": "user_abc"}}


@pytest.fixture
def mocked_services():
    with patch("auth.auth_controller._fetch_clerk_user", return_value=CLERK_USER) as fetch, \
         patch("auth.auth_controller.get_user_by_id_service", return_value=DB_USER) as get_user, \
         patch("auth.auth_controller.update_last_login_service") as last_login, \
         patch("auth.auth_controller.save_user_log_service") as save_log, \
         patch("auth.auth_controller.delete_user_service",
               return_value={"message": "deleted", "data": None, "token": "eyJdeleted"}) as delete, \
         patch("auth.auth_controller.create_user_service",
               return_value={"message": "created", "data": {"user_id": "user_abc"},
                             "token": "eyJcreated"}) as create, \
         patch("auth.auth_controller.update_user_service",
               return_value={"message": "updated", "data": None, "token": "eyJupdated"}) as update, \
         patch("auth.auth_controller.logout_user_service",
               return_value={"message": "logged out", "data": None, "token": "eyJlogout"}) as logout:
        yield SimpleNamespace(fetch=fetch, get_user=get_user, last_login=last_login,
                              save_log=save_log, delete=delete, create=create,
                              update=update, logout=logout)


def assert_rejected(response, mocked_services):
    assert response.status_code == 401
    assert response.get_json() == UNAUTHORIZED_BODY
    mocked_services.fetch.assert_not_called()
    mocked_services.delete.assert_not_called()
    mocked_services.get_user.assert_not_called()


def test_no_svix_headers_rejected(client, webhook_secret, mocked_services):
    response = client.post(URL, json=USER_DELETED)
    assert_rejected(response, mocked_services)


def test_bad_signature_rejected(client, webhook_secret, mocked_services):
    response = signed_post(client, USER_DELETED, key=b"attacker-guessed-key-0123456789ab")
    assert_rejected(response, mocked_services)


def test_wrong_configured_secret_rejected(client, monkeypatch, mocked_services):
    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", OTHER_SECRET)
    response = signed_post(client, SESSION_CREATED)
    assert_rejected(response, mocked_services)


@pytest.mark.parametrize("secret", [None, ""])
def test_unset_secret_rejects_everything(client, monkeypatch, mocked_services, secret):
    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", secret)
    response = signed_post(client, SESSION_CREATED)
    assert_rejected(response, mocked_services)


def test_stale_timestamp_rejected(client, webhook_secret, mocked_services):
    response = signed_post(client, USER_DELETED, timestamp=int(time.time()) - 301)
    assert_rejected(response, mocked_services)


def test_tampered_body_rejected(client, webhook_secret, mocked_services):
    ts = int(time.time())
    body = json.dumps(SESSION_CREATED).encode()
    headers = {
        "svix-id": "msg_1",
        "svix-timestamp": str(ts),
        "svix-signature": sign("msg_1", ts, body),
        "Content-Type": "application/json",
    }
    response = client.post(URL, data=json.dumps(USER_DELETED), headers=headers)
    assert_rejected(response, mocked_services)


def test_rejection_body_does_not_leak_reason(client, webhook_secret, mocked_services):
    response = client.post(URL, json=USER_DELETED, headers={"svix-id": "x"})
    assert "svix" not in response.get_data(as_text=True).lower()


def test_valid_session_created_returns_no_token(client, webhook_secret, mocked_services):
    response = signed_post(client, SESSION_CREATED)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == 200
    assert not _contains_token(payload)
    assert "eyJ" not in response.get_data(as_text=True)
    mocked_services.last_login.assert_called_once_with("user_abc")
    mocked_services.save_log.assert_called_once()


def test_valid_session_created_for_new_user_returns_no_token(client, webhook_secret, mocked_services):
    mocked_services.get_user.return_value = None
    response = signed_post(client, SESSION_CREATED)
    assert response.status_code == 200
    assert not _contains_token(response.get_json())
    mocked_services.create.assert_called_once()


@pytest.mark.parametrize(
    "payload,service",
    [
        ({"type": "user.created", "data": {"id": "user_abc"}}, "create"),
        ({"type": "user.updated", "data": {"id": "user_abc"}}, "update"),
        (USER_DELETED, "delete"),
        ({"type": "session.ended", "data": {"user_id": "user_abc", "status": "ended"}}, "logout"),
        ({"type": "session.removed", "data": {"user_id": "user_abc", "status": "removed"}}, "logout"),
    ],
)
def test_valid_events_dispatch_and_never_return_token(client, webhook_secret, mocked_services, payload, service):
    response = signed_post(client, payload)
    assert response.status_code == 200
    assert not _contains_token(response.get_json())
    assert "eyJ" not in response.get_data(as_text=True)
    getattr(mocked_services, service).assert_called_once()
