"""
Shared counting rules for the HIV EID (DPI) services.

Each rule the EID dashboard relies on is defined once here, so the summary,
laboratory and facility services cannot drift apart. The rules match the
legacy TypeScript API (openldr-api, src/modules/eid) unless marked ✱; the ✱
numbers are those of the design spec (docs/superpowers/specs/
2026-10-26-eid-dashboard-migration-design.md, §4.4). Value lists come from the
production value counts recorded in hiv/eid/data/schema_2026-10.md.
"""

from typing import NamedTuple, Optional

from sqlalchemy import and_, case, func, literal_column, not_, or_, text

from hiv.eid.models.eid_master_model import EIDMaster
from hiv.vl.services.vl_common import (
    TRUTHY_VALUES,
    _validated_dates,
    count_where,
    date_between_inclusive,  # noqa: F401  (re-exported for the EID services)
    split_values,
)
from utilities.service_helpers import InvalidParameter

FACILITY_TYPES = ("province", "district", "health_facility", "lab")
LAB_TYPES = ("all", "conventional", "poc")
POC_ANALYZER_CODES = ["MPIMA", "PIMA"]

# ✱7: FinalResult is the definitive result for every sample (conventional and
# PoC). Mapping confirmed by the user on 2026-10-26. Values in no class: INS,
# INST, "Insufficient sample", "Repeat Test".
RESULT_VALUES = {
    "positive": ["Positivo", "Reactive", "DTS"],
    "negative": ["Negativo", "Not Reactive", "Not Detected DBS", "NDET"],
    "indeterminate": ["INCONCLUSIVE", "Indeterminado", "Inconclusive*"],
}
# The legacy pending rule also counted these PCR_Result values; they appear in
# FinalResult, so they stay pending.
PENDING_RESULT_VALUES = ["NDT", "Nível de detecção baixo"]

# Legacy rejection buckets (default variant: DashboardController and
# LaboratoryController, and ClinicController.getRejectedSamplesByProvince).
# Any other non-empty code (COM, INLS, FDR, REJOL, PRTLA, ...) is `other`.
REJECTION_REASONS = [
    ("repeat_test", ["REPIT", "SPUN2"]),
    ("insufficient_sample", ["INS", "UNS"]),
    ("request_without_sample", ["RSA", "NSRP", "SDBSA"]),
    ("technical_problems", ["ERRTC", "ACC", "PROBT"]),
    ("overlapping_blood", ["SASOB"]),
    ("duplicate_registration", ["DUPRG"]),
    ("misidentified_sample", ["NAME"]),
    ("sample_over_30_days", ["AM30D"]),
]
# ClinicController.getRejectedSamplesByMonth adds REJOL and PRTLA.
_FACILITY_REJECTION_EXTRAS = {"repeat_test": ["REJOL"], "technical_problems": ["PRTLA"]}
REJECTION_REASONS_FACILITY = [
    (key, codes + _FACILITY_REJECTION_EXTRAS.get(key, [])) for key, codes in REJECTION_REASONS
]
_REJECTION_VARIANTS = {"default": REJECTION_REASONS, "facility": REJECTION_REASONS_FACILITY}

# The six TAT segments, in the order of the legacy `category` 0-5.
TAT_SEGMENTS = [
    ("collection_hub_reception", EIDMaster.SpecimenDatetime, EIDMaster.LIMSPreReg_ReceivedDateTime),
    ("hub_reception_hub_registration", EIDMaster.LIMSPreReg_ReceivedDateTime, EIDMaster.LIMSPreReg_RegistrationDateTime),
    ("hub_registration_lab_reception", EIDMaster.LIMSPreReg_RegistrationDateTime, EIDMaster.ReceivedDateTime),
    ("lab_reception_lab_registration", EIDMaster.ReceivedDateTime, EIDMaster.RegisteredDateTime),
    ("lab_registration_analysis", EIDMaster.RegisteredDateTime, EIDMaster.AnalysisDateTime),
    ("analysis_validation", EIDMaster.AnalysisDateTime, EIDMaster.AuthorisedDateTime),
]

