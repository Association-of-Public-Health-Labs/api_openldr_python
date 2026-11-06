import logging

from db.database import db
from usage.models import PatientAccessLog, UsageEvent
from utilities.permissions import dashboard_for_path

logger = logging.getLogger(__name__)

PAGE_MAX_LENGTH = 250


def clean_page(page):
    """The path only: no query string or fragment, trimmed, cut to the column width."""
    return page.split("?", 1)[0].split("#", 1)[0].strip()[:PAGE_MAX_LENGTH]


def record_page_view(user_id, dashboard, page):
    """Store one page view. Tracking never breaks the caller, so a failure is logged and swallowed."""
    try:
        db.session.add(UsageEvent(user_id=user_id, dashboard=dashboard, page=clean_page(page)))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Could not record page view for dashboard %s", dashboard)


_TB_FACILITY_PREFIXES = ("/tb/gx/facilities/", "/tb/gx/laboratories/")


def _values(args, name):
    """Non-empty string values of a query parameter. ``args`` may hold plain values or lists of them."""
    raw = args.get(name)
    if raw is None:
        return []
    items = raw if isinstance(raw, (list, tuple)) else [raw]
    return [str(v).strip() for v in items if v is not None and str(v).strip()]


def is_patient_request(path, args):
    """
    True when the endpoint returns patient rows: a ``/patients/`` route, or a TB facilities/laboratories
    route in its health-facility branch (a truthy ``health_facility``, or ``facility_type=health_facility``
    with no ``province`` and no ``district``; see docs/2026-11-05-role-check-audit.md).
    """
    if "/patients/" in path:
        return True
    if not path.startswith(_TB_FACILITY_PREFIXES):
        return False
    if _values(args, "health_facility"):
        return True
    facility_type = [v.lower() for v in _values(args, "facility_type")]
    return "health_facility" in facility_type and not _values(args, "province") and not _values(args, "district")


def count_rows(result):
    if isinstance(result, dict) and isinstance(result.get("data"), (list, tuple)):
        return len(result["data"])
    return len(result) if isinstance(result, (list, tuple)) else 0


def log_patient_access(user_id, path, row_count):
    """
    Store that a user opened patient rows: who, which dashboard and endpoint, how many rows. Never the
    query string, so search terms stay out. A failed write is logged at error level and swallowed:
    a users-database problem must not stop lab staff looking up a result.
    """
    try:
        db.session.add(PatientAccessLog(
            user_id=user_id,
            dashboard=dashboard_for_path(path) or "",
            endpoint=clean_page(path),
            row_count=row_count,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.error("Could not write patient access log for %s", clean_page(path), exc_info=True)
