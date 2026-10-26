"""
Shared cache for the dashboards' default reports (the "last 12 months" window).

The VL and TB dashboards open on reports over the last 12 months; computing them on the full
database takes long, and every visitor asked for the same figures. Those responses are kept in
JSON files shared by the gunicorn workers and refreshed twice a day by ``tools/warm_report_cache.py``
(a Coolify scheduled task), so a visitor gets them at once. Anything else — another period, a
province / district / facility filter, a drill-down, patient lists — is computed live, as before.

Only aggregate reports are cached: their figures do not depend on who asks. Patient endpoints and
single-facility requests (Admin-only) never are.

Settings (environment):
    REPORT_CACHE_ENABLED     "0" turns the cache off (default on).
    REPORT_CACHE_DIR         where the files live (default /tmp/openldr-report-cache).
    REPORT_CACHE_MAX_AGE_HOURS  an entry older than this is recomputed on the next request (default 24),
                             a safety net if the warm-up stops running.
"""

import hashlib
import json
import logging
import os
import tempfile
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Report endpoints whose default views are cached.
CACHED_PREFIXES = ("/hiv/vl/", "/tb/gx/", "/hiv/eid/")

# Filters a user picks (places, labs): their requests stay live, which keeps the cache small.
USER_FILTERS = ("province", "district", "health_facility", "lab_code")

# How far a window's dates may drift from today's: the dashboards build them in the browser's
# timezone (TB through UTC), so near midnight they can be a day off.
TOLERANCE = timedelta(days=1)

YEAR = "year"  # same day last year -> today (VL, TB summary and facility pages)
MONTHS = "months"  # 1st of the month 11 months ago -> today (TB laboratory page)


# --------------------------------------------------------------------------- settings


def enabled():
    return os.environ.get("REPORT_CACHE_ENABLED", "1") != "0"


def cache_dir():
    return os.environ.get("REPORT_CACHE_DIR", os.path.join(tempfile.gettempdir(), "openldr-report-cache"))


def max_age():
    try:
        hours = float(os.environ.get("REPORT_CACHE_MAX_AGE_HOURS", "24"))
    except ValueError:
        hours = 24.0
    return timedelta(hours=hours)


# --------------------------------------------------------------------------- default windows


def _year_ago(today):
    """Same day last year; 29 February falls back to the 28th (as the dashboards do)."""
    try:
        return today.replace(year=today.year - 1)
    except ValueError:
        return today.replace(year=today.year - 1, day=28)


def _months_ago_first(today, months=11):
    month = today.month - months
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def window_dates(kind, today=None):
    """The (start, end) of a default window for ``today``."""
    today = today or date.today()
    start = _year_ago(today) if kind == YEAR else _months_ago_first(today)
    return start, today


def window_param(kind, today=None):
    start, end = window_dates(kind, today)
    return f"{start.isoformat()},{end.isoformat()}"


def _parse_interval(values):
    """``["2025-10-21,2026-10-21"]`` (or two separate values) -> (start, end); None if not that shape."""
    parts = []
    for value in values or []:
        parts.extend(p.strip() for p in str(value).split(",") if p.strip())
    if len(parts) != 2:
        return None
    try:
        return date.fromisoformat(parts[0]), date.fromisoformat(parts[1])
    except ValueError:
        return None


def default_window(values, today=None):
    """Which default window an ``interval_dates`` value is (YEAR / MONTHS), or None."""
    parsed = _parse_interval(values)
    if parsed is None:
        return None
    start, end = parsed
    today = today or date.today()
    for kind in (YEAR, MONTHS):
        expected_start, expected_end = window_dates(kind, today)
        if abs(start - expected_start) <= TOLERANCE and abs(end - expected_end) <= TOLERANCE:
            return kind
    return None


# --------------------------------------------------------------------------- keys


def cache_key(path, args, today=None):
    """
    The cache key of a request, or None when it must be computed live.

    ``args`` maps each query parameter to its list of values (``request.args.lists()``). The dates
    are left out of the key: the entry stays valid while "last 12 months" moves on each day, until
    the warm-up recomputes it.
    """
    if not path.startswith(CACHED_PREFIXES) or "/patients/" in path:
        return None
    args = {k: list(v) for k, v in args.items()}
    if args.get("viewport"):  # map pans: every viewport would be a new file
        return None
    if any(args.get(name) for name in USER_FILTERS):
        return None
    if any(str(v).lower() == "health_facility" for v in args.get("facility_type", [])):
        return None
    kind = default_window(args.get("interval_dates"), today)
    if kind is None:
        return None
    rest = {k: v for k, v in sorted(args.items()) if k != "interval_dates"}
    return {"path": path, "window": kind, "params": rest}


def _file(key):
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()
    return os.path.join(cache_dir(), f"{digest}.json")


# --------------------------------------------------------------------------- store


def read(key, now=None):
    """The cached entry ``{"computed_at", "data", ...}`` if present and fresh enough, else None."""
    try:
        with open(_file(key), encoding="utf-8") as fh:
            entry = json.load(fh)
        computed_at = datetime.fromisoformat(entry["computed_at"])
    except (OSError, ValueError, KeyError):
        return None
    now = now or datetime.now(timezone.utc)
    if now - computed_at > max_age():
        return None
    return entry


def write(key, data, now=None):
    """Store a response atomically (a worker never reads a half-written file)."""
    now = now or datetime.now(timezone.utc)
    entry = {"key": key, "computed_at": now.isoformat(timespec="seconds"), "data": data}
    directory = cache_dir()
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, default=str)
        os.replace(tmp, _file(key))
    except (OSError, TypeError, ValueError):
        # A cache that cannot write must never break the report itself.
        logger.exception("Report cache: could not store %s", key.get("path"))
        return None
    return entry


def stored_keys():
    """Keys of every entry in the cache (the warm-up recomputes them)."""
    keys = []
    try:
        names = os.listdir(cache_dir())
    except OSError:
        return keys
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(cache_dir(), name), encoding="utf-8") as fh:
                keys.append(json.load(fh)["key"])
        except (OSError, ValueError, KeyError):
            continue
    return keys


def query_for(key, today=None):
    """Query parameters to recompute an entry today: its own filters and today's window."""
    params = [(name, value) for name, values in key["params"].items() for value in values]
    params.append(("interval_dates", window_param(key["window"], today)))
    return params
