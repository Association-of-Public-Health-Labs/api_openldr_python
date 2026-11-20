"""Password login and Clerk coexistence with real SQLite users and JWTs.

Credentials and identities are synthetic. Only report queries, Clerk profile
fetches and JWKS transport are replaced; no production database is contacted.
"""
from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import bcrypt
import pytest
from flask_jwt_extended import decode_token

from auth import auth_service
from auth.user_model import User, UserLogs
from configs import paths
from db.database import db
from tests.test_clerk_webhook import signed_post
from tests.test_token_verification import ISSUER, make_clerk_token, make_jwks
from tests.test_webhook_verification import SECRET
from utilities import token_verification


PASSWORD = "synthetic-password-42"
VL_URL = "/hiv/vl/summary/tat_by_month/"
VL_SERVICE = "hiv.vl.controllers.vl_controller_summary.tat_service_by_month"
DPI_URL = "/hiv/eid/laboratories/tested_samples_by_month/"
DPI_SERVICE = "hiv.eid.controllers.eid_controller_laboratory.tested_samples_by_month_service"
INVALID_CREDENTIALS = {
    "status": 401, "error": "Unauthorized", "message": "Invalid credentials",
}
SERVER_ERROR = {
    "status": 500, "error": "Internal Server Error", "message": "An error occurred",
}


@pytest.fixture(autouse=True)
def reject_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Login tests must never contact external services")

    monkeypatch.setattr("requests.sessions.Session.request", reject)


@pytest.fixture
def login_accounts(app):
    """Persist real accounts, allowing duplicate identifier regression cases."""
    created_ids = []

    def create(*, user_id=None, username=None, email=None, role="vl", stored_hash=None):
        suffix = uuid4().hex
        user_id = user_id or f"user_login_test_{suffix}"
        account = {
            "user_id": user_id,
            "username": username or f"synthetic_{suffix}",
            "email": email or f"login-{suffix}@example.test",
            "role": role,
        }
        if stored_hash is None:
            stored_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
        with app.app_context():
            now = datetime.now()
            db.session.add(User(
                user_id=user_id, user_name=account["username"],
                first_name="Synthetic", last_name="Actor", email=account["email"],
                password=stored_hash, role=role, start_date=now, updated_at=now,
            ))
            db.session.commit()
        created_ids.append(user_id)
        return account

    create.created_ids = created_ids
    yield create

    with app.app_context():
        db.session.rollback()
        if created_ids:
            UserLogs.query.filter(UserLogs.user_id.in_(created_ids)).delete(synchronize_session=False)
            User.query.filter(User.user_id.in_(created_ids)).delete(synchronize_session=False)
            db.session.commit()
        db.session.remove()


@pytest.fixture
def account(login_accounts):
    return login_accounts(user_id="user_login_test_42")


def login_payload(account, *identifiers):
    return {**{key: account[key] for key in identifiers}, "password": PASSWORD}


def assert_invalid_credentials(response):
    assert response.status_code == 401
    assert response.get_json() == INVALID_CREDENTIALS
    assert "token" not in response.get_json()


@pytest.mark.parametrize("identifiers", [("username",), ("email",), ("username", "email")])
def test_password_login_uses_bcrypt_and_preserves_clerk_shaped_subject(
    client, app, account, identifiers,
):
    response = client.post("/auth/login", json=login_payload(account, *identifiers))
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body, dict)
    assert body["status"] == 200
    assert body["data"]["user_id"] == account["user_id"]
    assert body["data"]["role"] == "vl"
    assert "password" not in str(body)
    with app.app_context():
        claims = decode_token(body["token"])
        assert claims["sub"] == account["user_id"]
        assert claims["user_id"] == account["user_id"]
        assert claims["role"] == "vl"
        assert User.query.filter_by(user_id=account["user_id"]).one().last_login is not None
        assert UserLogs.query.filter_by(user_id=account["user_id"], log_type="login").count() == 1


