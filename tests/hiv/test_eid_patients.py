"""EID patient searches: admin gate, paging, filters and contact privacy."""
import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.orm import Query

import pytest

from tests.hiv.sql_capture import service_sql
from hiv.eid.services import eid_services_patients as patients
from utilities import report_cache
from utilities.service_helpers import InvalidParameter

ARGS = {"interval_dates": ["2025-01-01,2025-12-31"]}
URL = "/hiv/eid/patients/by_facility/"
PHONE = "84 123 4567"
PTV = "PTV-MOTHER-0099"
KEYS = [
    "request_id", "name", "sex", "age_in_days", "requesting_province", "requesting_district",
    "requesting_facility", "testing_facility", "specimen_date", "registered_date",
    "analysis_date", "authorised_date", "lab_type", "result", "rejection_reason",
    "caregiver_phone", "mother_ptv_id",
]


@pytest.fixture
def admin():
    with patch.object(patients, "_get_user_role", return_value=("u1", "Admin")):
        yield


def patient_row(**values):
    fields = dict.fromkeys(KEYS)
    fields.update(request_id="R1", caregiver_phone=PHONE, mother_ptv_id=PTV,
                  registered_date=datetime(2025, 3, 4, 5, 6), **values)
    return SimpleNamespace(_asdict=lambda: dict(fields))


def test_columns_are_the_documented_keys():
    assert [column.key for column in patients.EID_PATIENT_COLUMNS] == KEYS


def test_rows_are_plain_dicts_with_iso_dates(app, admin):
    result, _ = service_sql(app, patients.get_patients_by_facility_service, ARGS,
                            results=[[patient_row()]])
    [record] = result["data"]
    assert list(record) == KEYS
    assert record["registered_date"] == "2025-03-04T05:06:00"
    assert record["caregiver_phone"] == PHONE and record["mother_ptv_id"] == PTV


def test_non_admin_is_refused_without_a_query(app):
    with patch.object(patients, "_get_user_role", return_value=("u2", "Viewer")):
        result, sql = service_sql(app, patients.get_patients_by_facility_service, ARGS)
    assert result["code"] == 403 and sql == []


def test_role_check_comes_before_parameter_validation(app):
    with patch.object(patients, "_get_user_role", return_value=("u2", "Viewer")):
        result, sql = service_sql(app, patients.get_patients_by_facility_service,
                                  {**ARGS, "lab_type": "bogus", "per_page": "x"})
    assert result["code"] == 403 and sql == []


def test_per_page_is_capped_at_500(app, admin):
    result, _ = service_sql(app, patients.get_patients_by_facility_service, {**ARGS, "per_page": 1000})
    assert result["per_page"] == 500


@pytest.mark.parametrize("extra", [{"page": 0}, {"per_page": 0}, {"page": "x"}, {"lab_type": "bogus"},
                                   {"result_type": ["maybe"]}, {"interval_dates": ["bad"]}])
def test_bad_parameters_are_a_400(app, admin, extra):
    with pytest.raises(InvalidParameter):
        service_sql(app, patients.get_patients_by_facility_service, {**ARGS, **extra})


def test_missing_required_filters_are_a_400(app, admin):
    result, _ = service_sql(app, patients.get_patients_by_name_service, ARGS)
    assert result["code"] == 400
    result, _ = service_sql(app, patients.get_patients_by_result_type_service, ARGS)
    assert result["code"] == 400


def test_service_never_logs_contacts(app, admin):
    with patch("logging.Logger._log") as log:
        service_sql(app, patients.get_patients_by_facility_service, ARGS, results=[[patient_row()]])
        # Failure path: the error is logged without its message or the rows.
        with app.app_context(), patch.object(Query, "count", lambda self: 0), \
                patch.object(Query, "all", side_effect=RuntimeError(PHONE + PTV)):
            result = patients.get_patients_by_facility_service(dict(ARGS))
    assert result["code"] == 500 and PHONE not in str(result)
    assert log.call_count == 1  # the failure, logged by class name only
    for call in log.call_args_list:
        text = repr(call)
        assert PHONE not in text and PTV not in text


def test_patient_routes_are_never_cached():
    assert report_cache.cache_key("/hiv/eid/patients/by_facility/", {}) is None


def test_admin_probe_over_http(client, auth_headers, app):
    """/hiv/eid/patients/by_facility/?per_page=1: 200 for an admin, 403 otherwise, 400 only after the role."""
    ok = {"status": "success", "page": 1, "per_page": 1, "total_count": 0, "total_pages": 0, "data": []}
    with patch("hiv.eid.controllers.eid_controller_patients.get_patients_by_facility_service", return_value=ok):
        assert client.get(URL + "?per_page=1", headers=auth_headers).status_code == 200
    assert client.get(URL + "?per_page=1").status_code == 401
    with patch.object(patients, "_get_user_role", return_value=("u2", "Viewer")):
        assert client.get(URL + "?per_page=1&lab_type=bogus", headers=auth_headers).status_code == 403
    with patch.object(patients, "_get_user_role", return_value=("u1", "Admin")):
        assert client.get(URL + "?lab_type=bogus", headers=auth_headers).status_code == 400
    with patch.object(patients, "_get_user_role", return_value=("u1", "Admin")), patch.object(Query, "all", lambda self: []), patch.object(Query, "count", lambda self: 0):
        assert client.get(URL + "?per_page=1", headers=auth_headers).status_code == 200
