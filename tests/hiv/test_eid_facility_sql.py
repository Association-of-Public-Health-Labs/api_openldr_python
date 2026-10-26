"""SQL-compilation tests for the EID Província/Distrito/US services.

Each service reproduces the rule of the legacy openldr-api ClinicController
route it replaces (spec Appendix A, "Província/Distrito/US"); only the spec's
✱ fixes differ (✱1 key_indicators per lab type, ✱5 inclusive end date, ✱7
FinalResult).
"""
import re

import pytest

from tests.hiv.sql_capture import service_sql
from hiv.eid.services import eid_services_facilities as fac

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


def row(**fields):
    return type("Row", (), fields)()


POSITIVE = "[EIDMaster].[FinalResult] IN ('Positivo', 'Reactive', 'DTS')"
NEGATIVE = "[EIDMaster].[FinalResult] IN ('Negativo', 'Not Reactive', 'Not Detected DBS', 'NDET')"
NULL_PROVINCE = "[EIDMaster].[RequestingProvinceName] != 'null'"
REQUESTING_NOT_NULL = [
    "[EIDMaster].[RequestingProvinceName] IS NOT NULL",
    "[EIDMaster].[RequestingDistrictName] IS NOT NULL",
    "[EIDMaster].[RequestingFacilityName] IS NOT NULL",
]
REASONS = ("repeat_test", "insufficient_sample", "request_without_sample",
           "technical_problems", "overlapping_blood", "duplicate_registration",
           "misidentified_sample", "sample_over_30_days", "other")
TAT_KEYS = ("collection_hub_reception", "hub_reception_hub_registration",
            "hub_registration_lab_reception", "lab_reception_lab_registration",
            "lab_registration_analysis", "analysis_validation")
BRACKETS = ("lt_7", "between_7_15", "between_16_21", "gt_21", "no_dates")
GENDER = ("male_positive", "male_negative", "female_positive", "female_negative")

BY_LEVEL = [
    fac.facility_registered_samples_service,
    fac.facility_tested_samples_service,
    fac.facility_rejected_samples_service,
    fac.facility_tested_samples_by_gender_service,
    fac.facility_tat_avg_service,
    fac.facility_tat_days_service,
    fac.facility_key_indicators_service,
]
MONTHLY = [
    fac.facility_registered_samples_by_month_service,
    fac.facility_tested_samples_by_month_service,
    fac.facility_rejected_samples_by_month_service,
    fac.facility_tested_samples_by_gender_by_month_service,
    fac.facility_tat_avg_by_month_service,
    fac.facility_tat_days_by_month_service,
]
CARD_SERVICES = BY_LEVEL + MONTHLY


def ids(service):
    return service.__name__


def assert_no_legacy_results(sql):
    """✱7: results come from FinalResult only."""
    assert "PCR_Result" not in sql and "POC_Result" not in sql


# --- every card route ---------------------------------------------------------
@pytest.mark.parametrize("service", CARD_SERVICES, ids=ids)
def test_every_card_service_on_the_new_rules(app, service):
    _, sqls = service_sql(app, service, ARGS)
    assert sqls
    for sql in sqls:
        assert_no_legacy_results(sql)
        assert not re.search(r"\[Result[A-Z]", sql)  # un-prefixed columns only
        assert "BETWEEN '2025-01-01' AND '2025-12-31'" not in sql  # ✱5


@pytest.mark.parametrize("service", CARD_SERVICES, ids=ids)
def test_every_card_service_drops_null_requesting_names(app, service):
    """Legacy Clinic routes: all three Requesting* names non-NULL; with no
    location given, a NULL or 'null' province is excluded too."""
    _, [sql] = service_sql(app, service, ARGS)
    for clause in REQUESTING_NOT_NULL:
        assert clause in sql
    assert NULL_PROVINCE in sql


@pytest.mark.parametrize("service", CARD_SERVICES, ids=ids)
def test_location_filter_replaces_null_province_line(app, service):
    _, [sql] = service_sql(app, service, {**ARGS, "province": ["Gaza"]})
    assert "[EIDMaster].[RequestingProvinceName] IN ('Gaza')" in sql
    assert NULL_PROVINCE not in sql


