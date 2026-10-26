"""SQL-compilation tests for hiv/eid/services/eid_common.py (the shared EID rules)."""
import pytest
from sqlalchemy import and_, select

from tests.hiv.sql_capture import to_sql
from utilities.service_helpers import InvalidParameter

WINDOW = ["2025-01-01,2025-12-31"]


@pytest.fixture
def eid(app):
    with app.app_context():
        from hiv.eid.services import eid_common

        yield eid_common


def sql_of(*clauses):
    return to_sql(and_(*clauses))


def select_sql(columns):
    return to_sql(select(*columns))


# --- lab type ----------------------------------------------------------------
def test_conventional_excludes_pima(eid):
    s = sql_of(eid.conventional_condition())
    assert "[EIDMaster].[IsPoc] = 'No'" in s
    assert "ltrim(rtrim([EIDMaster].[LIMSAnalyzerCode])) NOT IN ('MPIMA', 'PIMA')" in s


def test_poc_includes_pima(eid):
    s = sql_of(eid.poc_condition())
    assert (
        "[EIDMaster].[IsPoc] = 'Yes' OR "
        "ltrim(rtrim([EIDMaster].[LIMSAnalyzerCode])) IN ('MPIMA', 'PIMA')"
    ) in s


def test_lab_type_condition(eid):
    assert eid.lab_type_condition("all") is None
    assert sql_of(eid.lab_type_condition("conventional")) == sql_of(eid.conventional_condition())
    assert sql_of(eid.lab_type_condition("poc")) == sql_of(eid.poc_condition())


# --- results -----------------------------------------------------------------
def test_result_values_classes(eid):
    assert eid.RESULT_VALUES == {
        "positive": ["Positivo", "Reactive", "DTS"],
        "negative": ["Negativo", "Not Reactive", "Not Detected DBS", "NDET"],
        "indeterminate": ["INCONCLUSIVE", "Indeterminado", "Inconclusive*"],
    }
    assert eid.PENDING_RESULT_VALUES == ["NDT", "Nível de detecção baixo"]


def test_unclassified_values_are_in_no_class(eid):
    classified = set(eid.PENDING_RESULT_VALUES)
    for values in eid.RESULT_VALUES.values():
        classified.update(values)
    for value in ("INS", "INST", "Insufficient sample", "Repeat Test"):
        assert value not in classified


def test_results_read_final_result_only(eid):
    s = select_sql(
        [eid.result_count(kind, kind) for kind in ("positive", "negative", "indeterminate")]
        + [eid.count_where(eid.pending_condition(), "pending")]
    )
    assert "FinalResult" in s
    assert "PCR_Result" not in s and "POC_Result" not in s


def test_result_count_positive(eid):
    s = select_sql([eid.result_count("positive", "positive")])
    assert (
        "count(CASE WHEN ([EIDMaster].[FinalResult] IN ('Positivo', 'Reactive', 'DTS')) "
        "THEN 1 END) AS positive"
    ) in s


def test_tested_is_analysis_date_not_null(eid):
    assert sql_of(eid.tested_condition()) == "[EIDMaster].[AnalysisDateTime] IS NOT NULL"


# --- rejected / pending --------------------------------------------------------
def test_rejected_is_code_or_desc(eid):
    s = sql_of(eid.rejected_condition())
    assert "ltrim(rtrim([EIDMaster].[LIMSRejectionCode])) != ''" in s
    assert "ltrim(rtrim([EIDMaster].[LIMSRejectionDesc])) != ''" in s
    assert "!= '' OR [EIDMaster].[LIMSRejectionDesc] IS NOT NULL" in s


def test_pending_is_not_rejected_and_no_final_result(eid):
    s = sql_of(eid.pending_condition())
    assert s.startswith("NOT (")
    assert "[EIDMaster].[FinalResult] IS NULL" in s
    assert "[EIDMaster].[FinalResult] = ''" in s
    assert "[EIDMaster].[FinalResult] IN ('NDT', 'Nível de detecção baixo')" in s


# --- rejection reasons ---------------------------------------------------------
def test_rejection_reasons_buckets(eid):
    assert [k for k, _ in eid.REJECTION_REASONS] == [
        "repeat_test",
        "insufficient_sample",
        "request_without_sample",
        "technical_problems",
        "overlapping_blood",
        "duplicate_registration",
        "misidentified_sample",
        "sample_over_30_days",
    ]


