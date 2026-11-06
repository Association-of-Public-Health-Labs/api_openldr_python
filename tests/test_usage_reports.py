"""Admin-only usage reports and POST /admin/audit."""
import json
from datetime import datetime

import pytest

from configs import paths
from db.database import db
from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
from usage.models import AdminAuditLog, PatientAccessLog, UsageEvent
from utilities import token_verification as tv
from utilities.permissions import forbidden_response

REPORTS = ["summary", "active_users_by_month", "by_dashboard", "top_users", "top_pages", "patient_access"]
RANGE = "2026-11-01,2026-11-30"


@pytest.fixture(autouse=True)
def clerk_config(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))


@pytest.fixture(autouse=True)
def clean(app):
    with app.app_context():
        for model in (UsageEvent, PatientAccessLog, AdminAuditLog):
            model.query.delete()
        db.session.commit()
    yield


def bearer(admin=True, **extra):
    claim = {"admin": admin} if admin is not None else {}
    return {"Authorization": f"Bearer {make_clerk_token(openldr=claim, **extra)}"}


def at(day, hour=9, minute=0, month=11):
    return datetime(2026, month, day, hour, minute)


def seed(app, events=(), accesses=()):
    with app.app_context():
        for user, dashboard, page, when in events:
            db.session.add(UsageEvent(user_id=user, dashboard=dashboard, page=page, occurred_at=when))
        for user, dashboard, rows, when in accesses:
            db.session.add(PatientAccessLog(user_id=user, dashboard=dashboard, endpoint="/x/patients/", row_count=rows, occurred_at=when))
        db.session.commit()


EVENTS = [
    # previous period (Oct 2-31 has the same 30 days as Nov 1-30 -> Oct 2..Oct 31)
    ("old", "vl", "/lab", at(15, month=10)),
    # current period
    ("a", "vl", "/lab", at(2, 9, 0)),
    ("a", "vl", "/lab", at(2, 9, 10)),       # same session
    ("a", "vl", "/map", at(2, 11, 0)),       # new session
    ("a", "tb", "/home", at(3, 9, 0)),       # tb session
    ("b", "vl", "/lab", at(5, 10, 0)),
    ("b", "eid", "/lab", at(30, 23, 59)),    # last day is inclusive
    ("c", "vl", "/lab", at(1, 0, 0, month=12)),  # outside
]


def get(client, report, query=f"interval_dates={RANGE}", headers=None):
    return client.get(f"/usage/{report}/?{query}", headers=headers or bearer())


def test_summary(app, client):
    seed(app, EVENTS)
    body = get(client, "summary").get_json()
    # users a, b; sessions: a vl x2, a tb, b vl, b eid = 5
    assert body == {"active_users": 2, "sessions": 5, "sessions_per_user": 2.5, "previous": {"active_users": 1, "sessions": 1}}


def test_summary_dashboard_filter(app, client):
    seed(app, EVENTS)
    body = get(client, "summary", f"interval_dates={RANGE}&dashboard=vl").get_json()
    assert body == {"active_users": 2, "sessions": 3, "sessions_per_user": 1.5, "previous": {"active_users": 1, "sessions": 1}}


def test_summary_with_no_users_is_zero(app, client):
    body = get(client, "summary").get_json()
    assert body == {"active_users": 0, "sessions": 0, "sessions_per_user": 0, "previous": {"active_users": 0, "sessions": 0}}


def test_active_users_by_month(app, client):
    seed(app, EVENTS)
    rows = get(client, "active_users_by_month", "interval_dates=2026-10-01,2026-11-30").get_json()
    assert rows == [
        {"year": 2026, "month": 10, "dashboard": "vl", "active_users": 1},
        {"year": 2026, "month": 11, "dashboard": "eid", "active_users": 1},
        {"year": 2026, "month": 11, "dashboard": "tb", "active_users": 1},
        {"year": 2026, "month": 11, "dashboard": "vl", "active_users": 2},
    ]


def test_by_dashboard(app, client):
    seed(app, EVENTS)
    rows = get(client, "by_dashboard").get_json()
    assert rows == [
        {"dashboard": "eid", "active_users": 1, "sessions": 1, "sessions_per_user": 1},
        {"dashboard": "tb", "active_users": 1, "sessions": 1, "sessions_per_user": 1},
        {"dashboard": "vl", "active_users": 2, "sessions": 3, "sessions_per_user": 1.5},
    ]


def test_top_users_and_limit(app, client):
    seed(app, EVENTS)
    rows = get(client, "top_users").get_json()
    assert rows == [
        {"user_id": "a", "dashboards": ["tb", "vl"], "sessions": 3, "last_visit": "2026-11-03T09:00:00Z"},
        {"user_id": "b", "dashboards": ["eid", "vl"], "sessions": 2, "last_visit": "2026-11-30T23:59:00Z"},
    ]
    assert [r["user_id"] for r in get(client, "top_users", f"interval_dates={RANGE}&limit=1").get_json()] == ["a"]


def test_top_pages(app, client):
    seed(app, EVENTS)
    rows = get(client, "top_pages").get_json()
    assert rows == [
        {"dashboard": "vl", "page": "/lab", "views": 3},
        {"dashboard": "eid", "page": "/lab", "views": 1},
        {"dashboard": "tb", "page": "/home", "views": 1},
        {"dashboard": "vl", "page": "/map", "views": 1},
    ]
    assert len(get(client, "top_pages", f"interval_dates={RANGE}&limit=2").get_json()) == 2


