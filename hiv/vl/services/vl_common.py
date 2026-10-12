"""
Shared building blocks for the HIV Viral Load services.

Each counting rule the VL dashboard relies on is defined once here, so the
laboratory, facility and summary services cannot drift apart. The rules match
the legacy Node API (openldr-backend, src/app/viralload/controllers) unless
marked ✱; every ✱ is listed in CLAUDE.md under "VL parity with the legacy API".
"""

from collections import namedtuple
from datetime import date

from sqlalchemy import and_, case, cast, func, literal_column, or_, text
from sqlalchemy.dialects.mssql import DATE

from hiv.vl.models.vl import VlData
from utilities.service_helpers import InvalidParameter, coerce_interval_dates

YES_VALUES = ["YES", "Yes", "yes", "Sim", "SIM", "sim"]
TREATMENT_FAILURE_REASONS = ["Suspected treatment failure", "Suspeita de falha terapêutica"]
REASON_NOT_SPECIFIED_REASONS = ["Não preenchido", "Reason Not Specified"]
CONVENTIONAL_LAB_CODE_PATTERN = "P%"
TRUTHY_VALUES = {"true", "1", "yes"}

VlParams = namedtuple(
    "VlParams",
    "dates facilities facility_type disaggregation health_facility lab_codes age_range",
)

_REQUESTING_FILTER_COLUMNS = {
    "province": VlData.RequestingProvinceName,
    "district": VlData.RequestingDistrictName,
    "health_facility": VlData.RequestingFacilityName,
}
_TESTING_FILTER_COLUMNS = {
    "province": VlData.TestingProvinceName,
    "district": VlData.TestingDistrictName,
    "health_facility": VlData.TestingFacilityName,
}


# ---------------------------------------------------------------------------
# Request parameters
# ---------------------------------------------------------------------------
def split_values(raw):
    """Flatten repeated and comma-separated query values into a clean list."""
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    values = []
    for item in raw:
        values.extend(part.strip() for part in str(item).split(",") if part.strip())
    return values


def parse_age_range(raw):
    """``"15,49"`` (or ``["15", "49"]``) -> ``(15, 49)``; ``None`` when absent."""
    parts = split_values(raw)
    if not parts:
        return None
    try:
        low, high = (int(part) for part in parts)
    except ValueError:
        raise InvalidParameter("age_range must be two whole numbers: min,max") from None
    if low < 0 or high < low:
        raise InvalidParameter("age_range must satisfy 0 <= min <= max")
    return low, high


def _validated_dates(raw):
    values = split_values(raw)
    if values and len(values) != 2:
        raise InvalidParameter(
            "interval_dates must be two YYYY-MM-DD dates: start,end"
        )
    dates = coerce_interval_dates(raw)
    for value in dates:
        try:
            date.fromisoformat(value)
        except ValueError:
            raise InvalidParameter(
                "interval_dates must be two YYYY-MM-DD dates: start,end"
            ) from None
    return dates


def parse_vl_params(req_args):
    """Normalise the query parameters shared by every VL reporting endpoint."""
    facility_type = req_args.get("facility_type") or "province"
    health_facility = req_args.get("health_facility")

    if facility_type == "province":
        facilities = req_args.get("province") or []
    elif facility_type == "district":
        facilities = req_args.get("district") or []
    elif facility_type == "health_facility" and health_facility:
        facilities = [health_facility]
    else:
        facilities = []

    return VlParams(
        dates=_validated_dates(req_args.get("interval_dates")),
        facilities=[f.strip() for f in facilities if f and f.strip()],
        facility_type=facility_type,
        disaggregation=str(req_args.get("disaggregation") or "").strip().lower()
        in TRUTHY_VALUES,
        health_facility=health_facility,
        lab_codes=split_values(req_args.get("lab_code")),
        age_range=parse_age_range(req_args.get("age_range")),
    )


# ---------------------------------------------------------------------------
# Date windows
# ---------------------------------------------------------------------------
def date_between(column, dates):
    """``column BETWEEN start AND end`` on bare dates, as Node does.

    The end day only counts rows stamped exactly at midnight. This matches
    every legacy endpoint except the rejection ones.
    """
    return column.between(dates[0], dates[1])


def date_between_inclusive(column, dates):
    """``CAST(column AS DATE)`` between start and end, both days whole."""
    day = cast(column, DATE)
    return and_(day >= dates[0], day <= dates[1])


def year_month_columns(column):
    """Labelled year / month / month_name columns for monthly grouping."""
    return [
        func.year(column).label("year"),
        func.month(column).label("month"),
        func.datename(text("month"), column).label("month_name"),
    ]


# ---------------------------------------------------------------------------
# Counting rules
# ---------------------------------------------------------------------------
def _non_empty(column):
    return and_(column.is_not(None), column != "")


def count_where(condition, label):
    return func.count(case((condition, 1), else_=None)).label(label)


def has_result():
    """Node: ``ViralLoadResultCategory NOT LIKE ''`` (also drops NULLs)."""
    return VlData.ViralLoadResultCategory.not_like("")


