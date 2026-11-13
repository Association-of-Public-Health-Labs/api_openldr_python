"""Account deactivation against isolated SQLite users and real signed JWTs.

No production account, clinical database, Clerk API or SMTP server is contacted.
Only business report queries and Clerk transports are substituted.
"""
import json
import re
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import bcrypt
import pytest
from flask_jwt_extended import create_access_token, create_refresh_token
from sqlalchemy import Boolean, event
from sqlalchemy.dialects import mssql

from auth import auth_service
from auth.user_model import User, UserLogs
from configs import paths
from db.database import db
from tests.test_clerk_webhook import CLERK_USER, signed_post
from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
from tests.test_webhook_verification import SECRET
from utilities import report_cache, token_verification


PASSWORD = "synthetic-deactivation-password"
REPORT = "/hiv/vl/summary/number_of_samples_by_month/"
REPORT_SERVICE = "hiv.vl.controllers.vl_controller_summary.number_of_samples_service_by_month"
INVALID_CREDENTIALS = {"status": 401, "error": "Unauthorized", "message": "Invalid credentials"}
UNAUTHORIZED = {"status": "error", "code": 401, "message": "Invalid or missing token"}
ORIGINAL_DATE = datetime(2025, 1, 2, 3, 4, 5)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Deactivation tests must not use external services")
    monkeypatch.setattr("requests.sessions.Session.request", reject)


