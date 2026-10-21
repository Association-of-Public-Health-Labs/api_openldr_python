"""
Transport TAT of VL and EID samples (collection at the health facility → reception at the lab),
read from ReportData's weekly tables, the source of the CV/EID weekly spreadsheets' "Tempo de
Transporte" sheet (api-weekly-reports-python). Same rows, same filters, so the dashboard and the
spreadsheet agree:

- a week counts when it lies inside the window: start >= window start and end <= window end;
- rows without a requesting health facility are left out (the spreadsheet drops them too);
- only Sunday–Saturday rows: the VL table holds two extra windows (1–6 and 13–19 June 2026) from
  extra ETL runs, which repeat samples of the regular weeks;
- one row per facility, lab, type of test and week, the most recent: for some facilities the ETL
  inserts a new copy on every 8-hourly run instead of updating it (13 869 extra VL rows, ~68 000
  samples counted twice or more, by October 2026). The spreadsheet's query keeps the copies.

The intervals are the spreadsheet's "Colheita à Recepção no Lab" columns (<7, 7–15, 16–21, >21
days, and no reception date). EID also has the total tested; VL's table has no such column.
"""
from collections import namedtuple
from datetime import date, timedelta

from sqlalchemy import and_, cast, func, literal, literal_column
from sqlalchemy.dialects.mssql import DATE

from db.database import db
from hiv.vl.services.vl_common import split_values
from utilities.service_helpers import InvalidParameter

LEVELS = ("province", "district", "health_facility")
TYPES_OF_TEST = ("Convencional", "Point-of-care")

# Weeks on the dashboard's chart and week picker when no window is given.
DEFAULT_WEEKS = 28

TransportParams = namedtuple("TransportParams", "dates level provinces districts health_facility type_of_test")

# 7 January 1900 was a Sunday: a start date a multiple of 7 days after it is a Sunday too, whatever
# the server's DATEFIRST setting (which DATEPART(weekday) depends on).
_A_SUNDAY = "1900-01-07"


def _today():
    return date.today()


def last_complete_week(today):
    """Sunday–Saturday of the last week that has ended."""
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    start = sunday - timedelta(days=7)
    return [start.isoformat(), (start + timedelta(days=6)).isoformat()]


def recent_weeks(today, weeks=DEFAULT_WEEKS):
    """The last ``weeks`` complete Sunday–Saturday weeks."""
    start, end = last_complete_week(today)
    return [(date.fromisoformat(start) - timedelta(weeks=weeks - 1)).isoformat(), end]


def _dates(raw, default):
    values = split_values(raw)
    if not values:
        return default
    if len(values) != 2:
        raise InvalidParameter("interval_dates must be two YYYY-MM-DD dates: start,end")
    try:
        start, end = (date.fromisoformat(v) for v in values)
    except ValueError:
        raise InvalidParameter("interval_dates must be two YYYY-MM-DD dates: start,end") from None
    if start > end:
        raise InvalidParameter("interval_dates start must not be after end")
    return [start.isoformat(), end.isoformat()]


def parse_params(req_args, default_window):
    level = (req_args.get("facility_type") or "province").strip()
    if level not in LEVELS:
        raise InvalidParameter("facility_type must be province, district or health_facility")
    type_of_test = (req_args.get("type_of_test") or "").strip() or None
    if type_of_test and type_of_test not in TYPES_OF_TEST:
        raise InvalidParameter("type_of_test must be Convencional or Point-of-care")
    return TransportParams(
        dates=_dates(req_args.get("interval_dates"), default_window(_today())),
        level=level,
        provinces=split_values(req_args.get("province")),
        districts=split_values(req_args.get("district")),
        health_facility=(req_args.get("health_facility") or "").strip() or None,
        type_of_test=type_of_test,
    )


def _filters(model, params):
    facility = model.RequestingFacilityName
    filters = [
        facility.isnot(None),
        func.ltrim(func.rtrim(facility)) != "",
        model.TypeOfTest.isnot(None),
        func.datediff(literal_column("day"), model.start, model.end) == 6,
        func.datediff(literal_column("day"), literal(_A_SUNDAY), model.start) % 7 == 0,
        cast(model.start, DATE) >= params.dates[0],
        cast(model.end, DATE) <= params.dates[1],
    ]
    if params.provinces:
        filters.append(model.ProvinceName.in_(params.provinces))
    if params.districts:
        filters.append(model.DistrictName.in_(params.districts))
    if params.health_facility:
        filters.append(facility == params.health_facility)
    if params.type_of_test:
        filters.append(model.TypeOfTest == params.type_of_test)
    return and_(*filters)


