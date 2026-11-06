"""
Service accounts and /auth/* when PERMISSIONS_ENFORCED is on.

/auth/login is limited to the names in API_SERVICE_ACCOUNTS (bcrypt secret), a service token reads
report numbers on every dashboard and nothing else, and the API's user-management routes are
retired (410). With the flag off everything behaves as before, plus the caller is logged.
"""
import json
from datetime import datetime
from unittest.mock import patch

import bcrypt
import pytest
from flask_jwt_extended import create_access_token

from auth.user_model import User, UserLogs
from configs import paths
from db.database import db
from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
from utilities import token_verification as tv
from utilities.permissions import NO_PERMISSIONS, service_account_names, permissions_for_token

SECRET = "s3cret-" + "x" * 40
VL_URL = "/hiv/vl/summary/tat_by_month/"
VL_SERVICE = "hiv.vl.controllers.vl_controller_summary.tat_service_by_month"
UNAUTHORIZED = {"status": "error", "code": 401, "message": "Invalid or missing token"}
BAD_LOGIN = {"status": 401, "error": "Unauthorized", "message": "Invalid credentials"}


@pytest.fixture(autouse=True)
def clerk_config(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))


@pytest.fixture
def enforced(app, monkeypatch):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", True)
    monkeypatch.setattr(paths, "API_SERVICE_ACCOUNTS", "svc-dash, svc-other")


@pytest.fixture
def not_enforced(app, monkeypatch):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", False)
    monkeypatch.setattr(paths, "API_SERVICE_ACCOUNTS", "svc-dash")


@pytest.fixture(autouse=True)
def users(app):
    def row(name, user_id, password):
        return User(
            user_id=user_id, user_name=name, first_name="F", last_name="L",
            password=bcrypt.hashpw(password.encode(), bcrypt.gensalt(4)).decode(),
            start_date=datetime.now(), updated_at=datetime.now(), role="service", email=None,
        )
    with app.app_context():
        User.query.delete()
        UserLogs.query.delete()
        db.session.add_all([
            row("svc-dash", "svc-svc-dash", SECRET),
            row("alice", "alice-id", "alice-id"),  # personal account: user_id == password
        ])
        db.session.commit()
    yield
    with app.app_context():
        User.query.delete()
        UserLogs.query.delete()
        db.session.commit()


def login(client, username, password, **kw):
    return client.post("/auth/login", json={"username": username, "password": password}, **kw)


def service_headers(client):
    response = login(client, "svc-dash", SECRET)
    assert response.status_code == 200, response.data
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def hs256(app, user_name):
    with app.app_context():
        return {"Authorization": "Bearer " + create_access_token(identity="x", additional_claims={"user_name": user_name})}


# --- permissions ---------------------------------------------------------------

def test_service_account_names(app, monkeypatch):
    monkeypatch.setattr(paths, "API_SERVICE_ACCOUNTS", " a, b ,,c ")
    assert service_account_names() == frozenset({"a", "b", "c"})
    monkeypatch.setattr(paths, "API_SERVICE_ACCOUNTS", None)
    assert service_account_names() == frozenset()


def test_permissions_for_hs256_tokens(monkeypatch):
    monkeypatch.setattr(paths, "API_SERVICE_ACCOUNTS", "svc-dash")
    listed = permissions_for_token({"user_name": "svc-dash"})
    assert listed.dashboards == frozenset({"vl", "eid", "tb"})
    assert (listed.patient_data, listed.admin, listed.service) == (False, False, True)
    assert permissions_for_token({"user_name": "alice"}) == NO_PERMISSIONS
    assert permissions_for_token({"user_name": ["svc-dash"]}) == NO_PERMISSIONS
    assert permissions_for_token({}) == NO_PERMISSIONS
    # A Clerk-style token is never a service token, whatever its user_name.
    assert not permissions_for_token({"iss": ISSUER, "user_name": "svc-dash"}).service


# --- flag on ---------------------------------------------------------------------

def test_listed_service_account_logs_in_and_reads_a_report(client, enforced):
    headers = service_headers(client)
    with patch(VL_SERVICE, return_value=[]):
        assert client.get(VL_URL, headers=headers).status_code == 200


@pytest.mark.parametrize("url", [
    "/hiv/vl/patients/by_name/", "/hiv/eid/patients/by_name/", "/tb/gx/patients/by_name/",
])
def test_service_account_cannot_read_patient_rows(client, enforced, url):
    assert client.get(url, headers=service_headers(client)).status_code == 403


