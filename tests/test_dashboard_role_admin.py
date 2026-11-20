"""Persisted role assignment, administrative boundaries and Clerk synchronization.

All account operations use the SQLite users bind; Clerk requests carry real Svix
signatures and only the outbound profile fetch is replaced.
"""
from unittest.mock import patch
from uuid import uuid4

import pytest

from auth.user_model import User, UserLogs
from db.database import db
from tests.test_clerk_webhook import CLERK_USER, signed_post
from tests.test_dashboard_roles import bearer
from tests.test_webhook_verification import SECRET


CANONICAL_ROLES = ["Admin", "global", "vl", "dpi", "tb_gx", "tb_cl", "ad", "user"]
NON_ADMIN_ROLES = [role for role in CANONICAL_ROLES if role != "Admin"]


@pytest.fixture
def new_account(app):
    """Clean up accounts made through HTTP, outside the persisted-user factory."""
    yield {
        "username": "role-admin-test-new",
        "first_name": "New",
        "last_name": "Account",
        "password": "role-creation-password",
        "confirm_password": "role-creation-password",
        "email": "role-admin-test-new@example.test",
        "role": "vl",
    }
    with app.app_context():
        db.session.rollback()
        User.query.filter_by(user_name="role-admin-test-new").delete()
        db.session.commit()


def update_payload(user_id, role="vl", **extra):
    return {
        "user_id": user_id,
        "username": "role-admin-test-updated",
        "first_name": "Updated",
        "last_name": "Account",
        "email": "role-admin-test-updated@example.test",
        "role": role,
        **extra,
    }


def account_state(app):
    with app.app_context():
        accounts = [
            (u.user_id, u.user_name, u.first_name, u.last_name, u.email, u.role, u.password)
            for u in User.query.order_by(User.id).all()
        ]
        return accounts, UserLogs.query.count()


@pytest.mark.parametrize("role", CANONICAL_ROLES)
def test_admin_can_create_each_supported_role(client, app, persisted_user, new_account, role):
    actor = persisted_user(role="Admin")
    response = client.post("/auth/create", headers=bearer(app, actor, role="user"),
                           json={**new_account, "role": role})
    assert response.status_code == 200
    assert response.get_json()["data"]["role"] == role
    with app.app_context():
        created = User.query.filter_by(user_id=response.get_json()["data"]["user_id"]).one()
        assert created.role == role


@pytest.mark.parametrize("role", CANONICAL_ROLES)
def test_admin_can_assign_roles_without_replacing_password(client, app, persisted_user, role):
    actor = persisted_user(role="Admin")
    target = persisted_user(role="user")
    with app.app_context():
        original_hash = User.query.filter_by(user_id=target).one().password
    response = client.put("/auth/update", headers=bearer(app, actor, role="user"),
                          json=update_payload(target, role))
    assert response.status_code == 200
    with app.app_context():
        updated = User.query.filter_by(user_id=target).one()
        assert updated.role == role
        assert updated.password == original_hash
        assert updated.first_name == "Updated"
    assert response.get_json()["data"]["role"]["new"] == role


@pytest.mark.parametrize("role,canonical", [(" VL ", "vl"), ("Tb_Gx", "tb_gx"), ("GLOBAL", "global")])
def test_admin_role_assignment_normalizes_supported_input(client, app, persisted_user, role, canonical):
    actor = persisted_user(role="Admin")
    target = persisted_user(role="user")
    response = client.put("/auth/update", headers=bearer(app, actor), json=update_payload(target, role))
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(user_id=target).one().role == canonical


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("role", ["manager", "superadmin", "vl,dpi"])
def test_unknown_role_is_rejected_without_account_changes(client, app, persisted_user, new_account, operation, role):
    actor = persisted_user(role="Admin")
    target = persisted_user(role="user")
    before = account_state(app)
    if operation == "create":
        response = client.post("/auth/create", headers=bearer(app, actor),
                               json={**new_account, "role": role})
    else:
        response = client.put("/auth/update", headers=bearer(app, actor),
                              json=update_payload(target, role))
    assert response.status_code == 400
    assert account_state(app) == before


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
@pytest.mark.parametrize("operation", ["list", "create", "update", "delete"])
def test_reporting_roles_have_no_user_management_privileges(client, app, persisted_user, new_account, role, operation):
    actor = persisted_user(role=role)
    target = persisted_user(role="vl")
    before = account_state(app)
    headers = bearer(app, actor, role="Admin")
    if operation == "list":
        response = client.get("/auth/users", headers=headers)
    elif operation == "create":
        response = client.post("/auth/create", headers=headers, json={**new_account, "role": "Admin"})
    elif operation == "update":
        response = client.put("/auth/update", headers=headers, json=update_payload(target, "Admin"))
    else:
        response = client.delete("/auth/delete", headers=headers, json={"user_id": target})
    assert response.status_code == 403
    assert account_state(app) == before


