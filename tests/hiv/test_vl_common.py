"""Unit and SQL-compilation tests for hiv/vl/services/vl_common.py."""
import pytest
from sqlalchemy import and_

from tests.hiv.sql_capture import to_sql
from utilities.service_helpers import InvalidParameter
from utilities.utils import PROCESS_COMMON_PARAMS_VL

WINDOW = ["2025-01-01,2025-12-31"]


@pytest.fixture
def vl(app):
    with app.app_context():
        from hiv.vl.services import vl_common

        yield vl_common


def sql_of(clauses):
    return to_sql(and_(*clauses))


# --- parameters ------------------------------------------------------------
def test_parse_vl_params_accepts_csv_dates(vl):
    assert vl.parse_vl_params({"interval_dates": WINDOW}).dates == ["2025-01-01", "2025-12-31"]


def test_parse_vl_params_accepts_repeated_dates(vl):
    params = vl.parse_vl_params({"interval_dates": ["2025-01-01", "2025-03-31"]})
    assert params.dates == ["2025-01-01", "2025-03-31"]


def test_parse_vl_params_defaults_to_twelve_months(vl):
    dates = vl.parse_vl_params({}).dates
    assert len(dates) == 2 and dates[0] < dates[1]


def test_parse_vl_params_rejects_bad_dates(vl):
    with pytest.raises(InvalidParameter):
        vl.parse_vl_params({"interval_dates": ["2025-13-01,2025-12-31"]})


@pytest.mark.parametrize("raw", ["true", "True", "1", "yes", "YES"])
def test_parse_vl_params_truthy_disaggregation(vl, raw):
    assert vl.parse_vl_params({"disaggregation": raw}).disaggregation is True


@pytest.mark.parametrize("raw", [None, "", "false", "False", "0", "no"])
def test_parse_vl_params_falsy_disaggregation(vl, raw):
    assert vl.parse_vl_params({"disaggregation": raw}).disaggregation is False


def test_parse_vl_params_lab_codes_from_csv_and_repeats(vl):
    params = vl.parse_vl_params({"lab_code": ["PCD,PDD", " PJC "]})
    assert params.lab_codes == ["PCD", "PDD", "PJC"]


@pytest.mark.parametrize("raw,expected", [
    (None, None), ("15,49", (15, 49)), (["15", "49"], (15, 49)), (["15,49"], (15, 49)),
])
def test_parse_age_range(vl, raw, expected):
    assert vl.parse_age_range(raw) == expected


@pytest.mark.parametrize("raw", ["a,b", "49,15", "-1,10", "15", "15,20,30"])
def test_parse_age_range_rejects_bad_input(vl, raw):
    with pytest.raises(InvalidParameter):
        vl.parse_age_range(raw)


def test_parse_vl_params_facilities_follow_facility_type(vl):
    params = vl.parse_vl_params({"facility_type": "district", "district": [" Chibuto ", ""], "province": ["Gaza"]})
    assert params.facilities == ["Chibuto"]
    params = vl.parse_vl_params({"facility_type": "health_facility", "health_facility": "CS Chibuto"})
    assert params.facilities == ["CS Chibuto"]


def test_process_common_params_vl_accepts_repeated_dates():
    dates, *_ = PROCESS_COMMON_PARAMS_VL({"interval_dates": ["2025-01-01", "2025-03-31"]})
    assert dates == ["2025-01-01", "2025-03-31"]


@pytest.mark.parametrize("raw", ["True", "true", "1", "yes"])
def test_process_common_params_vl_truthy_disaggregation(raw):
    assert PROCESS_COMMON_PARAMS_VL({"disaggregation": raw})[3] is True


# --- date windows ----------------------------------------------------------
def test_date_between_keeps_node_bare_date_between(vl):
    from hiv.vl.models.vl import VlData

    sql = to_sql(vl.date_between(VlData.AnalysisDateTime, ["2025-01-01", "2025-12-31"]))
    assert sql == "[VlData].[AnalysisDateTime] BETWEEN '2025-01-01' AND '2025-12-31'"


def test_date_between_inclusive_casts_to_date(vl):
    from hiv.vl.models.vl import VlData

    sql = to_sql(vl.date_between_inclusive(VlData.RegisteredDateTime, ["2025-01-01", "2025-12-31"]))
    assert sql == (
        "CAST([VlData].[RegisteredDateTime] AS DATE) >= '2025-01-01' "
        "AND CAST([VlData].[RegisteredDateTime] AS DATE) <= '2025-12-31'"
    )


# --- counting rules --------------------------------------------------------
def test_rejected_condition_is_or_of_both_codes(vl):
    assert to_sql(vl.rejected_condition()) == (
        "[VlData].[LIMSRejectionCode] IS NOT NULL AND [VlData].[LIMSRejectionCode] != '' "
        "OR [VlData].[HIVVL_LIMSRejectionCode] IS NOT NULL AND [VlData].[HIVVL_LIMSRejectionCode] != ''"
    )


def test_tested_count_matches_node(vl):
    assert to_sql(vl.tested_count()) == (
        "count(CASE WHEN ([VlData].[AnalysisDateTime] IS NOT NULL "
        "AND [VlData].[AnalysisDateTime] != '') THEN 1 END)"
    )


