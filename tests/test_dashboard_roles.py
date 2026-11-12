"""HTTP authorization contracts backed by persisted SQLite users.

Only report queries are mocked. JWT verification, persisted identity resolution,
role checks and response-cache ordering run through the production pipeline.
"""
from unittest.mock import Mock, patch

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token
from flasgger import Swagger

from auth.user_model import User
from db.database import db
from utilities import report_cache
from utilities.controller_helpers import run_reporting_endpoint
from utilities.swagger import swagger_template


REPORTS = [
    ("vl", "/hiv/vl/summary/tat_by_month/",
     "hiv.vl.controllers.vl_controller_summary.tat_service_by_month"),
    ("dpi", "/hiv/eid/laboratories/tested_samples_by_month/",
     "hiv.eid.controllers.eid_controller_laboratory.tested_samples_by_month_service"),
    ("tb_gx", "/tb/gx/laboratories/registered_samples/",
     "tb.gxpert.controllers.tb_gx_controller_laboratory.registered_samples_by_lab_service"),
    ("tb_cl", "/tb/cultura/summary/summary_indicators/",
     "tb.cultura.controllers.tb_cultura_controller_summary.cultura_summary_indicators_service"),
]
ROLES = ["vl", "dpi", "tb_gx", "tb_cl", "ad", "global", "Admin"]
DICT_ENDPOINTS = [
    ("/dict/laboratories/", "dict.controllers.laboratories_controller.get_all_laboratories"),
    ("/dict/laboratories/provinces/", "dict.controllers.laboratories_controller.get_laboratories_by_province"),
    ("/dict/laboratories/province/districts/", "dict.controllers.laboratories_controller.get_laboratories_by_district"),
    ("/dict/facilities/", "dict.controllers.facilities_controller.get_all_facilities"),
    ("/dict/facilities/provinces/", "dict.controllers.facilities_controller.get_facilities_by_province"),
    ("/dict/facilities/province/districts/", "dict.controllers.facilities_controller.get_facilities_by_district"),
]


