"""
HIV VL facility (Província/Distrito/US) services.

Location filters use the Requesting* columns. With no location given, rows
whose RequestingProvinceName is NULL or the text 'null' are excluded, as in
Node, except on the two monthly "tested" services (Node has no default
there). Counting rules come from hiv/vl/services/vl_common.py.
"""
from sqlalchemy import and_, case, func

from db.database import db
from hiv.vl.models.vl import VlData
from hiv.vl.services.vl_common import (
    age_range_filters,
    breastfeeding_filter,
    date_between,
    date_between_inclusive,
    not_suppressed_count,
    parse_vl_params,
    pregnant_filter,
    rejected_condition,
    requesting_group_column,
    requesting_location_filters,
    suppressed_count,
    tat_averages,
    tat_filters,
    test_reason_counts,
    year_month_columns,
)
from utilities.auth_helpers import check_admin_access, get_user_role as _get_user_role
from utilities.utils import GENDER_SUPPRESSION, TOTAL_ALL, TOTAL_NOT_NULL, TOTAL_NULL


def _error(e):
    return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


def _facility_level_forbidden(req_args, params):
    """Single-facility aggregates (facility_type=health_facility) are Admin-only."""
    if params.facility_type != "health_facility":
        return None
    user_id, user_role = _get_user_role(req_args)
    return check_admin_access(user_id, user_role)


def _suppression_entities():
    return [suppressed_count(), not_suppressed_count()]


def _gender_suppression_entities():
    return [
        GENDER_SUPPRESSION([VlData.ViralLoadResultCategory, VlData.HL7SexCode], ["Suppressed", "M"]).label("male_suppressed"),
        GENDER_SUPPRESSION([VlData.ViralLoadResultCategory, VlData.HL7SexCode], ["Not Suppressed", "M"]).label("male_not_suppressed"),
        GENDER_SUPPRESSION([VlData.ViralLoadResultCategory, VlData.HL7SexCode], ["Suppressed", "F"]).label("female_suppressed"),
        GENDER_SUPPRESSION([VlData.ViralLoadResultCategory, VlData.HL7SexCode], ["Not Suppressed", "F"]).label("female_not_suppressed"),
    ]


def _totals_entities():
    return [
        TOTAL_ALL,
        TOTAL_NOT_NULL(VlData.ViralLoadResultCategory).label("total_not_null"),
        TOTAL_NULL(VlData.ViralLoadResultCategory).label("total_null"),
    ]


def _gender_values(row):
    return dict(
        male_suppressed=row.male_suppressed,
        male_not_suppressed=row.male_not_suppressed,
        female_suppressed=row.female_suppressed,
        female_not_suppressed=row.female_not_suppressed,
    )


def _tat_values(row):
    return dict(
        collection_reception=row.collection_reception,
        reception_registration=row.reception_registration,
        registration_analysis=row.registration_analysis,
        analysis_validation=row.analysis_validation,
    )


def _window(params):
    return dict(start_date=params.dates[0], end_date=params.dates[1])


def _age_group():
    return case(
        (VlData.AgeInYears.between(0, 14), "0-14"),
        (VlData.AgeInYears.between(15, 19), "15-19"),
        (VlData.AgeInYears.between(20, 24), "20-24"),
        (VlData.AgeInYears.between(25, 29), "25-29"),
        (VlData.AgeInYears.between(30, 34), "30-34"),
        (VlData.AgeInYears.between(35, 39), "35-39"),
        (VlData.AgeInYears.between(40, 44), "40-44"),
        (VlData.AgeInYears.between(45, 49), "45-49"),
        (VlData.AgeInYears >= 50, "50+"),
        else_="Unknown",
    ).label("age_group")


def _by_group(params, filters, *entities):
    group_col = requesting_group_column(params)
    return (
        VlData.query.with_entities(group_col.label("requesting_facility"), *entities)
        .filter(and_(*filters))
        .group_by(group_col)
        .order_by(group_col)
        .all()
    )


def _by_month(month_cols, filters, *entities):
    return (
        VlData.query.with_entities(*month_cols, *entities)
        .filter(and_(*filters))
        .group_by(*month_cols)
        .order_by(month_cols[0], month_cols[1])
        .all()
    )