# ✱ (spec ✱8) the legacy lists missed C680A, M200C, PNTHC and ALNTB, all
# present in production. Codes are compared trimmed ('PIMA ', 'MGIT ').
EQUIPMENT_GROUPS = [
    ("CAPCTM", ["ALINA", "AL-IM", "ALINB", "ALIND", "ALINK"]),
    ("ALINITY", ["ALNTA", "ALNTY", "ALNTB"]),
    ("M2000", ["M2000", "M200A", "M200B", "M200C"]),
    ("C6800", ["C6800", "C6800A", "C6800B", "C680A"]),
    ("PANTHER", ["PNTHA", "PNTHR", "PNTHC"]),
    ("MPIMA", ["MPIMA", "PIMA"]),
    ("MANUAL", ["MANUA", "MGIT", "SYSMX", ""]),
]

_REQUESTING_FILTER_COLUMNS = {
    "province": EIDMaster.RequestingProvinceName,
    "district": EIDMaster.RequestingDistrictName,
    "health_facility": EIDMaster.RequestingFacilityName,
}


class EidParams(NamedTuple):
    dates: list
    facilities: list
    facility_type: Optional[str]
    disaggregation: bool
    health_facility: Optional[str]
    lab_codes: list
    lab_type: str
    category: int


# ---------------------------------------------------------------------------
# Request parameters
# ---------------------------------------------------------------------------
def _parse_lab_type(raw):
    lab_type = str(raw or "all").strip().lower()
    if lab_type not in LAB_TYPES:
        raise InvalidParameter("lab_type must be one of: all, conventional, poc")
    return lab_type


def _parse_category(raw):
    if raw is None or str(raw).strip() == "":
        return 0
    try:
        category = int(str(raw).strip())
    except ValueError:
        raise InvalidParameter("category must be a whole number from 0 to 5") from None
    if not 0 <= category < len(TAT_SEGMENTS):
        raise InvalidParameter("category must be a whole number from 0 to 5")
    return category


def parse_eid_params(req_args):
    """Normalise the query parameters shared by every EID reporting endpoint.

    ``facility_type`` stays ``None`` when not given: the requesting level
    then groups by province, the laboratory level by testing lab.
    """
    facility_type = req_args.get("facility_type") or None
    if facility_type not in (None, *FACILITY_TYPES):
        raise InvalidParameter("facility_type must be one of: province, district, health_facility, lab")
    health_facility = req_args.get("health_facility")

    if facility_type in (None, "province"):
        facilities = req_args.get("province") or []
    elif facility_type == "district":
        facilities = req_args.get("district") or []
    elif facility_type == "health_facility" and health_facility:
        facilities = [health_facility] if isinstance(health_facility, str) else health_facility
    else:
        facilities = []
    if isinstance(facilities, str):
        facilities = [facilities]

    return EidParams(
        dates=_validated_dates(req_args.get("interval_dates")),
        facilities=[f.strip() for f in facilities if f and f.strip()],
        facility_type=facility_type,
        disaggregation=str(req_args.get("disaggregation") or "").strip().lower()
        in TRUTHY_VALUES,
        health_facility=health_facility,
        lab_codes=split_values(req_args.get("lab_code")),
        lab_type=_parse_lab_type(req_args.get("lab_type")),
        category=_parse_category(req_args.get("category")),
    )


# ---------------------------------------------------------------------------
# Lab type
# ---------------------------------------------------------------------------
def _trimmed(column):
    return func.ltrim(func.rtrim(column))


def conventional_condition():
    """``IsPoc = 'No'`` and not a PIMA analyzer.

    As in the legacy, a NULL analyzer code fails ``NOT IN`` and is excluded.
    """
    return and_(
        EIDMaster.IsPoc == "No",
        _trimmed(EIDMaster.LIMSAnalyzerCode).not_in(POC_ANALYZER_CODES),
    )


def poc_condition():
    return or_(
        EIDMaster.IsPoc == "Yes",
        _trimmed(EIDMaster.LIMSAnalyzerCode).in_(POC_ANALYZER_CODES),
    )


def lab_type_condition(lab_type):
    """The condition for ``lab_type``; ``None`` for ``all``."""
    if lab_type == "conventional":
        return conventional_condition()
    if lab_type == "poc":
        return poc_condition()
    return None