def test_non_validated_count_matches_node(vl):
    assert to_sql(vl.non_validated_count()) == (
        "count(CASE WHEN ([VlData].[ViralLoadResultCategory] IS NOT NULL "
        "AND [VlData].[ViralLoadResultCategory] != '' "
        "AND ([VlData].[AuthorisedDateTime] IS NULL OR [VlData].[AuthorisedDateTime] = '')) THEN 1 END)"
    )


def test_tat_filters_have_no_90_day_cap(vl):
    sql = sql_of(vl.tat_filters())
    assert sql == (
        "[VlData].[ViralLoadResultCategory] NOT LIKE '' "
        "AND datediff(day, [VlData].[SpecimenDatetime], [VlData].[ReceivedDateTime]) >= 0"
    )
    assert "90" not in sql


def test_tat_averages_are_the_four_segments(vl):
    names = [column.name for column in vl.tat_averages()]
    assert names == [
        "collection_reception", "reception_registration",
        "registration_analysis", "analysis_validation",
    ]


def test_pregnant_and_breastfeeding_value_list(vl):
    expected = "IN ('YES', 'Yes', 'yes', 'Sim', 'SIM', 'sim')"
    assert to_sql(vl.pregnant_filter()) == f"[VlData].[Pregnant] {expected}"
    assert to_sql(vl.breastfeeding_filter()) == f"[VlData].[BreastFeeding] {expected}"


def test_age_range_filter(vl):
    params = vl.parse_vl_params({"age_range": "15,49"})
    assert sql_of(vl.age_range_filters(params)) == "[VlData].[AgeInYears] BETWEEN 15 AND 49"
    assert vl.age_range_filters(vl.parse_vl_params({})) == []


# --- location and lab filters ----------------------------------------------
def test_requesting_location_filters(vl):
    with_location = vl.parse_vl_params({"province": ["Gaza"]})
    assert sql_of(vl.requesting_location_filters(with_location)) == "[VlData].[RequestingProvinceName] IN ('Gaza')"
    nothing = vl.parse_vl_params({})
    assert sql_of(vl.requesting_location_filters(nothing)) == "[VlData].[RequestingProvinceName] != 'null'"
    assert vl.requesting_location_filters(nothing, exclude_null_province=False) == []


@pytest.mark.parametrize("facility_type,disaggregation,expected", [
    ("province", "false", "RequestingProvinceName"),
    ("province", "true", "RequestingDistrictName"),
    ("district", "false", "RequestingDistrictName"),
    ("district", "true", "RequestingFacilityName"),
    ("health_facility", "false", "RequestingFacilityName"),
])
def test_requesting_group_column(vl, facility_type, disaggregation, expected):
    params = vl.parse_vl_params({"facility_type": facility_type, "disaggregation": disaggregation})
    assert vl.requesting_group_column(params).key == expected


def test_lab_code_filters(vl):
    codes = vl.parse_vl_params({"lab_code": ["PCD", "PDD"]})
    assert sql_of(vl.lab_code_filters(codes, True)) == "[VlData].[TestingFacilityCode] IN ('PCD', 'PDD')"
    nothing = vl.parse_vl_params({})
    assert sql_of(vl.lab_code_filters(nothing, True)) == "[VlData].[TestingFacilityCode] LIKE 'P%'"
    assert vl.lab_code_filters(nothing, False) == []
    located = vl.parse_vl_params({"province": ["Gaza"]})
    assert vl.lab_code_filters(located, True) == []


def test_rejection_lab_code_is_requestid_substring(vl):
    assert to_sql(vl.rejection_lab_code()) == "substring([VlData].[RequestID], 7, 3)"


# --- interval_dates must be exactly two dates ------------------------------
@pytest.mark.parametrize("raw", [
    ["2025-01-01"],
    "2025-01-01",
    ["2025-01-01,2025-02-01,2025-03-01"],
])
def test_parse_vl_params_rejects_wrong_number_of_dates(vl, raw):
    with pytest.raises(InvalidParameter):
        vl.parse_vl_params({"interval_dates": raw})


def test_parse_vl_params_rejects_reversed_dates(vl):
    with pytest.raises(InvalidParameter, match="must not be after end"):
        vl.parse_vl_params({"interval_dates": ["2025-12-31,2025-01-01"]})


@pytest.mark.parametrize("raw", [None, "False", "false", "0", "no"])
def test_process_common_params_vl_falsy_disaggregation(raw):
    assert PROCESS_COMMON_PARAMS_VL({"disaggregation": raw})[3] is False


def test_process_common_params_vl_default_dates_are_ordered():
    dates = PROCESS_COMMON_PARAMS_VL({})[0]
    assert len(dates) == 2 and dates[0] < dates[1]


def test_suppression_counts_accept_another_column(vl):
    from sqlalchemy import column
    category = column("category")
    assert "category = 'Suppressed'" in to_sql(vl.suppressed_count(column=category))
    assert "category = 'Not Suppressed'" in to_sql(vl.not_suppressed_count(column=category))
