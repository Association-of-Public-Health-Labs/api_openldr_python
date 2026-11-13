"""HTTP error boundaries use real JWT/SQLite authorization and only fake reports.

These tests exercise one representative route per existing reporting family.
No connection to SQL Server or external identity provider is made.
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from werkzeug.exceptions import InternalServerError, ServiceUnavailable

from utilities import report_cache
from utilities.service_helpers import InvalidParameter


REPORTS = [
    pytest.param(
        "/hiv/vl/summary/samples_history/",
        "hiv.vl.controllers.vl_controller_summary.samples_history_service_by_month",
        id="vl",
    ),
    pytest.param(
        "/hiv/eid/summary/indicators/",
        "hiv.eid.controllers.eid_controller_summary.summary_indicators_service",
        id="dpi",
    ),
    pytest.param(
        "/tb/gx/summary/summary_header_component/",
        "tb.gxpert.controllers.tb_gx_controller_summary.dashboard_header_component_summary_service",
        id="tb-gx",
    ),
    pytest.param(
        "/tb/cultura/summary/summary_indicators/",
        "tb.cultura.controllers.tb_cultura_controller_summary.cultura_summary_indicators_service",
        id="tb-cultura",
    ),
]
CACHEABLE_REPORTS = REPORTS[:3]


def generic_error(code=500):
    return {"status": "error", "code": code, "message": "An error occurred"}


@pytest.fixture
def enabled_cache(app, tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    monkeypatch.setenv("REPORT_CACHE_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("url,target", REPORTS)
@pytest.mark.parametrize("code", [400, 403, 404, 422])
def test_service_client_error_is_a_real_http_error(client, auth_headers, url, target, code):
    body = {"status": "error", "code": code, "message": "Invalid report filter"}
    with patch(target, return_value=body):
        response = client.get(url, headers=auth_headers)
    assert response.status_code == code
    assert response.get_json() == body


@pytest.mark.parametrize("url,target", REPORTS)
@pytest.mark.parametrize("code", [500, 503])
def test_service_server_error_only_exposes_the_generic_envelope(client, auth_headers, url, target, code):
    body = {
        "status": "error", "code": code,
        "message": "SELECT private_column FROM report_table",
        "error": "pyodbc.OperationalError: confidential database detail",
        "details": {"driver": "ODBC", "sql": "SELECT private_column"},
        "data": [{"connection": "sensitive-server"}],
    }
    with patch(target, return_value=body):
        response = client.get(url, headers=auth_headers)
    assert response.status_code == code
    assert response.get_json() == generic_error(code)


@pytest.mark.parametrize("url,target", REPORTS)
@pytest.mark.parametrize("code", [None, "503", True, 200, 600])
def test_invalid_service_error_code_fails_as_generic_500(client, auth_headers, url, target, code):
    body = {"status": "error", "code": code, "message": "SQL detail", "trace": "private trace"}
    with patch(target, return_value=body):
        response = client.get(url, headers=auth_headers)
    assert response.status_code == 500
    assert response.get_json() == generic_error()


@pytest.mark.parametrize("url,target", REPORTS)
def test_invalid_parameter_keeps_actionable_400(client, auth_headers, url, target):
    with patch(target, side_effect=InvalidParameter("interval_dates must contain two dates")):
        response = client.get(url, headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error", "code": 400, "message": "interval_dates must contain two dates",
    }


@pytest.mark.parametrize("url,target", REPORTS)
@pytest.mark.parametrize("exception,code", [
    (RuntimeError("pyodbc: SELECT confidential FROM Report"), 500),
    (InternalServerError(description="SELECT confidential FROM Report"), 500),
    (ServiceUnavailable(description="ODBC connection sensitive-server unavailable"), 503),
], ids=["unexpected", "http-500", "http-503"])
def test_unexpected_and_http_server_exceptions_are_generic(client, auth_headers, url, target, exception, code):
    with patch(target, side_effect=exception):
        response = client.get(url, headers=auth_headers)
    assert response.status_code == code
    assert response.is_json
    assert response.get_json() == generic_error(code)


@pytest.mark.parametrize("url,target", REPORTS)
@pytest.mark.parametrize("body", [
    [{"total": 7}],
    {"status": "success", "data": [{"total": 7}], "page": 1, "total": 1},
], ids=["list", "paginated-dict"])
def test_successful_reporting_shapes_are_preserved(client, auth_headers, url, target, body):
    with patch(target, return_value=body):
        response = client.get(url, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == body


@pytest.mark.parametrize("url,target", CACHEABLE_REPORTS)
@pytest.mark.parametrize("code", [400, 403, 500])
def test_service_errors_never_write_the_report_cache(client, auth_headers, enabled_cache, url, target, code):
    query = {"interval_dates": report_cache.window_param(report_cache.YEAR)}
    with patch(target, return_value={"status": "error", "code": code, "message": "Failure"}) as service:
        first = client.get(url, query_string=query, headers=auth_headers)
        second = client.get(url, query_string=query, headers=auth_headers)
    assert first.status_code == second.status_code == code
    assert service.call_count == 2
    assert "X-Report-Cache" not in first.headers
    assert "X-Report-Cache" not in second.headers
    assert not list(enabled_cache.glob("*.json"))


@pytest.mark.parametrize("url,target", CACHEABLE_REPORTS)
@pytest.mark.parametrize("code", [400, 403, 500])
def test_legacy_cached_error_is_recomputed_instead_of_served_as_200(client, auth_headers, enabled_cache, url, target, code):
    interval = report_cache.window_param(report_cache.YEAR)
    key = report_cache.cache_key(url, {"interval_dates": [interval]})
    assert key is not None
    # Bypass write(): old cache files may predate validation of report payloads.
    entry = {
        "key": key, "computed_at": datetime.now(timezone.utc).isoformat(),
        "data": {"status": "error", "code": code, "message": "SELECT private data"},
    }
    with open(report_cache._file(key), "w", encoding="utf-8") as cache_file:
        json.dump(entry, cache_file)
    with patch(target, return_value=[{"total": 9}]) as service:
        response = client.get(url, query_string={"interval_dates": interval}, headers=auth_headers)
    service.assert_called_once()
    assert response.status_code == 200
    assert response.get_json() == [{"total": 9}]
    assert response.headers.get("X-Report-Cache") == "MISS"
    assert report_cache.read(key)["data"] == [{"total": 9}]


@pytest.mark.parametrize("url,target", CACHEABLE_REPORTS)
@pytest.mark.parametrize("operation", ["cache_key", "read", "write"])
def test_optional_cache_failure_still_returns_the_successful_report(client, auth_headers, enabled_cache, url, target, operation):
    query = {"interval_dates": report_cache.window_param(report_cache.YEAR)}
    body = [{"total": 7}]
    with patch(target, return_value=body) as service:
        with patch.object(report_cache, operation, side_effect=RuntimeError("cache unavailable")):
            response = client.get(url, query_string=query, headers=auth_headers)
    service.assert_called_once()
    assert response.status_code == 200
    assert response.get_json() == body
    assert "X-Report-Cache" not in response.headers
    assert "X-Report-Computed-At" not in response.headers


def test_parser_client_error_keeps_existing_flask_restful_shape(client, auth_headers):
    target = "hiv.vl.controllers.vl_controller_patients.get_patients_by_facility_service"
    with patch(target) as service:
        response = client.get("/hiv/vl/patients/by_facility/?page=not-an-integer", headers=auth_headers)
    assert response.status_code == 400
    assert response.is_json
    assert "page" in response.get_json()["message"]
    service.assert_not_called()