def tested_count(label="tested"):
    """Node: ``AnalysisDatetime IS NOT NULL AND AnalysisDatetime <> ''``."""
    return count_where(
        and_(
            VlData.AnalysisDateTime.is_not(None),
            VlData.AnalysisDateTime != literal_column("''"),
        ),
        label,
    )


def suppressed_count(label="suppressed", column=None):
    column = VlData.ViralLoadResultCategory if column is None else column
    return count_where(column == "Suppressed", label)


def not_suppressed_count(label="not_suppressed", column=None):
    column = VlData.ViralLoadResultCategory if column is None else column
    return count_where(column == "Not Suppressed", label)


def rejected_condition():
    """Either rejection code is non-empty (✱ Node's clinic endpoints used AND)."""
    return or_(
        _non_empty(VlData.LIMSRejectionCode),
        _non_empty(VlData.HIVVL_LIMSRejectionCode),
    )


def rejected_count(label="rejected"):
    return count_where(rejected_condition(), label)


def non_validated_count(label="non_validated"):
    return count_where(
        and_(
            _non_empty(VlData.ViralLoadResultCategory),
            or_(
                VlData.AuthorisedDateTime.is_(None),
                VlData.AuthorisedDateTime == literal_column("''"),
            ),
        ),
        label,
    )


def test_reason_counts():
    return [
        count_where(VlData.ReasonForTest == "Routine", "routine"),
        count_where(VlData.ReasonForTest.in_(TREATMENT_FAILURE_REASONS), "treatment_failure"),
        count_where(VlData.ReasonForTest.in_(REASON_NOT_SPECIFIED_REASONS), "reason_not_specified"),
    ]


def tat_filters():
    """Rows that enter a TAT average.

    A non-empty result category and a non-negative collection -> reception
    interval. ✱ Node meant to add a 90-day cap, but a duplicate object key
    dropped it, so no cap is applied here either.
    """
    return [
        has_result(),
        func.datediff(text("day"), VlData.SpecimenDatetime, VlData.ReceivedDateTime) >= 0,
    ]


def tat_averages():
    """The four TAT segments; AVG of an INT DATEDIFF truncates, as in Node."""
    segments = [
        ("collection_reception", VlData.SpecimenDatetime, VlData.ReceivedDateTime),
        ("reception_registration", VlData.ReceivedDateTime, VlData.RegisteredDateTime),
        ("registration_analysis", VlData.RegisteredDateTime, VlData.AnalysisDateTime),
        ("analysis_validation", VlData.AnalysisDateTime, VlData.AuthorisedDateTime),
    ]
    return [
        func.avg(func.datediff(text("day"), start, end)).label(name)
        for name, start, end in segments
    ]


def pregnant_filter():
    return VlData.Pregnant.in_(YES_VALUES)


def breastfeeding_filter():
    return VlData.BreastFeeding.in_(YES_VALUES)


def age_range_filters(params):
    if params.age_range is None:
        return []
    low, high = params.age_range
    return [VlData.AgeInYears.between(low, high)]


# ---------------------------------------------------------------------------
# Location and laboratory filters
# ---------------------------------------------------------------------------
def requesting_location_filters(params, exclude_null_province=True):
    """Facility-page location filter on the Requesting* columns.

    With no location given, Node drops rows whose RequestingProvinceName is
    NULL or the text 'null' (``!= 'null'`` excludes NULL as well).
    """
    column = _REQUESTING_FILTER_COLUMNS.get(params.facility_type)
    if params.facilities and column is not None:
        return [column.in_(params.facilities)]
    if exclude_null_province:
        return [VlData.RequestingProvinceName != "null"]
    return []


def requesting_group_column(params):
    """Grouping column for the facility ``*_by_facility`` endpoints."""
    if params.disaggregation:
        if params.facility_type == "province":
            return VlData.RequestingDistrictName
        if params.facility_type == "district":
            return VlData.RequestingFacilityName
        return VlData.RequestingProvinceName
    if params.facility_type == "province":
        return VlData.RequestingProvinceName
    if params.facility_type == "district":
        return VlData.RequestingDistrictName
    return VlData.RequestingFacilityName


def testing_location_filters(params):
    """Laboratory-page location filter on the Testing* columns."""
    column = _TESTING_FILTER_COLUMNS.get(params.facility_type)
    if params.facilities and column is not None:
        return [column.in_(params.facilities)]
    return []


def lab_code_filters(params, conventional_default):
    """``TestingFacilityCode IN lab_code``.

    With no lab and no location filter, the endpoints that ask for it are
    limited to conventional labs (codes starting with P), as in Node.
    """
    if params.lab_codes:
        return [VlData.TestingFacilityCode.in_(params.lab_codes)]
    if conventional_default and not params.facilities:
        return [VlData.TestingFacilityCode.like(CONVENTIONAL_LAB_CODE_PATTERN)]
    return []


def rejection_lab_code():
    """Lab code for rejections: characters 7-9 of RequestID, as in Node."""
    return func.substring(VlData.RequestID, 7, 3)