def test_service_account_cannot_use_tb_health_facility(client, enforced):
    from unittest.mock import MagicMock
    labs = "tb.gxpert.services.tb_gx_services_laboratories"
    with patch(f"{labs}.get_user_by_id_service", return_value=None), \
         patch(f"{labs}.get_patients", return_value=MagicMock(all=lambda: [])), \
         patch(f"{labs}.process_patients", return_value=[]):
        response = client.get("/tb/gx/laboratories/registered_samples/",
                              headers=service_headers(client), query_string={"health_facility": "X"})
    assert response.status_code == 403


def test_service_account_cannot_call_usage_reports(client, enforced):
    response = client.get("/usage/summary/", headers=service_headers(client),
                          query_string={"interval_dates": "2026-11-01,2026-11-30"})
    assert response.status_code == 403


def test_unlisted_personal_account_login_is_401_with_the_same_body(client, enforced):
    unlisted = login(client, "alice", "alice-id")
    wrong_secret = login(client, "svc-dash", "nope")
    missing_row = login(client, "svc-other", SECRET)  # listed, but no row
    for response in (unlisted, wrong_secret, missing_row):
        assert response.status_code == 401
        assert response.get_json() == BAD_LOGIN


def test_personal_row_with_a_listed_name_is_not_a_service_login(client, app, enforced):
    with app.app_context():
        User.query.filter_by(user_name="svc-dash").delete()
        db.session.add(User(
            user_id="personal-id", user_name="svc-dash", first_name="F", last_name="L",
            password=bcrypt.hashpw(SECRET.encode(), bcrypt.gensalt(4)).decode(),
            start_date=datetime.now(), updated_at=datetime.now(), role="Admin", email=None,
        ))
        db.session.commit()
    response = login(client, "svc-dash", SECRET)
    assert response.status_code == 401
    assert response.get_json() == BAD_LOGIN


def test_overlong_password_is_a_plain_401(client, enforced):
    response = login(client, "svc-dash", "x" * 200)
    assert response.status_code == 401
    assert response.get_json() == BAD_LOGIN


def test_old_personal_hs256_token_is_401_on_a_report(client, app, enforced):
    with patch(VL_SERVICE, return_value=[]) as service:
        response = client.get(VL_URL, headers=hs256(app, "alice"))
    assert response.status_code == 401
    assert response.get_json() == UNAUTHORIZED
    service.assert_not_called()


def test_token_of_a_name_removed_from_the_list_is_401(client, app, enforced, monkeypatch):
    headers = service_headers(client)
    monkeypatch.setattr(paths, "API_SERVICE_ACCOUNTS", "svc-other")
    with patch(VL_SERVICE, return_value=[]):
        response = client.get(VL_URL, headers=headers)
    assert response.status_code == 401
    assert response.get_json() == UNAUTHORIZED


RETIRED = [("get", "/auth/users"), ("post", "/auth/create"), ("put", "/auth/update"), ("delete", "/auth/delete")]


@pytest.mark.parametrize("method,url", RETIRED)
def test_user_management_routes_are_gone_even_without_a_token(client, enforced, method, url):
    response = getattr(client, method)(url)
    assert response.status_code == 410
    assert response.get_json()["code"] == 410


@pytest.mark.parametrize("method,url", RETIRED)
def test_user_management_routes_are_gone_with_a_token(client, enforced, auth_headers, method, url):
    assert getattr(client, method)(url, headers=auth_headers).status_code == 410


def test_clerk_webhook_still_reaches_its_signature_check(client, enforced):
    response = client.post("/auth/clerk", json={"type": "session.created"})
    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid webhook signature"


# --- flag off --------------------------------------------------------------------

@pytest.mark.parametrize("method,url", RETIRED)
def test_flag_off_user_management_routes_need_a_token_as_before(client, not_enforced, method, url):
    assert getattr(client, method)(url).status_code == 401


def test_flag_off_personal_login_and_old_token_work_as_before(client, app, not_enforced):
    response = login(client, "alice", "alice-id")
    assert response.status_code == 200
    assert response.get_json()["status"] == 200
    headers = {"Authorization": f"Bearer {response.get_json()['token']}"}
    with patch(VL_SERVICE, return_value=[]):
        assert client.get(VL_URL, headers=headers).status_code == 200


