"""
HIV EID summary (Sumário) services.

Each function reproduces the legacy openldr-api DashboardController route
named in its docstring (src/modules/eid/controllers/DashboardController.ts):
same date column, same exclusions. The counting rules come from
hiv/eid/services/eid_common.py. Differences from the legacy are the spec's ✱
fixes only (docs/superpowers/specs/2026-10-26-eid-dashboard-migration-design.md
§4.4):

- ✱3: the positivity line is positive ÷ tested.
- ✱5: every date window includes its end day.
- ✱6: conventional/PoC follow the lab-type rule, not RequestID digits.
- ✱7: every result count reads FinalResult.
- ✱8: equipment groups add the analyzer codes the legacy missed (C680A ->
  C6800, M200C -> M2000, PNTHC -> PANTHER, ALNTB -> ALINITY), compared
  trimmed; equipment counts are expected to be higher than the legacy.

The legacy dashboard routes had no location filter and no null-province
exclusion; the location and ``lab_code`` filters apply only when given.
"""
from sqlalchemy import and_, case, func, literal_column, text

from hiv.eid.models.eid_master_model import EIDMaster
from hiv.eid.services.eid_common import (
    REJECTION_REASONS,
    RESULT_VALUES,
    TAT_SEGMENTS,
    EQUIPMENT_GROUPS,
    conventional_condition,
    date_between_inclusive,
    equipment_counts,
    equipment_filters,
    lab_type_condition,
    location_filters,
    parse_eid_params,
    pending_condition,
    poc_condition,
    rejected_condition,
    rejection_reason_counts,
    result_count,
    tat_averages,
    tat_bracket_counts,
    tat_filters,
    tested_condition,
)

_REJECTION_KEYS = [key for key, _ in REJECTION_REASONS] + ["other"]
_EQUIPMENT_KEYS = [key for key, _ in EQUIPMENT_GROUPS]
_TAT_KEYS = [key for key, _, _ in TAT_SEGMENTS]
_BRACKET_KEYS = ["lt_7", "between_7_15", "between_16_21", "gt_21", "no_dates"]


def _error(e):
    return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


def _count(condition, label):
    return func.count(case((condition, 1), else_=None)).label(label)


def _total(label):
    return func.count(literal_column("1")).label(label)


def _is_positive():
    return EIDMaster.FinalResult.in_(RESULT_VALUES["positive"])


def _positivity(positive, tested):
    """Percent positive of tested, 1 decimal; 0 when nothing was tested."""
    return round(100.0 * positive / tested, 1) if tested else 0


def _month_columns(column):
    return [
        func.year(column).label("year"),
        func.month(column).label("month"),
        func.datename(text("month"), column).label("month_name"),
    ]


def _monthly(query, month_cols):
    return query.group_by(*month_cols).order_by(month_cols[0], month_cols[1]).all()


def _month_keys(row):
    return dict(year=row.year, month=row.month, month_name=row.month_name)


def _base_filters(params, date_column, with_lab_type=True):
    """Inclusive window (✱5), optional location / ``lab_code`` / ``lab_type``."""
    filters = [date_between_inclusive(date_column, params.dates)]
    filters += location_filters(params, exclude_null_province=False)
    if params.lab_codes:
        filters.append(EIDMaster.TestingFacilityCode.in_(params.lab_codes))
    if with_lab_type:
        lab_type = lab_type_condition(params.lab_type)
        if lab_type is not None:
            filters.append(lab_type)
    return filters


