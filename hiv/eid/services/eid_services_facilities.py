"""
HIV EID Província/Distrito/US (facility) services.

Each card function reproduces the legacy openldr-api ClinicController route
named in its docstring (src/modules/eid/controllers/ClinicController.ts):
same date column, same exclusions. The counting rules come from
hiv/eid/services/eid_common.py. Differences from the legacy are the spec's ✱
fixes only (docs/superpowers/specs/2026-10-26-eid-dashboard-migration-design.md
§4.4):

- ✱1: ``key_indicators/`` gives each lab type its own rows (the legacy
  province page called the PoC route for both tabs).
- ✱5: every date window includes its end day.
- ✱7: every result count reads FinalResult (the legacy read PCR_Result /
  POC_Result patterns).

Every route keeps the legacy exclusion of rows with a NULL requesting
province, district or facility name; with no location given, a province
stored as the text 'null' is dropped too (spec §4.1). By-level routes group by
``group_column(params, "requesting")``: province by default, one level down
with ``disaggregation`` (the drill), and return the name as
``requesting_facility``. ``lab_type`` splits on ``IsPoc`` alone, as the legacy
Clinic routes did. ``lab_code`` filters ``TestingFacilityCode``.
"""
from sqlalchemy import and_, case, func, literal_column, or_, text

from db.database import db
from hiv.eid.models.eid_master_model import EIDMaster
from hiv.eid.services.eid_common import (
    PENDING_RESULT_VALUES,
    REJECTION_REASONS,
    RESULT_VALUES,
    TAT_SEGMENTS,
    date_between_inclusive,
    group_column,
    location_filters,
    parse_eid_params,
    rejection_reason_counts,
    result_count,
    tat_averages,
    tat_bracket_counts,
    tat_filters,
)
from utilities.utils import (
    DATE_PART,
    LAB_TYPE_EID,
    MONTH,
    PROCESS_COMMON_PARAMS_VL,
    YEAR,
)

_REJECTION_KEYS = [key for key, _ in REJECTION_REASONS] + ["other"]
_TAT_KEYS = [key for key, _, _ in TAT_SEGMENTS]
_BRACKET_KEYS = ["lt_7", "between_7_15", "between_16_21", "gt_21", "no_dates"]
_GENDER_KEYS = ["male_positive", "male_negative", "female_positive", "female_negative"]
_KEY = "requesting_facility"


def _error(e):
    return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


def _count(condition, label):
    return func.count(case((condition, 1), else_=None)).label(label)


def _total(label):
    return func.count(literal_column("1")).label(label)


def _positivity(positive, tested):
    """Percent positive of tested, 1 decimal; 0 when nothing was tested."""
    return round(100.0 * positive / tested, 1) if tested else 0


def _month_columns(column):
    return [
        func.year(column).label("year"),
        func.month(column).label("month"),
        func.datename(text("month"), column).label("month_name"),
    ]


def _month_keys(row):
    return dict(year=row.year, month=row.month, month_name=row.month_name)


def _is_poc_condition(lab_type):
    """``IsPoc`` alone, as the legacy Clinic routes split conventional / PoC."""
    if lab_type == "conventional":
        return EIDMaster.IsPoc == "No"
    if lab_type == "poc":
        return EIDMaster.IsPoc == "Yes"
    return None


def _scope_filters(params, with_lab_type=True):
    """Location, NULL-name exclusions, ``lab_code`` and ``lab_type``.

    Legacy Clinic routes: RequestingProvinceName, RequestingDistrictName and
    RequestingFacilityName all non-NULL.
    """
    filters = location_filters(params)
    filters += [
        EIDMaster.RequestingProvinceName.is_not(None),
        EIDMaster.RequestingDistrictName.is_not(None),
        EIDMaster.RequestingFacilityName.is_not(None),
    ]
    if params.lab_codes:
        filters.append(EIDMaster.TestingFacilityCode.in_(params.lab_codes))
    if with_lab_type:
        lab_type = _is_poc_condition(params.lab_type)
        if lab_type is not None:
            filters.append(lab_type)
    return filters