# ---------------------------------------------------------------------------
# Results, tested, rejected, pending
# ---------------------------------------------------------------------------
def result_count(kind, label):
    """Count of rows whose ``FinalResult`` is in ``RESULT_VALUES[kind]`` (✱7)."""
    return count_where(EIDMaster.FinalResult.in_(RESULT_VALUES[kind]), label)


def tested_condition():
    return EIDMaster.AnalysisDateTime.is_not(None)


def _non_empty_trimmed(column):
    return and_(column.is_not(None), _trimmed(column) != "")


def rejected_condition():
    """``LIMSRejectionCode`` or ``LIMSRejectionDesc`` non-empty after trimming."""
    return or_(
        _non_empty_trimmed(EIDMaster.LIMSRejectionCode),
        _non_empty_trimmed(EIDMaster.LIMSRejectionDesc),
    )


def legacy_rejected_conditions():
    """The rejected-sample rule of the facility routes (legacy, ruling R20).

    ``IsPoc = 'No'`` and ``LIMSRejectionCode <> ''`` (a NULL code is dropped
    too). The caller windows these rows on ``AnalysisDateTime``.
    """
    return [EIDMaster.IsPoc == "No", EIDMaster.LIMSRejectionCode != ""]


def pending_condition():
    """Not rejected and no definitive result (✱7); NDT values stay pending."""
    return and_(
        not_(rejected_condition()),
        or_(
            EIDMaster.FinalResult.is_(None),
            EIDMaster.FinalResult == "",
            EIDMaster.FinalResult.in_(PENDING_RESULT_VALUES),
        ),
    )


def rejection_reason_counts(variant="default"):
    """The 8 coded buckets plus ``other`` (9 labelled counts in every variant).

    ``variant="default"``: the Dashboard and Laboratory routes and
    ClinicController.getRejectedSamplesByProvince (``facilities/rejected_samples/``).
    ``variant="facility"``: ClinicController.getRejectedSamplesByMonth
    (``facilities/rejected_samples_by_month/``), where REJOL is a repeat test
    and PRTLA a technical problem.

    ``other`` is a non-empty rejection code that is in no bucket (COM, INLS,
    ...), as in the legacy. A row rejected only by description counts in
    ``rejected_condition()`` totals but in no reason column.
    """
    try:
        reasons = _REJECTION_VARIANTS[variant]
    except KeyError:
        raise ValueError(f"unknown rejection reason variant: {variant!r}") from None
    code = _trimmed(EIDMaster.LIMSRejectionCode)
    bucketed = [c for _, codes in reasons for c in codes]
    counts = [count_where(code.in_(codes), key) for key, codes in reasons]
    counts.append(
        count_where(
            and_(_non_empty_trimmed(EIDMaster.LIMSRejectionCode), code.not_in(bucketed)),
            "other",
        )
    )
    return counts


# ---------------------------------------------------------------------------
# Turnaround time
# ---------------------------------------------------------------------------
def _days(start, end):
    return func.datediff(text("day"), start, end)


def _hub_before_lab():
    hub_first = func.isnull(
        func.isnull(EIDMaster.LIMSPreReg_ReceivedDateTime, EIDMaster.LIMSPreReg_RegistrationDateTime),
        "1900-01-01",
    )
    lab_first = func.isnull(
        func.isnull(EIDMaster.ReceivedDateTime, EIDMaster.RegisteredDateTime),
        "2100-01-01",
    )
    return hub_first < lab_first