def test_rejection_reason_codes(eid):
    reasons = dict(eid.REJECTION_REASONS)
    assert reasons["repeat_test"] == ["REPIT", "SPUN2"]
    assert reasons["insufficient_sample"] == ["INS", "UNS"]
    assert reasons["request_without_sample"] == ["RSA", "NSRP", "SDBSA"]
    assert reasons["technical_problems"] == ["ERRTC", "ACC", "PROBT"]
    assert reasons["overlapping_blood"] == ["SASOB"]
    assert reasons["duplicate_registration"] == ["DUPRG"]
    assert reasons["misidentified_sample"] == ["NAME"]
    assert reasons["sample_over_30_days"] == ["AM30D"]
    facility = dict(eid.REJECTION_REASONS_FACILITY)
    assert facility["repeat_test"] == ["REPIT", "SPUN2", "REJOL"]
    assert facility["technical_problems"] == ["ERRTC", "ACC", "PROBT", "PRTLA"]
    assert {k: v for k, v in facility.items() if k not in ("repeat_test", "technical_problems")} == {
        k: v for k, v in reasons.items() if k not in ("repeat_test", "technical_problems")
    }


@pytest.mark.parametrize("variant", ["default", "facility"])
def test_rejection_variants_keep_the_9_labels(eid, variant):
    s = select_sql(eid.rejection_reason_counts(variant))
    labels = [k for k, _ in eid.REJECTION_REASONS] + ["other"]
    assert [c.name for c in eid.rejection_reason_counts(variant)] == labels
    for label in labels:
        assert f"AS {label}" in s


def test_rejol_is_other_by_default(eid):
    counts = {c.name: to_sql(c) for c in eid.rejection_reason_counts()}
    assert "'REJOL'" not in counts["repeat_test"] and "'PRTLA'" not in counts["technical_problems"]
    assert "'REJOL'" not in counts["other"] and "'PRTLA'" not in counts["other"]  # NOT IN list lacks them
    assert "NOT IN ('REPIT', 'SPUN2', 'INS', 'UNS'" in counts["other"]


def test_rejol_is_repeat_test_on_facility(eid):
    counts = {c.name: to_sql(c) for c in eid.rejection_reason_counts("facility")}
    assert "IN ('REPIT', 'SPUN2', 'REJOL')" in counts["repeat_test"]
    assert "IN ('ERRTC', 'ACC', 'PROBT', 'PRTLA')" in counts["technical_problems"]
    assert "NOT IN ('REPIT', 'SPUN2', 'REJOL', 'INS'" in counts["other"]


def test_rejection_unknown_variant(eid):
    with pytest.raises(ValueError):
        eid.rejection_reason_counts("other")


def test_rejection_reason_counts_has_other(eid):
    s = select_sql(eid.rejection_reason_counts())
    labels = [k for k, _ in eid.REJECTION_REASONS] + ["other"]
    assert len(eid.rejection_reason_counts()) == 9
    for label in labels:
        assert f"AS {label}" in s


def test_unbucketed_code_counts_as_other(eid):
    """'COM' (14 rows in production) is in no bucket, so it lands in `other`."""
    bucketed = {code for _, codes in eid.REJECTION_REASONS for code in codes}
    for code in ("COM", "INLS", "FDR", "AMONR", "HAEM", "15DIA", "NOCD", "OUTR", "SAALC"):
        assert code not in bucketed
    other = to_sql(eid.rejection_reason_counts()[-1])
    assert other.startswith(
        "count(CASE WHEN ([EIDMaster].[LIMSRejectionCode] IS NOT NULL AND "
        "ltrim(rtrim([EIDMaster].[LIMSRejectionCode])) != '' AND "
    )
    assert "ltrim(rtrim([EIDMaster].[LIMSRejectionCode])) NOT IN ('REPIT', 'SPUN2', 'INS', 'UNS'" in other
    assert "AS other" in select_sql(eid.rejection_reason_counts()[-1:])
    assert "'COM'" not in other


def test_description_only_rejection_is_not_other(eid):
    """`other` needs a non-empty code; a desc-only rejection is in no reason column."""
    other = to_sql(eid.rejection_reason_counts()[-1])
    assert "LIMSRejectionDesc" not in other
    assert "[EIDMaster].[LIMSRejectionCode] IS NULL" not in other
    assert "LIMSRejectionDesc" in sql_of(eid.rejected_condition())


# --- TAT ---------------------------------------------------------------------
def test_tat_segments(eid):
    assert [(k, a.key, b.key) for k, a, b in eid.TAT_SEGMENTS] == [
        ("collection_hub_reception", "SpecimenDatetime", "LIMSPreReg_ReceivedDateTime"),
        ("hub_reception_hub_registration", "LIMSPreReg_ReceivedDateTime", "LIMSPreReg_RegistrationDateTime"),
        ("hub_registration_lab_reception", "LIMSPreReg_RegistrationDateTime", "ReceivedDateTime"),
        ("lab_reception_lab_registration", "ReceivedDateTime", "RegisteredDateTime"),
        ("lab_registration_analysis", "RegisteredDateTime", "AnalysisDateTime"),
        ("analysis_validation", "AnalysisDateTime", "AuthorisedDateTime"),
    ]