def _base_filters(params, date_column, with_lab_type=True):
    """Inclusive window (✱5) on ``date_column`` plus ``_scope_filters``."""
    return [date_between_inclusive(date_column, params.dates)] + _scope_filters(
        params, with_lab_type
    )


def _by_level(params, columns, filters, keys, extra=None):
    """Run a by-level query; rows carry ``requesting_facility`` + ``keys``."""
    column = group_column(params, "requesting")
    rows = (
        EIDMaster.query.with_entities(column.label(_KEY), *columns)
        .filter(and_(*filters))
        .group_by(column)
        .order_by(column)
        .all()
    )
    return [
        {_KEY: getattr(row, _KEY), **(extra or {}), **{k: getattr(row, k) for k in keys}}
        for row in rows
    ]


def _by_month(date_column, columns, filters, keys, extra=None):
    """Run a monthly query on ``date_column``; rows carry year, month, month_name."""
    month_cols = _month_columns(date_column)
    rows = (
        EIDMaster.query.with_entities(*month_cols, *columns)
        .filter(and_(*filters))
        .group_by(*month_cols)
        .order_by(month_cols[0], month_cols[1])
        .all()
    )
    return [
        dict(**_month_keys(row), **(extra or {}), **{k: getattr(row, k) for k in keys})
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Registered   (clinic/samples_registered_province, clinic/samples_registered_month)
# ---------------------------------------------------------------------------
_REGISTERED_KEYS = ["conventional", "poc", "total"]


def _registered_columns():
    return [
        _count(EIDMaster.IsPoc == "No", "conventional"),
        _count(EIDMaster.IsPoc == "Yes", "poc"),
        _total("total"),
    ]


def facility_registered_samples_service(req_args):
    """Registered ``conventional``, ``poc`` and ``total`` per requesting level.

    Legacy getRegisteredSamplesByProvince: RegisteredDateTime window;
    conventional / poc split on ``IsPoc`` alone.
    """
    params = parse_eid_params(req_args)
    try:
        return _by_level(
            params, _registered_columns(),
            _base_filters(params, EIDMaster.RegisteredDateTime), _REGISTERED_KEYS,
        )
    except Exception as e:
        return _error(e)


def facility_registered_samples_by_month_service(req_args):
    """Monthly registered ``conventional``, ``poc`` and ``total``, by registration month.

    Legacy getRegisteredSamplesByMonth: RegisteredDateTime window and month.
    """
    params = parse_eid_params(req_args)
    try:
        return _by_month(
            EIDMaster.RegisteredDateTime, _registered_columns(),
            _base_filters(params, EIDMaster.RegisteredDateTime), _REGISTERED_KEYS,
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Tested   (clinic/samples_tested_province, clinic/samples_tested_month)
# ---------------------------------------------------------------------------
_TESTED_KEYS = ["conventional", "poc", "total", "positive", "negative"]


def _tested_columns():
    return [
        _count(EIDMaster.IsPoc == "No", "conventional"),
        _count(EIDMaster.IsPoc == "Yes", "poc"),
        _total("total"),
        result_count("positive", "positive"),
        result_count("negative", "negative"),
    ]


def facility_tested_samples_service(req_args):
    """Tested ``conventional``, ``poc``, ``total``, ``positive``, ``negative`` per level.

    Legacy getTestedSamplesByProvince: AnalysisDateTime window, every row
    (rejected rows are not left out); conventional / poc on ``IsPoc``.
    ``lab_type`` keeps one of the two (the card's Todos/PoC/Convencional).
    ✱7 positive / negative read FinalResult (new columns).
    """
    params = parse_eid_params(req_args)
    try:
        return _by_level(
            params, _tested_columns(),
            _base_filters(params, EIDMaster.AnalysisDateTime), _TESTED_KEYS,
        )
    except Exception as e:
        return _error(e)


def facility_tested_samples_by_month_service(req_args):
    """Monthly tested ``conventional``, ``poc``, ``total``, ``positive``, ``negative``.

    Legacy getTestedSamplesByMonth: AnalysisDateTime window and month; as
    ``facility_tested_samples_service``.
    """
    params = parse_eid_params(req_args)
    try:
        return _by_month(
            EIDMaster.AnalysisDateTime, _tested_columns(),
            _base_filters(params, EIDMaster.AnalysisDateTime), _TESTED_KEYS,
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Rejected   (clinic/samples_rejected_by_facility, clinic/samples_rejected_by_month)
# ---------------------------------------------------------------------------
def _rejected_filters(params):
    """Legacy: AnalysisDateTime window, ``IsPoc = 'No'``, ``LIMSRejectionCode <> ''``.

    ``<> ''`` drops a NULL code too; a row rejected by description only is
    not counted (legacy). ``lab_type`` does not apply (conventional only).
    """
    filters = _base_filters(params, EIDMaster.AnalysisDateTime, with_lab_type=False)
    return filters + [EIDMaster.IsPoc == "No", EIDMaster.LIMSRejectionCode != ""]


def facility_rejected_samples_service(req_args):
    """Rejected samples by reason (9 buckets) and ``total`` per requesting level.

    Legacy getRejectedSamplesByProvince: reasons of the default variant
    (REJOL and PRTLA count as ``other``).
    """
    params = parse_eid_params(req_args)
    try:
        return _by_level(
            params, [*rejection_reason_counts("default"), _total("total")],
            _rejected_filters(params), _REJECTION_KEYS + ["total"],
        )
    except Exception as e:
        return _error(e)


def facility_rejected_samples_by_month_service(req_args):
    """Monthly rejected samples by reason (9 buckets) and ``total``, by analysis month.

    Legacy getRejectedSamplesByMonth: reasons of the facility variant (REJOL
    is a repeat test, PRTLA a technical problem).
    """
    params = parse_eid_params(req_args)
    try:
        return _by_month(
            EIDMaster.AnalysisDateTime, [*rejection_reason_counts("facility"), _total("total")],
            _rejected_filters(params), _REJECTION_KEYS + ["total"],
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Gender   (clinic/samples_tested_gender_province, clinic/samples_tested_gender_month)
# ---------------------------------------------------------------------------
def _gender_columns():
    """Sex (``HL7SexCode`` M / F) × result (✱7 FinalResult)."""
    columns = []
    for sex, prefix in (("M", "male"), ("F", "female")):
        for kind in ("positive", "negative"):
            columns.append(_count(
                and_(EIDMaster.FinalResult.in_(RESULT_VALUES[kind]), EIDMaster.HL7SexCode == sex),
                f"{prefix}_{kind}",
            ))
    return columns


def facility_tested_samples_by_gender_service(req_args):
    """``male_positive``, ``male_negative``, ``female_positive``, ``female_negative`` per level.

    Legacy getTestedSamplesByGenderByProvince: AnalysisDateTime window.
    ``lab_type`` is the legacy ``category`` (Todos / Poc / Convencional),
    now on ``IsPoc``. ✱7 results read FinalResult (the legacy read
    POC_Result / PCR_Result = 'Positivo' / 'Negativo', and its Todos
    category counted every POC_Result positive regardless of sex).
    """
    params = parse_eid_params(req_args)
    try:
        return _by_level(
            params, _gender_columns(),
            _base_filters(params, EIDMaster.AnalysisDateTime), _GENDER_KEYS,
        )
    except Exception as e:
        return _error(e)


def facility_tested_samples_by_gender_by_month_service(req_args):
    """Monthly ``male_positive``, ``male_negative``, ``female_positive``, ``female_negative``.

    Legacy getTestedSamplesByGenderByMonth: AnalysisDateTime window and
    month; as ``facility_tested_samples_by_gender_service``.
    """
    params = parse_eid_params(req_args)
    try:
        return _by_month(
            EIDMaster.AnalysisDateTime, _gender_columns(),
            _base_filters(params, EIDMaster.AnalysisDateTime), _GENDER_KEYS,
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# TAT averages   (clinic/samples_tat_avg_province, clinic/samples_tat_avg_month)
# ---------------------------------------------------------------------------
def _tat_filters(params, variant):
    """AnalysisDateTime window + the route's legacy TAT filters (conventional only)."""
    return _base_filters(params, EIDMaster.AnalysisDateTime, with_lab_type=False) + tat_filters(
        variant
    )


def facility_tat_avg_service(req_args):
    """Average days of the six TAT segments per requesting level.

    Legacy getTatAvgSamplesByProvince: AnalysisDateTime window,
    ``tat_filters("facility_tat_avg")`` (IsPoc 'No', hub dates before lab
    dates, no PBC, registration -> analysis <= 30 days, hub registration ->
    lab reception >= 0, collection -> hub registration >= 0); integer
    averages with 0 counted as 1.
    """
    params = parse_eid_params(req_args)
    try:
        return _by_level(
            params, tat_averages(zero_as_one=True),
            _tat_filters(params, "facility_tat_avg"), _TAT_KEYS,
        )
    except Exception as e:
        return _error(e)


def facility_tat_avg_by_month_service(req_args):
    """Monthly average days of the six TAT segments, by analysis month.

    Legacy getTatAvgSamplesByMonth: as ``facility_tat_avg_service``.
    """
    params = parse_eid_params(req_args)
    try:
        return _by_month(
            EIDMaster.AnalysisDateTime, tat_averages(zero_as_one=True),
            _tat_filters(params, "facility_tat_avg"), _TAT_KEYS,
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# TAT brackets   (clinic/samples_tat_days_province, clinic/samples_tat_days_month)
# ---------------------------------------------------------------------------
def facility_tat_days_service(req_args):
    """Day brackets of TAT segment ``category`` (0-5) per requesting level.

    Legacy getTatDaysSamplesByProvince: AnalysisDateTime window,
    ``tat_filters("facility_tat_days")`` (IsPoc 'No', hub dates before lab
    dates, no PBC, registration -> analysis <= 30 days); brackets <7, 7-15,
    16-21, >21 and no dates. Rows carry ``category`` (the segment name).
    """
    params = parse_eid_params(req_args)
    segment = TAT_SEGMENTS[params.category][0]
    try:
        return _by_level(
            params, tat_bracket_counts(params.category),
            _tat_filters(params, "facility_tat_days"), _BRACKET_KEYS,
            extra={"category": segment},
        )
    except Exception as e:
        return _error(e)


def facility_tat_days_by_month_service(req_args):
    """Monthly day brackets of TAT segment ``category`` (0-5), by analysis month.

    Legacy getTatDaysSamplesByMonth: as ``facility_tat_days_service``.
    """
    params = parse_eid_params(req_args)
    segment = TAT_SEGMENTS[params.category][0]
    try:
        return _by_month(
            EIDMaster.AnalysisDateTime, tat_bracket_counts(params.category),
            _tat_filters(params, "facility_tat_days"), _BRACKET_KEYS,
            extra={"category": segment},
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Key indicators   (clinic/conventional/key_indicators, clinic/poc/key_indicators)
# ---------------------------------------------------------------------------
_KEY_INDICATOR_KEYS = ["registered", "tested", "rejected", "pending", "positive"]


def facility_key_indicators_service(req_args):
    """Registered, tested, rejected, pending, positive and positivity per level.

    Legacy getKeyIndicatorsConventional / getKeyIndicatorsPoc (the Sumário
    map drill table): rows with AnalysisDateTime OR RegisteredDateTime in
    the window; tested = analysed in the window; registered, rejected and
    pending = registered in the window; rejected =
    ``HL7ResultStatusCode = 'X'``; pending = no result and status not 'X'
    (a NULL status is not pending, as in the legacy); positive = analysed in
    the window and positive. ✱1 ``lab_type`` conventional / poc gives each lab
    type its own rows (``IsPoc`` 'No' / 'Yes'); ``all`` is both. ✱7 pending
    and positive read FinalResult. ``positivity`` = positive ÷ tested
    (percent, 1 decimal; 0 when nothing was tested).
    """
    params = parse_eid_params(req_args)
    analysed = date_between_inclusive(EIDMaster.AnalysisDateTime, params.dates)
    registered = date_between_inclusive(EIDMaster.RegisteredDateTime, params.dates)
    no_result = or_(
        EIDMaster.FinalResult.is_(None),
        EIDMaster.FinalResult == "",
        EIDMaster.FinalResult.in_(PENDING_RESULT_VALUES),
    )
    filters = [or_(analysed, registered)] + _scope_filters(params)
    columns = [
        _count(registered, "registered"),
        _count(analysed, "tested"),
        _count(and_(registered, EIDMaster.HL7ResultStatusCode == "X"), "rejected"),
        _count(and_(registered, no_result, EIDMaster.HL7ResultStatusCode != "X"), "pending"),
        _count(and_(analysed, EIDMaster.FinalResult.in_(RESULT_VALUES["positive"])), "positive"),
    ]
    try:
        rows = _by_level(params, columns, filters, _KEY_INDICATOR_KEYS)
        for row in rows:
            row["positivity"] = _positivity(row["positive"], row["tested"])
        return rows
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Route no card uses (spec §4.3): only renamed to the rebuilt columns.
# ---------------------------------------------------------------------------
def _build_facility_filters(facilities, facility_type):
    """Build facility filter conditions based on facility_type (Requesting* columns)."""
    if not facilities:
        return []
    if facility_type == "province":
        return [EIDMaster.RequestingProvinceName.in_(facilities)]
    elif facility_type == "district":
        return [EIDMaster.RequestingDistrictName.in_(facilities)]
    elif facility_type == "health_facility":
        return [EIDMaster.RequestingFacilityName.in_(facilities)]
    return []


def _year_month_group_order(date_field):
    """Return (group_by, order_by) tuples for year/month grouping."""
    cols = [YEAR(date_field), MONTH(date_field), DATE_PART("month", date_field)]
    return cols, cols


def _apply_lab_type_filter(filters, lab_type):
    """Append LAB_TYPE_EID filter if lab_type is not 'all'."""
    lab_filter = LAB_TYPE_EID(EIDMaster, lab_type)
    if lab_filter is not None:
        filters.append(lab_filter)


# ---------------------------------------------------------------------------
# facilities/tested_samples_by_age/   (no legacy card)
# ---------------------------------------------------------------------------
def facility_tested_samples_by_age_service(req_args):
    """Tested samples grouped by year/month and EID age groups (using AgeInDays)."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_cols, order_cols = _year_month_group_order(EIDMaster.AnalysisDateTime)

    # EID age groups based on AgeInDays:
    # 0-2 months (~0-60 days), 2-9 months (~61-270 days),
    # 9-18 months (~271-540 days), 18+ months (>540 days)
    age_case = case(
        (EIDMaster.AgeInDays.between(0, 60), "0-2 months"),
        (EIDMaster.AgeInDays.between(61, 270), "2-9 months"),
        (EIDMaster.AgeInDays.between(271, 540), "9-18 months"),
        (EIDMaster.AgeInDays > 540, "18+ months"),
        else_="Unknown",
    ).label("age_group")

    try:
        # Use subquery to work around SQL Server parameterized CASE in GROUP BY
        subq = (
            db.session.query(
                EIDMaster.AnalysisDateTime,
                age_case,
            )
            .filter(and_(*filters))
            .subquery()
        )
        query = (
            db.session.query(
                func.year(subq.c.AnalysisDateTime).label("year"),
                func.month(subq.c.AnalysisDateTime),
                func.datename(text("month"), subq.c.AnalysisDateTime),
                subq.c.age_group,
                func.count().label("total"),
            )
            .group_by(
                func.year(subq.c.AnalysisDateTime),
                func.month(subq.c.AnalysisDateTime),
                func.datename(text("month"), subq.c.AnalysisDateTime),
                subq.c.age_group,
            )
            .order_by(
                func.year(subq.c.AnalysisDateTime),
                func.month(subq.c.AnalysisDateTime),
                subq.c.age_group,
            )
        )
        data = query.all()
        return [
            dict(
                year=row[0], month=row[1], month_name=row[2],
                age_group=row.age_group, total=row.total,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}