# ---------------------------------------------------------------------------
# 1. summary/indicators/   (dash/pcr/indicators + dash/poc/indicators)
# ---------------------------------------------------------------------------
def summary_indicators_service(req_args):
    """Monthly registered, tested, rejected, pending, by registration month.

    Legacy: RegisteredDateTime window and month; tested = AnalysisDateTime
    set; rejected = rejection code or description; pending = not rejected and
    no result. ✱6 ``lab_type`` uses the lab-type rule (the legacy split PCR
    and PoC by RequestID digits). ✱7 pending reads FinalResult.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.RegisteredDateTime)
    try:
        query = EIDMaster.query.with_entities(
            *month_cols,
            _total("registered"),
            _count(tested_condition(), "tested"),
            _count(rejected_condition(), "rejected"),
            _count(pending_condition(), "pending"),
        ).filter(and_(*_base_filters(params, EIDMaster.RegisteredDateTime)))
        return [
            dict(**_month_keys(row), registered=row.registered, tested=row.tested,
                 rejected=row.rejected, pending=row.pending)
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 2. summary/positivity/   (dash/samples_positivity)
# ---------------------------------------------------------------------------
def summary_positivity_service(req_args):
    """Monthly tested, results and positivity, by analysis month.

    Legacy: AnalysisDateTime window and month, ``HL7ResultStatusCode = 'F'``,
    tested = every such row. ✱7 results read FinalResult; the conventional
    and PoC positives use the lab-type rule. ✱3 ``positivity`` is
    positive ÷ tested (percent), not conventional ÷ total.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.AnalysisDateTime)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime)
    filters.append(EIDMaster.HL7ResultStatusCode == "F")
    try:
        query = EIDMaster.query.with_entities(
            *month_cols,
            _total("tested"),
            result_count("positive", "positive"),
            result_count("negative", "negative"),
            result_count("indeterminate", "indeterminate"),
            _count(and_(_is_positive(), conventional_condition()), "conventional_positive"),
            _count(and_(_is_positive(), poc_condition()), "poc_positive"),
        ).filter(and_(*filters))
        return [
            dict(**_month_keys(row), tested=row.tested, positive=row.positive,
                 negative=row.negative, indeterminate=row.indeterminate,
                 conventional_positive=row.conventional_positive,
                 poc_positive=row.poc_positive,
                 positivity=_positivity(row.positive, row.tested))
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 3. summary/indicators_by_province/   (dash/indicators_by_province)
# ---------------------------------------------------------------------------
def summary_indicators_by_province_service(req_args):
    """Per requesting province: registered, tested, rejected, pending,
    conventional, poc, positive and positivity.

    Legacy: RegisteredDateTime window, RequestingProvinceName not NULL,
    conventional = ``IsPoc = 'No'``, poc = ``IsPoc = 'Yes'`` (this legacy
    route split on IsPoc only). ✱7 positive and pending read FinalResult.
    ``positivity`` = positive ÷ tested (percent).
    """
    params = parse_eid_params(req_args)
    filters = _base_filters(params, EIDMaster.RegisteredDateTime, with_lab_type=False)
    filters.append(EIDMaster.RequestingProvinceName.is_not(None))
    try:
        rows = (
            EIDMaster.query.with_entities(
                EIDMaster.RequestingProvinceName.label("province"),
                _total("registered"),
                _count(tested_condition(), "tested"),
                _count(rejected_condition(), "rejected"),
                _count(pending_condition(), "pending"),
                _count(EIDMaster.IsPoc == "No", "conventional"),
                _count(EIDMaster.IsPoc == "Yes", "poc"),
                result_count("positive", "positive"),
            )
            .filter(and_(*filters))
            .group_by(EIDMaster.RequestingProvinceName)
            .order_by(EIDMaster.RequestingProvinceName)
            .all()
        )
        return [
            dict(province=row.province, registered=row.registered, tested=row.tested,
                 rejected=row.rejected, pending=row.pending,
                 conventional=row.conventional, poc=row.poc, positive=row.positive,
                 positivity=_positivity(row.positive, row.tested))
            for row in rows
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 4. summary/tat/   (dash/pcr/tat)
# ---------------------------------------------------------------------------
def summary_tat_service(req_args):
    """Monthly average days of the six TAT segments, by analysis month.

    Legacy: AnalysisDateTime window and month, ``tat_filters("summary")``
    (conventional only by ``IsPoc = 'No'``), integer averages, no
    zero-as-one.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.AnalysisDateTime)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime, with_lab_type=False)
    filters += tat_filters("summary")
    try:
        query = EIDMaster.query.with_entities(
            *month_cols, *tat_averages(zero_as_one=False)
        ).filter(and_(*filters))
        return [
            dict(**_month_keys(row), **{key: getattr(row, key) for key in _TAT_KEYS})
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 5. summary/tat_samples/   (dash/pcr/tat_samples)
# ---------------------------------------------------------------------------
def summary_tat_samples_service(req_args):
    """Monthly day brackets of TAT segment ``category`` (0-5), by analysis month.

    Legacy: AnalysisDateTime window and month,
    ``tat_filters("summary_tat_samples")``; brackets <7, 7-15, 16-21, >21 and
    no dates.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.AnalysisDateTime)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime, with_lab_type=False)
    filters += tat_filters("summary_tat_samples")
    segment = TAT_SEGMENTS[params.category][0]
    try:
        query = EIDMaster.query.with_entities(
            *month_cols, *tat_bracket_counts(params.category)
        ).filter(and_(*filters))
        return [
            dict(**_month_keys(row), category=segment,
                 **{key: getattr(row, key) for key in _BRACKET_KEYS})
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 6. summary/rejected_samples_by_month/   (dash/rejected_samples_monthly)
# ---------------------------------------------------------------------------
def summary_rejected_samples_by_month_service(req_args):
    """Monthly rejected samples by reason (9 buckets) and ``total``.

    Legacy: RegisteredDateTime window and month, ``IsPoc = 'No'``; reasons
    of the default variant (REJOL and PRTLA count as ``other``). ``total``
    counts every rejected row (code or description), as the indicators'
    ``rejected``; a row rejected by description only is in no reason.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.RegisteredDateTime)
    filters = _base_filters(params, EIDMaster.RegisteredDateTime, with_lab_type=False)
    filters += [rejected_condition(), EIDMaster.IsPoc == "No"]
    try:
        query = EIDMaster.query.with_entities(
            *month_cols, *rejection_reason_counts("default"), _total("total")
        ).filter(and_(*filters))
        return [
            dict(**_month_keys(row), **{key: getattr(row, key) for key in _REJECTION_KEYS},
                 total=row.total)
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 7. summary/samples_by_equipment_by_month/   (dash/samples_by_equipment_monthly)
# ---------------------------------------------------------------------------
def summary_samples_by_equipment_by_month_service(req_args):
    """Monthly tested samples per analyzer group, by analysis month.

    Legacy: AnalysisDateTime window and month, ``HL7ResultStatusCode = 'F'``,
    ``IsPoc = 'No'``, no PBC exclusion.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.AnalysisDateTime)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime, with_lab_type=False)
    filters += equipment_filters(exclude_pbc=False)
    try:
        query = EIDMaster.query.with_entities(*month_cols, *equipment_counts()).filter(
            and_(*filters)
        )
        return [
            dict(**_month_keys(row), tested=row.tested,
                 **{key: getattr(row, key) for key in _EQUIPMENT_KEYS})
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Routes no card uses (kept registered, on the same rules)
# ---------------------------------------------------------------------------
def summary_samples_by_equipment_service(req_args):
    """Tested samples per analyzer group, per testing lab (dash/samples_by_equipment).

    Legacy: AnalysisDateTime window, ``HL7ResultStatusCode = 'F'``,
    ``IsPoc = 'No'``, no PBC exclusion, grouped by TestingFacilityName.
    """
    params = parse_eid_params(req_args)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime, with_lab_type=False)
    filters += equipment_filters(exclude_pbc=False)
    try:
        rows = (
            EIDMaster.query.with_entities(
                EIDMaster.TestingFacilityName.label("testing_facility"), *equipment_counts()
            )
            .filter(and_(*filters))
            .group_by(EIDMaster.TestingFacilityName)
            .order_by(EIDMaster.TestingFacilityName)
            .all()
        )
        return [
            dict(testing_facility=row.testing_facility, tested=row.tested,
                 **{key: getattr(row, key) for key in _EQUIPMENT_KEYS})
            for row in rows
        ]
    except Exception as e:
        return _error(e)