# ---------------------------------------------------------------------------
# 1. facility_registered_samples_service   (legacy /clinic_registered_samples_by_facility)
# ---------------------------------------------------------------------------
def facility_registered_samples_service(req_args):
    """Registered samples per location (registration date)."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    filters = [
        date_between(VlData.RegisteredDateTime, params.dates),
        *requesting_location_filters(params),
    ]
    try:
        data = _by_group(params, filters, *_suppression_entities(),
                         *_gender_suppression_entities(), *_totals_entities())
        return [
            dict(
                requesting_facility=row.requesting_facility,
                total=row.total, total_not_null=row.total_not_null,
                total_null=row.total_null, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
                **_gender_values(row), **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 2. facility_tested_samples_by_month_service   (legacy /clinic_samples_tested_by_month)
# ---------------------------------------------------------------------------
def facility_tested_samples_by_month_service(req_args):
    """Tested samples per month (no 'null' province default, as in Node)."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *requesting_location_filters(params, exclude_null_province=False),
    ]
    try:
        data = _by_month(month_cols, filters, *_suppression_entities(),
                         *_gender_suppression_entities(), *_totals_entities())
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                total=row.total, total_not_null=row.total_not_null,
                total_null=row.total_null, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
                **_gender_values(row), **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 3. facility_tested_samples_by_facility_service   (legacy /clinic_samples_tested_by_facility)
# ---------------------------------------------------------------------------
def facility_tested_samples_by_facility_service(req_args):
    """Tested samples per location (analysis date)."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *requesting_location_filters(params),
    ]
    try:
        data = _by_group(params, filters, *_suppression_entities(), *_totals_entities())
        return [
            dict(
                requesting_facility=row.requesting_facility,
                total=row.total, total_not_null=row.total_not_null,
                total_null=row.total_null, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 4. facility_tested_samples_by_month_by_gender_service   (legacy /clinic_samples_tested_by_gender)
# ---------------------------------------------------------------------------
def facility_tested_samples_by_month_by_gender_service(req_args):
    """Tested samples per month by sex (no 'null' province default, as in Node)."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *requesting_location_filters(params, exclude_null_province=False),
    ]
    try:
        data = _by_month(month_cols, filters, TOTAL_ALL, *_gender_suppression_entities())
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                total=row.total, **_gender_values(row), **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 5. facility_tested_samples_by_gender_by_facility_service
#    (legacy /clinic_samples_tested_by_gender_and_facility)
# ---------------------------------------------------------------------------
def facility_tested_samples_by_gender_by_facility_service(req_args):
    """Tested samples per location by sex (one row per location)."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *requesting_location_filters(params),
    ]
    try:
        data = _by_group(params, filters, TOTAL_ALL, *_gender_suppression_entities())
        return [
            dict(
                requesting_facility=row.requesting_facility,
                total=row.total, **_gender_values(row), **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 6. facility_tested_samples_by_age_by_month_service   (legacy /clinic_samples_tested_by_age)
# ---------------------------------------------------------------------------
def facility_tested_samples_by_age_by_month_service(req_args):
    """Tested samples per month and age group; optional age_range filter."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *requesting_location_filters(params),
        *age_range_filters(params),
    ]
    try:
        # Subquery: SQL Server cannot GROUP BY a parameterised CASE directly.
        subq = (
            db.session.query(
                VlData.AnalysisDateTime.label("analysis"),
                VlData.ViralLoadResultCategory.label("category"),
                _age_group(),
            )
            .filter(and_(*filters))
            .subquery()
        )
        month_cols = year_month_columns(subq.c.analysis)
        data = (
            db.session.query(
                *month_cols,
                subq.c.age_group,
                func.count().label("total"),
                suppressed_count(column=subq.c.category),
                not_suppressed_count(column=subq.c.category),
            )
            .group_by(*month_cols, subq.c.age_group)
            .order_by(month_cols[0], month_cols[1], subq.c.age_group)
            .all()
        )
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                age_group=row.age_group, total=row.total,
                suppressed=row.suppressed, not_suppressed=row.not_suppressed,
                **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 7. facility_tested_samples_by_age_by_facility_service
