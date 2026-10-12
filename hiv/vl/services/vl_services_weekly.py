"""
Weekly VL lab reports read from ReportData.Resume (legacy /lab_weekly_report
and /lab_weekly_report_national).

The window filters on the week's start_date, both ends inclusive. Without
interval_dates, the per-lab report shows the current Sunday-Saturday week and
the national report the last 12 weeks, as in Node.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func

from db.database import db
from hiv.vl.models.report_data import Resume
from hiv.vl.services.vl_common import date_between_inclusive, parse_vl_params
from utilities.service_helpers import InvalidParameter


def _today():
    return date.today()


def current_week(today):
    """Sunday..Saturday of the week containing ``today``."""
    start = today - timedelta(days=(today.weekday() + 1) % 7)
    return [start.isoformat(), (start + timedelta(days=6)).isoformat()]


def last_12_weeks(today):
    return [(today - timedelta(weeks=12)).isoformat(), today.isoformat()]


def _day(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat() if value is not None else None


def _resume_rows(req_args, by_lab, default_window):
    params = parse_vl_params(req_args)
    dates = params.dates if req_args.get("interval_dates") else default_window(_today())

    keys = [Resume.week, Resume.start_date, Resume.end_date]
    if by_lab:
        keys = [Resume.labcode, Resume.labname, *keys]

    filters = [date_between_inclusive(Resume.start_date, dates)]
    if params.lab_codes:
        filters.append(Resume.labcode.in_(params.lab_codes))

    return (
        db.session.query(
            *keys,
            func.sum(Resume.backlogs).label("backlogs"),
            func.sum(Resume.tests).label("tests"),
            func.sum(Resume.registered).label("registrations"),
            func.sum(Resume.rejected).label("rejections"),
            func.sum(Resume.capacity).label("capacity"),
            func.avg(Resume.tat).label("tat"),
        )
        .filter(*filters)
        .group_by(*keys)
        .order_by(Resume.start_date)
        .all()
    )


def _figures(row):
    return dict(
        week=row.week,
        start=_day(row.start_date),
        end=_day(row.end_date),
        backlogs=row.backlogs,
        tests=row.tests,
        registrations=row.registrations,
        rejections=row.rejections,
        capacity=row.capacity,
        tat=float(row.tat) if row.tat is not None else None,
    )


def _error(e):
    return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


def weekly_report_service(req_args):
    """One row per lab and week."""
    try:
        rows = _resume_rows(req_args, by_lab=True, default_window=current_week)
    except InvalidParameter:
        raise
    except Exception as e:
        return _error(e)
    return [dict(lab_code=row.labcode, lab_name=row.labname, **_figures(row)) for row in rows]


def weekly_report_national_service(req_args):
    """One row per week (tat is the unweighted mean of the lab TATs, as in Node)."""
    try:
        rows = _resume_rows(req_args, by_lab=False, default_window=last_12_weeks)
    except InvalidParameter:
        raise
    except Exception as e:
        return _error(e)
    return [_figures(row) for row in rows]
