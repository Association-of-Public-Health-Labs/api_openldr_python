"""SQL-compilation tests for the EID laboratory (Laboratório) services.

Each service reproduces the rule of the legacy openldr-api LaboratoryController
route it replaces (spec Appendix A, "Laboratório"); only the spec's ✱ fixes
differ.
"""
import pytest

from tests.hiv.sql_capture import service_sql
from hiv.eid.services import eid_services_laboratory as lab

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


CONVENTIONAL = "ltrim(rtrim([EIDMaster].[LIMSAnalyzerCode])) NOT IN ('MPIMA', 'PIMA')"
POC = (
    "[EIDMaster].[IsPoc] = 'Yes' OR "
    "ltrim(rtrim([EIDMaster].[LIMSAnalyzerCode])) IN ('MPIMA', 'PIMA')"
)
POSITIVE = "[EIDMaster].[FinalResult] IN ('Positivo', 'Reactive', 'DTS')"
NEGATIVE = "[EIDMaster].[FinalResult] IN ('Negativo', 'Not Reactive', 'Not Detected DBS', 'NDET')"
NOT_REJECTED = "[EIDMaster].[LIMSRejectionCode] IS NULL OR [EIDMaster].[LIMSRejectionCode] = ''"
REJECTED = "ltrim(rtrim([EIDMaster].[LIMSRejectionDesc])) != ''"
FINAL_STATUS = "[EIDMaster].[HL7ResultStatusCode] = 'F'"
LAB_CODES = {**ARGS, "lab_code": ["PJV", "PMB"]}
TESTING_CODE_IN = "[EIDMaster].[TestingFacilityCode] IN ('PJV', 'PMB')"
RECEIVING_CODE_IN = "[EIDMaster].[ReceivingFacilityCode] IN ('PJV', 'PMB')"
REASONS = ("repeat_test", "insufficient_sample", "request_without_sample",
           "technical_problems", "overlapping_blood", "duplicate_registration",
           "misidentified_sample", "sample_over_30_days", "other")
EQUIPMENT = ("CAPCTM", "ALINITY", "M2000", "C6800", "PANTHER", "MPIMA", "MANUAL")
TAT_KEYS = ("collection_hub_reception", "hub_reception_hub_registration",
            "hub_registration_lab_reception", "lab_reception_lab_registration",
            "lab_registration_analysis", "analysis_validation")


def assert_no_legacy_results(sql):
    """✱4/✱7: results come from FinalResult only."""
    assert "PCR_Result" not in sql and "POC_Result" not in sql