@pytest.fixture
def accounts(app):
    ids = []

    def create(role="vl", *, active=True):
        uid = "soft-" + uuid4().hex
        account = {"user_id": uid, "username": uid, "email": uid + "@example.test", "role": role}
        with app.app_context():
            db.session.add(User(
                user_id=uid, user_name=uid, email=account["email"], role=role,
                first_name="Synthetic", last_name="Account",
                password=bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode(),
                start_date=ORIGINAL_DATE, updated_at=ORIGINAL_DATE, is_active=active,
            ))
            db.session.commit()
        ids.append(uid)
        return account

    yield create
    with app.app_context():
        db.session.rollback()
        UserLogs.query.filter(UserLogs.user_id.in_(ids)).delete(synchronize_session=False)
        User.query.filter(User.user_id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        db.session.remove()


@pytest.fixture
def admin(accounts):
    return accounts("Admin")


@pytest.fixture
def target(accounts):
    return accounts()


@pytest.fixture
def clerk(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
    monkeypatch.setattr(paths, "CLERK_WEBHOOK_SECRET_KEY", SECRET)
    monkeypatch.setattr(token_verification, "_clerk_jwks", token_verification.JwksCache(make_jwks))


def bearer(app, account, issuer="api", *, refresh=False):
    uid = account["user_id"] if isinstance(account, dict) else account
    if issuer == "clerk":
        token = make_clerk_token(sub=uid)
    else:
        with app.app_context():
            factory = create_refresh_token if refresh else create_access_token
            token = factory(identity=uid, additional_claims={"role": "Admin", "user_id": uid})
    return {"Authorization": "Bearer " + token}


def deactivate(client, app, admin, target):
    return client.delete("/auth/delete", headers=bearer(app, admin), json={"user_id": target["user_id"]})


def login(client, account):
    return client.post("/auth/login", json={"username": account["username"], "password": PASSWORD})


def history(app, target):
    with app.app_context():
        entry = UserLogs(
            user_id=target["user_id"], log_id=str(uuid4()), log_date=ORIGINAL_DATE,
            log_type="login", log_details=json.dumps({"event": "historical_login"}),
        )
        db.session.add(entry)
        db.session.commit()
        return entry.id, entry.log_id, entry.log_date, entry.log_details


def test_model_uses_boolean_bit_and_nvarchar50_account_primary_key():
    assert isinstance(User.__table__.c.is_active.type, Boolean)
    assert User.__table__.c.is_active.nullable is False
    assert str(User.__table__.c.is_active.type.compile(dialect=mssql.dialect())) == "BIT"
    assert [column.name for column in User.__table__.primary_key] == ["user_id"]
    assert str(User.__table__.c.user_id.type.compile(dialect=mssql.dialect())) == "NVARCHAR(50)"


def test_delete_preserves_row_response_and_historical_audit_and_records_actor(client, app, admin, target):
    old_log = history(app, target)
    before = datetime.now()
    response = deactivate(client, app, admin, target)
    after = datetime.now()
    assert response.status_code == 200
    assert response.get_json() == {
        "message": "User deleted successfully",
        "data": {"user_id": target["user_id"], "username": target["username"],
                 "first_name": "Synthetic", "last_name": "Account",
                 "email": target["email"], "role": "vl"},
    }
    with app.app_context():
        user = User.query.filter_by(user_id=target["user_id"]).one()
        assert user.is_active is False
        assert before <= user.updated_at <= after
        stored_log = db.session.get(UserLogs, old_log[0])
        assert (stored_log.id, stored_log.log_id, stored_log.log_date, stored_log.log_details) == old_log
        audit = UserLogs.query.filter_by(user_id=user.user_id, log_type="user_deactivated").one()
        details = json.loads(audit.log_details)
        assert details["actor_id"] == admin["user_id"]
        assert details["target_user_id"] == user.user_id
        assert details["deactivated_at"] == user.updated_at.isoformat()
        assert audit.log_date == user.updated_at


def test_repeated_delete_preserves_first_timestamp_and_has_one_transition_audit(client, app, admin, target):
    first = deactivate(client, app, admin, target)
    assert first.status_code == 200
    with app.app_context():
        first_date = User.query.filter_by(user_id=target["user_id"]).one().updated_at
    second = deactivate(client, app, admin, target)
    assert second.status_code == 200
    assert second.get_json() == first.get_json()
    with app.app_context():
        assert User.query.filter_by(user_id=target["user_id"]).one().updated_at == first_date
        assert UserLogs.query.filter_by(user_id=target["user_id"], log_type="user_deactivated").count() == 1


def test_loaded_orm_account_reflects_deactivation_in_same_session(app, admin, target):
    with app.app_context():
        loaded = User.query.filter_by(user_id=target["user_id"]).one()
        assert loaded.is_active is True and loaded.updated_at == ORIGINAL_DATE
        result = auth_service.delete_user_service(target["user_id"], admin["user_id"])
        assert result["message"] == "User deleted successfully"
        assert loaded.is_active is False
        assert loaded.updated_at > ORIGINAL_DATE
        first_date = loaded.updated_at
        repeated = auth_service.delete_user_service(target["user_id"], admin["user_id"])
        assert repeated == result
        assert loaded.is_active is False and loaded.updated_at == first_date
        assert UserLogs.query.filter_by(user_id=target["user_id"], log_type="user_deactivated").count() == 1


def test_delete_executes_conditioned_update_without_physical_delete(client, app, admin, target):
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.upper())
    with app.app_context():
        engine = db.engines["users"]
        event.listen(engine, "before_cursor_execute", capture)
        try:
            assert deactivate(client, app, admin, target).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", capture)
    assert not any(sql.lstrip().startswith("DELETE") for sql in statements)
    updates = [sql for sql in statements if sql.lstrip().startswith("UPDATE OPENLDR_API_USER_USERS")]
    assert len(updates) == 1
    assert "UPDATED_AT" in updates[0].split("WHERE")[0]
    assert "IS_ACTIVE" in updates[0].split("WHERE")[0]
    assert "USER_ID" in updates[0].split("WHERE")[1]
    assert "IS_ACTIVE" in updates[0].split("WHERE")[1]


def test_real_selects_and_deactivation_update_compile_compatible_bit_predicates_for_sql_server(client, app, admin, target):
    compiled = []
    def capture(conn, clauseelement, multiparams, params, execution_options):
        if getattr(clauseelement, "__visit_name__", None) in {"select", "update"}:
            sql = str(clauseelement.compile(dialect=mssql.dialect())).upper()
            if "OPENLDR_API_USER_USERS" in sql:
                compiled.append(sql)
    with app.app_context():
        engine = db.engines["users"]
        event.listen(engine, "before_execute", capture)
        try:
            assert auth_service.get_user_by_id_service(target["user_id"]) is not None
            assert isinstance(auth_service.get_all_users_service(admin["user_id"]), list)
            assert deactivate(client, app, admin, target).status_code == 200
        finally:
            event.remove(engine, "before_execute", capture)
    selects = [sql for sql in compiled if sql.lstrip().startswith("SELECT")]
    updates = [sql for sql in compiled if sql.lstrip().startswith("UPDATE")]
    assert any(re.search(r"IS_ACTIVE\s*=\s*1\b", sql) for sql in selects)
    assert len(updates) == 1
    assert re.search(r"IS_ACTIVE\s*=\s*1\b", updates[0].split("WHERE")[1])
    # SQL Server BIT has = 1 predicates; IS 1 is accepted by SQLite only.
    assert not any(re.search(r"\bIS\s+1\b", sql) for sql in compiled)


@pytest.mark.parametrize("role", ["vl", "global", "user", "dpi", "tb_gx", "tb_cl", "ad"])
def test_non_admin_cannot_deactivate_even_with_admin_claim(client, app, accounts, target, role):
    actor = accounts(role)
    response = deactivate(client, app, actor, target)
    assert response.status_code == 403
    with app.app_context():
        user = User.query.filter_by(user_id=target["user_id"]).one()
        assert user.is_active is True
        assert user.updated_at == ORIGINAL_DATE
        assert UserLogs.query.filter_by(user_id=user.user_id).count() == 0


def test_missing_token_cannot_deactivate(client, app, target):
    response = client.delete("/auth/delete", json={"user_id": target["user_id"]})
    assert response.status_code == 401
    with app.app_context():
        assert User.query.filter_by(user_id=target["user_id"]).one().is_active is True


def test_unknown_target_preserves_existing_404(client, app, admin):
    response = client.delete("/auth/delete", headers=bearer(app, admin), json={"user_id": "unknown-synthetic"})
    assert response.status_code == 404
    assert response.get_json()["message"] == "User not found"


def test_failure_to_commit_rolls_back_state_timestamp_and_transition_audit(client, app, admin, target):
    old_log = history(app, target)
    with app.app_context():
        with patch.object(db.session, "commit", side_effect=RuntimeError("private db detail")):
            response = deactivate(client, app, admin, target)
        assert response.status_code == 500
        assert "private db detail" not in response.get_data(as_text=True)
        user = User.query.filter_by(user_id=target["user_id"]).one()
        assert user.is_active is True
        assert user.updated_at == ORIGINAL_DATE
        assert UserLogs.query.filter_by(user_id=user.user_id, log_type="user_deactivated").count() == 0
        assert db.session.get(UserLogs, old_log[0]) is not None


def test_failure_to_write_transition_audit_rolls_back_deactivation(client, app, admin, target):
    old_log = history(app, target)
    with app.app_context():
        with patch.object(db.session, "add", side_effect=RuntimeError("private audit failure")):
            response = deactivate(client, app, admin, target)
        assert response.status_code == 500
        assert "private audit failure" not in response.get_data(as_text=True)
        user = User.query.filter_by(user_id=target["user_id"]).one()
        assert user.is_active is True and user.updated_at == ORIGINAL_DATE
        assert UserLogs.query.filter_by(user_id=user.user_id).count() == 1
        assert db.session.get(UserLogs, old_log[0]) is not None


def test_admin_deactivating_own_account_cannot_use_same_token_again(client, app, admin):
    headers = bearer(app, admin)
    response = client.delete("/auth/delete", headers=headers, json={"user_id": admin["user_id"]})
    assert response.status_code == 200
    assert client.get("/auth/users", headers=headers).status_code == 401


def test_inactive_password_login_is_generic_and_other_active_account_still_works(client, app, admin, target, accounts):
    other = accounts()
    assert login(client, target).status_code == 200
    assert deactivate(client, app, admin, target).status_code == 200
    with app.app_context():
        last_login = User.query.filter_by(user_id=target["user_id"]).one().last_login
        log_count = UserLogs.query.filter_by(user_id=target["user_id"]).count()
    response = login(client, target)
    assert response.status_code == 401
    assert response.get_json() == INVALID_CREDENTIALS
    assert login(client, other).status_code == 200
    with app.app_context():
        assert User.query.filter_by(user_id=target["user_id"]).one().last_login == last_login
        assert UserLogs.query.filter_by(user_id=target["user_id"]).count() == log_count


def test_preexisting_inactive_account_cannot_password_login(client, app, accounts):
    account = accounts(active=False)
    response = login(client, account)
    assert response.status_code == 401
    assert response.get_json() == INVALID_CREDENTIALS
    with app.app_context():
        assert User.query.filter_by(user_id=account["user_id"]).one().last_login is None
        assert UserLogs.query.filter_by(user_id=account["user_id"]).count() == 0


def test_active_account_with_inactive_duplicate_identifier_can_still_login(client, app, accounts):
    inactive = accounts(active=False)
    active = accounts()
    with app.app_context():
        user = User.query.filter_by(user_id=inactive["user_id"]).one()
        user.user_name = active["username"]
        db.session.commit()
    response = login(client, active)
    assert response.status_code == 200
    assert response.get_json()["data"]["user_id"] == active["user_id"]


@pytest.mark.parametrize("issuer", ["api", "clerk"])
def test_previously_issued_token_cannot_read_cached_report_after_commit(client, app, admin, target, clerk, tmp_path, monkeypatch, issuer):
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    monkeypatch.setenv("REPORT_CACHE_DIR", str(tmp_path))
    headers = bearer(app, target, issuer)
    query = {"interval_dates": report_cache.window_param(report_cache.YEAR)}
    with patch(REPORT_SERVICE, return_value=[{"synthetic_total": 7}]) as service:
        assert client.get(REPORT, headers=headers, query_string=query).headers["X-Report-Cache"] == "MISS"
        assert client.get(REPORT, headers=headers, query_string=query).headers["X-Report-Cache"] == "HIT"
        assert deactivate(client, app, admin, target).status_code == 200
        response = client.get(REPORT, headers=headers, query_string=query)
    assert response.status_code == 401
    assert response.get_json() == UNAUTHORIZED
    assert "X-Report-Cache" not in response.headers
    assert service.call_count == 1


@pytest.mark.parametrize("issuer", ["api", "clerk"])
@pytest.mark.parametrize("operation", ["dictionary", "suggestion"])
@pytest.mark.parametrize("state", ["inactive", "missing"])
def test_inactive_or_missing_subject_cannot_use_shared_protected_operations(client, app, accounts, clerk, issuer, operation, state):
    actor = accounts(active=False) if state == "inactive" else "missing-synthetic-subject"
    headers = bearer(app, actor, issuer)
    if operation == "dictionary":
        # Rejected authentication must precede any dictionary or SMTP call.
        with patch("dict.controllers.facilities_controller.get_all_facilities", return_value=[]) as service:
            response = client.get("/dict/facilities/", headers=headers)
    else:
        with patch("suggestions.controller.send_suggestion") as service:
            response = client.post("/hiv/vl/send-suggestion?duvida=true", headers=headers,
                                   json={"content": "Synthetic", "reportTitle": "Synthetic"})
    assert response.status_code == 401
    assert response.get_json() == UNAUTHORIZED
    service.assert_not_called()


@pytest.mark.parametrize("state", ["inactive", "missing"])
@pytest.mark.parametrize("operation", ["list", "create", "update", "delete"])
def test_api_management_rechecks_inactive_or_missing_jwt_subject(client, app, accounts, target, state, operation):
    actor = accounts("Admin", active=False) if state == "inactive" else "missing-synthetic-admin"
    headers = bearer(app, actor)
    if operation == "list":
        response = client.get("/auth/users", headers=headers)
    elif operation == "create":
        response = client.post("/auth/create", headers=headers, json={})
    elif operation == "update":
        response = client.put("/auth/update", headers=headers, json={})
    else:
        response = client.delete("/auth/delete", headers=headers, json={"user_id": target["user_id"]})
    assert response.status_code == 401
    with app.app_context():
        assert User.query.filter_by(user_id=target["user_id"]).one().is_active is True


def test_operational_list_and_lookup_hide_inactive_but_authorized_history_is_retained(client, app, admin, target):
    old_log = history(app, target)
    assert deactivate(client, app, admin, target).status_code == 200
    listed = client.get("/auth/users", headers=bearer(app, admin))
    assert listed.status_code == 200
    assert admin["user_id"] in {u["user_id"] for u in listed.get_json()}
    assert target["user_id"] not in {u["user_id"] for u in listed.get_json()}
    with app.app_context():
        assert auth_service.get_user_by_id_service(target["user_id"]) is None
        historical = auth_service.get_user_by_id_service(target["user_id"], include_inactive=True)
        assert historical is not None and historical.is_active is False
        assert db.session.get(UserLogs, old_log[0]).user_id == historical.user_id


def test_signed_clerk_deletion_is_idempotent_soft_deactivation(client, app, target, clerk):
    old_log = history(app, target)
    event = {"type": "user.deleted", "data": {"id": target["user_id"]}}
    assert signed_post(client, event).status_code == 200
    with app.app_context():
        first_date = User.query.filter_by(user_id=target["user_id"]).one().updated_at
    assert signed_post(client, event).status_code == 200
    with app.app_context():
        user = User.query.filter_by(user_id=target["user_id"]).one()
        assert user.is_active is False and user.updated_at == first_date
        audits = UserLogs.query.filter_by(user_id=user.user_id).all()
        assert len(audits) == 2  # Existing history plus one atomic transition.
        changed = next(entry for entry in audits if entry.id != old_log[0])
        assert changed.log_type == "user_deactivated"
        assert json.loads(changed.log_details)["actor_id"] == "clerk"


def test_signed_clerk_session_cannot_recreate_or_log_in_inactive_account(client, app, accounts, clerk):
    target = accounts(active=False)
    profile = {**CLERK_USER, "id": target["user_id"]}
    with patch("auth.auth_controller._fetch_clerk_user", return_value=profile), \
         patch("auth.auth_controller.provision_clerk_user_service", side_effect=AssertionError("Must not recreate")):
        response = signed_post(client, {"type": "session.created", "data": {"user_id": target["user_id"], "id": "synthetic-session"}})
    assert response.status_code == 401
    assert "token" not in response.get_json()
    with app.app_context():
        user = User.query.filter_by(user_id=target["user_id"]).one()
        assert user.is_active is False and user.last_login is None
        assert user.updated_at == ORIGINAL_DATE
        assert UserLogs.query.filter_by(user_id=user.user_id).count() == 0


def test_signed_clerk_profile_cannot_reactivate_or_overwrite_disabled_account(client, app, accounts, clerk):
    target = accounts(active=False)
    with app.app_context():
        original_hash = User.query.filter_by(user_id=target["user_id"]).one().password
    profile = {**CLERK_USER, "id": target["user_id"], "public_metadata": {"role": "Admin", "is_active": True}}
    with patch("auth.auth_controller._fetch_clerk_user", return_value=profile):
        response = signed_post(client, {"type": "user.updated", "data": {"id": target["user_id"]}})
    assert response.status_code == 404
    with app.app_context():
        user = User.query.filter_by(user_id=target["user_id"]).one()
        assert user.is_active is False and user.role == "vl"
        assert user.password == original_hash and user.updated_at == ORIGINAL_DATE


def test_direct_clerk_provisioning_cannot_recreate_inactive_identity(app, accounts):
    target = accounts(active=False)
    args = {"user_id": target["user_id"], "username": "Changed synthetic profile",
            "first_name": "Changed", "last_name": "Profile", "email": "changed@example.test",
            "password": PASSWORD, "confirm_password": PASSWORD, "role": "Admin"}
    with app.app_context():
        stored_hash = User.query.filter_by(user_id=target["user_id"]).one().password
        result = auth_service.provision_clerk_user_service(args)
        assert result["status"] == 409
        user = User.query.filter_by(user_id=target["user_id"]).one()
        assert user.is_active is False and user.password == stored_hash
        assert user.user_name == target["username"] and user.role == "vl"
        assert user.updated_at == ORIGINAL_DATE
        assert UserLogs.query.filter_by(user_id=user.user_id).count() == 0


def test_last_login_service_cannot_mark_inactive_account_as_authenticated(app, accounts):
    target = accounts(active=False)
    with app.app_context():
        result = auth_service.update_last_login_service(target["user_id"])
        assert result["status"] == 404
        user = User.query.filter_by(user_id=target["user_id"]).one()
        assert user.is_active is False and user.last_login is None
        assert user.updated_at == ORIGINAL_DATE


def test_no_refresh_route_exists_and_refresh_token_cannot_be_used_as_access(client, app, target):
    assert not any("refresh" in rule.rule.lower() for rule in app.url_map.iter_rules())
    headers = bearer(app, target, refresh=True)
    with patch(REPORT_SERVICE, return_value=[]) as service:
        assert client.get(REPORT, headers=headers).status_code == 401
    assert client.get("/auth/users", headers=headers).status_code in {401, 422}
    service.assert_not_called()
