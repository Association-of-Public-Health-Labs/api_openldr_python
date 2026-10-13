"""SQL-compilation tests for the VL laboratory services."""
from types import SimpleNamespace

from tests.hiv.sql_capture import captured_queries, service_sql, to_sql
from hiv.vl.services import vl_services_laboratory as lab

ARGS = {"interval_dates": ["2025-01-01,2025-12-31"]}
P_DEFAULT = "[VlData].[TestingFacilityCode] LIKE 'P%'"
TAT_RULE = (
    "[VlData].[ViralLoadResultCategory] NOT LIKE '' AND "
    "datediff(day, [VlData].[SpecimenDatetime], [VlData].[ReceivedDateTime]) >= 0"
)
OR_RULE = "[VlData].[LIMSRejectionCode] != '' OR [VlData].[HIVVL_LIMSRejectionCode] IS NOT NULL"
INCLUSIVE = (
    "CAST([VlData].[RegisteredDateTime] AS DATE) >= '2025-01-01' AND "
    "CAST([VlData].[RegisteredDateTime] AS DATE) <= '2025-12-31'"
)


def test_tested_samples_defaults_to_conventional_labs(app):
    _, [sql] = service_sql(app, lab.tested_samples_service, ARGS)
    assert P_DEFAULT in sql
    assert "[VlData].[AnalysisDateTime] BETWEEN '2025-01-01' AND '2025-12-31'" in sql
    assert "[VlData].[TestingFacilityName] IS NOT NULL" in sql
    assert "GROUP BY [VlData].[TestingFacilityName]" in sql


def test_tested_samples_lab_code_replaces_default(app):
    _, [sql] = service_sql(app, lab.tested_samples_service, {**ARGS, "lab_code": ["PCD,PDD"]})
    assert "[VlData].[TestingFacilityCode] IN ('PCD', 'PDD')" in sql
    assert "LIKE 'P%'" not in sql


def test_tested_samples_location_replaces_default(app):
    _, [sql] = service_sql(app, lab.tested_samples_service, {**ARGS, "province": ["Gaza"]})
    assert "[VlData].[TestingProvinceName] IN ('Gaza')" in sql
    assert "LIKE 'P%'" not in sql


def test_tested_samples_lab_code_and_location_together(app):
    _, [sql] = service_sql(
        app, lab.tested_samples_service, {**ARGS, "province": ["Gaza"], "lab_code": ["PXM"]}
    )
    assert "[VlData].[TestingProvinceName] IN ('Gaza')" in sql
    assert "[VlData].[TestingFacilityCode] IN ('PXM')" in sql
    assert "LIKE 'P%'" not in sql


def test_tested_samples_by_month_has_no_conventional_default(app):
    _, [sql] = service_sql(app, lab.tested_samples_by_month_service, ARGS)
    assert "LIKE 'P%'" not in sql
    assert "GROUP BY year([VlData].[AnalysisDateTime])" in sql


def test_tat_by_lab_applies_tat_rule_and_default(app):
    _, [sql] = service_sql(app, lab.tat_by_lab_service, ARGS)
    assert TAT_RULE in sql and P_DEFAULT in sql
    assert "< 90" not in sql
    assert "GROUP BY [VlData].[TestingFacilityName]" in sql


def test_tat_by_month_applies_tat_rule_and_default(app):
    _, [sql] = service_sql(app, lab.tat_by_month_service, ARGS)
    assert TAT_RULE in sql and P_DEFAULT in sql


def test_rejected_samples_groups_by_requestid_lab_code(app):
    _, [sql] = service_sql(app, lab.rejected_samples_service, {**ARGS, "lab_code": ["PCD"]})
    assert OR_RULE in sql
    assert INCLUSIVE in sql
    assert "substring([VlData].[RequestID], 7, 3) IN ('PCD')" in sql
    assert "GROUP BY substring([VlData].[RequestID], 7, 3)" in sql
    assert "LIKE 'P%'" not in sql


def test_rejected_samples_by_month_groups_by_registration_month(app):
    _, [sql] = service_sql(app, lab.rejected_samples_by_month_service, ARGS)
    assert OR_RULE in sql and INCLUSIVE in sql
    assert "GROUP BY year([VlData].[RegisteredDateTime])" in sql
    assert "LIKE 'P%'" not in sql


def test_rejected_samples_merges_dictionary_names(app):
    vl_rows = [
        SimpleNamespace(lab_code="PDD", total=2),
        SimpleNamespace(lab_code="PCD", total=3),
        SimpleNamespace(lab_code="ZZZ", total=1),
    ]
    dict_rows = [
        SimpleNamespace(LabCode="PCD ", LabName="Cabo Delgado"),
        SimpleNamespace(LabCode="PDD", LabName=" Cabo Delgado "),
    ]
    result, sql = service_sql(app, lab.rejected_samples_service, ARGS, results=[vl_rows, dict_rows])
    assert result == [
        {"lab_code": "PCD", "testing_facility": "Cabo Delgado", "total": 3},
        {"lab_code": "PDD", "testing_facility": "Cabo Delgado", "total": 2},
    ]
    assert "[Laboratories].[LabCode] IN ('PCD', 'PDD', 'ZZZ')" in sql[1]
    assert "[Laboratories].[LabName] != ''" in sql[1]


def test_lab_names_skips_the_query_for_no_codes(app):
    with app.app_context(), captured_queries() as queries:
        assert lab.lab_names([]) == {}
    assert queries == []


def test_lab_endpoints_no_longer_require_admin(app):
    args = {**ARGS, "facility_type": "health_facility", "health_facility": "Lab X"}
    result, _ = service_sql(app, lab.tested_samples_service, args)
    assert result == []
