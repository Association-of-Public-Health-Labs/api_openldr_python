"""SQL-compilation tests for the EID summary (Sumário) services.

Each service reproduces the rule of the legacy openldr-api DashboardController
route it replaces (spec Appendix A); only the spec's ✱ fixes differ.
"""
import pytest

from tests.hiv.sql_capture import service_sql
from hiv.eid.services import eid_services_summary as summary

ARGS = {"interval_dates": ["2025-01-01,2025-12-31"]}


def window(column):
    """✱5: the inclusive date window on ``column``."""
    return (
        f"CAST([EIDMaster].[{column}] AS DATE) >= '2025-01-01' AND "
        f"CAST([EIDMaster].[{column}] AS DATE) <= '2025-12-31'"
    )


def monthly_group(column):
    return (
        f"GROUP BY year([EIDMaster].[{column}]), month([EIDMaster].[{column}]), "
        f"datename(month, [EIDMaster].[{column}])"
    )


CONVENTIONAL = "ltrim(rtrim([EIDMaster].[LIMSAnalyzerCode])) NOT IN ('MPIMA', 'PIMA')"
POC = (
    "[EIDMaster].[IsPoc] = 'Yes' OR "
    "ltrim(rtrim([EIDMaster].[LIMSAnalyzerCode])) IN ('MPIMA', 'PIMA')"
)
POSITIVE = "[EIDMaster].[FinalResult] IN ('Positivo', 'Reactive', 'DTS')"
REJECTED = "ltrim(rtrim([EIDMaster].[LIMSRejectionDesc])) != ''"
FINAL_STATUS = "[EIDMaster].[HL7ResultStatusCode] = 'F'"


def assert_no_legacy_results(sql):
    """✱7: results come from FinalResult only."""
    assert "PCR_Result" not in sql and "POC_Result" not in sql


# --- summary/indicators/ (dash/pcr/indicators + dash/poc/indicators) ---------
def test_indicators_monthly_on_registered_date(app):
    _, [sql] = service_sql(app, summary.summary_indicators_service, ARGS)
    assert window("RegisteredDateTime") in sql
    assert monthly_group("RegisteredDateTime") in sql
    assert "AnalysisDateTime] AS DATE" not in sql
    for label in ("registered", "tested", "rejected", "pending"):
        assert f"AS {label}" in sql
    assert REJECTED in sql
    assert "[EIDMaster].[FinalResult] IN ('NDT', 'Nível de detecção baixo')" in sql
    assert "RequestID" not in sql  # ✱6
    assert_no_legacy_results(sql)


def test_indicators_by_lab_type_poc(app):
    _, [sql] = service_sql(app, summary.summary_indicators_service, {**ARGS, "lab_type": "poc"})
    assert POC in sql


def test_indicators_by_lab_type_conventional(app):
    _, [sql] = service_sql(
        app, summary.summary_indicators_service, {**ARGS, "lab_type": "conventional"}
    )
    assert "[EIDMaster].[IsPoc] = 'No'" in sql and CONVENTIONAL in sql


def test_indicators_all_has_no_lab_type_condition(app):
    _, [sql] = service_sql(app, summary.summary_indicators_service, ARGS)
    assert "IsPoc" not in sql


def test_indicators_rows_shape(app):
    row = type("Row", (), dict(year=2025, month=1, month_name="January", registered=10,
                               tested=8, rejected=1, pending=1))()
    result, _ = service_sql(app, summary.summary_indicators_service, ARGS, results=[[row]])
    assert result == [dict(year=2025, month=1, month_name="January", registered=10,
                           tested=8, rejected=1, pending=1)]


def test_location_and_lab_code_filters(app):
    _, [sql] = service_sql(
        app,
        summary.summary_indicators_service,
        {**ARGS, "province": ["Gaza"], "lab_code": ["PJV", "PMB"]},
    )
    assert "[EIDMaster].[RequestingProvinceName] IN ('Gaza')" in sql
    assert "[EIDMaster].[TestingFacilityCode] IN ('PJV', 'PMB')" in sql


def test_summary_routes_have_no_null_province_exclusion(app):
    """The legacy dash routes had no location filter at all."""
    _, [sql] = service_sql(app, summary.summary_indicators_service, ARGS)
    assert "RequestingProvinceName" not in sql