def test_flag_off_bad_login_body_is_unchanged(client, not_enforced):
    response = login(client, "alice", "wrong")
    assert response.status_code == 200
    assert response.get_json() == [BAD_LOGIN]


def login_log_context(app, user_id):
    with app.app_context():
        logs = UserLogs.query.filter_by(user_id=user_id, log_type="login").all()
        assert len(logs) == 1
        return json.loads(logs[0].log_details)["context"]


def test_flag_off_login_records_ip_and_user_agent(client, app, not_enforced):
    login(client, "alice", "alice-id", headers={"X-Forwarded-For": "203.0.113.9", "User-Agent": "probe/1"})
    assert login_log_context(app, "alice-id") == {"ip": "203.0.113.9", "user_agent": "probe/1"}


def test_login_log_falls_back_to_remote_addr(client, app, not_enforced):
    login(client, "alice", "alice-id", headers={"User-Agent": "probe/2"})
    context = login_log_context(app, "alice-id")
    assert context["ip"] == "127.0.0.1" and context["user_agent"] == "probe/2"


def test_flag_on_login_is_logged_with_the_caller(client, app, enforced):
    login(client, "svc-dash", SECRET, headers={"X-Forwarded-For": "198.51.100.4"})
    assert login_log_context(app, "svc-svc-dash")["ip"] == "198.51.100.4"


def test_flag_on_lookup_error_is_a_generic_500(client, enforced):
    with patch("auth.auth_service.User") as model:
        model.query.filter_by.side_effect = RuntimeError("DRIVERDETAIL server=x")
        response = login(client, "svc-dash", SECRET)
    assert response.status_code == 500
    assert "DRIVERDETAIL" not in response.get_data(as_text=True)
    assert response.get_json() == {"status": "error", "code": 500, "message": "An error occurred"}


def test_flag_on_token_error_is_a_generic_500(client, enforced):
    with patch("auth.auth_service.create_access_token", side_effect=RuntimeError("KEYDETAIL")):
        response = login(client, "svc-dash", SECRET)
    assert response.status_code == 500
    assert "KEYDETAIL" not in response.get_data(as_text=True)
    assert response.get_json()["message"] == "An error occurred"


# --- a listed account also logs in with the flag off ------------------------------------

def test_flag_off_listed_account_logs_in_with_its_secret(client, not_enforced):
    response = login(client, "svc-dash", SECRET)
    assert response.status_code == 200 and response.get_json()["token"]


def test_flag_off_listed_account_wrong_secret_is_401(client, not_enforced):
    response = login(client, "svc-dash", "svc-svc-dash")  # its user_id is not its password
    assert response.status_code == 401 and response.get_json() == BAD_LOGIN


def test_flag_off_listed_account_token_gets_numbers_but_not_patients_or_usage(client, not_enforced):
    headers = service_headers(client)
    with patch(VL_SERVICE, return_value=[]):
        assert client.get(VL_URL, headers=headers).status_code == 200
    assert client.get("/hiv/vl/patients/by_name/", headers=headers).status_code == 403
    assert client.get("/usage/summary/", headers=headers,
                      query_string={"interval_dates": "2026-11-01,2026-11-30"}).status_code == 403


def test_flag_off_unlisted_name_follows_the_old_path(client, not_enforced):
    assert login(client, "alice", "alice-id").get_json()["status"] == 200
    assert login(client, "alice", "wrong").get_json() == [BAD_LOGIN]


# --- tools/create_service_account.py ------------------------------------------------

def test_create_service_account_builds_the_row():
    from tools.create_service_account import build_service_account
    secret, row = build_service_account("tb-dashboard")
    assert (row.user_id, row.user_name, row.role) == ("svc-tb-dashboard", "tb-dashboard", "service")
    assert len(secret) >= 64 and secret not in row.password
    assert bcrypt.checkpw(secret.encode(), row.password.encode())
    assert build_service_account("tb-dashboard")[0] != secret


@pytest.mark.parametrize("name", ["", "Upper", "1abc", "-abc", "a_b", "a b", "a.b", "a\n"])
def test_create_service_account_refuses_a_bad_name(name):
    from tools.create_service_account import build_service_account, main, validate_name
    with pytest.raises(ValueError):
        validate_name(name)
    with pytest.raises(ValueError):
        build_service_account(name)
    assert main([name]) == 2


def test_create_service_account_needs_exactly_one_argument():
    from tools.create_service_account import main
    assert main([]) == 2 and main(["a", "b"]) == 2
