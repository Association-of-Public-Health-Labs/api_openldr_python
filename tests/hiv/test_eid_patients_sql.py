"""SQL-compilation tests for the EID patient searches."""
from unittest.mock import patch

import pytest
from sqlalchemy.dialects import mssql

from tests.hiv.sql_capture import service_sql
from hiv.eid.services import eid_services_patients as patients
from hiv.eid.services.eid_common import RESULT_VALUES

ARGS = {"interval_dates": ["2025-01-01,2025-12-31"]}


@pytest.fixture(autouse=True)
def admin():
    with patch.object(patients, "_get_user_role", return_value=("u1", "Admin")):
        yield


def run(app, service, extra=None):
    result, sqls = service_sql(app, service, {**ARGS, **(extra or {})})
    return result, sqls[-1]


def in_list(values):
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def test_selects_labelled_columns_ordered_by_request_id(app):
    _, sql = run(app, patients.get_patients_by_facility_service)
    select = sql
    for label in ("request_id", "caregiver_phone", "mother_ptv_id", "lab_type", "rejection_reason"):
        assert f"AS {label}" in select
    assert "[EIDMaster].[CaregiverMobileContact] AS caregiver_phone" in select
    assert "[EIDMaster].[PtvMother] AS mother_ptv_id" in select
    assert "[EIDMaster].[FinalResult] AS result" in select
    assert "ORDER BY [EIDMaster].[RequestID]" in sql


def test_window_is_registered_date_inclusive(app):
    _, sql = run(app, patients.get_patients_by_facility_service)
    assert ("CAST([EIDMaster].[RegisteredDateTime] AS DATE) >= '2025-01-01' AND "
            "CAST([EIDMaster].[RegisteredDateTime] AS DATE) <= '2025-12-31'") in sql


def test_facility_filters_are_bound(app):
    _, sql = run(app, patients.get_patients_by_facility_service, {
        "health_facility": "CS X", "province": ["Gaza"], "district": ["Chibuto"], "lab_code": ["PXM"],
    })
    assert "[EIDMaster].[RequestingFacilityName] = 'CS X'" in sql
    assert "[EIDMaster].[RequestingProvinceName] IN ('Gaza')" in sql
    assert "[EIDMaster].[RequestingDistrictName] IN ('Chibuto')" in sql
    assert "[EIDMaster].[TestingFacilityCode] IN ('PXM')" in sql


def test_facility_is_optional_for_the_admin_probe(app):
    result, sql = run(app, patients.get_patients_by_facility_service, {"per_page": 1})
    assert result["status"] == "success"
    assert "RequestingFacilityName] =" not in sql.split("WHERE", 1)[1]


@pytest.mark.parametrize("lab_type,marker", [("poc", "IsPoc] = 'Yes'"), ("conventional", "IsPoc] = 'No'")])
def test_lab_type_filter(app, lab_type, marker):
    _, sql = run(app, patients.get_patients_by_facility_service, {"lab_type": lab_type})
    assert marker in sql.split("WHERE", 1)[1]


def test_lab_type_all_adds_no_filter(app):
    _, sql = run(app, patients.get_patients_by_facility_service, {"lab_type": "all"})
    assert "IsPoc" not in sql.split("WHERE", 1)[1]


def test_lab_type_label_per_row(app):
    _, sql = run(app, patients.get_patients_by_facility_service)
    assert "THEN 'poc'" in sql and "THEN 'conventional'" in sql and "AS lab_type" in sql


@pytest.mark.parametrize("kind", ["positive", "negative", "indeterminate"])
def test_result_type_uses_final_result_values(app, kind):
    _, sql = run(app, patients.get_patients_by_result_type_service, {"result_type": [kind]})
    assert f"[EIDMaster].[FinalResult] IN {in_list(RESULT_VALUES[kind])}" in sql.split("WHERE", 1)[1]


def test_rejected_and_pending_use_the_shared_rules(app):
    _, sql = run(app, patients.get_patients_by_result_type_service, {"result_type": ["rejected"]})
    assert "LIMSRejectionCode" in sql.split("WHERE", 1)[1]
    _, sql = run(app, patients.get_patients_by_result_type_service, {"result_type": ["pending"]})
    assert "NOT (" in sql.split("WHERE", 1)[1] and "FinalResult] IS NULL" in sql


def test_multiple_result_types_are_ored(app):
    _, sql = run(app, patients.get_patients_by_result_type_service, {"result_type": ["positive,negative"]})
    where = sql.split("WHERE", 1)[1]
    assert " OR " in where and "'Positivo'" in where and "'Negativo'" in where


def test_name_is_a_bound_parameter(app):
    hostile = "x' OR 1=1 --"
    with app.app_context():
        # compile without literal rendering to prove the text is a bind, not SQL
        query = patients.EIDMaster.query.with_entities(*patients.EID_PATIENT_COLUMNS).filter(
            patients._FULL_NAME.icontains(hostile, autoescape=True))
        statement = str(query.statement.compile(dialect=mssql.dialect()))
    assert "OR 1=1" not in statement
    _, sql = run(app, patients.get_patients_by_name_service, {"name": hostile})
    assert "x'' OR 1=1 --" in sql  # quote doubled: stays inside the literal


def test_name_search_escapes_like_wildcards(app):
    _, sql = run(app, patients.get_patients_by_name_service, {"name": "50%_x"})
    assert "ESCAPE" in sql and "50/%/_x" in sql
