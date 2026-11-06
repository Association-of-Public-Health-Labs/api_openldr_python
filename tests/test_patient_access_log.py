"""Patient access log: written by run_reporting_endpoint, never from the search terms."""
from unittest.mock import patch

import pytest

from db.database import db
from usage.models import PatientAccessLog
from usage.service import is_patient_request

VL_BY_NAME = "hiv.vl.controllers.vl_controller_patients.get_patients_by_name_service"
VL_SUMMARY = "hiv.vl.controllers.vl_controller_summary.samples_history_service_by_month"
URL = "/hiv/vl/patients/by_name/"


@pytest.fixture(autouse=True)
def clean_log(app):
    with app.app_context():
        PatientAccessLog.query.delete()
        db.session.commit()
    yield


def rows(app):
    with app.app_context():
        return [
            (r.user_id, r.dashboard, r.endpoint, r.row_count, r.occurred_at)
            for r in PatientAccessLog.query.order_by(PatientAccessLog.id)
        ]


@pytest.mark.parametrize("result,count", [([{"id": 1}, {"id": 2}], 2), ({"data": [{"id": 1}], "page": 1}, 1), ([], 0)])
def test_successful_patient_search_writes_one_row(app, client, auth_headers, result, count):
    with patch(VL_BY_NAME, return_value=result):
        assert client.get(URL, headers=auth_headers, query_string={"name": "x"}).status_code == 200
    log = rows(app)
    assert len(log) == 1
    user_id, dashboard, endpoint, row_count, occurred_at = log[0]
    assert (user_id, dashboard, endpoint, row_count) == ("test-123", "vl", URL, count)
    assert occurred_at is not None


def test_search_term_is_never_stored(app, client, auth_headers):
    with patch(VL_BY_NAME, return_value=[{"id": 1}]):
        client.get(URL + "?name=ANA_SECRETA", headers=auth_headers)
    log = rows(app)
    assert len(log) == 1
    assert not any("ANA_SECRETA" in str(value) for value in log[0])


def test_403_writes_no_row(app, client, auth_headers):
    with patch(VL_BY_NAME, return_value={"status": "error", "code": 403, "message": "Forbidden"}):
        assert client.get(URL, headers=auth_headers).status_code == 403
    assert rows(app) == []


def test_aggregate_request_writes_no_row(app, client, auth_headers):
    with patch(VL_SUMMARY, return_value=[{"year": 2025}]):
        assert client.get("/hiv/vl/summary/samples_history/", headers=auth_headers).status_code == 200
    assert rows(app) == []


def test_log_failure_still_returns_data(app, client, auth_headers, caplog):
    with patch(VL_BY_NAME, return_value=[{"id": 1}]), \
         patch("usage.service.PatientAccessLog", side_effect=RuntimeError("users db down")):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == [{"id": 1}]
    assert any(r.levelname == "ERROR" for r in caplog.records)
    assert rows(app) == []


def test_logging_helper_failure_cannot_500_a_patient_lookup(app, client, auth_headers, caplog):
    with patch(VL_BY_NAME, return_value=[{"id": 1}]), \
         patch("usage.service.count_rows", side_effect=RuntimeError("helper bug")):
        response = client.get(URL, headers=auth_headers, query_string={"name": "x"})
    assert response.status_code == 200
    assert response.get_json() == [{"id": 1}]
    assert any(r.levelname == "ERROR" for r in caplog.records)


@pytest.mark.parametrize("patient_data,status", [(True, 400), (False, 403)])
def test_eid_probe_without_a_name_checks_the_permission_and_logs_nothing(
        app, client, patient_data, status, monkeypatch):
    # /hiv/eid/patients/by_name/ with no name is the dashboards' access probe: 400 with patient
    # access, 403 without, and it must never leave a patient access row.
    from configs import paths
    from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
    from utilities import token_verification as tv

    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", True)
    claim = {"dashboards": ["vl", "eid", "tb"], "patientData": patient_data}
    headers = {"Authorization": f"Bearer {make_clerk_token(openldr=claim)}"}
    with patch("utilities.auth_helpers.get_user_by_id_service", return_value=None):
        response = client.get("/hiv/eid/patients/by_name/", headers=headers)
    assert response.status_code == status
    assert rows(app) == []


TB_LAB = "/tb/gx/laboratories/registered_samples/"
TB_FAC = "/tb/gx/facilities/registered_samples/"


@pytest.mark.parametrize("path,args,expected", [
    ("/hiv/vl/patients/by_name/", {}, True),
    ("/hiv/eid/patients/by_name/", {}, True),
    ("/tb/gx/patients/by_name/", {}, True),
    (TB_LAB, {"health_facility": "X"}, True),
    (TB_FAC, {"health_facility": ["X"]}, True),
    (TB_LAB, {"facility_type": "health_facility"}, True),
    (TB_FAC, {"facility_type": ["health_facility"]}, True),
    (TB_LAB, {"facility_type": "health_facility", "province": ["X"]}, False),
    (TB_LAB, {"facility_type": "health_facility", "district": "X"}, False),
    (TB_LAB, {"facility_type": "province"}, False),
    (TB_LAB, {}, False),
    (TB_LAB, {"health_facility": ""}, False),
    ("/tb/gx/summary/registered_samples/", {"health_facility": "X"}, False),
    ("/tb/cultura/summary/registered_samples/", {"health_facility": ["X"]}, False),
    ("/hiv/vl/facilities/registered_samples/", {"health_facility": "X"}, False),
    ("/hiv/eid/facilities/registered_samples/", {"health_facility": "X"}, False),
    ("/hiv/vl/summary/samples_history/", {}, False),
])
def test_is_patient_request(path, args, expected):
    assert is_patient_request(path, args) is expected


def test_tb_laboratory_patient_request_is_logged(app, client, auth_headers):
    target = "tb.gxpert.controllers.tb_gx_controller_laboratory.registered_samples_by_lab_service"
    with patch(target, return_value=[{"patient": 1}]):
        response = client.get(TB_LAB, headers=auth_headers, query_string={"health_facility": "X"})
    assert response.status_code == 200
    assert [(r[1], r[2], r[3]) for r in rows(app)] == [("tb", TB_LAB, 1)]