def test_patient_access(app, client):
    seed(app, accesses=[
        ("a", "vl", 5, at(2)), ("a", "vl", 7, at(4)), ("a", "tb", 1, at(3)),
        ("b", "vl", 2, at(30, 23, 30)), ("b", "vl", 2, at(1, month=12)),
    ])
    rows = get(client, "patient_access").get_json()
    assert rows == [
        {"user_id": "a", "dashboard": "tb", "accesses": 1, "last_access": "2026-11-03T09:00:00Z"},
        {"user_id": "a", "dashboard": "vl", "accesses": 2, "last_access": "2026-11-04T09:00:00Z"},
        {"user_id": "b", "dashboard": "vl", "accesses": 1, "last_access": "2026-11-30T23:30:00Z"},
    ]
    only_tb = get(client, "patient_access", f"interval_dates={RANGE}&dashboard=tb").get_json()
    assert [r["dashboard"] for r in only_tb] == ["tb"]


def test_interval_dates_as_two_values(app, client):
    seed(app, EVENTS)
    body = get(client, "summary", "interval_dates=2026-11-01&interval_dates=2026-11-30").get_json()
    assert body["active_users"] == 2


@pytest.mark.parametrize("query", ["", "interval_dates=", "interval_dates=2026-11-01", "interval_dates=nope,2026-11-30",
                                   "interval_dates=2026-11-30,2026-11-01", "interval_dates=2026-11-01,2026-11-30,2026-12-01"])
@pytest.mark.parametrize("report", REPORTS)
def test_bad_interval_is_400_without_exception_text(client, report, query):
    response = get(client, report, query)
    body = response.get_json()
    assert response.status_code == 400
    assert body["status"] == "error" and body["code"] == 400 and "error" not in body
    assert "Traceback" not in body["message"] and "ValueError" not in body["message"]


@pytest.mark.parametrize("limit", ["x", "0", "-1", "1000"])
def test_bad_limit_is_400(client, limit):
    assert get(client, "top_users", f"interval_dates={RANGE}&limit={limit}").status_code == 400


@pytest.mark.parametrize("flag", [True, False])
@pytest.mark.parametrize("report", REPORTS)
def test_non_admin_is_403(app, client, monkeypatch, report, flag):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", flag)
    for headers in (bearer(admin=False), bearer(admin=None)):
        response = get(client, report, headers=headers)
        assert response.status_code == 403
        assert response.get_json() == forbidden_response()[0]


@pytest.mark.parametrize("flag", [True, False])
def test_admin_is_allowed_with_flag_either_way(app, client, monkeypatch, flag):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", flag)
    assert get(client, "summary").status_code == 200


def test_missing_token_is_401(client):
    assert client.get(f"/usage/summary/?interval_dates={RANGE}").status_code == 401


def test_service_token_is_403_even_with_admin(app, client, monkeypatch):
    from utilities import controller_helpers
    from utilities.permissions import Permissions

    real = controller_helpers.permissions_for_token
    monkeypatch.setattr(controller_helpers, "permissions_for_token",
                        lambda claims: Permissions(admin=True, service=True))
    assert get(client, "summary").status_code == 403
    assert client.post("/admin/audit", headers=bearer(), json={"action": "x", "target_user_id": "t"}).status_code == 403
    monkeypatch.setattr(controller_helpers, "permissions_for_token", real)


# --- POST /admin/audit ---

def audit_rows(app):
    with app.app_context():
        return [(r.actor_user_id, r.action, r.target_user_id, r.changes) for r in AdminAuditLog.query.order_by(AdminAuditLog.id)]


def test_audit_stores_token_subject_as_actor(app, client):
    body = {"action": "update_permissions", "target_user_id": "user_t", "changes": {"dashboards": {"from": ["vl"], "to": ["vl", "tb"]}},
            "actor_user_id": "spoofed", "actor": "spoofed"}
    response = client.post("/admin/audit", headers=bearer(), json=body)
    assert response.status_code == 201
    rows = audit_rows(app)
    assert len(rows) == 1
    actor, action, target, changes = rows[0]
    assert (actor, action, target) == ("user_abc", "update_permissions", "user_t")
    assert json.loads(changes) == body["changes"]


def test_audit_changes_optional(app, client):
    assert client.post("/admin/audit", headers=bearer(), json={"action": "a", "target_user_id": "t"}).status_code == 201
    assert audit_rows(app)[0][3] is None


@pytest.mark.parametrize("body", [{"target_user_id": "t"}, {"action": "a"}, {"action": "", "target_user_id": "t"},
                                  {"action": "a", "target_user_id": " "}, {"action": 3, "target_user_id": "t"},
                                  {"action": "a" * 51, "target_user_id": "t"}, ["a"]])
def test_audit_rejects_bad_body(app, client, body):
    response = client.post("/admin/audit", headers=bearer(), json=body)
    assert response.status_code == 400
    assert audit_rows(app) == []


@pytest.mark.parametrize("flag", [True, False])
def test_audit_requires_admin(app, client, monkeypatch, flag):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", flag)
    response = client.post("/admin/audit", headers=bearer(admin=False), json={"action": "a", "target_user_id": "t"})
    assert response.status_code == 403
    assert audit_rows(app) == []
    assert client.post("/admin/audit", json={"action": "a", "target_user_id": "t"}).status_code == 401