HUB_ORDER = (
    "isnull(isnull([EIDMaster].[LIMSPreReg_ReceivedDateTime], "
    "[EIDMaster].[LIMSPreReg_RegistrationDateTime]), '1900-01-01') < "
    "isnull(isnull([EIDMaster].[ReceivedDateTime], [EIDMaster].[RegisteredDateTime]), '2100-01-01')"
)
COLLECTION_TO_LAB = "datediff(day, [EIDMaster].[SpecimenDatetime], [EIDMaster].[ReceivedDateTime]) >= 0"
HUB_REG_BEFORE_LAB = "[EIDMaster].[LIMSPreReg_RegistrationDateTime] < [EIDMaster].[ReceivedDateTime]"
HUB_REC_BEFORE_REG = "[EIDMaster].[LIMSPreReg_ReceivedDateTime] < [EIDMaster].[RegisteredDateTime]"
HUB_TO_LAB_90 = (
    "datediff(day, [EIDMaster].[LIMSPreReg_RegistrationDateTime], [EIDMaster].[ReceivedDateTime]) "
    "BETWEEN 0 AND 90"
)
HUB_TO_LAB_0 = "datediff(day, [EIDMaster].[LIMSPreReg_RegistrationDateTime], [EIDMaster].[ReceivedDateTime]) >= 0"
ANALYSIS_30 = "datediff(day, [EIDMaster].[RegisteredDateTime], [EIDMaster].[AnalysisDateTime]) <= 30"
COLLECTION_TO_HUB = "datediff(day, [EIDMaster].[SpecimenDatetime], [EIDMaster].[LIMSPreReg_RegistrationDateTime]) >= 0"
LAB_NAME = "[EIDMaster].[TestingFacilityName] IS NOT NULL"
NOT_REJECTED_CODE = "[EIDMaster].[LIMSRejectionCode] IS NULL OR [EIDMaster].[LIMSRejectionCode] = ''"


def test_tat_filters_summary(eid):
    s = sql_of(*eid.tat_filters("summary"))
    for clause in ("[EIDMaster].[IsPoc] = 'No'", COLLECTION_TO_LAB, HUB_ORDER, HUB_REG_BEFORE_LAB, HUB_REC_BEFORE_REG):
        assert clause in s
    for absent in ("PBC", "<= 30", "BETWEEN 0 AND 90", "LIMSAnalyzerCode", "LIMSRejectionCode", "TestingFacility"):
        assert absent not in s


def test_tat_filters_summary_tat_samples(eid):
    s = sql_of(*eid.tat_filters("summary_tat_samples"))
    for clause in ("[EIDMaster].[IsPoc] = 'No'", COLLECTION_TO_LAB, HUB_ORDER, HUB_REG_BEFORE_LAB):
        assert clause in s
    assert HUB_REC_BEFORE_REG not in s
    for absent in ("PBC", "<= 30", "BETWEEN 0 AND 90", "LIMSAnalyzerCode", "TestingFacility"):
        assert absent not in s


def test_tat_filters_lab_tat(eid):
    s = sql_of(*eid.tat_filters("lab_tat"))
    for clause in (
        NOT_REJECTED_CODE, sql_of(eid.conventional_condition()), LAB_NAME, HUB_ORDER,
        HUB_TO_LAB_90, ANALYSIS_30, COLLECTION_TO_HUB,
        "[EIDMaster].[TestingFacilityCode] NOT IN ('PBC', 'PEM')",
    ):
        assert clause in s
    assert "UEM" not in s and HUB_REG_BEFORE_LAB not in s and COLLECTION_TO_LAB not in s


def test_tat_filters_lab_tat_samples(eid):
    s = sql_of(*eid.tat_filters("lab_tat_samples"))
    for clause in (
        "[EIDMaster].[IsPoc] = 'No'", LAB_NAME, HUB_ORDER, ANALYSIS_30, HUB_TO_LAB_0,
        COLLECTION_TO_HUB, "[EIDMaster].[TestingFacilityCode] NOT IN ('PBC', 'UEM')",
    ):
        assert clause in s
    for absent in ("BETWEEN 0 AND 90", "PEM", "LIMSAnalyzerCode", "LIMSRejectionCode"):
        assert absent not in s