def summary_number_of_samples_service(req_args):
    """Monthly ``total``, ``conventional`` and ``poc`` samples
    (dash/pcr/number_of_samples + dash/poc/number_of_samples).

    Legacy: AnalysisDateTime window, grouped by the registration month.
    ✱6 conventional/PoC use the lab-type rule (the legacy PCR route split by
    RequestID digits); ``lab_type`` filters the rows.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.RegisteredDateTime)
    try:
        query = EIDMaster.query.with_entities(
            *month_cols,
            _total("total"),
            _count(conventional_condition(), "conventional"),
            _count(poc_condition(), "poc"),
        ).filter(and_(*_base_filters(params, EIDMaster.AnalysisDateTime)))
        return [
            dict(**_month_keys(row), total=row.total, conventional=row.conventional,
                 poc=row.poc)
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


def summary_samples_positivity_service(req_args):
    """Single row: tested, results and results by sex.

    No legacy route; same base as ``summary/positivity/`` (AnalysisDateTime
    window, ``HL7ResultStatusCode = 'F'``, ``lab_type``). ✱7 FinalResult;
    sex from HL7SexCode F / M.
    """
    params = parse_eid_params(req_args)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime)
    filters.append(EIDMaster.HL7ResultStatusCode == "F")
    negative = EIDMaster.FinalResult.in_(RESULT_VALUES["negative"])
    female = EIDMaster.HL7SexCode == "F"
    male = EIDMaster.HL7SexCode == "M"
    try:
        row = (
            EIDMaster.query.with_entities(
                _total("tested"),
                result_count("positive", "positive"),
                result_count("negative", "negative"),
                result_count("indeterminate", "indeterminate"),
                _count(and_(female, _is_positive()), "female_positive"),
                _count(and_(male, _is_positive()), "male_positive"),
                _count(and_(female, negative), "female_negative"),
                _count(and_(male, negative), "male_negative"),
            )
            .filter(and_(*filters))
            .one()
        )
        return dict(
            tested=row.tested, positive=row.positive, negative=row.negative,
            indeterminate=row.indeterminate,
            female_positive=row.female_positive, male_positive=row.male_positive,
            female_negative=row.female_negative, male_negative=row.male_negative,
        )
    except Exception as e:
        return _error(e)
