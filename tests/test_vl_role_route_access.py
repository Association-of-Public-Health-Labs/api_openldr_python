"""Exercise the VL role on every registered reporting route with both JWT issuers.

Password login uses a synthetic persisted account and the real HTTP login route.
Clerk uses a locally signed RS256 token and fake JWKS retrieval. Authorization,
persisted role lookup and request parsing are real; only report queries and mail
delivery are replaced, so the suite never queries production data or sends mail.
"""

import importlib
from unittest.mock import Mock, patch

import bcrypt
import pytest
from flask import Flask
from flask_restful import Api

from auth.user_model import User, UserLogs
from configs import paths
from db.database import db
from dict.routes import dict_routes
from hiv.eid.routes import eid_routes
from hiv.vl.routes import vl_routes
from suggestions.routes import MODULES
from tb.cultura.routes import tb_cultura_routes
from tb.gxpert.routes import tb_gxpert_routes
from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
from utilities import token_verification
from utilities.controller_helpers import run_reporting_endpoint


REPORT_PREFIXES = ("/hiv/vl/", "/hiv/eid/", "/tb/gx/", "/tb/cultura/")
SYNTHETIC_PASSWORD = "vl-route-test-password"
SYNTHETIC_USER_ID = "user_vl_route_access_fixture"


def _registered_get_paths():
    """Derive cases from the actual route registrations, without any database."""
    inventory = Flask("vl-role-route-inventory")
    api = Api(inventory)
    for register in (vl_routes, eid_routes, tb_gxpert_routes, tb_cultura_routes, dict_routes):
        register(api)
    return sorted(
        rule.rule for rule in inventory.url_map.iter_rules()
        if "GET" in rule.methods and rule.rule.startswith((*REPORT_PREFIXES, "/dict/"))
    )


GET_PATHS = _registered_get_paths()
DICTIONARY_SERVICES = {
    "/dict/laboratories/": "dict.controllers.laboratories_controller.get_all_laboratories",
    "/dict/laboratories/provinces/": "dict.controllers.laboratories_controller.get_laboratories_by_province",
    "/dict/laboratories/province/districts/": "dict.controllers.laboratories_controller.get_laboratories_by_district",
    "/dict/facilities/": "dict.controllers.facilities_controller.get_all_facilities",
    "/dict/facilities/provinces/": "dict.controllers.facilities_controller.get_facilities_by_province",
    "/dict/facilities/province/districts/": "dict.controllers.facilities_controller.get_facilities_by_district",
}


@pytest.fixture
def vl_token(client, app, persisted_user, monkeypatch, request):
    """Return a real verified token for the same persisted VL account."""
    user_id = persisted_user(role="vl", user_id=SYNTHETIC_USER_ID)
    with app.app_context():
        user = User.query.filter_by(user_id=user_id).one()
        user.user_name = "synthetic_vl"
        user.email = "synthetic-vl@example.test"
        user.password = bcrypt.hashpw(
            SYNTHETIC_PASSWORD.encode(), bcrypt.gensalt(rounds=4)
        ).decode()
        db.session.commit()
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", False)

    if request.param == "password":
        response = client.post("/auth/login", json={
            "username": "synthetic_vl", "email": "synthetic-vl@example.test",
            "password": SYNTHETIC_PASSWORD,
        })
        assert response.status_code == 200, response.get_json()
        payload = response.get_json()
        assert payload["status"] == 200, payload
        assert payload["data"]["role"] == "vl"
        assert payload["data"]["user_id"] == user_id
        token = payload["token"]
    else:
        monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
        monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
        monkeypatch.setattr(token_verification, "_clerk_jwks", token_verification.JwksCache(make_jwks))
        token = make_clerk_token(sub=user_id)
    yield {"Authorization": f"Bearer {token}"}

    with app.app_context():
        UserLogs.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        db.session.commit()


@pytest.mark.parametrize("vl_token", ["password", "clerk"], indirect=True)
@pytest.mark.parametrize("url", GET_PATHS)
def test_vl_role_on_every_registered_reporting_get(client, app, vl_token, url, monkeypatch):
    """VL reports/dictionaries succeed; patient and other-domain routes deny."""
    query = Mock(return_value=[])
    if url.startswith("/dict/"):
        service_target = DICTIONARY_SERVICES[url]
        with patch(service_target, query):
            response = client.get(url, headers=vl_token)
        allowed = True
    else:
        rule = next(rule for rule in app.url_map.iter_rules() if rule.rule == url)
        resource_class = app.view_functions[rule.endpoint].view_class
        controller = importlib.import_module(resource_class.__module__)
        assert controller.run_reporting_endpoint is run_reporting_endpoint, url

        def report_with_fake_query(parse_fn, service_fn):
            # Keep the real authentication, persisted permissions and parsing.
            return run_reporting_endpoint(parse_fn, query)

        monkeypatch.setattr(controller, "run_reporting_endpoint", report_with_fake_query)
        response = client.get(url, headers=vl_token, query_string={
            "interval_dates": ["2024-01-01", "2024-12-31"],
            "province": "Maputo", "facility_type": "province",
        })
        allowed = url.startswith("/hiv/vl/") and "/patients/" not in url

    assert response.status_code == (200 if allowed else 403), (url, response.get_json())
    if allowed:
        assert response.get_json() == []
        query.assert_called_once()
        if not url.startswith("/dict/"):
            assert query.call_args.args[0]["user_id"] == SYNTHETIC_USER_ID
    else:
        query.assert_not_called()
        assert response.get_json() == {
            "status": "error", "code": 403, "message": "Access denied for this role",
        }


def test_vl_route_cases_cover_every_registered_reporting_get(app):
    registered = {
        rule.rule for rule in app.url_map.iter_rules()
        if "GET" in rule.methods and rule.rule.startswith((*REPORT_PREFIXES, "/dict/"))
    }
    assert set(GET_PATHS) == registered
    assert {url for url in registered if url.startswith("/dict/")} == set(DICTIONARY_SERVICES)


@pytest.mark.parametrize("vl_token", ["password", "clerk"], indirect=True)
@pytest.mark.parametrize("prefix", MODULES)
def test_vl_role_on_every_suggestion_route(client, vl_token, prefix):
    with patch("suggestions.controller.send_suggestion") as send:
        response = client.post(prefix + "/send-suggestion?duvida=true", headers=vl_token,
                               json={"content": "Synthetic access-control check"})
    allowed = prefix in {"/hiv", "/hiv/vl"}
    assert response.status_code == (200 if allowed else 403)
    assert send.call_count == int(allowed)


@pytest.mark.parametrize("vl_token", ["password"], indirect=True)
def test_vl_role_cannot_list_users(client, vl_token):
    response = client.get("/auth/users", headers=vl_token)
    assert response.status_code == 403
    assert response.get_json()["code"] == 403
