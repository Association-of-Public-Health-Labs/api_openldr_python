"""
HIV VL summary (Sumário) services.

Each function matches one legacy Node dashboard endpoint (named in its
docstring); the counting rules come from hiv/vl/services/vl_common.py.
"""
import json
from pathlib import Path

from sqlalchemy import and_, func

from hiv.vl.models.vl import VlData
from hiv.vl.services.vl_common import (
    date_between,
    has_result,
    non_validated_count,
    not_suppressed_count,
    parse_vl_params,
    rejected_count,
    requesting_location_filters,
    suppressed_count,
    tat_averages,
    tat_filters,
    test_reason_counts,
    tested_count,
    testing_location_filters,
    year_month_columns,
)
from utilities.utils import TOTAL_ALL

_TAT_VS_DISALINKS_FILE = Path(__file__).resolve().parent.parent / "data" / "tat_vs_disalinks.json"


def _error(e):
    return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


def _monthly(query, month_cols):
    return query.group_by(*month_cols).order_by(month_cols[0], month_cols[1]).all()


# ---------------------------------------------------------------------------
# 1. header_indicators_service_by_month
# ---------------------------------------------------------------------------
def header_indicators_service_by_month(req_args):
    """Single-row totals: registered, tested, suppressed, not_suppressed, rejected."""
    params = parse_vl_params(req_args)
    filters = [
        date_between(VlData.RegisteredDateTime, params.dates),
        *testing_location_filters(params),
    ]
    try:
        row = (
            VlData.query.with_entities(
                func.count().label("registered"),
                tested_count(),
                suppressed_count(),
                not_suppressed_count(),
                rejected_count(),
            )
            .filter(and_(*filters))
            .one()
        )
        return dict(
            registered=row.registered,
            tested=row.tested,
            suppressed=row.suppressed,
            not_suppressed=row.not_suppressed,
            rejected=row.rejected,
            facilities=params.facilities,
            start_date=params.dates[0],
            end_date=params.dates[1],
        )
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 2. number_of_samples_service_by_month   (legacy /dash_number_of_samples)
# ---------------------------------------------------------------------------
def number_of_samples_service_by_month(req_args):
    """Samples analysed per month (every row with an AnalysisDateTime in range)."""
    params = parse_vl_params(req_args)
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *testing_location_filters(params),
    ]
    try:
        data = _monthly(
            VlData.query.with_entities(*month_cols, TOTAL_ALL).filter(and_(*filters)),
            month_cols,
        )
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                total=row.total,
                start_date=params.dates[0], end_date=params.dates[1],
                facilities=params.facilities,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 3. viral_suppression_service_by_month   (legacy /dash_viral_suppression)
# ---------------------------------------------------------------------------
def viral_suppression_service_by_month(req_args):
    """Monthly suppression; total = rows with a non-empty result category."""
    params = parse_vl_params(req_args)
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        has_result(),
        *testing_location_filters(params),
    ]
    try:
        data = _monthly(
            VlData.query.with_entities(
                *month_cols, TOTAL_ALL, suppressed_count(), not_suppressed_count()
            ).filter(and_(*filters)),
            month_cols,
        )
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                total=row.total,
                suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
                start_date=params.dates[0], end_date=params.dates[1],
                facilities=params.facilities,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 4. tat_service_by_month   (legacy /dash_tat)
# ---------------------------------------------------------------------------
def tat_service_by_month(req_args):
    """National TAT per month; ✱ no 90-day cap (Node's cap never applied)."""
    params = parse_vl_params(req_args)
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *tat_filters(),
        *testing_location_filters(params),
    ]
    try:
        data = _monthly(
            VlData.query.with_entities(*month_cols, *tat_averages()).filter(and_(*filters)),
            month_cols,
        )
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                collection_reception=row.collection_reception,
                reception_registration=row.reception_registration,
                registration_analysis=row.registration_analysis,
                analysis_validation=row.analysis_validation,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 5. suppression_by_province_service_by_month   (legacy /dash_map)
# ---------------------------------------------------------------------------
def suppression_by_province_service_by_month(req_args):
    """Suppression and test reasons per requesting province (map card)."""
    params = parse_vl_params(req_args)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        has_result(),
        *requesting_location_filters(params, exclude_null_province=False),
    ]
    try:
        data = (
            VlData.query.with_entities(
                VlData.RequestingProvinceName.label("province"),
                TOTAL_ALL,
                suppressed_count(),
                not_suppressed_count(),
                *test_reason_counts(),
            )
            .filter(and_(*filters))
            .group_by(VlData.RequestingProvinceName)
            .order_by(VlData.RequestingProvinceName)
            .all()
        )
        return [
            dict(
                province=row.province,
                total=row.total,
                suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
                routine=row.routine,
                treatment_failure=row.treatment_failure,
                reason_not_specified=row.reason_not_specified,
                start_date=params.dates[0], end_date=params.dates[1],
                facilities=params.facilities,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 6. samples_history_service_by_month   (legacy /dash_indicators)
# ---------------------------------------------------------------------------
def samples_history_service_by_month(req_args):
    """Monthly indicators table, grouped by registration month."""
    params = parse_vl_params(req_args)
    month_cols = year_month_columns(VlData.RegisteredDateTime)
    filters = [
        date_between(VlData.RegisteredDateTime, params.dates),
        *testing_location_filters(params),
    ]
    try:
        data = _monthly(
            VlData.query.with_entities(
                *month_cols,
                func.count().label("registered"),
                tested_count(),
                suppressed_count(),
                rejected_count(),
                non_validated_count(),
            ).filter(and_(*filters)),
            month_cols,
        )
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                registered=row.registered,
                tested=row.tested,
                suppressed=row.suppressed,
                rejected=row.rejected,
                non_validated=row.non_validated,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 7. tat_vs_disalinks_service   (legacy /dash_tat_vs_disalinks)
# ---------------------------------------------------------------------------
def tat_vs_disalinks_service(req_args):
    """Static TAT vs Disa*Link counts per semester, copied from the legacy API."""
    with _TAT_VS_DISALINKS_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)
