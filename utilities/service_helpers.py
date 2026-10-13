from datetime import datetime

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, text


def default_interval_dates(months=12):
    """Return a fresh [start_date, end_date] window for each request."""
    current = datetime.now()
    return [
        (current - relativedelta(months=months)).strftime("%Y-%m-%d"),
        current.strftime("%Y-%m-%d"),
    ]


def coerce_interval_dates(raw_dates):
    """
    Normalize interval date inputs from reqparse.

    Supported shapes:
    - ["2024-01-01,2024-12-31"]
    - ["2024-01-01", "2024-12-31"]
    - "2024-01-01,2024-12-31"
    """
    if not raw_dates:
        return default_interval_dates()

    if isinstance(raw_dates, str):
        parts = [part.strip() for part in raw_dates.split(",") if part.strip()]
        return parts if len(parts) == 2 else default_interval_dates()

    if isinstance(raw_dates, (list, tuple)):
        if len(raw_dates) == 1 and isinstance(raw_dates[0], str):
            return coerce_interval_dates(raw_dates[0])
        parts = [str(part).strip() for part in raw_dates[:2] if str(part).strip()]
        return parts if len(parts) == 2 else default_interval_dates()

    return default_interval_dates()


def parse_bool(value, default=False):
    """Convert mixed string/bool inputs into a boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def clean_facilities(facilities):
    """Normalize facility inputs into a trimmed list."""
    if not facilities:
        return []
    if isinstance(facilities, str):
        facilities = [facilities]
    return [facility.strip() for facility in facilities if facility and facility.strip()]


def build_facility_filters(facilities, facility_type, field_map):
    """Build a single IN filter for the selected facility scope."""
    facilities = clean_facilities(facilities)
    column = field_map.get(facility_type)
    if not facilities or column is None:
        return []
    return [column.in_(facilities)]


def get_group_column(disaggregation, facility_type, base_map, nested_map):
    """Pick the correct grouping column for normal vs disaggregated responses."""
    if disaggregation:
        return nested_map.get(facility_type, base_map["province"])
    return base_map.get(facility_type, base_map["province"])


def year_month_group_order(date_field):
    """Return shared group_by/order_by columns for monthly aggregations."""
    columns = [
        func.year(date_field).label("year"),
        func.month(date_field),
        func.datename(text("month"), date_field),
    ]
    return columns, columns


def apply_lab_type_filter(filters, model, lab_type, resolver):
    """Append a lab type filter when the resolver yields one."""
    condition = resolver(model, lab_type)
    if condition is not None:
        filters.append(condition)


def get_user_role(req_args, user_lookup):
    """Resolve request user context without propagating lookup failures."""
    user_id = req_args.get("user_id")
    if user_id is None:
        return None, "Unknown"

    try:
        user = user_lookup(user_id)
    except Exception:
        return user_id, "Unknown"

    return user_id, user.role if user else "Unknown"


def build_error_response(error, message="An Error Occurred", code=500):
    """Standardize service-layer error payloads."""
    return {
        "status": "error",
        "code": code,
        "message": message,
        "error": str(error),
    }


class InvalidParameter(ValueError):
    """A query parameter the caller sent is malformed. Mapped to HTTP 400."""
