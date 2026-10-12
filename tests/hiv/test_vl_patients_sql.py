"""VL patient searches: filters, paging and record processing."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.hiv.sql_capture import service_sql
from hiv.vl.services import vl_services_patients as patients
from utilities.service_helpers import InvalidParameter
from utilities.utils import process_patients

ARGS = {"interval_dates": ["2025-01-01,2025-12-31"]}


@pytest.fixture(autouse=True)
def admin():
    with patch.object(patients, "_get_user_role", return_value=("u1", "Admin")):
        yield


def run(app, service, extra):
    result, [sql] = service_sql(app, service, {**ARGS, **extra})
    return result, sql


def test_by_facility_applies_drill_down_filters(app):
    result, sql = run(app, patients.get_patients_by_facility_service, {
        "health_facility": "CS X", "province": ["Gaza"], "district": ["Chibuto"],
        "lab_code": ["PXM"], "age_range": ["15,49"], "pregnant": "true",
        "rejected": "1", "result_type": ["not_suppressed"],
    })
    assert result["status"] == "success"
    # rejected=1 switches to the rejection cards' inclusive registration window
    assert "CAST([VlData].[RegisteredDateTime] AS DATE) >= '2025-01-01'" in sql
    assert "[VlData].[RequestingFacilityName] = 'CS X'" in sql
    assert "[VlData].[RequestingProvinceName] IN ('Gaza')" in sql
    assert "[VlData].[RequestingDistrictName] IN ('Chibuto')" in sql
    assert "[VlData].[TestingFacilityCode] IN ('PXM')" in sql
    assert "[VlData].[AgeInYears] BETWEEN 15 AND 49" in sql
    assert "[VlData].[Pregnant] IN ('YES', 'Yes', 'yes', 'Sim', 'SIM', 'sim')" in sql
    assert "[VlData].[HIVVL_LIMSRejectionCode] IS NOT NULL" in sql
    assert "[VlData].[ViralLoadResultCategory] IN ('Not Suppressed')" in sql
    assert "ORDER BY [VlData].[RequestID]" in sql


def test_false_flags_add_no_filter(app):
    _, sql = run(app, patients.get_patients_by_facility_service, {
        "health_facility": "CS X", "pregnant": "false", "breastfeeding": "0", "rejected": "no",
    })
    assert "Pregnant" not in sql.split("WHERE", 1)[1]
    assert "BreastFeeding" not in sql.split("WHERE", 1)[1]
    assert "LIMSRejectionCode" not in sql.split("WHERE", 1)[1]


def test_per_page_is_capped_at_500(app):
    result, _ = run(app, patients.get_patients_by_name_service, {"first_name": "Ana", "per_page": 5000})
    assert result["per_page"] == 500


@pytest.mark.parametrize("extra", [{"page": 0}, {"per_page": 0}, {"page": "x"}])
def test_bad_paging_is_a_400(app, extra):
    with pytest.raises(InvalidParameter):
        service_sql(app, patients.get_patients_by_name_service, {**ARGS, "first_name": "Ana", **extra})


def test_test_reason_list_is_mapped(app):
    _, sql = run(app, patients.get_patients_by_test_reason_service,
                 {"test_reason": ["Routine", "Repeat", "Suspected treatment failure"]})
    assert ("[VlData].[ReasonForTest] IN ('Routine', 'Repeat after breastfeeding', 'Repeat', "
            "'Suspected treatment failure', 'Suspeita de falha terapêutica')") in sql


def test_unknown_test_reason_is_a_400(app):
    with pytest.raises(InvalidParameter):
        service_sql(app, patients.get_patients_by_test_reason_service, {**ARGS, "test_reason": ["Bogus"]})


def test_result_type_endpoint_uses_analysis_date(app):
    _, sql = run(app, patients.get_patients_by_result_type_service, {"result_type": ["suppressed"]})
    assert "[VlData].[AnalysisDateTime] BETWEEN '2025-01-01' AND '2025-12-31'" in sql
    assert "[VlData].[ViralLoadResultCategory] IN ('Suppressed')" in sql


def test_unknown_result_type_is_a_400(app):
    with pytest.raises(InvalidParameter):
        service_sql(app, patients.get_patients_by_result_type_service, {**ARGS, "result_type": ["maybe"]})


def test_non_admin_is_refused(app):
    with patch.object(patients, "_get_user_role", return_value=("u2", "Viewer")):
        result, sql = service_sql(app, patients.get_patients_by_facility_service,
                                  {**ARGS, "health_facility": "CS X"})
    assert result["code"] == 403 and sql == []


def vl_row(**values):
    row = {column.key: None for column in patients.VL_PATIENT_ENTITIES}
    row.update(values)
    return SimpleNamespace(**row)


def test_process_vl_patient_handles_nulls():
    [record] = process_patients([vl_row(RequestID="R1")], ["2025-01-01", "2025-12-31"],
                                "province", None, "vl", None, None)
    assert record["reason_for_test"] == "Reason Not Specified"
    assert record["nid"] is None and record["phone"] is None and record["final_result"] is None


def test_process_vl_patient_picks_first_non_empty_values():
    row = vl_row(
        RequestID="R2", HealthcareNo=" ", REFNO=None, NATIONALID="NID-9", UNIQUEID="U1",
        TELHOME="", TELWORK=None, MOBILE="84 000 0000",
        FinalViralLoadResult=None, HIVVL_ViralLoadResult="", HIVVL_ViralLoadCAPCTM="<20",
        ReasonForTest="Suspeita de falha terapêutica",
    )
    [record] = process_patients([row], ["2025-01-01", "2025-12-31"], "province", None, "vl", None, None)
    assert record["nid"] == "NID-9"
    assert record["phone"] == "84 000 0000"
    assert record["final_result"] == "<20"
    assert record["reason_for_test"] == "Suspected treatment failure"


def test_date_basis_analysis_windows_on_analysis_date(app):
    _, sql = run(app, patients.get_patients_by_facility_service,
                 {"health_facility": "CS X", "date_basis": "analysis"})
    assert "[VlData].[AnalysisDateTime] BETWEEN '2025-01-01' AND '2025-12-31'" in sql
    assert "RegisteredDateTime] BETWEEN" not in sql


def test_rejected_uses_inclusive_registration_window(app):
    _, sql = run(app, patients.get_patients_by_facility_service,
                 {"health_facility": "CS X", "rejected": "true", "date_basis": "analysis"})
    assert "CAST([VlData].[RegisteredDateTime] AS DATE) >=" in sql
    assert "AnalysisDateTime] BETWEEN" not in sql


def test_bogus_date_basis_is_a_400(app):
    with pytest.raises(InvalidParameter):
        service_sql(app, patients.get_patients_by_facility_service,
                    {**ARGS, "health_facility": "CS X", "date_basis": "bogus"})


def test_registration_basis_keeps_endpoint_default(app):
    _, sql = run(app, patients.get_patients_by_result_type_service,
                 {"result_type": ["suppressed"], "date_basis": "registration"})
    assert "[VlData].[AnalysisDateTime] BETWEEN" in sql


def test_reason_not_specified_includes_null_reasons(app):
    _, sql = run(app, patients.get_patients_by_test_reason_service,
                 {"test_reason": ["Reason Not Specified"]})
    assert "[VlData].[ReasonForTest] IS NULL" in sql
    assert "[VlData].[ReasonForTest] IN ('Não preenchido'" in sql


def test_name_search_escapes_like_wildcards(app):
    _, sql = run(app, patients.get_patients_by_name_service, {"first_name": "50%_x"})
    assert "ESCAPE" in sql
    assert "50/%/_x" in sql