def bearer(app, identity, **claims):
    with app.app_context():
        token = create_access_token(identity=identity, additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


def change_role(app, user_id, role):
    with app.app_context():
        User.query.filter_by(user_id=user_id).update({"role": role})
        db.session.commit()


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("domain,url,service", REPORTS)
def test_each_role_sees_only_its_reports(client, app, persisted_user, role, domain, url, service):
    user_id = persisted_user(role=role)
    with patch(service, return_value=[{"total": 7}]) as query:
        response = client.get(url, headers=bearer(app, user_id, role="Admin"))
    if role in {domain, "global", "Admin"}:
        assert response.status_code == 200
        assert response.get_json() == [{"total": 7}]
        query.assert_called_once()
        assert query.call_args.args[0]["user_id"] == user_id
    else:
        assert response.status_code == 403
        query.assert_not_called()


@pytest.mark.parametrize("role", ROLES)
def test_reserved_ad_namespace_uses_same_authorization_pipeline(app, persisted_user, role):
    """Exercise the reserved namespace without publishing a premature AD route."""
    user_id = persisted_user(role=role)
    query = Mock(return_value=[{"total": 7}])
    with app.test_request_context(
        "/hiv/ad/summary/indicators/", headers=bearer(app, user_id),
    ):
        response = run_reporting_endpoint(lambda: {}, query)
    if role in {"ad", "global", "Admin"}:
        assert response == [{"total": 7}]
        query.assert_called_once()
    else:
        assert response[1] == 403
        query.assert_not_called()


@pytest.mark.parametrize("domain,url,service", REPORTS)
def test_all_report_domains_require_verified_token(client, domain, url, service):
    with patch(service, return_value=[]) as query:
        response = client.get(url)
    assert response.status_code == 401
    query.assert_not_called()


@pytest.mark.parametrize("role", ["user", "User", "admin", "", "unknown", " vl "])
def test_unassigned_or_unknown_roles_cannot_read_reports(client, app, persisted_user, role):
    user_id = persisted_user(role=role)
    _, url, service = REPORTS[0]
    with patch(service, return_value=[]) as query:
        response = client.get(url, headers=bearer(app, user_id, role="Admin"))
    assert response.status_code == 403
    query.assert_not_called()


def test_verified_subject_wins_over_conflicting_identity_and_role_claims(client, app, persisted_user):
    user_id = persisted_user(role="vl")
    admin_id = persisted_user(role="Admin")
    headers = bearer(app, user_id, user_id=admin_id, role="Admin")
    with patch(REPORTS[0][2], return_value=[]) as vl_query:
        own = client.get(REPORTS[0][1], headers=headers)
    with patch(REPORTS[1][2], return_value=[]) as dpi_query:
        other = client.get(REPORTS[1][1], headers=headers)
    assert own.status_code == 200
    assert vl_query.call_args.args[0]["user_id"] == user_id
    assert other.status_code == 403
    dpi_query.assert_not_called()


def test_deleted_user_cannot_reuse_valid_token(client, app, persisted_user):
    user_id = persisted_user(role="vl")
    headers = bearer(app, user_id, role="vl")
    _, url, service = REPORTS[0]
    with patch(service, return_value=[]) as query:
        assert client.get(url, headers=headers).status_code == 200
        with app.app_context():
            User.query.filter_by(user_id=user_id).delete()
            db.session.commit()
        response = client.get(url, headers=headers)
    assert response.status_code == 403
    assert query.call_count == 1


def test_role_change_is_applied_on_next_request_with_same_token(client, app, persisted_user):
    user_id = persisted_user(role="global")
    headers = bearer(app, user_id, role="global")
    _, url, service = REPORTS[1]
    with patch(service, return_value=[]) as query:
        assert client.get(url, headers=headers).status_code == 200
        change_role(app, user_id, "vl")
        response = client.get(url, headers=headers)
    assert response.status_code == 403
    assert query.call_count == 1


def test_role_revocation_is_checked_before_cached_report(client, app, persisted_user, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_CACHE_DIR", str(tmp_path))
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    user_id = persisted_user(role="vl")
    headers = bearer(app, user_id, role="vl")
    url = "/hiv/vl/summary/number_of_samples_by_month/"
    service = "hiv.vl.controllers.vl_controller_summary.number_of_samples_service_by_month"
    query_params = {"interval_dates": report_cache.window_param(report_cache.YEAR)}
    with patch(service, return_value=[{"total": 7}]) as query:
        first = client.get(url, headers=headers, query_string=query_params)
        cached = client.get(url, headers=headers, query_string=query_params)
        change_role(app, user_id, "dpi")
        denied = client.get(url, headers=headers, query_string=query_params)
    assert first.status_code == cached.status_code == 200
    assert first.headers["X-Report-Cache"] == "MISS"
    assert cached.headers["X-Report-Cache"] == "HIT"
    assert denied.status_code == 403
    assert "X-Report-Cache" not in denied.headers
    assert query.call_count == 1


def test_missing_persisted_identity_cannot_use_admin_claim(client, app):
    _, url, service = REPORTS[0]
    with patch(service, return_value=[]) as query:
        response = client.get(url, headers=bearer(app, "missing-user", role="Admin"))
    assert response.status_code == 403
    query.assert_not_called()


def test_role_lookup_failure_returns_fixed_500_before_service(client, app):
    _, url, service = REPORTS[0]
    with patch("utilities.controller_helpers.get_user_by_id_service", side_effect=RuntimeError("SELECT password FROM private_users; secret=value")):
        with patch(service, return_value=[]) as query:
            response = client.get(url, headers=bearer(app, "actor", role="Admin"))
    assert response.status_code == 500
    assert response.get_json() == {
        "status": "error", "code": 500, "message": "An error occurred",
    }
    query.assert_not_called()


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("url,service", DICT_ENDPOINTS)
def test_dictionary_access_is_shared_by_assigned_roles(client, app, persisted_user, role, url, service):
    user_id = persisted_user(role=role)
    with patch(service, return_value=[]) as query:
        response = client.get(url, headers=bearer(app, user_id))
    assert response.status_code == 200
    query.assert_called_once()


@pytest.mark.parametrize("role", ["user", "unknown"])
@pytest.mark.parametrize("url,service", DICT_ENDPOINTS)
def test_dictionary_denies_unassigned_roles(client, app, persisted_user, role, url, service):
    user_id = persisted_user(role=role)
    with patch(service, return_value=[]) as query:
        response = client.get(url, headers=bearer(app, user_id))
    assert response.status_code == 403
    query.assert_not_called()


@pytest.mark.parametrize("url,service", DICT_ENDPOINTS)
def test_dictionary_requires_verified_token(client, url, service):
    with patch(service, return_value=[]) as query:
        response = client.get(url)
    assert response.status_code == 401
    query.assert_not_called()


@pytest.mark.parametrize("role", ["global", "vl", "dpi", "tb_gx", "tb_cl", "ad"])
def test_reporting_roles_cannot_create_users(client, app, persisted_user, role):
    user_id = persisted_user(role=role)
    response = client.post("/auth/create", headers=bearer(app, user_id, role="Admin"), json={
        "username": "should-not-be-created",
        "first_name": "Unauthorized",
        "last_name": "User",
        "password": "test-new-password",
        "confirm_password": "test-new-password",
        "email": "no-create@example.test",
        "role": "Admin",
    })
    assert response.status_code == 403
    with app.app_context():
        assert User.query.filter_by(user_name="should-not-be-created").first() is None


def test_swagger_remains_public_without_authorizing_report_requests():
    app = Flask("public-role-docs")
    Swagger(app, template=swagger_template)
    client = app.test_client()
    assert client.get("/apidocs/").status_code == 200
    assert client.get("/apispec_1.json").status_code == 200


@pytest.mark.parametrize("role", ["global", "vl"])
@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_reporting_roles_do_not_gain_write_permissions(app, persisted_user, role, method):
    actor = persisted_user(role=role)
    parser, service = Mock(return_value={}), Mock(return_value=[])
    with app.test_request_context("/hiv/vl/summary/new_report/", method=method,
                                  headers=bearer(app, actor)):
        body, code = run_reporting_endpoint(parser, service)
    assert code == 403
    parser.assert_not_called()
    service.assert_not_called()


@pytest.mark.parametrize("role,url,allowed", [
    ("vl", "/hiv/send-suggestion", True),
    ("dpi", "/hiv/eid/send-suggestion", True),
    ("ad", "/hiv/send-suggestion", True),
    ("tb_gx", "/tb/send-suggestion", True),
    ("tb_cl", "/tb/cultura/send-suggestion", True),
    ("global", "/tb/cultura/send-suggestion", True),
    ("vl", "/tb/send-suggestion", False),
    ("tb_cl", "/hiv/send-suggestion", False),
    ("dpi", "/hiv/vl/send-suggestion", False),
])
def test_suggestions_follow_division_and_family_access(client, app, persisted_user, role, url, allowed):
    actor = persisted_user(role=role)
    with patch("suggestions.controller.send_suggestion") as send:
        response = client.post(url + "?duvida=true", json={"content": "test"},
                               headers=bearer(app, actor))
    assert response.status_code == (200 if allowed else 403)
    assert send.call_count == int(allowed)