@pytest.mark.parametrize("service", CARD_SERVICES, ids=ids)
def test_every_card_service_rejects_bad_lab_type(app, service):
    from utilities.service_helpers import InvalidParameter

    with pytest.raises(InvalidParameter):
        service_sql(app, service, {**ARGS, "lab_type": "pcr"})


@pytest.mark.parametrize("service", CARD_SERVICES, ids=ids)
def test_lab_code_filters_testing_facility(app, service):
    _, [sql] = service_sql(app, service, {**ARGS, "lab_code": ["PJV", "PMB"]})
    assert "[EIDMaster].[TestingFacilityCode] IN ('PJV', 'PMB')" in sql


# --- drill levels (R19: group_column(params, "requesting")) -------------------
@pytest.mark.parametrize("service", BY_LEVEL, ids=ids)
@pytest.mark.parametrize(
    "extra, group",
    [
        ({}, "RequestingProvinceName"),
        ({"disaggregation": "true"}, "RequestingDistrictName"),  # nationwide districts
        ({"facility_type": "province", "province": ["Gaza"], "disaggregation": "True"},
         "RequestingDistrictName"),
        ({"facility_type": "district", "district": ["Chokwe"]}, "RequestingDistrictName"),
        ({"facility_type": "district", "district": ["Chokwe"], "disaggregation": "true"},
         "RequestingFacilityName"),
        ({"facility_type": "health_facility", "health_facility": "CS Chokwe"},
         "RequestingFacilityName"),
    ],
)
def test_by_level_groups_by_requesting_level(app, service, extra, group):
    _, [sql] = service_sql(app, service, {**ARGS, **extra})
    assert f"[EIDMaster].[{group}] AS requesting_facility" in sql
    assert f"GROUP BY [EIDMaster].[{group}]" in sql


def test_disaggregation_without_province_is_nationwide(app):
    _, [sql] = service_sql(app, fac.facility_tested_samples_service,
                           {**ARGS, "disaggregation": "true"})
    assert "GROUP BY [EIDMaster].[RequestingDistrictName]" in sql
    assert "RequestingProvinceName] IN" not in sql


def test_district_drill_filters_district(app):
    _, [sql] = service_sql(
        app, fac.facility_tested_samples_service,
        {**ARGS, "facility_type": "district", "district": ["Chokwe"], "disaggregation": "true"},
    )
    assert "[EIDMaster].[RequestingDistrictName] IN ('Chokwe')" in sql


@pytest.mark.parametrize("service", MONTHLY, ids=ids)
def test_monthly_routes_have_no_level_column(app, service):
    _, [sql] = service_sql(app, service, ARGS)
    assert "AS requesting_facility" not in sql


# --- registered_samples / _by_month (clinic/samples_registered_*) -------------
@pytest.mark.parametrize(
    "service",
    [fac.facility_registered_samples_service, fac.facility_registered_samples_by_month_service],
    ids=ids,
)
def test_registered_on_registered_date_ispoc_split(app, service):
    _, [sql] = service_sql(app, service, ARGS)
    assert window("RegisteredDateTime") in sql
    assert "CASE WHEN ([EIDMaster].[IsPoc] = 'No') THEN 1 END) AS conventional" in sql
    assert "CASE WHEN ([EIDMaster].[IsPoc] = 'Yes') THEN 1 END) AS poc" in sql
    assert "AS total" in sql
    assert "AnalysisDateTime" not in sql


def test_registered_by_month_groups_by_registration_month(app):
    _, [sql] = service_sql(app, fac.facility_registered_samples_by_month_service, ARGS)
    assert monthly_group("RegisteredDateTime") in sql


def test_registered_rows_shape(app):
    data = row(requesting_facility="Gaza", conventional=7, poc=3, total=10)
    result, _ = service_sql(app, fac.facility_registered_samples_service, ARGS, results=[[data]])
    assert result == [dict(requesting_facility="Gaza", conventional=7, poc=3, total=10)]