@pytest.mark.parametrize("identifiers", [("username",), ("email",), ("username", "email")])
@pytest.mark.parametrize("password", ["wrong-password", "user_login_test_42"])
def test_invalid_password_and_public_user_id_are_rejected(client, app, account, identifiers, password):
    payload = {**login_payload(account, *identifiers), "password": password}
    assert_invalid_credentials(client.post("/auth/login", json=payload))
    with app.app_context():
        assert User.query.filter_by(user_id=account["user_id"]).one().last_login is None
        assert UserLogs.query.filter_by(user_id=account["user_id"]).count() == 0


@pytest.mark.parametrize("key", ["username", "email"])
def test_unknown_identifier_returns_same_generic_401(client, account, key):
    assert_invalid_credentials(client.post("/auth/login", json={
        key: "does-not-exist@example.test", "password": PASSWORD,
    }))


def test_both_identifiers_must_match_the_same_account(client, account, login_accounts):
    other = login_accounts()
    assert_invalid_credentials(client.post("/auth/login", json={
        "username": account["username"], "email": other["email"], "password": PASSWORD,
    }))


@pytest.mark.parametrize("payload", [
    {}, {"password": PASSWORD}, {"username": "synthetic"},
    {"email": "synthetic@example.test"},
    {"username": "", "password": PASSWORD},
    {"username": "   ", "password": PASSWORD},
    {"username": None, "password": PASSWORD},
    {"username": "synthetic", "password": ""},
    {"username": "synthetic", "password": None},
    {"username": ["synthetic"], "password": PASSWORD},
    {"username": {"value": "synthetic"}, "password": PASSWORD},
    {"username": 42, "password": PASSWORD},
    {"email": ["synthetic@example.test"], "password": PASSWORD},
    {"username": "synthetic", "password": [PASSWORD]},
    {"username": "synthetic", "password": {"value": PASSWORD}},
    {"username": "synthetic", "password": 42},
])
def test_missing_or_invalid_login_input_is_http_400(client, payload):
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 400
    assert "token" not in response.get_json()


@pytest.mark.parametrize("payload", [None, [], "synthetic", 42])
def test_non_object_login_input_is_http_400(client, payload):
    response = client.post("/auth/login", json=payload, content_type="application/json")
    assert response.status_code == 400


@pytest.mark.parametrize("stored_hash", ["unused-test-password-hash", "$2b$12$broken", ""])
def test_invalid_stored_hash_is_a_generic_401(client, login_accounts, stored_hash, caplog, capsys):
    account = login_accounts(stored_hash=stored_hash)
    response = client.post("/auth/login", json=login_payload(account, "username", "email"))
    assert_invalid_credentials(response)
    captured = capsys.readouterr()
    output = captured.out + captured.err + caplog.text
    assert account["email"] not in output
    assert account["username"] not in output
    assert PASSWORD not in output


@pytest.mark.parametrize("identifier", ["username", "email"])
def test_ambiguous_identifier_does_not_select_arbitrary_account(client, account, login_accounts, identifier):
    login_accounts(**{identifier: account[identifier]})
    assert_invalid_credentials(client.post("/auth/login", json=login_payload(account, identifier)))


def test_both_identifiers_can_disambiguate_one_account(client, account, login_accounts):
    login_accounts(username=account["username"])
    login_accounts(email=account["email"])
    response = client.post("/auth/login", json=login_payload(account, "username", "email"))
    assert response.status_code == 200
    assert response.get_json()["data"]["user_id"] == account["user_id"]


def test_duplicate_username_and_email_are_rejected(client, account, login_accounts):
    login_accounts(username=account["username"], email=account["email"])
    assert_invalid_credentials(client.post("/auth/login", json=login_payload(account, "username", "email")))


def test_local_login_never_calls_clerk(client, account):
    with patch("auth.auth_controller._fetch_clerk_user", side_effect=AssertionError("No Clerk lookup")):
        response = client.post("/auth/login", json=login_payload(account, "username", "email"))
    assert response.status_code == 200
    assert response.get_json()["token"]