# What a row says, under the names the queries below use.
_COUNT_COLUMNS = {
    "samples": "TestedSamplesWithCollectionDate",
    "lt_7": "collection_to_lab_reception_lt_7",
    "between_7_15": "collection_to_lab_reception_7_15",
    "between_16_21": "collection_to_lab_reception_16_21",
    "gt_21": "collection_to_lab_reception_gt_21",
    "no_reception_date": "collection_to_lab_reception_no_data",
}


def _latest_rows(model, params):
    """The window's rows, one per facility, lab, type of test and week: the most recently updated."""
    order = [model.updated.desc()]
    if hasattr(model, "id"):
        order.append(model.id.desc())
    copy = (
        func.row_number()
        .over(
            partition_by=[
                model.RequestingFacilityCode,
                model.RequestingFacilityName,
                model.TestingFacilityName,
                model.TypeOfTest,
                model.start,
                model.end,
            ],
            order_by=order,
        )
        .label("copy")
    )
    columns = [
        model.ProvinceName.label("province"),
        model.DistrictName.label("district"),
        model.RequestingFacilityName.label("health_facility"),
        model.FacilityNationalCode.label("facility_code"),
        model.start.label("start"),
        model.end.label("end"),
        *[getattr(model, column).label(name) for name, column in _COUNT_COLUMNS.items()],
    ]
    if hasattr(model, "TotalTestedSamples"):
        columns.append(model.TotalTestedSamples.label("total_tested"))
    return db.session.query(*columns, copy).filter(_filters(model, params)).subquery("latest")


def _sums(rows):
    names = [*_COUNT_COLUMNS, *(["total_tested"] if "total_tested" in rows.c else [])]
    return [func.sum(rows.c[name]).label(name) for name in names]


def _counts(row):
    n = lambda name: int(getattr(row, name, None) or 0)
    total = getattr(row, "total_tested", None)
    samples = n("samples")
    return dict(
        samples_with_collection_date=samples,
        lt_7=n("lt_7"),
        between_7_15=n("between_7_15"),
        between_16_21=n("between_16_21"),
        gt_21=n("gt_21"),
        no_reception_date=n("no_reception_date"),
        # EID only: VL's table holds just the samples with a collection date.
        total_tested=int(total) if total is not None else None,
        no_collection_date=int(total) - samples if total is not None else None,
    )


def _location_keys(rows, level):
    keys = [rows.c.province]
    if level in ("district", "health_facility"):
        keys.append(rows.c.district)
    if level == "health_facility":
        keys.append(rows.c.health_facility)
    return keys


def _location_columns(rows, level):
    # A facility is one row even when some weeks lack its national code (CS Morrumbene, Sep 2026):
    # grouped by name, with the code the table has.
    if level == "health_facility":
        return [func.max(func.ltrim(func.rtrim(rows.c.facility_code))).label("facility_code")]
    return []


def _error(e):
    return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


def tat_by_location(model, req_args):
    """One row per province, district or health facility (``facility_type``), summed over the window's weeks."""
    params = parse_params(req_args, last_complete_week)
    try:
        latest = _latest_rows(model, params)
        keys = _location_keys(latest, params.level)
        rows = (
            db.session.query(*keys, *_location_columns(latest, params.level), *_sums(latest))
            .filter(latest.c.copy == 1)
            .group_by(*keys)
            .order_by(*keys)
            .all()
        )
    except Exception as e:
        return _error(e)
    out = []
    for row in rows:
        place = dict(province=row.province)
        if params.level in ("district", "health_facility"):
            place["district"] = row.district
        if params.level == "health_facility":
            place["health_facility"] = row.health_facility
            place["facility_code"] = (row.facility_code or "").strip() or None
        out.append(dict(**place, start_date=params.dates[0], end_date=params.dates[1], **_counts(row)))
    return out


def _day(value):
    return value.date().isoformat() if hasattr(value, "date") else value.isoformat()


def tat_by_week(model, req_args):
    """One row per week for the area (country, or the given province / district / health facility)."""
    params = parse_params(req_args, recent_weeks)
    try:
        latest = _latest_rows(model, params)
        rows = (
            db.session.query(latest.c.start, latest.c.end, *_sums(latest))
            .filter(latest.c.copy == 1)
            .group_by(latest.c.start, latest.c.end)
            .order_by(latest.c.start)
            .all()
        )
    except Exception as e:
        return _error(e)
    return [dict(start_date=_day(row.start), end_date=_day(row.end), **_counts(row)) for row in rows]