def test_tat_filters_facility_tat_days(eid):
    s = sql_of(*eid.tat_filters("facility_tat_days"))
    for clause in ("[EIDMaster].[IsPoc] = 'No'", HUB_ORDER, "[EIDMaster].[TestingFacilityCode] != 'PBC'", ANALYSIS_30):
        assert clause in s
    for absent in ("PEM", "UEM", "NOT IN", "BETWEEN", HUB_TO_LAB_0, COLLECTION_TO_HUB, "LIMSRejectionCode", "TestingFacilityName"):
        assert absent not in s


def test_tat_filters_facility_tat_avg(eid):
    s = sql_of(*eid.tat_filters("facility_tat_avg"))
    for clause in (
        "[EIDMaster].[IsPoc] = 'No'", HUB_ORDER, "[EIDMaster].[TestingFacilityCode] != 'PBC'",
        ANALYSIS_30, HUB_TO_LAB_0, COLLECTION_TO_HUB,
    ):
        assert clause in s
    for absent in ("PEM", "UEM", "BETWEEN", "LIMSAnalyzerCode", "LIMSRejectionCode"):
        assert absent not in s


def test_tat_filters_unknown_variant(eid):
    with pytest.raises(ValueError):
        eid.tat_filters("default")


def test_tat_averages(eid):
    plain = select_sql(eid.tat_averages(zero_as_one=False))
    assert (
        "avg(datediff(day, [EIDMaster].[SpecimenDatetime], "
        "[EIDMaster].[LIMSPreReg_ReceivedDateTime])) AS collection_hub_reception"
    ) in plain
    assert "CASE" not in plain
    one = select_sql(eid.tat_averages(zero_as_one=True))
    assert "CASE WHEN (avg(datediff(day, [EIDMaster].[AnalysisDateTime], [EIDMaster].[AuthorisedDateTime])) = 0) THEN 1" in one
    for key, _, _ in eid.TAT_SEGMENTS:
        assert f"AS {key}" in one


def test_tat_brackets_labels(eid):
    s = select_sql(eid.tat_bracket_counts(0))
    for k in ("lt_7", "between_7_15", "between_16_21", "gt_21", "no_dates"):
        assert f"AS {k}" in s
    assert "datediff(day, [EIDMaster].[SpecimenDatetime], [EIDMaster].[LIMSPreReg_ReceivedDateTime]) < 7" in s
    assert "IS NULL) THEN 1 END) AS no_dates" in s


def test_tat_brackets_follow_category(eid):
    s = select_sql(eid.tat_bracket_counts(5))
    assert "datediff(day, [EIDMaster].[AnalysisDateTime], [EIDMaster].[AuthorisedDateTime])" in s
    assert "SpecimenDatetime" not in s


# --- equipment ---------------------------------------------------------------
def test_equipment_groups_map_analyzer_codes(eid):
    groups = dict(eid.EQUIPMENT_GROUPS)
    assert [k for k, _ in eid.EQUIPMENT_GROUPS] == [
        "CAPCTM", "ALINITY", "M2000", "C6800", "PANTHER", "MPIMA", "MANUAL",
    ]
    assert groups["CAPCTM"] == ["ALINA", "AL-IM", "ALINB", "ALIND", "ALINK"]
    assert groups["C6800"] == ["C6800", "C6800A", "C6800B", "C680A"]
    assert groups["M2000"] == ["M2000", "M200A", "M200B", "M200C"]
    assert groups["PANTHER"] == ["PNTHA", "PNTHR", "PNTHC"]
    assert groups["ALINITY"] == ["ALNTA", "ALNTY", "ALNTB"]
    assert groups["MPIMA"] == ["MPIMA", "PIMA"]
    assert groups["MANUAL"] == ["MANUA", "MGIT", "SYSMX", ""]


def test_equipment_counts_trim_codes(eid):
    columns = eid.equipment_counts()
    assert len(columns) == 8
    s = select_sql(columns)
    assert "count(1) AS tested" in s
    assert "ltrim(rtrim([EIDMaster].[LIMSAnalyzerCode])) IN ('MANUA', 'MGIT', 'SYSMX', '')" in s


def test_equipment_filters_exclude_pbc_by_default(eid):
    s = sql_of(*eid.equipment_filters())
    assert s == sql_of(*eid.equipment_filters(exclude_pbc=True))
    assert "[EIDMaster].[HL7ResultStatusCode] = 'F'" in s
    assert "[EIDMaster].[IsPoc] = 'No'" in s
    assert "[EIDMaster].[TestingFacilityCode] != 'PBC'" in s
    assert "LIMSAnalyzerCode" not in s


