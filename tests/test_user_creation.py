"""Regression coverage for administrative creation and signed Clerk provisioning.

All database assertions use the test application's in-memory SQLite users bind.
No production configuration, SQL Server connection or Clerk API is used.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from auth import auth_service
from auth.user_model import User, UserLogs
from configs import paths
from db.database import db
from tests.test_clerk_webhook import CLERK_USER, _contains_token, signed_post
from tests.test_webhook_verification import SECRET


CREATE_URL = "/auth/create"
FORBIDDEN = {
    "status": 403,
    "error": "Forbidden",
    "message": "Admin permission required",
}


@pytest.fixture(autouse=True)
def isolated_users(app):
    """Leave the shared session-scoped test application clean after each test."""
    with app.app_context():
        db.session.remove()
        UserLogs.query.delete()
        User.query.delete()
        db.session.commit()
        try:
            yield
        finally:
            db.session.rollback()
            UserLogs.query.delete()
            User.query.delete()
            db.session.commit()
            db.session.remove()


@pytest.fixture
def user_args():
    return {
        "username": "new_user",
        "first_name": "New",
        "last_name": "User",
        "password": "test-password-for-creation",
        "confirm_password": "test-password-for-creation",
        "email": "new-user@example.test",
        "role": "user",
    }


def persist_actor(role="Admin", user_id="actor-admin"):
    now = datetime.now()
    actor = User(
        user_id=user_id,
        user_name="actor",
        first_name="Actor",
        last_name="Test",
        email="actor@example.test",
        password="unused-password-hash",
        role=role,
        start_date=now,
        updated_at=now,
    )
    db.session.add(actor)
    db.session.commit()
    return actor


def jwt_headers(identity, role="Admin", expires_delta=None):
    token = create_access_token(
        identity=identity,
        additional_claims={"role": role},
        expires_delta=expires_delta,
    )
    return {"Authorization": f"Bearer {token}"}


def assert_no_created_user(actor_count=0):
    assert User.query.count() == actor_count
    assert UserLogs.query.count() == 0


@pytest.mark.parametrize("role", ["user", "User", "admin", " Admin "])
def test_service_requires_exact_persisted_admin(user_args, role):
    actor = persist_actor(role=role)
    user_args["role"] = "Admin"

    result = auth_service.create_user_service(user_args, actor.user_id)

    assert result == FORBIDDEN
    assert_no_created_user(actor_count=1)


@pytest.mark.parametrize("identity", [None, "", "unknown-user"])
def test_service_denies_absent_or_unknown_actor_without_writes(user_args, identity):
    result = auth_service.create_user_service(user_args, identity)

    assert result == FORBIDDEN
    assert_no_created_user()


@pytest.mark.parametrize(
    "requested_role,stored_role",
    [("Admin", "Admin"), (" admin ", "Admin"), ("ADMIN", "Admin"),
     ("User", "user"), (" user ", "user"), ("uSeR", "user")],
)
def test_admin_creates_user_with_canonical_role(user_args, requested_role, stored_role):
    actor = persist_actor()
    user_args["role"] = requested_role

    result = auth_service.create_user_service(user_args, actor.user_id)

    assert result["message"] == "User created successfully"
    created = User.query.filter_by(user_id=result["data"]["user_id"]).one()
    assert created.role == stored_role
    assert created.user_name == user_args["username"]
    assert result["data"] == {
        "user_id": created.user_id,
        "username": user_args["username"],
        "first_name": user_args["first_name"],
        "last_name": user_args["last_name"],
        "email": user_args["email"],
        "role": stored_role,
    }
    assert "token" not in result
    assert User.query.count() == 2


@pytest.mark.parametrize("role", ["manager", "superadmin", "", None,
                                  1, ["Admin"], {"role": "Admin"}])
def test_service_rejects_unknown_or_empty_role_without_writes(user_args, role):
    actor = persist_actor()
    user_args["role"] = role

    result = auth_service.create_user_service(user_args, actor.user_id)

    assert result["status"] == 400
    assert result["error"] == "Bad Request"
    assert_no_created_user(actor_count=1)


@pytest.mark.parametrize("role", ["user", "User"])
def test_http_ignores_admin_claim_for_non_admin_actor(client, user_args, role):
    actor = persist_actor(role=role)
    user_args["role"] = "Admin"

    response = client.post(CREATE_URL, json=user_args,
                           headers=jwt_headers(actor.user_id, role="Admin"))

    assert response.status_code == 403
    assert response.get_json() == FORBIDDEN
    assert_no_created_user(actor_count=1)


def test_http_denies_unknown_identity_even_with_admin_claim(client, user_args):
    response = client.post(CREATE_URL, json=user_args,
                           headers=jwt_headers("deleted-user", role="Admin"))

    assert response.status_code == 401
    assert response.get_json() == {
        "status": 401, "error": "Unauthorized", "message": "User not authenticated",
    }
    assert_no_created_user()


@pytest.mark.parametrize("via_http", [False, True])
def test_basic_user_cannot_select_clerk_or_bypass_authorization(client, user_args, via_http):
    actor = persist_actor(role="User")
    user_args.update({"provider": "clerk", "user_id": "requested-clerk-id",
                      "bypass": True, "skip_permission_check": True, "role": "Admin"})

    if via_http:
        response = client.post(CREATE_URL, json=user_args,
                               headers=jwt_headers(actor.user_id))
        assert response.status_code == 403
        result = response.get_json()
    else:
        result = auth_service.create_user_service(user_args, actor.user_id)

    assert result == FORBIDDEN
    assert_no_created_user(actor_count=1)


@pytest.mark.parametrize("role,expected_role", [("Admin", "Admin"), ("User", "user")])
def test_http_admin_creation_preserves_success_contract(client, user_args, role, expected_role):
    actor = persist_actor()
    user_args["role"] = role

    response = client.post(CREATE_URL, json=user_args,
                           headers=jwt_headers(actor.user_id, role="user"))

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "User created successfully"
    assert payload["data"]["role"] == expected_role
    assert User.query.filter_by(user_id=payload["data"]["user_id"]).one().role == expected_role
    assert not _contains_token(payload)


@pytest.mark.parametrize("error_kind", ["missing_field", "password_mismatch", "unknown_role"])
def test_http_creation_validation_returns_400_without_writes(client, user_args, error_kind):
    actor = persist_actor()
    if error_kind == "missing_field":
        user_args.pop("first_name")
    elif error_kind == "password_mismatch":
        user_args["confirm_password"] = "different-password"
    else:
        user_args["role"] = "superadmin"

    response = client.post(CREATE_URL, json=user_args,
                           headers=jwt_headers(actor.user_id))

    assert response.status_code == 400
    assert_no_created_user(actor_count=1)


@pytest.mark.parametrize("status,error", [(400, "Bad Request"), (403, "Forbidden"),
                                         (500, "Internal Server Error")])
def test_http_creation_uses_service_error_status(client, user_args, status, error):
    actor = persist_actor()
    message = "private-sql SELECT password FROM users" if status == 500 else "Creation failed"
    body = {"status": status, "error": error, "message": message}
    with patch("auth.auth_controller.create_user_service", return_value=body):
        response = client.post(CREATE_URL, json=user_args,
                               headers=jwt_headers(actor.user_id))

    assert response.status_code == status
    if status == 500:
        assert response.get_json() == {
            "status": 500, "error": "Internal Server Error", "message": "An error occurred"
        }
        assert message not in response.get_data(as_text=True)
    else:
        assert response.get_json() == body
    assert_no_created_user(actor_count=1)


@pytest.mark.parametrize("token_kind,expected_status", [("missing", 401), ("expired", 401),
                                                       ("malformed", 422)])
def test_http_creation_rejects_invalid_auth_before_service(client, user_args,
                                                         token_kind, expected_status):
    if token_kind == "missing":
        headers = {}
    elif token_kind == "expired":
        headers = jwt_headers("actor-admin", expires_delta=timedelta(seconds=-1))
    else:
        headers = {"Authorization": "Bearer invalid-token"}
    with patch("auth.auth_controller.create_user_service") as create:
        response = client.post(CREATE_URL, json=user_args, headers=headers)

    assert response.status_code == expected_status
    create.assert_not_called()
    assert_no_created_user()


def test_http_creation_lookup_error_fails_closed_without_details(client, user_args, caplog):
    private_detail = "private-sql SELECT password FROM users; actor@example.test"
    with patch("auth.auth_controller.get_user_by_id_service",
               side_effect=RuntimeError(private_detail)):
        response = client.post(CREATE_URL, json=user_args,
                               headers=jwt_headers("actor-admin"))

    assert response.status_code == 500
    assert response.get_json()["error"] == "Internal Server Error"
    assert private_detail not in response.get_data(as_text=True)
    assert private_detail not in caplog.text
    assert_no_created_user()


def test_http_creation_commit_error_rolls_back_without_details(client, user_args, caplog):
    actor = persist_actor()
    private_detail = "private-sql INSERT INTO users VALUES (new-user@example.test)"
    with patch.object(db.session, "commit", side_effect=RuntimeError(private_detail)):
        response = client.post(CREATE_URL, json=user_args,
                               headers=jwt_headers(actor.user_id))

    assert response.status_code == 500
    assert response.get_json()["error"] == "Internal Server Error"
    assert private_detail not in response.get_data(as_text=True)
    assert private_detail not in caplog.text
    assert_no_created_user(actor_count=1)


def test_clerk_provisioning_forces_basic_role_without_admin(user_args):
    user_args.update({"user_id": "user_clerk_new", "provider": "clerk", "role": "Admin"})

    result = auth_service.provision_clerk_user_service(user_args)

    assert result["message"] == "User created successfully"
    assert result["data"]["role"] == "user"
    assert User.query.one().role == "user"
    assert User.query.one().user_id == "user_clerk_new"
    assert not _contains_token(result)


@pytest.mark.parametrize("event", ["user.created", "session.created"])
def test_signed_clerk_event_provisions_without_admin_or_token(client, monkeypatch, event):
    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", SECRET)
    clerk_user = {**CLERK_USER, "public_metadata": {"role": "Admin"}}
    data = {"id": "user_abc"} if event == "user.created" else {
        "id": "session-new", "user_id": "user_abc"
    }
    with patch("auth.auth_controller._fetch_clerk_user", return_value=clerk_user), \
         patch("auth.auth_controller.create_user_service",
               side_effect=AssertionError("Webhook must use Clerk provisioning")) as create:
        response = signed_post(client, {"type": event, "data": data})

    assert response.status_code == 200
    assert response.get_json()["message"] == "User created successfully"
    assert not _contains_token(response.get_json())
    assert User.query.one().user_id == "user_abc"
    assert User.query.one().role == "user"
    create.assert_not_called()


@pytest.mark.parametrize("status,error", [(400, "Bad Request"), (500, "Internal Server Error")])
def test_signed_clerk_creation_error_does_not_record_success(client, monkeypatch, status, error):
    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", SECRET)
    message = "private-sql INSERT INTO users" if status == 500 else "Could not create user"
    body = {"status": status, "error": error, "message": message}
    with patch("auth.auth_controller._fetch_clerk_user", return_value=CLERK_USER), \
         patch("auth.auth_controller.provision_clerk_user_service",
               return_value=body):
        response = signed_post(client, {"type": "user.created", "data": {"id": "user_abc"}})

    assert response.status_code == status
    if status == 500:
        assert response.get_json() == {
            "status": 500, "error": "Internal Server Error", "message": "An error occurred"
        }
        assert message not in response.get_data(as_text=True)
    else:
        assert response.get_json() == body
    assert_no_created_user()