def tat_filters(variant):
    """The TAT quality filters of one legacy route family (parity, R12).

    Each variant reproduces the WHERE clauses of the legacy openldr-api
    routes (src/modules/eid/controllers), apart from the date window and
    location filters, which the routes add:

    - ``"summary"``: DashboardController.getPCRTurnAroundTime
      (``summary/tat/``). ``IsPoc = 'No'``; collection -> lab reception >= 0;
      hub dates before lab dates; hub registration < lab reception; hub
      reception < lab registration. No day limits, no lab exclusion.
    - ``"summary_tat_samples"``: DashboardController.getPCRTurnAroundTimeSamples
      (``summary/tat_samples/``). As ``"summary"`` without
      ``LIMSPreReg_ReceivedDateTime < RegisteredDateTime``.
    - ``"lab_tat"``: LaboratoryController.getTatByConventional
      (``laboratories/tat/``). Not rejected (``LIMSRejectionCode`` NULL or
      ''); the conventional rule; a testing lab name; hub dates before lab
      dates; hub registration -> lab reception 0-90 days; registration ->
      analysis <= 30 days; collection -> hub registration >= 0;
      ``TestingFacilityCode NOT IN ('PBC', 'PEM')``.
    - ``"lab_tat_samples"``: LaboratoryController.getTurnAroundTimeSamples
      (``laboratories/tat_samples/``). ``IsPoc = 'No'``; a testing lab name;
      hub dates before lab dates; registration -> analysis <= 30 days;
      hub registration -> lab reception >= 0 (no 90-day limit); collection
      -> hub registration >= 0; ``TestingFacilityCode NOT IN ('PBC', 'UEM')``.
    - ``"facility_tat_days"``: ClinicController.getTatDaysSamplesByMonth and
      getTatDaysSamplesByProvince (``facilities/tat_days*``). ``IsPoc = 'No'``;
      hub dates before lab dates; ``TestingFacilityCode <> 'PBC'``;
      registration -> analysis <= 30 days.
    - ``"facility_tat_avg"``: ClinicController.getTatAvgSamplesByMonth and
      getTatAvgSamplesByProvince (``facilities/tat_avg*``). As
      ``"facility_tat_days"`` plus hub registration -> lab reception >= 0 and
      collection -> hub registration >= 0.

    The facility routes also drop NULL Requesting province/district/facility
    names; that belongs to the route's location filters.
    """
    not_poc = EIDMaster.IsPoc == "No"
    hub_order = _hub_before_lab()
    hub_to_lab = _days(EIDMaster.LIMSPreReg_RegistrationDateTime, EIDMaster.ReceivedDateTime)
    collection_to_hub = _days(EIDMaster.SpecimenDatetime, EIDMaster.LIMSPreReg_RegistrationDateTime) >= 0
    analysis_within_30 = _days(EIDMaster.RegisteredDateTime, EIDMaster.AnalysisDateTime) <= 30
    has_lab_name = EIDMaster.TestingFacilityName.is_not(None)

    if variant in ("summary", "summary_tat_samples"):
        filters = [
            not_poc,
            _days(EIDMaster.SpecimenDatetime, EIDMaster.ReceivedDateTime) >= 0,
            hub_order,
            EIDMaster.LIMSPreReg_RegistrationDateTime < EIDMaster.ReceivedDateTime,
        ]
        if variant == "summary":
            filters.append(EIDMaster.LIMSPreReg_ReceivedDateTime < EIDMaster.RegisteredDateTime)
        return filters
    if variant == "lab_tat":
        return [
            or_(EIDMaster.LIMSRejectionCode.is_(None), EIDMaster.LIMSRejectionCode == ""),
            conventional_condition(),
            has_lab_name,
            hub_order,
            hub_to_lab.between(0, 90),
            analysis_within_30,
            collection_to_hub,
            EIDMaster.TestingFacilityCode.not_in(["PBC", "PEM"]),
        ]
    if variant == "lab_tat_samples":
        return [
            not_poc,
            has_lab_name,
            hub_order,
            analysis_within_30,
            hub_to_lab >= 0,
            collection_to_hub,
            EIDMaster.TestingFacilityCode.not_in(["PBC", "UEM"]),
        ]
    if variant in ("facility_tat_days", "facility_tat_avg"):
        filters = [
            not_poc,
            hub_order,
            EIDMaster.TestingFacilityCode != "PBC",
            analysis_within_30,
        ]
        if variant == "facility_tat_avg":
            filters += [hub_to_lab >= 0, collection_to_hub]
        return filters
    raise ValueError(f"unknown TAT filter variant: {variant!r}")


def tat_averages(zero_as_one):
    """``AVG(DATEDIFF(day, ...))`` per segment (integer, truncating).

    With ``zero_as_one`` an average of 0 is reported as 1, as the legacy
    laboratory TAT routes did.
    """
    columns = []
    for key, start, end in TAT_SEGMENTS:
        average = func.avg(_days(start, end))
        if zero_as_one:
            average = case((average == 0, 1), else_=average)
        columns.append(average.label(key))
    return columns


