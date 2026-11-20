"""derive_sessions: a new session after more than 30 minutes without an event, per user and dashboard."""
from datetime import datetime, timedelta
from types import SimpleNamespace

from usage.sessions import derive_sessions

T0 = datetime(2026, 11, 1, 9, 0)


def event(user="u1", dashboard="vl", minutes=0):
    return SimpleNamespace(user_id=user, dashboard=dashboard, occurred_at=T0 + timedelta(minutes=minutes))


def test_empty_input_gives_no_sessions():
    assert derive_sessions([]) == []


def test_events_29_minutes_apart_are_one_session():
    sessions = derive_sessions([event(minutes=0), event(minutes=29)])
    assert len(sessions) == 1
    assert (sessions[0].start, sessions[0].end, sessions[0].events) == (T0, T0 + timedelta(minutes=29), 2)


def test_exactly_30_minutes_is_still_one_session():
    assert len(derive_sessions([event(minutes=0), event(minutes=30)])) == 1


def test_events_31_minutes_apart_are_two_sessions():
    assert len(derive_sessions([event(minutes=0), event(minutes=31)])) == 2


def test_gap_is_measured_between_consecutive_events_not_from_session_start():
    assert len(derive_sessions([event(minutes=0), event(minutes=25), event(minutes=50), event(minutes=75)])) == 1


def test_unsorted_input_is_ordered_first():
    assert len(derive_sessions([event(minutes=29), event(minutes=0)])) == 1


def test_same_times_on_two_dashboards_are_two_sessions():
    sessions = derive_sessions([event(dashboard="vl", minutes=0), event(dashboard="tb", minutes=1)])
    assert sorted(s.dashboard for s in sessions) == ["tb", "vl"]


def test_two_users_are_separate_sessions():
    sessions = derive_sessions([event(user="a", minutes=0), event(user="b", minutes=1)])
    assert sorted(s.user_id for s in sessions) == ["a", "b"]
