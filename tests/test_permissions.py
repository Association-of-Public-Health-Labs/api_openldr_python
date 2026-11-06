"""Permission gate: claim parsing, path mapping, and the check in authenticate_request."""
from unittest.mock import patch

import pytest
from flask import Flask

from configs import paths
from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
from utilities import controller_helpers, report_cache, token_verification as tv
from utilities.permissions import (
    NO_PERMISSIONS,
    Permissions,
    current_permissions,
    dashboard_for_path,
    forbidden_response,
    parse_claim,
    permissions_for_token,
)

VL_URL = "/hiv/vl/summary/tat_by_month/"
VL_SERVICE = "hiv.vl.controllers.vl_controller_summary.tat_service_by_month"


@pytest.mark.parametrize(
    "claims,expected",
    [
        (
            {"openldr": {"dashboards": ["vl", "tb"], "patientData": True, "admin": True}},
            Permissions(frozenset({"vl", "tb"}), True, True, False),
        ),
        ({}, NO_PERMISSIONS),
        ({"openldr": "vl"}, NO_PERMISSIONS),
        ({"openldr": {"dashboards": "vl"}}, NO_PERMISSIONS),
        ({"openldr": {"dashboards": ["vl", "nope", 3, None]}}, Permissions(frozenset({"vl"}))),
        ({"openldr": {"dashboards": ["eid"], "patientData": "yes"}}, Permissions(frozenset({"eid"}))),
        ({"openldr": {"admin": 1}}, NO_PERMISSIONS),
        (None, NO_PERMISSIONS),
    ],
    ids=["good", "no-key", "string-section", "string-dashboards", "unknown-dropped", "patientData-yes", "admin-1", "not-a-dict"],
)
def test_parse_claim(claims, expected):
    assert parse_claim(claims) == expected


def test_hs256_style_claims_get_no_permissions_even_with_an_openldr_claim():
    claims = {"openldr": {"dashboards": ["vl"]}, "role": "Admin"}
    assert permissions_for_token(claims) == NO_PERMISSIONS
    assert permissions_for_token({**claims, "iss": ISSUER}).dashboards == frozenset({"vl"})


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/hiv/vl/summary/x/", "vl"),
        ("/hiv/eid/x/", "eid"),
        ("/tb/gx/x/", "tb"),
        ("/tb/cultura/x/", "tb"),
        ("/tb/send-suggestion", "tb"),
        ("/dict/x/", None),
        ("/usage/events", None),
        ("/auth/login", None),
        ("/hivex/", None),
    ],
)
def test_dashboard_for_path(path, expected):
    assert dashboard_for_path(path) == expected


def test_forbidden_response():
    assert forbidden_response() == ({"status": "error", "code": 403, "message": "Forbidden"}, 403)


@pytest.fixture
def clerk_config(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))


@pytest.fixture
def enforced(app, monkeypatch):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", True)


def bearer(dashboards=None):
    extra = {} if dashboards is None else {"openldr": {"dashboards": dashboards}}
    return {"Authorization": f"Bearer {make_clerk_token(**extra)}"}


def get_vl(client, headers):
    with patch(VL_SERVICE, return_value=[]) as service:
        response = client.get(VL_URL, headers=headers)
    return response, service


def test_flag_on_without_dashboard_is_403(client, clerk_config, enforced):
    response, service = get_vl(client, bearer(["tb"]))
    assert response.status_code == 403
    assert response.get_json() == forbidden_response()[0]
    service.assert_not_called()


def test_flag_on_with_dashboard_passes(client, clerk_config, enforced):
    response, service = get_vl(client, bearer(["vl"]))
    assert response.status_code == 200
    service.assert_called_once()


def test_flag_off_without_claim_passes(client, clerk_config):
    response, _ = get_vl(client, bearer())
    assert response.status_code == 200


def test_flag_on_no_claim_is_403_and_bad_token_still_401(client, clerk_config, enforced):
    assert get_vl(client, bearer())[0].status_code == 403
    assert get_vl(client, {"Authorization": "Bearer nope"})[0].status_code == 401


def test_flag_on_no_claim_on_dict_endpoint_passes(clerk_config):
    probe = Flask(__name__)
    probe.config.update(PERMISSIONS_ENFORCED=True, SECRET_KEY="probe")

    @probe.route("/dict/x/")
    def dict_x():
        user_id, err = controller_helpers.authenticate_request()
        return err if err is not None else {"user": user_id, "dashboards": sorted(current_permissions().dashboards)}

    response = probe.test_client().get("/dict/x/", headers=bearer())
    assert response.status_code == 200
    assert response.get_json() == {"user": "user_abc", "dashboards": []}


def test_flag_on_cached_report_without_dashboard_is_403(app, client, clerk_config, enforced, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_CACHE_DIR", str(tmp_path))
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    key = {"path": VL_URL, "window": report_cache.YEAR, "params": {}}
    report_cache.write(key, [{"total": 1}])
    query = {"interval_dates": report_cache.window_param(report_cache.YEAR)}

    allowed = client.get(VL_URL, query_string=query, headers=bearer(["vl"]))
    assert allowed.status_code == 200
    assert allowed.headers["X-Report-Cache"] == "HIT"

    denied = client.get(VL_URL, query_string=query, headers=bearer(["tb"]))
    assert denied.status_code == 403
    assert "X-Report-Cache" not in denied.headers
