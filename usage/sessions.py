"""Sessions are not stored; they are derived from page-view events."""
from dataclasses import dataclass
from datetime import datetime, timedelta

SESSION_GAP = timedelta(minutes=30)


@dataclass(frozen=True)
class Session:
    user_id: str
    dashboard: str
    start: datetime
    end: datetime
    events: int


def derive_sessions(events):
    """
    Group events (objects with ``user_id``, ``dashboard`` and ``occurred_at``) into sessions: per user
    and dashboard, a new session starts after more than 30 minutes without an event.
    """
    ordered = sorted(events, key=lambda e: (e.user_id, e.dashboard, e.occurred_at))
    sessions = []
    current = None
    for e in ordered:
        if current and (current[0], current[1]) == (e.user_id, e.dashboard) and e.occurred_at - current[3] <= SESSION_GAP:
            current[3] = e.occurred_at
            current[4] += 1
            continue
        if current:
            sessions.append(Session(*current))
        current = [e.user_id, e.dashboard, e.occurred_at, e.occurred_at, 1]
    if current:
        sessions.append(Session(*current))
    return sessions