@pytest.mark.parametrize("identifiers", [("username",), ("email",), ("username", "email")])
def test_login_trims_identifiers(client, account, identifiers):
    payload = login_payload(account, *identifiers)
    for identifier in identifiers:
        payload[identifier] = "  " + payload[identifier] + "  "
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    assert response.get_json()["data"]["user_id"] == account["user_id"]


def test_password_whitespace_is_significant(client, login_accounts):
    password = "  significant synthetic password  "
    account = login_accounts(stored_hash=bcrypt.hashpw(
        password.encode(), bcrypt.gensalt(rounds=4),
    ).decode())
    payload = {**login_payload(account, "username", "email"), "password": password}
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    assert_invalid_credentials(client.post("/auth/login", json={
        **payload, "password": password.strip(),
    }))


@pytest.mark.parametrize("password", ["a" * 73, "á" * 37])
def test_bcrypt_password_limit_counts_utf8_bytes(client, app, account, password):
    response = client.post("/auth/login", json={
        **login_payload(account, "username", "email"), "password": password,
    })
    assert response.status_code == 400
    assert "token" not in response.get_json()
    with app.app_context():
        assert User.query.filter_by(user_id=account["user_id"]).one().last_login is None
        assert UserLogs.query.filter_by(user_id=account["user_id"]).count() == 0


@pytest.mark.parametrize("password", ["a" * 72, "á" * 36])
def test_bcrypt_password_accepts_exactly_72_utf8_bytes(client, login_accounts, password):
    account = login_accounts(stored_hash=bcrypt.hashpw(
        password.encode(), bcrypt.gensalt(rounds=4),
    ).decode())
    response = client.post("/auth/login", json={
        **login_payload(account, "username", "email"), "password": password,
    })
    assert response.status_code == 200
    assert response.get_json()["data"]["user_id"] == account["user_id"]


@pytest.mark.parametrize("failure", ["commit", "token", "query"])
def test_login_internal_errors_are_generic_and_rollback(client, app, account, failure, caplog, capsys):
    private_details = "SELECT password FROM private_users; private-db-secret"
    with app.app_context():
        real_rollback = db.session.rollback
        with patch.object(db.session, "rollback", wraps=real_rollback) as rollback:
            if failure == "commit":
                target = patch.object(db.session, "commit", side_effect=RuntimeError(private_details))
            elif failure == "query":
                target = patch("sqlalchemy.orm.Query.all", side_effect=RuntimeError(private_details))
            else:
                target = patch("auth.auth_service.create_access_token", side_effect=RuntimeError(private_details))
            with target:
                response = client.post("/auth/login", json=login_payload(account, "username", "email"))
            assert response.status_code == 500
            assert response.get_json() == SERVER_ERROR
            rollback.assert_called()
        assert User.query.filter_by(user_id=account["user_id"]).one().last_login is None
        assert UserLogs.query.filter_by(user_id=account["user_id"]).count() == 0
    output = capsys.readouterr()
    assert private_details not in response.get_data(as_text=True) + output.out + output.err + caplog.text


def test_service_error_contract_is_dictionary(app, account):
    with app.app_context():
        result = auth_service.login_user_service({
            **login_payload(account, "username", "email"), "password": "wrong-password",
        })
    assert result == INVALID_CREDENTIALS


def test_legacy_clerk_identifier_password_is_disabled_without_overwriting_hash(
    client, app, login_accounts,
):
    user_id = "user_legacy_clerk_42"
    legacy_hash = bcrypt.hashpw(user_id.encode(), bcrypt.gensalt(rounds=4)).decode()
    account = login_accounts(user_id=user_id, stored_hash=legacy_hash)
    assert_invalid_credentials(client.post("/auth/login", json={
        **login_payload(account, "username", "email"), "password": user_id,
    }))
    with app.app_context():
        user = User.query.filter_by(user_id=user_id).one()
        assert user.password == legacy_hash
        assert user.last_login is None