# --- summary/positivity/ (dash/samples_positivity) ---------------------------
def test_positivity_monthly_on_analysis_date(app):
    _, [sql] = service_sql(app, summary.summary_positivity_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert monthly_group("AnalysisDateTime") in sql
    assert FINAL_STATUS in sql
    for label in ("tested", "positive", "negative", "indeterminate",
                  "conventional_positive", "poc_positive"):
        assert f"AS {label}" in sql
    assert POSITIVE in sql
    assert CONVENTIONAL in sql and POC in sql
    assert_no_legacy_results(sql)


def test_positivity_is_positive_over_tested(app):
    """✱3: the line is positive ÷ tested (percent, 1 decimal)."""
    row = type("Row", (), dict(year=2025, month=1, month_name="January", tested=200,
                               positive=9, negative=190, indeterminate=1,
                               conventional_positive=6, poc_positive=3))()
    result, _ = service_sql(app, summary.summary_positivity_service, ARGS, results=[[row]])
    assert result == [dict(year=2025, month=1, month_name="January", tested=200,
                           positive=9, negative=190, indeterminate=1,
                           conventional_positive=6, poc_positive=3, positivity=4.5)]


def test_positivity_is_zero_when_no_tested(app):
    result, _ = service_sql(app, summary.summary_positivity_service, ARGS, results=[[]])
    assert result == []
    row = type("Row", (), dict(year=2025, month=1, month_name="January", tested=0,
                               positive=0, negative=0, indeterminate=0,
                               conventional_positive=0, poc_positive=0))()
    result, _ = service_sql(app, summary.summary_positivity_service, ARGS, results=[[row]])
    assert result[0]["positivity"] == 0


# --- summary/indicators_by_province/ (dash/indicators_by_province) ----------
def test_indicators_by_province_on_registered_date(app):
    _, [sql] = service_sql(app, summary.summary_indicators_by_province_service, ARGS)
    assert window("RegisteredDateTime") in sql
    assert "[EIDMaster].[RequestingProvinceName] IS NOT NULL" in sql
    assert "GROUP BY [EIDMaster].[RequestingProvinceName]" in sql
    for label in ("registered", "tested", "rejected", "pending", "conventional", "poc", "positive"):
        assert f"AS {label}" in sql
    # Legacy split on this route: IsPoc only.
    assert "CASE WHEN ([EIDMaster].[IsPoc] = 'No') THEN 1 END) AS conventional" in sql
    assert "CASE WHEN ([EIDMaster].[IsPoc] = 'Yes') THEN 1 END) AS poc" in sql
    assert POSITIVE in sql
    assert_no_legacy_results(sql)


def test_indicators_by_province_rows_shape(app):
    row = type("Row", (), dict(province="Gaza", registered=100, tested=80, rejected=2,
                               pending=18, conventional=70, poc=30, positive=4))()
    result, _ = service_sql(
        app, summary.summary_indicators_by_province_service, ARGS, results=[[row]]
    )
    assert result == [dict(province="Gaza", registered=100, tested=80, rejected=2,
                           pending=18, conventional=70, poc=30, positive=4, positivity=5.0)]


# --- summary/tat/ (dash/pcr/tat) ---------------------------------------------
def test_tat_monthly_on_analysis_date_with_summary_filters(app):
    _, [sql] = service_sql(app, summary.summary_tat_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert monthly_group("AnalysisDateTime") in sql
    assert "[EIDMaster].[IsPoc] = 'No'" in sql
    assert "[EIDMaster].[LIMSPreReg_ReceivedDateTime] < [EIDMaster].[RegisteredDateTime]" in sql
    for key in ("collection_hub_reception", "hub_reception_hub_registration",
                "hub_registration_lab_reception", "lab_reception_lab_registration",
                "lab_registration_analysis", "analysis_validation"):
        assert f"AS {key}" in sql
    assert "PBC" not in sql
    assert "CASE WHEN (avg(" not in sql  # no zero-as-one on the dashboard


# --- summary/tat_samples/ (dash/pcr/tat_samples) -----------------------------
def test_tat_samples_monthly_brackets(app):
    _, [sql] = service_sql(app, summary.summary_tat_samples_service, {**ARGS, "category": "2"})
    assert window("AnalysisDateTime") in sql
    assert monthly_group("AnalysisDateTime") in sql
    assert "[EIDMaster].[IsPoc] = 'No'" in sql
    assert "[EIDMaster].[LIMSPreReg_ReceivedDateTime] < [EIDMaster].[RegisteredDateTime]" not in sql
    days = "datediff(day, [EIDMaster].[LIMSPreReg_RegistrationDateTime], [EIDMaster].[ReceivedDateTime])"
    assert f"{days} < 7" in sql
    for label in ("lt_7", "between_7_15", "between_16_21", "gt_21", "no_dates"):
        assert f"AS {label}" in sql


@pytest.mark.parametrize(
    "category, start, end",
    [("0", "SpecimenDatetime", "LIMSPreReg_ReceivedDateTime"),
     ("5", "AnalysisDateTime", "AuthorisedDateTime")],
)
def test_tat_samples_category_scale_is_zero_to_five(app, category, start, end):
    _, [sql] = service_sql(app, summary.summary_tat_samples_service, {**ARGS, "category": category})
    assert f"datediff(day, [EIDMaster].[{start}], [EIDMaster].[{end}]) < 7" in sql


def test_tat_samples_rows_shape(app):
    row = type("Row", (), dict(year=2025, month=3, month_name="March", lt_7=5,
                               between_7_15=4, between_16_21=3, gt_21=2, no_dates=1))()
    result, _ = service_sql(
        app, summary.summary_tat_samples_service, {**ARGS, "category": "0"}, results=[[row]]
    )
    assert result == [dict(year=2025, month=3, month_name="March",
                           category="collection_hub_reception", lt_7=5, between_7_15=4,
                           between_16_21=3, gt_21=2, no_dates=1)]


# --- summary/rejected_samples_by_month/ (dash/rejected_samples_monthly) ------
def test_rejected_by_month_on_registered_date(app):
    _, [sql] = service_sql(app, summary.summary_rejected_samples_by_month_service, ARGS)
    assert window("RegisteredDateTime") in sql
    assert monthly_group("RegisteredDateTime") in sql
    assert "[EIDMaster].[IsPoc] = 'No'" in sql
    assert REJECTED in sql
    for key in ("repeat_test", "insufficient_sample", "request_without_sample",
                "technical_problems", "overlapping_blood", "duplicate_registration",
                "misidentified_sample", "sample_over_30_days", "other", "total"):
        assert f"AS {key}" in sql
    # default variant: REJOL and PRTLA are `other`
    assert "REJOL" not in sql and "PRTLA" not in sql


# --- summary/samples_by_equipment_by_month/ (dash/samples_by_equipment_monthly)
def test_equipment_by_month_on_analysis_date(app):
    _, [sql] = service_sql(app, summary.summary_samples_by_equipment_by_month_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert monthly_group("AnalysisDateTime") in sql
    assert FINAL_STATUS in sql and "[EIDMaster].[IsPoc] = 'No'" in sql
    assert "PBC" not in sql  # legacy: no PBC exclusion on the dashboard
    assert "AS tested" in sql
    for key in ("CAPCTM", "ALINITY", "M2000", "C6800", "PANTHER", "MPIMA", "MANUAL"):
        assert f"AS [{key}]" in sql


# --- routes no card uses -----------------------------------------------------
def test_equipment_by_lab(app):
    _, [sql] = service_sql(app, summary.summary_samples_by_equipment_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert "GROUP BY [EIDMaster].[TestingFacilityName]" in sql
    assert FINAL_STATUS in sql and "PBC" not in sql


def test_number_of_samples(app):
    """Legacy dash/pcr/number_of_samples: AnalysisDateTime window, registration month."""
    _, [sql] = service_sql(app, summary.summary_number_of_samples_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert monthly_group("RegisteredDateTime") in sql
    assert CONVENTIONAL in sql and POC in sql
    assert "RequestID" not in sql


def test_samples_positivity_single_row(app):
    _, [sql] = service_sql(app, summary.summary_samples_positivity_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert FINAL_STATUS in sql
    assert "[EIDMaster].[HL7SexCode] = 'F'" in sql
    assert "GROUP BY" not in sql
    assert_no_legacy_results(sql)


@pytest.mark.parametrize(
    "name",
    [n for n in dir(summary) if n.startswith("summary_") and n.endswith("_service")],
)
def test_every_service_reads_only_final_result(app, name):
    _, sqls = service_sql(app, getattr(summary, name), ARGS)
    assert sqls
    for sql in sqls:
        assert_no_legacy_results(sql)
        assert "BETWEEN '2025-01-01' AND '2025-12-31'" not in sql  # ✱5