def test_equipment_filters_without_pbc_exclusion(eid):
    s = sql_of(*eid.equipment_filters(exclude_pbc=False))
    assert "[EIDMaster].[HL7ResultStatusCode] = 'F'" in s
    assert "[EIDMaster].[IsPoc] = 'No'" in s
    assert "PBC" not in s and "TestingFacilityCode" not in s


# --- parameters --------------------------------------------------------------
def test_parse_defaults(eid):
    p = eid.parse_eid_params({"interval_dates": WINDOW})
    assert p.dates == ["2025-01-01", "2025-12-31"]
    assert p.lab_type == "all"
    assert p.category == 0
    assert p.facility_type is None
    assert p.disaggregation is False
    assert p.facilities == [] and p.lab_codes == []


def test_parse_values(eid):
    p = eid.parse_eid_params(
        {
            "interval_dates": WINDOW,
            "lab_type": "PoC",
            "category": "5",
            "facility_type": "province",
            "province": ["Zambézia", " "],
            "disaggregation": "True",
            "lab_code": ["PMB,PHL"],
        }
    )
    assert p.lab_type == "poc"
    assert p.category == 5
    assert p.facilities == ["Zambézia"]
    assert p.disaggregation is True
    assert p.lab_codes == ["PMB", "PHL"]


def test_parse_rejects_bad_lab_type(eid):
    with pytest.raises(InvalidParameter):
        eid.parse_eid_params({"lab_type": "foo"})


@pytest.mark.parametrize("category", ["9", "-1", "abc", "1.5"])
def test_parse_rejects_category_out_of_range(eid, category):
    with pytest.raises(InvalidParameter):
        eid.parse_eid_params({"category": category})


def test_parse_rejects_bad_dates(eid):
    with pytest.raises(InvalidParameter):
        eid.parse_eid_params({"interval_dates": ["2025-12-31,2025-01-01"]})


# --- location and grouping ---------------------------------------------------
def test_location_filter_matches_vl_normalisation(eid):
    from hiv.vl.services import vl_common

    args = {"facility_type": "province", "province": ["Zambézia"]}
    eid_sql = sql_of(*eid.location_filters(eid.parse_eid_params(args)))
    vl_sql = sql_of(*vl_common.requesting_location_filters(vl_common.parse_vl_params(args)))
    assert eid_sql == "[EIDMaster].[RequestingProvinceName] IN ('Zambézia')"
    assert eid_sql == vl_sql.replace("[VlData]", "[EIDMaster]")


def test_location_filter_without_location_excludes_null_province(eid):
    p = eid.parse_eid_params({})
    assert sql_of(*eid.location_filters(p)) == "[EIDMaster].[RequestingProvinceName] != 'null'"
    assert eid.location_filters(p, exclude_null_province=False) == []


def test_location_filter_district_and_facility(eid):
    p = eid.parse_eid_params({"facility_type": "district", "district": ["Mocuba"]})
    assert sql_of(*eid.location_filters(p)) == "[EIDMaster].[RequestingDistrictName] IN ('Mocuba')"
    p = eid.parse_eid_params({"facility_type": "health_facility", "health_facility": "CS Mocuba"})
    assert sql_of(*eid.location_filters(p)) == "[EIDMaster].[RequestingFacilityName] IN ('CS Mocuba')"


@pytest.mark.parametrize(
    "args, expected",
    [
        ({}, "RequestingProvinceName"),
        ({"facility_type": "province"}, "RequestingProvinceName"),
        ({"disaggregation": "true"}, "RequestingDistrictName"),
        ({"facility_type": "province", "disaggregation": "true"}, "RequestingDistrictName"),
        ({"facility_type": "district"}, "RequestingDistrictName"),
        ({"facility_type": "district", "disaggregation": "true"}, "RequestingFacilityName"),
        ({"facility_type": "health_facility"}, "RequestingFacilityName"),
    ],
)
def test_group_column_requesting(eid, args, expected):
    assert eid.group_column(eid.parse_eid_params(args), "requesting").key == expected


@pytest.mark.parametrize(
    "args, expected",
    [
        ({}, "TestingFacilityName"),
        ({"facility_type": "lab"}, "TestingFacilityName"),
        ({"facility_type": "province"}, "RequestingProvinceName"),
        ({"facility_type": "district"}, "RequestingDistrictName"),
        ({"facility_type": "health_facility"}, "RequestingFacilityName"),
    ],
)
def test_group_column_lab(eid, args, expected):
    assert eid.group_column(eid.parse_eid_params(args), "lab").key == expected


def test_group_column_rejects_unknown_level(eid):
    with pytest.raises(ValueError):
        eid.group_column(eid.parse_eid_params({}), "other")