def test_registered_by_month_rows_shape(app):
    data = row(year=2025, month=1, month_name="January", conventional=7, poc=3, total=10)
    result, _ = service_sql(app, fac.facility_registered_samples_by_month_service, ARGS,
                            results=[[data]])
    assert result == [dict(year=2025, month=1, month_name="January", conventional=7, poc=3,
                           total=10)]


# --- tested_samples / _by_month (clinic/samples_tested_*) ---------------------
@pytest.mark.parametrize(
    "service",
    [fac.facility_tested_samples_service, fac.facility_tested_samples_by_month_service],
    ids=ids,
)
def test_tested_on_analysis_date_with_results(app, service):
    _, [sql] = service_sql(app, service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert "CASE WHEN ([EIDMaster].[IsPoc] = 'No') THEN 1 END) AS conventional" in sql
    assert "CASE WHEN ([EIDMaster].[IsPoc] = 'Yes') THEN 1 END) AS poc" in sql
    assert POSITIVE in sql and NEGATIVE in sql
    for label in ("total", "positive", "negative"):
        assert f"AS {label}" in sql
    assert "LIMSRejectionCode" not in sql  # legacy did not drop rejected rows


@pytest.mark.parametrize(
    "service",
    [fac.facility_tested_samples_service, fac.facility_tested_samples_by_month_service],
    ids=ids,
)
@pytest.mark.parametrize("lab_type, value", [("conventional", "No"), ("poc", "Yes")])
def test_tested_lab_type_is_ispoc(app, service, lab_type, value):
    _, [sql] = service_sql(app, service, {**ARGS, "lab_type": lab_type})
    where = sql.split(" WHERE ")[1]
    assert f"[EIDMaster].[IsPoc] = '{value}'" in where
    assert "LIMSAnalyzerCode" not in sql


def test_tested_by_month_groups_by_analysis_month(app):
    _, [sql] = service_sql(app, fac.facility_tested_samples_by_month_service, ARGS)
    assert monthly_group("AnalysisDateTime") in sql


def test_tested_rows_shape(app):
    data = row(requesting_facility="Gaza", conventional=7, poc=3, total=10, positive=1,
               negative=8)
    result, _ = service_sql(app, fac.facility_tested_samples_service, ARGS, results=[[data]])
    assert result == [dict(requesting_facility="Gaza", conventional=7, poc=3, total=10,
                           positive=1, negative=8)]


def test_tested_by_month_rows_shape(app):
    data = row(year=2025, month=3, month_name="March", conventional=7, poc=3, total=10,
               positive=1, negative=8)
    result, _ = service_sql(app, fac.facility_tested_samples_by_month_service, ARGS,
                            results=[[data]])
    assert result == [dict(year=2025, month=3, month_name="March", conventional=7, poc=3,
                           total=10, positive=1, negative=8)]


# --- rejected_samples / _by_month (clinic/samples_rejected_*) -----------------
@pytest.mark.parametrize(
    "service",
    [fac.facility_rejected_samples_service, fac.facility_rejected_samples_by_month_service],
    ids=ids,
)
def test_rejected_legacy_filters(app, service):
    """Legacy: AnalysisDateTime window, IsPoc 'No', LIMSRejectionCode <> ''."""
    _, [sql] = service_sql(app, service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert "[EIDMaster].[IsPoc] = 'No'" in sql
    assert "[EIDMaster].[LIMSRejectionCode] != ''" in sql
    assert "RegisteredDateTime" not in sql
    for key in REASONS + ("total",):
        assert f"AS {key}" in sql


def test_rejected_by_level_uses_default_reasons(app):
    _, [sql] = service_sql(app, fac.facility_rejected_samples_service, ARGS)
    assert "IN ('REPIT', 'SPUN2')" in sql
    assert "IN ('ERRTC', 'ACC', 'PROBT')" in sql
    assert "REJOL" not in sql and "PRTLA" not in sql  # both count as `other`


def test_rejected_by_month_uses_facility_reasons(app):
    _, [sql] = service_sql(app, fac.facility_rejected_samples_by_month_service, ARGS)
    assert "IN ('REPIT', 'SPUN2', 'REJOL')" in sql
    assert "IN ('ERRTC', 'ACC', 'PROBT', 'PRTLA')" in sql
    assert monthly_group("AnalysisDateTime") in sql


def test_rejected_rows_shape(app):
    reasons = dict(zip(REASONS, range(1, 10)))
    data = row(requesting_facility="Gaza", total=45, **reasons)
    result, _ = service_sql(app, fac.facility_rejected_samples_service, ARGS, results=[[data]])
    assert result == [dict(requesting_facility="Gaza", **reasons, total=45)]


def test_rejected_by_month_rows_shape(app):
    reasons = dict(zip(REASONS, range(1, 10)))
    data = row(year=2025, month=1, month_name="January", total=45, **reasons)
    result, _ = service_sql(app, fac.facility_rejected_samples_by_month_service, ARGS,
                            results=[[data]])
    assert result == [dict(year=2025, month=1, month_name="January", **reasons, total=45)]


# --- tested_samples_by_gender / _by_month (clinic/samples_tested_gender_*) -----
@pytest.mark.parametrize(
    "service",
    [fac.facility_tested_samples_by_gender_service,
     fac.facility_tested_samples_by_gender_by_month_service],
    ids=ids,
)
def test_gender_results_by_sex(app, service):
    _, [sql] = service_sql(app, service, ARGS)
    assert window("AnalysisDateTime") in sql
    for sex, kind, values in (("M", "positive", POSITIVE), ("M", "negative", NEGATIVE),
                              ("F", "positive", POSITIVE), ("F", "negative", NEGATIVE)):
        label = f"{'male' if sex == 'M' else 'female'}_{kind}"
        assert (f"CASE WHEN ({values} AND [EIDMaster].[HL7SexCode] = '{sex}') "
                f"THEN 1 END) AS {label}") in sql
    assert "IsPoc" not in sql  # lab_type=all (legacy category Todos)
    assert_no_legacy_results(sql)


@pytest.mark.parametrize(
    "service",
    [fac.facility_tested_samples_by_gender_service,
     fac.facility_tested_samples_by_gender_by_month_service],
    ids=ids,
)
@pytest.mark.parametrize("lab_type, value", [("conventional", "No"), ("poc", "Yes")])
def test_gender_lab_type_is_the_legacy_category(app, service, lab_type, value):
    _, [sql] = service_sql(app, service, {**ARGS, "lab_type": lab_type})
    assert f"[EIDMaster].[IsPoc] = '{value}'" in sql


def test_gender_by_month_groups_by_analysis_month(app):
    _, [sql] = service_sql(app, fac.facility_tested_samples_by_gender_by_month_service, ARGS)
    assert monthly_group("AnalysisDateTime") in sql


def test_gender_rows_shape(app):
    counts = dict(zip(GENDER, (1, 2, 3, 4)))
    data = row(requesting_facility="Gaza", **counts)
    result, _ = service_sql(app, fac.facility_tested_samples_by_gender_service, ARGS,
                            results=[[data]])
    assert result == [dict(requesting_facility="Gaza", **counts)]


def test_gender_by_month_rows_shape(app):
    counts = dict(zip(GENDER, (1, 2, 3, 4)))
    data = row(year=2025, month=1, month_name="January", **counts)
    result, _ = service_sql(app, fac.facility_tested_samples_by_gender_by_month_service, ARGS,
                            results=[[data]])
    assert result == [dict(year=2025, month=1, month_name="January", **counts)]


# --- tat_avg / _by_month (clinic/samples_tat_avg_*) ----------------------------
HUB_ORDER = (
    "isnull(isnull([EIDMaster].[LIMSPreReg_ReceivedDateTime], "
    "[EIDMaster].[LIMSPreReg_RegistrationDateTime]), '1900-01-01') < "
    "isnull(isnull([EIDMaster].[ReceivedDateTime], [EIDMaster].[RegisteredDateTime]), '2100-01-01')"
)
WITHIN_30 = "datediff(day, [EIDMaster].[RegisteredDateTime], [EIDMaster].[AnalysisDateTime]) <= 30"
HUB_TO_LAB = ("datediff(day, [EIDMaster].[LIMSPreReg_RegistrationDateTime], "
              "[EIDMaster].[ReceivedDateTime]) >= 0")
COLLECTION_TO_HUB = ("datediff(day, [EIDMaster].[SpecimenDatetime], "
                     "[EIDMaster].[LIMSPreReg_RegistrationDateTime]) >= 0")


@pytest.mark.parametrize(
    "service", [fac.facility_tat_avg_service, fac.facility_tat_avg_by_month_service], ids=ids
)
def test_tat_avg_facility_tat_avg_filters(app, service):
    _, [sql] = service_sql(app, service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert "[EIDMaster].[IsPoc] = 'No'" in sql
    assert HUB_ORDER in sql and WITHIN_30 in sql
    assert "[EIDMaster].[TestingFacilityCode] != 'PBC'" in sql
    assert HUB_TO_LAB in sql and COLLECTION_TO_HUB in sql
    assert "CASE WHEN (avg(" in sql  # zero counted as one
    for key in TAT_KEYS:
        assert f"AS {key}" in sql


def test_tat_avg_by_month_groups_by_analysis_month(app):
    _, [sql] = service_sql(app, fac.facility_tat_avg_by_month_service, ARGS)
    assert monthly_group("AnalysisDateTime") in sql


def test_tat_avg_rows_shape(app):
    tat = dict(zip(TAT_KEYS, range(1, 7)))
    data = row(requesting_facility="Gaza", **tat)
    result, _ = service_sql(app, fac.facility_tat_avg_service, ARGS, results=[[data]])
    assert result == [dict(requesting_facility="Gaza", **tat)]


def test_tat_avg_by_month_rows_shape(app):
    tat = dict(zip(TAT_KEYS, range(1, 7)))
    data = row(year=2025, month=1, month_name="January", **tat)
    result, _ = service_sql(app, fac.facility_tat_avg_by_month_service, ARGS, results=[[data]])
    assert result == [dict(year=2025, month=1, month_name="January", **tat)]


# --- tat_days / _by_month (clinic/samples_tat_days_*) --------------------------
@pytest.mark.parametrize(
    "service", [fac.facility_tat_days_service, fac.facility_tat_days_by_month_service], ids=ids
)
def test_tat_days_facility_tat_days_filters(app, service):
    _, [sql] = service_sql(app, service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert "[EIDMaster].[IsPoc] = 'No'" in sql
    assert HUB_ORDER in sql and WITHIN_30 in sql
    assert "[EIDMaster].[TestingFacilityCode] != 'PBC'" in sql
    assert HUB_TO_LAB not in sql and COLLECTION_TO_HUB not in sql  # tat_avg only
    for label in BRACKETS:
        assert f"AS {label}" in sql


@pytest.mark.parametrize(
    "service", [fac.facility_tat_days_service, fac.facility_tat_days_by_month_service], ids=ids
)
@pytest.mark.parametrize(
    "category, start, end",
    [("0", "SpecimenDatetime", "LIMSPreReg_ReceivedDateTime"),
     ("2", "LIMSPreReg_RegistrationDateTime", "ReceivedDateTime"),
     ("5", "AnalysisDateTime", "AuthorisedDateTime")],
)
def test_tat_days_brackets_of_category(app, service, category, start, end):
    _, [sql] = service_sql(app, service, {**ARGS, "category": category})
    days = f"datediff(day, [EIDMaster].[{start}], [EIDMaster].[{end}])"
    assert f"{days} < 7" in sql
    assert f"{days} IS NULL" in sql  # no_dates


def test_tat_days_rejects_bad_category(app):
    from utilities.service_helpers import InvalidParameter

    with pytest.raises(InvalidParameter):
        service_sql(app, fac.facility_tat_days_service, {**ARGS, "category": "6"})


def test_tat_days_by_month_groups_by_analysis_month(app):
    _, [sql] = service_sql(app, fac.facility_tat_days_by_month_service, ARGS)
    assert monthly_group("AnalysisDateTime") in sql


def test_tat_days_rows_shape(app):
    brackets = dict(zip(BRACKETS, (5, 4, 3, 2, 1)))
    data = row(requesting_facility="Gaza", **brackets)
    result, _ = service_sql(app, fac.facility_tat_days_service, {**ARGS, "category": "4"},
                            results=[[data]])
    assert result == [dict(requesting_facility="Gaza", category="lab_registration_analysis",
                           **brackets)]


def test_tat_days_by_month_rows_shape(app):
    brackets = dict(zip(BRACKETS, (5, 4, 3, 2, 1)))
    data = row(year=2025, month=1, month_name="January", **brackets)
    result, _ = service_sql(app, fac.facility_tat_days_by_month_service, ARGS, results=[[data]])
    assert result == [dict(year=2025, month=1, month_name="January",
                           category="collection_hub_reception", **brackets)]


# --- key_indicators (clinic/conventional|poc/key_indicators) -------------------
def test_key_indicators_window_is_analysis_or_registration(app):
    _, [sql] = service_sql(app, fac.facility_key_indicators_service, ARGS)
    where = sql.split(" WHERE ")[1]
    assert f"({window('AnalysisDateTime')} OR {window('RegisteredDateTime')})" in where


def test_key_indicators_counts(app):
    _, [sql] = service_sql(app, fac.facility_key_indicators_service, ARGS)
    analysed, registered = window("AnalysisDateTime"), window("RegisteredDateTime")
    assert f"CASE WHEN ({analysed}) THEN 1 END) AS tested" in sql
    assert f"CASE WHEN ({registered}) THEN 1 END) AS registered" in sql
    assert (f"CASE WHEN ({registered} AND [EIDMaster].[HL7ResultStatusCode] = 'X') "
            "THEN 1 END) AS rejected") in sql
    assert f"CASE WHEN ({analysed} AND {POSITIVE}) THEN 1 END) AS positive" in sql
    pending = sql.split("AS rejected")[1].split("AS pending")[0]
    assert registered in pending
    assert "[EIDMaster].[HL7ResultStatusCode] != 'X'" in pending
    assert "[EIDMaster].[FinalResult] IS NULL" in pending
    assert "LIMSRejectionCode" not in sql  # legacy rejected = status 'X'
    assert_no_legacy_results(sql)


@pytest.mark.parametrize("lab_type, value", [("conventional", "No"), ("poc", "Yes")])
def test_key_indicators_lab_type_gets_its_own_rows(app, lab_type, value):
    """✱1: each lab type gets its own data (legacy IsPoc split)."""
    _, [sql] = service_sql(app, fac.facility_key_indicators_service,
                           {**ARGS, "lab_type": lab_type})
    assert f"[EIDMaster].[IsPoc] = '{value}'" in sql


def test_key_indicators_all_has_no_lab_type_filter(app):
    _, [sql] = service_sql(app, fac.facility_key_indicators_service, ARGS)
    assert "IsPoc" not in sql


def test_key_indicators_rows_shape_and_positivity(app):
    rows = [
        row(requesting_facility="Chokwe", registered=20, tested=8, rejected=1, pending=2,
            positive=1),
        row(requesting_facility="Guija", registered=3, tested=0, rejected=0, pending=3,
            positive=0),
    ]
    result, _ = service_sql(app, fac.facility_key_indicators_service, ARGS, results=[rows])
    assert result == [
        dict(requesting_facility="Chokwe", registered=20, tested=8, rejected=1, pending=2,
             positive=1, positivity=12.5),
        dict(requesting_facility="Guija", registered=3, tested=0, rejected=0, pending=3,
             positive=0, positivity=0),
    ]


# --- tested_samples_by_age (no card) ------------------------------------------
def test_tested_by_age_uses_rebuilt_columns(app):
    _, [sql] = service_sql(app, fac.facility_tested_samples_by_age_service, ARGS)
    assert "AgeInDays" in sql and "AnalysisDateTime" in sql
    assert not re.search(r"\[Result[A-Z]", sql)


def test_service_errors_never_raise(app):
    def boom(self):
        raise RuntimeError("db down")

    from unittest.mock import patch
    from sqlalchemy.orm import Query

    with app.app_context(), patch.object(Query, "all", boom):
        result = fac.facility_tested_samples_service(dict(ARGS))
    assert result["status"] == "error" and result["code"] == 500