def test_admin_can_list_and_delete_users(client, app, persisted_user):
    actor = persisted_user(role="Admin")
    target = persisted_user(role="vl")
    headers = bearer(app, actor, role="user")
    try:
        listed = client.get("/auth/users", headers=headers)
        assert listed.status_code == 200
        assert {actor, target} <= {u["user_id"] for u in listed.get_json()}
        deleted = client.delete("/auth/delete", headers=headers, json={"user_id": target})
        assert deleted.status_code == 200
        with app.app_context():
            assert User.query.filter_by(user_id=target).one().is_active is False
    finally:
        with app.app_context():
            UserLogs.query.filter(UserLogs.user_id.in_([actor, target])).delete(synchronize_session=False)
            db.session.commit()


@pytest.mark.parametrize("password_fields", [
    {"password": "new-password"},
    {"confirm_password": "new-password"},
    {"password": "new-password", "confirm_password": "different"},
])
def test_partial_password_update_is_rejected_without_changes(client, app, persisted_user, password_fields):
    actor = persisted_user(role="Admin")
    target = persisted_user(role="vl")
    before = account_state(app)
    response = client.put("/auth/update", headers=bearer(app, actor),
                          json=update_payload(target, "dpi", **password_fields))
    assert response.status_code == 400
    assert account_state(app) == before


@pytest.mark.parametrize("role", ["vl", "global", "Admin"])
def test_signed_clerk_profile_update_preserves_local_role_and_password(client, app, persisted_user, monkeypatch, role):
    from configs import paths

    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", SECRET)
    target = persisted_user(role=role)
    with app.app_context():
        original_hash = User.query.filter_by(user_id=target).one().password
    profile = {**CLERK_USER, "id": target, "public_metadata": {"role": "Admin"},
               "unsafe_metadata": {"role": "Admin"}}
    with patch("auth.auth_controller._fetch_clerk_user", return_value=profile):
        response = signed_post(client, {"type": "user.updated", "data": {"id": target}})
    assert response.status_code == 200
    with app.app_context():
        updated = User.query.filter_by(user_id=target).one()
        assert updated.role == role
        assert updated.password == original_hash
        assert updated.first_name == profile["first_name"]
        assert updated.last_name == profile["last_name"]
        assert updated.email == profile["email_addresses"][0]["email_address"]
        UserLogs.query.filter_by(user_id=target).delete()
        db.session.commit()


def test_signed_clerk_creation_cannot_assign_admin_from_metadata(client, app, monkeypatch):
    from configs import paths

    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", SECRET)
    target = f"role-clerk-created-{uuid4()}"
    profile = {**CLERK_USER, "id": target, "first_name": "Provisioned",
               "last_name": target, "role": "Admin", "public_metadata": {"role": "Admin"}}
    try:
        with patch("auth.auth_controller._fetch_clerk_user", return_value=profile):
            response = signed_post(client, {"type": "user.created", "data": {"id": target}})
        assert response.status_code == 200
        with app.app_context():
            assert User.query.filter_by(user_id=target).one().role == "global"
    finally:
        with app.app_context():
            UserLogs.query.filter_by(user_id=target).delete()
            User.query.filter_by(user_id=target).delete()
            db.session.commit()


@pytest.mark.parametrize("role", ["vl", "global"])
def test_patient_search_keeps_existing_admin_only_restriction(client, app, persisted_user, role):
    actor = persisted_user(role=role)
    service = "hiv.vl.controllers.vl_controller_patients.get_patients_by_name_service"
    with patch(service, return_value=[]) as query:
        response = client.get("/hiv/vl/patients/by_name/", headers=bearer(app, actor, role="Admin"))
    assert response.status_code == 403
    query.assert_not_called()
