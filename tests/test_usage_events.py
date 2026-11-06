"""POST /usage/events: page-view tracking for the admin dashboard."""
import logging

import pytest

from db.database import db
from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
from configs import paths
from utilities import token_verification as tv
from utilities.permissions import forbidden_response
from usage.models import UsageEvent

URL = "/usage/events"


@pytest.fixture
def clerk_config(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))


@pytest.fixture(autouse=True)
def clean_events(app):
    with app.app_context():
        UsageEvent.query.delete()
        db.session.commit()
    yield


def bearer(dashboards=None):
    extra = {} if dashboards is None else {"openldr": {"dashboards": dashboards}}
    return {"Authorization": f"Bearer {make_clerk_token(**extra)}"}


def stored(app):
    with app.app_context():
        return [(e.user_id, e.dashboard, e.page, e.occurred_at) for e in UsageEvent.query.order_by(UsageEvent.id)]


def test_records_event_for_token_user(app, client, clerk_config):
    response = client.post(URL, headers=bearer(), json={"dashboard": "vl", "page": "/lab", "user_id": "someone-else"})
    assert response.status_code == 204
    rows = stored(app)
    assert len(rows) == 1
    user_id, dashboard, page, occurred_at = rows[0]
    assert (user_id, dashboard, page) == ("user_abc", "vl", "/lab")
    assert occurred_at is not None


@pytest.mark.parametrize("dashboard", ["nope", "", None, 3, "VL", "admin"])
def test_rejects_unknown_dashboard(app, client, clerk_config, dashboard):
    response = client.post(URL, headers=bearer(), json={"dashboard": dashboard, "page": "/lab"})
    assert response.status_code == 400
    assert stored(app) == []


@pytest.mark.parametrize("body", [{"dashboard": "vl"}, {"dashboard": "vl", "page": ""}, {"dashboard": "vl", "page": "   "},
                                  {"dashboard": "vl", "page": 5}, {"dashboard": "vl", "page": "?q=1"}])
def test_rejects_missing_page(app, client, clerk_config, body):
    response = client.post(URL, headers=bearer(), json=body)
    assert response.status_code == 400
    assert stored(app) == []


@pytest.mark.parametrize("kwargs", [{"data": "not json", "content_type": "text/plain"}, {"json": ["vl"]}])
def test_rejects_non_object_body(app, client, clerk_config, kwargs):
    assert client.post(URL, headers=bearer(), **kwargs).status_code == 400
    assert stored(app) == []


def test_page_stripped_of_query_and_truncated(app, client, clerk_config):
    assert client.post(URL, headers=bearer(), json={"dashboard": "vl", "page": "/lab?name=Ana"}).status_code == 204
    assert client.post(URL, headers=bearer(), json={"dashboard": "vl", "page": "/lab#top"}).status_code == 204
    assert client.post(URL, headers=bearer(), json={"dashboard": "vl", "page": "/" + "a" * 499}).status_code == 204
    pages = [row[2] for row in stored(app)]
    assert pages[:2] == ["/lab", "/lab"]
    assert len(pages[2]) == 250


def test_no_token_is_401(app, client):
    assert client.post(URL, json={"dashboard": "vl", "page": "/lab"}).status_code == 401
    assert client.post(URL, headers={"Authorization": "Bearer nope"}, json={"dashboard": "vl", "page": "/lab"}).status_code == 401
    assert stored(app) == []


def test_flag_on_without_dashboard_access_is_403(app, client, clerk_config, monkeypatch):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", True)
    denied = client.post(URL, headers=bearer(["tb"]), json={"dashboard": "vl", "page": "/lab"})
    assert denied.status_code == 403
    assert denied.get_json() == forbidden_response()[0]
    assert stored(app) == []
    assert client.post(URL, headers=bearer(["vl"]), json={"dashboard": "vl", "page": "/lab"}).status_code == 204
    assert len(stored(app)) == 1


def test_flag_off_any_known_dashboard_is_recorded(app, client, clerk_config, monkeypatch):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", False)
    assert client.post(URL, headers=bearer(), json={"dashboard": "eid", "page": "/x"}).status_code == 204
    assert len(stored(app)) == 1


def test_db_failure_returns_204_and_logs(app, client, clerk_config, monkeypatch, caplog):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(db.session, "commit", boom)
    with caplog.at_level(logging.ERROR):
        response = client.post(URL, headers=bearer(), json={"dashboard": "vl", "page": "/lab"})
    assert response.status_code == 204
    assert any("page view" in r.getMessage().lower() for r in caplog.records)
    monkeypatch.undo()
    assert stored(app) == []