# --- laboratories/tested_samples_by_month/ (lab/all/samples_tested_by_month) --
def test_tested_by_month_on_analysis_date_not_rejected(app):
    _, [sql] = service_sql(app, lab.tested_samples_by_month_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert monthly_group("AnalysisDateTime") in sql
    assert NOT_REJECTED in sql
    assert POSITIVE in sql and NEGATIVE in sql
    for label in ("total", "positive", "negative"):
        assert f"AS {label}" in sql
    assert "IsPoc" not in sql  # lab_type=all: no lab-type filter
    assert_no_legacy_results(sql)


@pytest.mark.parametrize("lab_type, value", [("conventional", "No"), ("poc", "Yes")])
def test_tested_by_month_lab_type_is_ispoc_only(app, lab_type, value):
    """Legacy lab/all/samples_tested_by_month split on IsPoc alone."""
    _, [sql] = service_sql(app, lab.tested_samples_by_month_service, {**ARGS, "lab_type": lab_type})
    assert f"[EIDMaster].[IsPoc] = '{value}'" in sql
    assert "LIMSAnalyzerCode" not in sql


def test_tested_by_month_lab_code_is_testing_facility(app):
    _, [sql] = service_sql(app, lab.tested_samples_by_month_service, LAB_CODES)
    assert TESTING_CODE_IN in sql


def test_tested_by_month_rows_shape(app):
    data = row(year=2025, month=1, month_name="January", total=10, positive=1, negative=8)
    result, _ = service_sql(app, lab.tested_samples_by_month_service, ARGS, results=[[data]])
    assert result == [dict(year=2025, month=1, month_name="January", total=10,
                           positive=1, negative=8)]


# --- laboratories/registered_samples_by_month/ (lab/all/samples_registered_by_month)
def test_registered_by_month_on_registered_date(app):
    _, [sql] = service_sql(app, lab.registered_samples_by_month_service, ARGS)
    assert window("RegisteredDateTime") in sql
    assert monthly_group("RegisteredDateTime") in sql
    assert "CASE WHEN ([EIDMaster].[IsPoc] = 'No') THEN 1 END) AS conventional" in sql
    assert "CASE WHEN ([EIDMaster].[IsPoc] = 'Yes') THEN 1 END) AS poc" in sql
    assert "AS total" in sql
    assert "AnalysisDateTime" not in sql


def test_registered_by_month_lab_code_is_receiving_facility(app):
    _, [sql] = service_sql(app, lab.registered_samples_by_month_service, LAB_CODES)
    assert RECEIVING_CODE_IN in sql
    assert "TestingFacilityCode" not in sql


def test_registered_by_month_rows_shape(app):
    data = row(year=2025, month=2, month_name="February", total=10, conventional=7, poc=3)
    result, _ = service_sql(app, lab.registered_samples_by_month_service, ARGS, results=[[data]])
    assert result == [dict(year=2025, month=2, month_name="February", total=10,
                           conventional=7, poc=3)]


# --- laboratories/tested_samples/ (lab/conventional|poc/samples_tested) -------
def test_tested_conventional_by_lab(app):
    _, [sql] = service_sql(app, lab.tested_samples_service, {**ARGS, "lab_type": "conventional"})
    assert window("AnalysisDateTime") in sql
    assert "GROUP BY [EIDMaster].[TestingFacilityCode], [EIDMaster].[TestingFacilityName]" in sql
    assert NOT_REJECTED in sql
    assert "[EIDMaster].[IsPoc] = 'No'" in sql and CONVENTIONAL in sql
    assert "[EIDMaster].[TestingFacilityName] IS NOT NULL" in sql
    assert "[EIDMaster].[TestingFacilityCode] != 'PBC'" in sql
    assert POSITIVE in sql and NEGATIVE in sql
    assert_no_legacy_results(sql)


def test_tested_poc_by_lab(app):
    _, [sql] = service_sql(app, lab.tested_samples_service, {**ARGS, "lab_type": "poc"})
    assert POC in sql
    assert "[EIDMaster].[TestingFacilityCode] IS NOT NULL" in sql
    assert "PBC" not in sql  # legacy PoC route had no PBC exclusion
    assert_no_legacy_results(sql)


def test_tested_all_is_conventional_or_poc(app):
    _, [sql] = service_sql(app, lab.tested_samples_service, ARGS)
    assert CONVENTIONAL in sql and POC in sql


@pytest.mark.parametrize(
    "extra, group",
    [
        ({}, "TestingFacilityName"),
        ({"facility_type": "lab"}, "TestingFacilityName"),
        ({"facility_type": "lab", "disaggregation": "true"}, "RequestingProvinceName"),
        ({"facility_type": "province"}, "RequestingProvinceName"),
        ({"facility_type": "province", "disaggregation": "true"}, "RequestingDistrictName"),
        ({"facility_type": "district"}, "RequestingDistrictName"),
        ({"facility_type": "district", "disaggregation": "true"}, "RequestingFacilityName"),
        ({"facility_type": "health_facility"}, "RequestingFacilityName"),
    ],
)
def test_tested_drill_levels(app, extra, group):
    _, [sql] = service_sql(
        app, lab.tested_samples_service, {**ARGS, "lab_type": "conventional", **extra}
    )
    if group == "TestingFacilityName":  # lab level also groups by the code (L2)
        group = "TestingFacilityCode], [EIDMaster].[TestingFacilityName"
    assert f"GROUP BY [EIDMaster].[{group}]" in sql


def test_tested_district_filters_and_groups(app):
    """Legacy drill province -> district: rows per district of the clicked province."""
    _, [sql] = service_sql(
        app, lab.tested_samples_service,
        {**ARGS, "lab_type": "conventional", "facility_type": "province",
         "province": ["Gaza"], "disaggregation": "true"},
    )
    assert "[EIDMaster].[RequestingProvinceName] IN ('Gaza')" in sql
    assert "GROUP BY [EIDMaster].[RequestingDistrictName]" in sql


def test_tested_lab_code_is_testing_facility(app):
    _, [sql] = service_sql(app, lab.tested_samples_service, LAB_CODES)
    assert TESTING_CODE_IN in sql


def test_tested_no_null_province_exclusion(app):
    """The legacy lab routes had no location filter."""
    _, [sql] = service_sql(app, lab.tested_samples_service, ARGS)
    assert "'null'" not in sql


def test_tested_rows_shape_lab_and_requesting(app):
    data = row(testing_facility="Lab A", testing_facility_code="PJV", total=10, positive=1,
               negative=9)
    result, _ = service_sql(app, lab.tested_samples_service, ARGS, results=[[data]])
    assert result == [dict(testing_facility="Lab A", testing_facility_code="PJV", total=10,
                           positive=1, negative=9)]

    data = row(requesting_facility="Gaza", total=10, positive=1, negative=9)
    result, _ = service_sql(
        app, lab.tested_samples_service, {**ARGS, "facility_type": "province"}, results=[[data]]
    )
    assert result == [dict(requesting_facility="Gaza", total=10, positive=1, negative=9)]


# --- laboratories/tat/ (lab/conventional/tat) ---------------------------------
def test_tat_by_lab_with_lab_tat_filters(app):
    _, [sql] = service_sql(app, lab.tat_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert "GROUP BY [EIDMaster].[TestingFacilityCode], [EIDMaster].[TestingFacilityName]" in sql
    assert NOT_REJECTED in sql  # legacy excludes rejected rows
    assert CONVENTIONAL in sql
    assert "[EIDMaster].[TestingFacilityCode] NOT IN ('PBC', 'PEM')" in sql
    assert "BETWEEN 0 AND 90" in sql
    assert "CASE WHEN (avg(" in sql  # zero counted as one
    for key in TAT_KEYS:
        assert f"AS {key}" in sql


@pytest.mark.parametrize(
    "extra, groups",
    [
        ({"facility_type": "lab", "disaggregation": "true"}, ["RequestingProvinceName"]),
        ({"facility_type": "province"}, ["RequestingProvinceName"]),
        ({"facility_type": "province", "disaggregation": "true"},
         ["RequestingProvinceName", "RequestingDistrictName"]),
        ({"facility_type": "district", "disaggregation": "true"},
         ["RequestingProvinceName", "RequestingDistrictName", "RequestingFacilityName"]),
    ],
)
def test_tat_drill_groups_by_hierarchy(app, extra, groups):
    """Legacy: each drill level groups by every level above it too."""
    _, [sql] = service_sql(app, lab.tat_service, {**ARGS, **extra})
    expected = ", ".join(f"[EIDMaster].[{g}]" for g in groups)
    assert f"GROUP BY {expected}" in sql
    assert f"GROUP BY {expected}," not in sql


def test_tat_lab_code_is_testing_facility(app):
    _, [sql] = service_sql(app, lab.tat_service, LAB_CODES)
    assert TESTING_CODE_IN in sql


def test_tat_rows_shape_at_district_level(app):
    tat = dict(zip(TAT_KEYS, range(1, 7)))
    data = row(province="Gaza", requesting_facility="Chokwe", **tat)
    result, _ = service_sql(
        app, lab.tat_service,
        {**ARGS, "facility_type": "province", "province": ["Gaza"], "disaggregation": "true"},
        results=[[data]],
    )
    assert result == [dict(province="Gaza", requesting_facility="Chokwe", **tat)]


def test_tat_rows_shape_at_lab_level(app):
    tat = dict(zip(TAT_KEYS, range(1, 7)))
    data = row(testing_facility="Lab A", testing_facility_code="PJV", **tat)
    result, _ = service_sql(app, lab.tat_service, ARGS, results=[[data]])
    assert result == [dict(testing_facility="Lab A", testing_facility_code="PJV", **tat)]


# --- laboratories/tat_samples/ (lab/tat_samples) ------------------------------
def test_tat_samples_per_lab_brackets(app):
    _, [sql] = service_sql(app, lab.tat_samples_service, {**ARGS, "category": "2"})
    assert window("AnalysisDateTime") in sql
    assert "GROUP BY [EIDMaster].[TestingFacilityCode], [EIDMaster].[TestingFacilityName]" in sql
    assert "[EIDMaster].[TestingFacilityCode] NOT IN ('PBC', 'UEM')" in sql
    assert "BETWEEN 0 AND 90" not in sql  # no 90-day limit on this route
    days = "datediff(day, [EIDMaster].[LIMSPreReg_RegistrationDateTime], [EIDMaster].[ReceivedDateTime])"
    assert f"{days} < 7" in sql
    for label in ("lt_7", "between_7_15", "between_16_21", "gt_21", "no_dates"):
        assert f"AS {label}" in sql


def test_tat_samples_lab_code_is_testing_facility(app):
    _, [sql] = service_sql(app, lab.tat_samples_service, LAB_CODES)
    assert TESTING_CODE_IN in sql


@pytest.mark.parametrize(
    "category, start, end",
    [("0", "SpecimenDatetime", "LIMSPreReg_ReceivedDateTime"),
     ("5", "AnalysisDateTime", "AuthorisedDateTime")],
)
def test_tat_samples_category_scale_is_zero_to_five(app, category, start, end):
    _, [sql] = service_sql(app, lab.tat_samples_service, {**ARGS, "category": category})
    assert f"datediff(day, [EIDMaster].[{start}], [EIDMaster].[{end}]) < 7" in sql


def test_tat_samples_rows_shape(app):
    data = row(testing_facility="Lab A", testing_facility_code="PJV", lt_7=5, between_7_15=4,
               between_16_21=3, gt_21=2, no_dates=1)
    result, _ = service_sql(
        app, lab.tat_samples_service, {**ARGS, "category": "5"}, results=[[data]]
    )
    assert result == [dict(testing_facility="Lab A", testing_facility_code="PJV", category="analysis_validation", lt_7=5,
                           between_7_15=4, between_16_21=3, gt_21=2, no_dates=1)]


# --- laboratories/rejected_samples/ (lab/rejected_samples) --------------------
def test_rejected_by_receiving_lab(app):
    _, [sql] = service_sql(app, lab.rejected_samples_service, ARGS)
    assert window("RegisteredDateTime") in sql
    assert ("GROUP BY [EIDMaster].[ReceivingFacilityCode], "
            "[EIDMaster].[ReceivingFacilityName]") in sql
    assert "[EIDMaster].[IsPoc] = 'No'" in sql
    assert REJECTED in sql
    for key in REASONS + ("total",):
        assert f"AS {key}" in sql
    assert "REJOL" not in sql and "PRTLA" not in sql  # default variant


def test_rejected_lab_code_is_receiving_facility(app):
    """✱2: the lab filter applies, on the receiving lab."""
    _, [sql] = service_sql(app, lab.rejected_samples_service, LAB_CODES)
    assert RECEIVING_CODE_IN in sql
    assert "TestingFacilityCode" not in sql


def test_rejected_rows_shape(app):
    reasons = dict(zip(REASONS, range(1, 10)))
    data = row(receiving_facility="Lab A", receiving_facility_code="PJV", total=50, **reasons)
    result, _ = service_sql(app, lab.rejected_samples_service, ARGS, results=[[data]])
    assert result == [dict(receiving_facility="Lab A", receiving_facility_code="PJV",
                           **reasons, total=50)]


# --- laboratories/rejected_samples_by_month/ (lab/rejected_samples_monthly) ---
def test_rejected_by_month_on_registered_date(app):
    _, [sql] = service_sql(app, lab.rejected_samples_by_month_service, ARGS)
    assert window("RegisteredDateTime") in sql
    assert monthly_group("RegisteredDateTime") in sql
    assert "[EIDMaster].[IsPoc] = 'No'" in sql
    assert REJECTED in sql
    for key in REASONS + ("total",):
        assert f"AS {key}" in sql


def test_rejected_by_month_lab_code_is_receiving_facility(app):
    _, [sql] = service_sql(app, lab.rejected_samples_by_month_service, LAB_CODES)
    assert RECEIVING_CODE_IN in sql


def test_rejected_by_month_rows_shape(app):
    reasons = dict(zip(REASONS, range(1, 10)))
    data = row(year=2025, month=1, month_name="January", total=50, **reasons)
    result, _ = service_sql(app, lab.rejected_samples_by_month_service, ARGS, results=[[data]])
    assert result == [dict(year=2025, month=1, month_name="January", **reasons, total=50)]


# --- laboratories/samples_by_equipment/ (lab/samples_by_equipment) ------------
def test_equipment_by_lab_excludes_pbc(app):
    _, [sql] = service_sql(app, lab.samples_by_equipment_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert "GROUP BY [EIDMaster].[TestingFacilityCode], [EIDMaster].[TestingFacilityName]" in sql
    assert FINAL_STATUS in sql and "[EIDMaster].[IsPoc] = 'No'" in sql
    assert "[EIDMaster].[TestingFacilityCode] != 'PBC'" in sql
    assert "AS tested" in sql
    for key in EQUIPMENT:
        assert f"AS [{key}]" in sql
    assert "'C680A'" in sql and "'ALNTB'" in sql  # ✱8


def test_equipment_by_lab_lab_code(app):
    _, [sql] = service_sql(app, lab.samples_by_equipment_service, LAB_CODES)
    assert TESTING_CODE_IN in sql


def test_equipment_by_lab_rows_shape(app):
    groups = dict(zip(EQUIPMENT, range(1, 8)))
    data = row(testing_facility="Lab A", testing_facility_code="PJV", tested=40, **groups)
    result, _ = service_sql(app, lab.samples_by_equipment_service, ARGS, results=[[data]])
    assert result == [dict(testing_facility="Lab A", testing_facility_code="PJV", tested=40,
                           **groups)]


# --- laboratories/samples_by_equipment_by_month/ (lab/samples_by_equipment_monthly)
def test_equipment_by_month_keeps_pbc(app):
    _, [sql] = service_sql(app, lab.samples_by_equipment_by_month_service, ARGS)
    assert window("AnalysisDateTime") in sql
    assert monthly_group("AnalysisDateTime") in sql
    assert FINAL_STATUS in sql and "[EIDMaster].[IsPoc] = 'No'" in sql
    assert "PBC" not in sql
    for key in EQUIPMENT:
        assert f"AS [{key}]" in sql


def test_equipment_by_month_lab_code(app):
    _, [sql] = service_sql(app, lab.samples_by_equipment_by_month_service, LAB_CODES)
    assert TESTING_CODE_IN in sql


def test_equipment_by_month_rows_shape(app):
    groups = dict(zip(EQUIPMENT, range(1, 8)))
    data = row(year=2025, month=1, month_name="January", tested=40, **groups)
    result, _ = service_sql(app, lab.samples_by_equipment_by_month_service, ARGS, results=[[data]])
    assert result == [dict(year=2025, month=1, month_name="January", tested=40, **groups)]


# --- every card route ---------------------------------------------------------
CARD_SERVICES = [
    lab.tested_samples_by_month_service,
    lab.registered_samples_by_month_service,
    lab.tested_samples_service,
    lab.tat_service,
    lab.tat_samples_service,
    lab.rejected_samples_service,
    lab.rejected_samples_by_month_service,
    lab.samples_by_equipment_service,
    lab.samples_by_equipment_by_month_service,
]


@pytest.mark.parametrize("service", CARD_SERVICES, ids=lambda s: s.__name__)
def test_every_card_service_on_the_new_rules(app, service):
    _, sqls = service_sql(app, service, ARGS)
    assert sqls
    for sql in sqls:
        assert_no_legacy_results(sql)
        assert "BETWEEN '2025-01-01' AND '2025-12-31'" not in sql  # ✱5


@pytest.mark.parametrize("service", CARD_SERVICES, ids=lambda s: s.__name__)
def test_every_card_service_rejects_bad_lab_type(app, service):
    from utilities.service_helpers import InvalidParameter

    with pytest.raises(InvalidParameter):
        service_sql(app, service, {**ARGS, "lab_type": "pcr"})


# --- laboratories/labs/ and lab codes on lab-level rows (plan 2c, L1/L2) -------
def test_labs_lists_distinct_codes_by_lab_type(app):
    _, sqls = service_sql(app, lab.laboratory_labs_service, ARGS)
    assert len(sqls) == 2
    conventional, poc = sqls
    for sql in sqls:
        assert "DISTINCT" in sql
        assert "[EIDMaster].[TestingFacilityCode]" in sql
        assert "[EIDMaster].[TestingFacilityName]" in sql
        assert "[EIDMaster].[TestingFacilityCode] IS NOT NULL" in sql
        assert "[EIDMaster].[TestingFacilityName] IS NOT NULL" in sql
        assert "ORDER BY [EIDMaster].[TestingFacilityName], [EIDMaster].[TestingFacilityCode]" in sql
    assert CONVENTIONAL in conventional and POC not in conventional
    assert POC in poc and CONVENTIONAL not in poc


def test_labs_rows_shape_orders_by_name_and_keeps_both_types(app):
    conv = [row(code="PJV", name="Lab B"), row(code="PMB", name="Lab A")]
    poc = [row(code="PJV", name="Lab B"), row(code="X1", name="Lab C")]
    result, _ = service_sql(app, lab.laboratory_labs_service, ARGS, results=[conv, poc])
    assert result == [
        dict(code="PMB", name="Lab A", lab_type="conventional"),
        dict(code="PJV", name="Lab B", lab_type="conventional"),
        dict(code="PJV", name="Lab B", lab_type="poc"),
        dict(code="X1", name="Lab C", lab_type="poc"),
    ]


def test_tested_samples_lab_level_groups_by_code(app):
    _, [sql] = service_sql(app, lab.tested_samples_service, ARGS)
    assert "GROUP BY [EIDMaster].[TestingFacilityCode], [EIDMaster].[TestingFacilityName]" in sql
    assert ("ORDER BY [EIDMaster].[TestingFacilityName], "
            "[EIDMaster].[TestingFacilityCode]") in sql
    assert "AS testing_facility_code" in sql


def test_tested_samples_lab_level_row_has_code(app):
    data = row(testing_facility="Lab A", testing_facility_code="PJV", total=10, positive=1,
               negative=9)
    result, _ = service_sql(app, lab.tested_samples_service, ARGS, results=[[data]])
    assert result == [dict(testing_facility="Lab A", testing_facility_code="PJV", total=10,
                           positive=1, negative=9)]


@pytest.mark.parametrize("level", ["province", "district", "health_facility"])
def test_tested_samples_province_level_has_no_code(app, level):
    _, [sql] = service_sql(app, lab.tested_samples_service, {**ARGS, "facility_type": level})
    assert "testing_facility_code" not in sql
    data = row(requesting_facility="Gaza", total=10, positive=1, negative=9)
    result, _ = service_sql(
        app, lab.tested_samples_service, {**ARGS, "facility_type": level}, results=[[data]]
    )
    assert result == [dict(requesting_facility="Gaza", total=10, positive=1, negative=9)]


def test_tat_lab_level_groups_by_code(app):
    _, [sql] = service_sql(app, lab.tat_service, ARGS)
    assert "GROUP BY [EIDMaster].[TestingFacilityCode], [EIDMaster].[TestingFacilityName]" in sql
    assert ("ORDER BY [EIDMaster].[TestingFacilityName], "
            "[EIDMaster].[TestingFacilityCode]") in sql
    assert "AS testing_facility_code" in sql
    tat = dict(zip(TAT_KEYS, range(1, 7)))
    data = row(testing_facility="Lab A", testing_facility_code="PJV", **tat)
    result, _ = service_sql(app, lab.tat_service, ARGS, results=[[data]])
    assert result == [dict(testing_facility="Lab A", testing_facility_code="PJV", **tat)]


def test_tat_below_lab_level_has_no_code(app):
    _, [sql] = service_sql(app, lab.tat_service, {**ARGS, "facility_type": "province"})
    assert "testing_facility_code" not in sql


def test_tat_samples_returns_testing_code(app):
    _, [sql] = service_sql(app, lab.tat_samples_service, {**ARGS, "category": "2"})
    assert "GROUP BY [EIDMaster].[TestingFacilityCode], [EIDMaster].[TestingFacilityName]" in sql
    assert "AS testing_facility_code" in sql
    assert ("ORDER BY [EIDMaster].[TestingFacilityName], "
            "[EIDMaster].[TestingFacilityCode]") in sql
    data = row(testing_facility="Lab A", testing_facility_code="PJV", lt_7=5, between_7_15=4,
               between_16_21=3, gt_21=2, no_dates=1)
    result, _ = service_sql(
        app, lab.tat_samples_service, {**ARGS, "category": "5"}, results=[[data]]
    )
    assert result[0]["testing_facility_code"] == "PJV"
    assert result[0]["testing_facility"] == "Lab A"


def test_samples_by_equipment_returns_testing_code(app):
    _, [sql] = service_sql(app, lab.samples_by_equipment_service, ARGS)
    assert "GROUP BY [EIDMaster].[TestingFacilityCode], [EIDMaster].[TestingFacilityName]" in sql
    assert "AS testing_facility_code" in sql
    assert ("ORDER BY [EIDMaster].[TestingFacilityName], "
            "[EIDMaster].[TestingFacilityCode]") in sql
    groups = dict(zip(EQUIPMENT, range(1, 8)))
    data = row(testing_facility="Lab A", testing_facility_code="PJV", tested=40, **groups)
    result, _ = service_sql(app, lab.samples_by_equipment_service, ARGS, results=[[data]])
    assert result == [dict(testing_facility="Lab A", testing_facility_code="PJV", tested=40,
                           **groups)]


def test_rejected_samples_returns_receiving_code(app):
    _, [sql] = service_sql(app, lab.rejected_samples_service, ARGS)
    assert ("GROUP BY [EIDMaster].[ReceivingFacilityCode], "
            "[EIDMaster].[ReceivingFacilityName]") in sql
    assert ("ORDER BY [EIDMaster].[ReceivingFacilityName], "
            "[EIDMaster].[ReceivingFacilityCode]") in sql
    assert "AS receiving_facility_code" in sql
    reasons = dict(zip(REASONS, range(1, 10)))
    data = row(receiving_facility="Lab A", receiving_facility_code="PJV", total=50, **reasons)
    result, _ = service_sql(app, lab.rejected_samples_service, ARGS, results=[[data]])
    assert result == [dict(receiving_facility="Lab A", receiving_facility_code="PJV",
                           **reasons, total=50)]