#    (legacy /clinic_samples_tested_by_age_and_facility)
# ---------------------------------------------------------------------------
def facility_tested_samples_by_age_by_facility_service(req_args):
    """Tested samples per location and age group; optional age_range filter.

    Node returned one row per location for the selected age range; here
    the rows are split by age group and the dashboard sums them.
    """
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    group_col = requesting_group_column(params)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *requesting_location_filters(params),
        *age_range_filters(params),
    ]
    try:
        subq = (
            db.session.query(
                group_col.label("requesting_facility"),
                VlData.ViralLoadResultCategory.label("category"),
                _age_group(),
            )
            .filter(and_(*filters))
            .subquery()
        )
        data = (
            db.session.query(
                subq.c.requesting_facility,
                subq.c.age_group,
                func.count().label("total"),
                suppressed_count(column=subq.c.category),
                not_suppressed_count(column=subq.c.category),
            )
            .group_by(subq.c.requesting_facility, subq.c.age_group)
            .order_by(subq.c.requesting_facility, subq.c.age_group)
            .all()
        )
        return [
            dict(
                requesting_facility=row.requesting_facility,
                age_group=row.age_group, total=row.total,
                suppressed=row.suppressed, not_suppressed=row.not_suppressed,
                **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 8. facility_tested_samples_by_test_reason_by_month_service
# ---------------------------------------------------------------------------
def facility_tested_samples_by_test_reason_by_month_service(req_args):
    """Tested samples per month by reason for test."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *requesting_location_filters(params),
    ]
    try:
        data = _by_month(month_cols, filters, *test_reason_counts(), TOTAL_ALL)
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                routine=row.routine, treatment_failure=row.treatment_failure,
                reason_not_specified=row.reason_not_specified, total=row.total,
                **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 9. facility_tested_samples_by_test_reason_by_facility_service
#    (legacy /clinic_samples_by_test_reason, summed by the dashboard)
# ---------------------------------------------------------------------------
def facility_tested_samples_by_test_reason_by_facility_service(req_args):
    """Tested samples per location by reason for test."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *requesting_location_filters(params),
    ]
    try:
        data = _by_group(params, filters, *test_reason_counts(), TOTAL_ALL)
        return [
            dict(
                requesting_facility=row.requesting_facility,
                routine=row.routine, treatment_failure=row.treatment_failure,
                reason_not_specified=row.reason_not_specified, total=row.total,
                **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 10/11. pregnant and breastfeeding women, per month
# ---------------------------------------------------------------------------
def _special_population_by_month(req_args, population_filter):
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        population_filter,
        *requesting_location_filters(params),
    ]
    try:
        data = _by_month(month_cols, filters, *_suppression_entities(), TOTAL_ALL)
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                total=row.total, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed, **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


def facility_tested_samples_pregnant_service(req_args):
    """Tested samples for pregnant women per month."""
    return _special_population_by_month(req_args, pregnant_filter())


def facility_tested_samples_breastfeeding_service(req_args):
    """Tested samples for breastfeeding women per month."""
    return _special_population_by_month(req_args, breastfeeding_filter())


# ---------------------------------------------------------------------------
# 12/13. rejected samples   (legacy /clinic_samples_rejected_by_month, _by_facility)
# ---------------------------------------------------------------------------
def _rejection_filters(params):
    """✱ Either rejection code (Node required both) and an inclusive
    registration-date window (Node's BETWEEN dropped most of the end day)."""
    return [
        rejected_condition(),
        date_between_inclusive(VlData.RegisteredDateTime, params.dates),
        *requesting_location_filters(params),
    ]


def facility_rejected_samples_by_month_service(req_args):
    """Rejected samples per registration month."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    month_cols = year_month_columns(VlData.RegisteredDateTime)
    try:
        data = _by_month(month_cols, _rejection_filters(params), TOTAL_ALL)
        return [
            dict(year=row.year, month=row.month, month_name=row.month_name,
                 total=row.total, **_window(params))
            for row in data
        ]
    except Exception as e:
        return _error(e)


def facility_rejected_samples_by_facility_service(req_args):
    """Rejected samples per location."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    try:
        data = _by_group(params, _rejection_filters(params), TOTAL_ALL)
        return [
            dict(requesting_facility=row.requesting_facility, total=row.total, **_window(params))
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 14/15. turnaround time   (legacy /clinic_tat, /clinic_tat_by_facility)
# ---------------------------------------------------------------------------
def _tat_filter_list(params):
    return [
        date_between(VlData.AnalysisDateTime, params.dates),
        *tat_filters(),
        *requesting_location_filters(params),
    ]


def facility_tat_by_month_service(req_args):
    """TAT per month; ✱ no 90-day cap (Node's cap never applied)."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    try:
        data = _by_month(month_cols, _tat_filter_list(params), *tat_averages())
        return [
            dict(year=row.year, month=row.month, month_name=row.month_name, **_tat_values(row))
            for row in data
        ]
    except Exception as e:
        return _error(e)


def facility_tat_by_facility_service(req_args):
    """TAT per location; ✱ no 90-day cap (Node's cap never applied)."""
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    try:
        data = _by_group(params, _tat_filter_list(params), *tat_averages())
        return [
            dict(requesting_facility=row.requesting_facility, **_tat_values(row), **_window(params))
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 16/17. pregnant and breastfeeding women, per location
#        (legacy /clinic_tests_by_pregnancy, /clinic_tests_by_breastfeeding)
# ---------------------------------------------------------------------------
def _special_population_by_facility(req_args, population_filter):
    params = parse_vl_params(req_args)
    forbidden = _facility_level_forbidden(req_args, params)
    if forbidden:
        return forbidden
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        population_filter,
        *requesting_location_filters(params),
    ]
    try:
        data = _by_group(params, filters, TOTAL_ALL, *_suppression_entities())
        return [
            dict(
                requesting_facility=row.requesting_facility,
                total=row.total, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed, **_window(params),
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


def facility_tested_samples_pregnant_by_facility_service(req_args):
    """Tested samples for pregnant women per location."""
    return _special_population_by_facility(req_args, pregnant_filter())


def facility_tested_samples_breastfeeding_by_facility_service(req_args):
    """Tested samples for breastfeeding women per location."""
    return _special_population_by_facility(req_args, breastfeeding_filter())