def tat_bracket_counts(category):
    """Day brackets for the TAT segment ``category`` (0-5)."""
    if not 0 <= category < len(TAT_SEGMENTS):
        raise InvalidParameter("category must be a whole number from 0 to 5")
    _, start, end = TAT_SEGMENTS[category]
    days = _days(start, end)
    return [
        count_where(days < 7, "lt_7"),
        count_where(days.between(7, 15), "between_7_15"),
        count_where(days.between(16, 21), "between_16_21"),
        count_where(days > 21, "gt_21"),
        count_where(days.is_(None), "no_dates"),
    ]


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------
def equipment_counts():
    """``tested`` (all rows) and one count per analyzer group (trimmed codes)."""
    code = _trimmed(EIDMaster.LIMSAnalyzerCode)
    return [func.count(literal_column("1")).label("tested")] + [
        count_where(code.in_(codes), key) for key, codes in EQUIPMENT_GROUPS
    ]


def equipment_filters(exclude_pbc=True):
    """Final results of non-PoC requests (``HL7ResultStatusCode = 'F'``).

    ``IsPoc = 'No'`` as in the legacy (the full conventional rule would empty
    the MPIMA group by construction). The PBC exclusion is route-specific
    (``TestingFacilityCode <> 'PBC'``, which also drops a NULL code). The
    legacy openldr-api routes (src/modules/eid/controllers) set it as follows:

    - LaboratoryController.getSamplesByEquipment (per lab,
      ``laboratories/samples_by_equipment/``): excludes PBC, so pass ``True``.
    - LaboratoryController.getSamplesByEquipmentMonthly
      (``laboratories/samples_by_equipment_by_month/``): no exclusion, so pass ``False``.
    - DashboardController.getSamplesByEquipmentMonthly
      (``summary/samples_by_equipment_by_month/``): no exclusion, so pass ``False``.
    - DashboardController.getSamplesByEquipment (per lab, summary): no
      exclusion, so pass ``False``.
    """
    filters = [
        EIDMaster.HL7ResultStatusCode == "F",
        EIDMaster.IsPoc == "No",
    ]
    if exclude_pbc:
        filters.append(EIDMaster.TestingFacilityCode != "PBC")
    return filters


# ---------------------------------------------------------------------------
# Location filters and grouping
# ---------------------------------------------------------------------------
def location_filters(params, exclude_null_province=True):
    """Location filter on the Requesting* columns, as VL's facility pages.

    With no location given, rows whose RequestingProvinceName is NULL or the
    text 'null' are dropped (``!= 'null'`` excludes NULL as well).
    """
    column = _REQUESTING_FILTER_COLUMNS.get(params.facility_type or "province")
    if params.facilities and column is not None:
        return [column.in_(params.facilities)]
    if exclude_null_province:
        return [EIDMaster.RequestingProvinceName != "null"]
    return []


_REQUESTING_LEVELS = ["province", "district", "health_facility"]
_LEVEL_COLUMNS = {
    "lab": EIDMaster.TestingFacilityName,
    "province": EIDMaster.RequestingProvinceName,
    "district": EIDMaster.RequestingDistrictName,
    "health_facility": EIDMaster.RequestingFacilityName,
}


def group_column(params, level):
    """Grouping column for by-level routes.

    ``level="requesting"``: province by default; ``disaggregation`` drills one
    level down (province -> district -> facility), as VL does.
    ``level="lab"``: ``facility_type`` names the level (``lab`` by default,
    then province, district, health_facility); ``disaggregation`` drills one
    level down the chain lab -> province -> district -> health_facility.
    """
    if level == "requesting":
        chain = _REQUESTING_LEVELS
        current = params.facility_type if params.facility_type in chain else (
            "health_facility" if params.facility_type else "province"
        )
    elif level == "lab":
        chain = ["lab"] + _REQUESTING_LEVELS
        current = params.facility_type if params.facility_type in chain else "lab"
    else:
        raise ValueError(f"unknown grouping level: {level!r}")

    index = chain.index(current)
    if params.disaggregation:
        if level == "requesting" and current == "health_facility":
            index = 0  # VL: health_facility + disaggregation -> province
        else:
            index = min(index + 1, len(chain) - 1)
    return _LEVEL_COLUMNS[chain[index]]