def test_password_token_is_accepted_by_reporting_pipeline_and_keeps_vl_boundary(client, account):
    response = client.post("/auth/login", json=login_payload(account, "username", "email"))
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.get_json()['token']}"}
    with patch(VL_SERVICE, return_value=[{"total": 7}]) as vl_query:
        own = client.get(VL_URL, headers=headers)
    with patch(DPI_SERVICE, return_value=[]) as dpi_query:
        other = client.get(DPI_URL, headers=headers)
    assert own.status_code == 200
    assert own.get_json() == [{"total": 7}]
    assert vl_query.call_args.args[0]["user_id"] == account["user_id"]
    assert other.status_code == 403
    dpi_query.assert_not_called()


def test_clerk_rs256_token_still_uses_persisted_vl_role(client, account, monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", None)
    fetch = Mock(side_effect=make_jwks)
    monkeypatch.setattr(token_verification, "_clerk_jwks", token_verification.JwksCache(fetch))
    token = make_clerk_token(sub=account["user_id"], role="Admin")
    headers = {"Authorization": f"Bearer {token}"}
    with patch(VL_SERVICE, return_value=[{"total": 7}]) as vl_query:
        own = client.get(VL_URL, headers=headers)
    with patch(DPI_SERVICE, return_value=[]) as dpi_query:
        other = client.get(DPI_URL, headers=headers)
    assert own.status_code == 200
    assert own.get_json() == [{"total": 7}]
    assert vl_query.call_args.args[0]["user_id"] == account["user_id"]
    assert other.status_code == 403
    dpi_query.assert_not_called()
    fetch.assert_called_once()


@pytest.mark.parametrize("event_type", ["session.created", "user.updated"])
def test_signed_clerk_events_preserve_local_role_and_password(
    client, app, account, monkeypatch, event_type,
):
    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", SECRET)
    profile = {
        "first_name": "Changed", "last_name": "Profile",
        "email_addresses": [{"email_address": account["email"]}],
        "public_metadata": {"role": "Admin"},
    }
    with app.app_context():
        original_hash = User.query.filter_by(user_id=account["user_id"]).one().password
    event_data = {"id": account["user_id"]}
    if event_type == "session.created":
        event_data = {"id": "sess_login_test", "user_id": account["user_id"]}
    with patch("auth.auth_controller._fetch_clerk_user", return_value=profile):
        response = signed_post(client, {"type": event_type, "data": event_data})
    assert response.status_code == 200
    assert "token" not in response.get_data(as_text=True).lower()
    with app.app_context():
        user = User.query.filter_by(user_id=account["user_id"]).one()
        assert user.role == "vl"
        assert user.password == original_hash
        assert bcrypt.checkpw(PASSWORD.encode(), user.password.encode())
        if event_type == "session.created":
            assert user.last_login is not None
        else:
            assert user.first_name == "Changed"
    login = client.post("/auth/login", json=login_payload(account, "email"))
    assert login.status_code == 200


def test_new_clerk_account_has_no_public_identifier_password(client, app, login_accounts, monkeypatch):
    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", SECRET)
    user_id = "user_login_new_clerk_42"
    login_accounts.created_ids.append(user_id)
    profile = {
        "first_name": "New", "last_name": "ClerkActor",
        "email_addresses": [{"email_address": "new-clerk@example.test"}],
    }
    with patch("auth.auth_controller._fetch_clerk_user", return_value=profile):
        response = signed_post(client, {"type": "user.created", "data": {"id": user_id}})
    assert response.status_code == 200
    assert "token" not in response.get_data(as_text=True).lower()
    with app.app_context():
        user = User.query.filter_by(user_id=user_id).one()
        assert user.role == "global"
        assert not bcrypt.checkpw(user_id.encode(), user.password.encode())
        username = user.user_name
    assert_invalid_credentials(client.post("/auth/login", json={
        "username": username, "email": "new-clerk@example.test", "password": user_id,
    }))
