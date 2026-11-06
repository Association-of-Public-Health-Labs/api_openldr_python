"""Read side of the usage module: admin reports computed from the usage tables."""
from collections import defaultdict
from datetime import date, datetime, timedelta

from usage.models import PatientAccessLog, UsageEvent
from usage.sessions import derive_sessions
from utilities.service_helpers import InvalidParameter

INTERVAL_MESSAGE = "interval_dates must be two YYYY-MM-DD dates: start,end"
MAX_LIMIT = 100


def parse_period(raw):
    """
    ``interval_dates`` (``["start,end"]`` or ``["start", "end"]``) as ``(start, end_exclusive)`` datetimes.
    The end date counts as a whole day. Missing or malformed values raise InvalidParameter.
    """
    values = []
    for item in raw or []:
        values.extend(part.strip() for part in str(item).split(",") if part.strip())
    if len(values) != 2:
        raise InvalidParameter(INTERVAL_MESSAGE)
    try:
        start, end = (date.fromisoformat(v) for v in values)
    except ValueError:
        raise InvalidParameter(INTERVAL_MESSAGE) from None
    if start > end:
        raise InvalidParameter("interval_dates start must not be after end")
    return datetime.combine(start, datetime.min.time()), datetime.combine(end + timedelta(days=1), datetime.min.time())


def parse_limit(raw, default):
    if raw is None or raw == "":
        return default
    try:
        limit = int(raw)
    except ValueError:
        raise InvalidParameter(f"limit must be a whole number from 1 to {MAX_LIMIT}") from None
    if not 1 <= limit <= MAX_LIMIT:
        raise InvalidParameter(f"limit must be a whole number from 1 to {MAX_LIMIT}")
    return limit


def _events(period, dashboard=None):
    start, end = period
    query = UsageEvent.query.filter(UsageEvent.occurred_at >= start, UsageEvent.occurred_at < end)
    if dashboard:
        query = query.filter(UsageEvent.dashboard == dashboard)
    return query.all()


def _per_user(sessions, users):
    return round(sessions / users, 2) if users else 0


def _totals(events):
    users = {e.user_id for e in events}
    sessions = len(derive_sessions(events))
    return len(users), sessions


def summary(period, dashboard=None):
    start, end = period
    previous = (start - (end - start), start)
    users, sessions = _totals(_events(period, dashboard))
    prev_users, prev_sessions = _totals(_events(previous, dashboard))
    return {
        "active_users": users,
        "sessions": sessions,
        "sessions_per_user": _per_user(sessions, users),
        "previous": {"active_users": prev_users, "sessions": prev_sessions},
    }


def active_users_by_month(period, dashboard=None):
    users = defaultdict(set)
    for e in _events(period, dashboard):
        users[(e.occurred_at.year, e.occurred_at.month, e.dashboard)].add(e.user_id)
    return [
        {"year": year, "month": month, "dashboard": name, "active_users": len(ids)}
        for (year, month, name), ids in sorted(users.items())
    ]


def by_dashboard(period):
    events = defaultdict(list)
    for e in _events(period):
        events[e.dashboard].append(e)
    rows = []
    for name in sorted(events):
        users, sessions = _totals(events[name])
        rows.append({"dashboard": name, "active_users": users, "sessions": sessions,
                     "sessions_per_user": _per_user(sessions, users)})
    return rows


def top_users(period, limit, dashboard=None):
    events = _events(period, dashboard)
    sessions = defaultdict(int)
    for s in derive_sessions(events):
        sessions[s.user_id] += 1
    dashboards = defaultdict(set)
    last_visit = {}
    for e in events:
        dashboards[e.user_id].add(e.dashboard)
        last_visit[e.user_id] = max(last_visit.get(e.user_id, e.occurred_at), e.occurred_at)
    rows = [
        {"user_id": user, "dashboards": sorted(dashboards[user]), "sessions": count,
         "last_visit": last_visit[user].isoformat()}
        for user, count in sessions.items()
    ]
    rows.sort(key=lambda r: (-r["sessions"], r["user_id"]))
    return rows[:limit]


def top_pages(period, limit, dashboard=None):
    views = defaultdict(int)
    for e in _events(period, dashboard):
        views[(e.dashboard, e.page)] += 1
    rows = [{"dashboard": d, "page": p, "views": n} for (d, p), n in views.items()]
    rows.sort(key=lambda r: (-r["views"], r["dashboard"], r["page"]))
    return rows[:limit]


def patient_access(period, dashboard=None):
    start, end = period
    query = PatientAccessLog.query.filter(PatientAccessLog.occurred_at >= start, PatientAccessLog.occurred_at < end)
    if dashboard:
        query = query.filter(PatientAccessLog.dashboard == dashboard)
    counts = defaultdict(lambda: [0, None])
    for row in query.all():
        entry = counts[(row.user_id, row.dashboard)]
        entry[0] += 1
        entry[1] = max(entry[1], row.occurred_at) if entry[1] else row.occurred_at
    return [
        {"user_id": user, "dashboard": name, "accesses": count, "last_access": last.isoformat()}
        for (user, name), (count, last) in sorted(counts.items())
    ]
