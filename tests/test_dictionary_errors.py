"""Dictionary GETs share reporting HTTP errors and persisted authorization."""

from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from utilities import controller_helpers, report_cache


ROUTES = [
    ("/dict/facilities/", "dict.controllers.facilities_controller.get_all_facilities", {}),
    ("/dict/facilities/provinces/", "dict.controllers.facilities_controller.get_facilities_by_province", {"province": ["Maputo", "Gaza"]}),
    ("/dict/facilities/province/districts/", "dict.controllers.facilities_controller.get_facilities_by_district", {"district": ["District A", "District B"]}),
    ("/dict/laboratories/", "dict.controllers.laboratories_controller.get_all_laboratories", {}),
    ("/dict/laboratories/provinces/", "dict.controllers.laboratories_controller.get_laboratories_by_province", {"province": ["Maputo", "Gaza"]}),
    ("/dict/laboratories/province/districts/", "dict.controllers.laboratories_controller.get_laboratories_by_district", {"district": ["District A", "District B"]}),
]


def bearer(app, user_id):
    with app.app_context():
        token = create_access_token(identity=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def dictionary_identity(app, persisted_user):
    user_id = persisted_user(role="vl")
    return user_id, bearer(app, user_id)


@pytest.mark.parametrize("url,target,query", ROUTES)
def test_dictionary_exception_is_generic_http_500(client, dictionary_identity, url, target, query):
    _, headers = dictionary_identity
    with patch(target, side_effect=RuntimeError("pyodbc: SELECT synthetic_secret FROM example")):
        response = client.get(url, query_string=query, headers=headers)
    assert response.status_code == 500
    assert response.get_json() == {
        "status": "error", "code": 500, "message": "An error occurred",
    }
    assert b"SELECT" not in response.data and b"pyodbc" not in response.data


@pytest.mark.parametrize("url,target,query", ROUTES)
def test_dictionary_success_preserves_lists_filters_and_one_role_lookup(
    app, client, dictionary_identity, monkeypatch, url, target, query,
):
    user_id, headers = dictionary_identity
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    payload = [{"Code": "synthetic-code", "Name": "Synthetic dictionary value"}]
    with patch(target, return_value=payload) as service, patch.object(
        controller_helpers, "get_user_by_id_service",
        wraps=controller_helpers.get_user_by_id_service,
    ) as lookup, patch.object(report_cache, "read") as read, patch.object(report_cache, "write") as write:
        response = client.get(url, query_string=query, headers=headers)
    assert response.status_code == 200
    assert response.get_json() == payload
    assert "X-Report-Cache" not in response.headers
    read.assert_not_called()
    write.assert_not_called()
    lookup.assert_called_once_with(user_id)
    if not query:
        service.assert_called_once_with()
    else:
        service.assert_called_once()
        assert service.call_args.args[0] == {**query, "user_id": user_id}


@pytest.mark.parametrize("url,target,query", ROUTES)
@pytest.mark.parametrize("code", [400, 403, 404])
def test_dictionary_service_error_uses_real_http_4xx(
    client, dictionary_identity, url, target, query, code,
):
    _, headers = dictionary_identity
    payload = {"status": "error", "code": code, "message": "Synthetic client error"}
    with patch(target, return_value=payload):
        response = client.get(url, query_string=query, headers=headers)
    assert response.status_code == code
    assert response.get_json() == payload


@pytest.mark.parametrize("url,target,query", ROUTES)
@pytest.mark.parametrize("code", [500, 503])
def test_dictionary_service_error_hides_all_http_5xx_details(
    client, dictionary_identity, url, target, query, code,
):
    _, headers = dictionary_identity
    payload = {
        "status": "error", "code": code, "message": "SELECT synthetic_secret",
        "error": "pyodbc synthetic detail", "details": {"sql": "SELECT synthetic_secret"},
    }
    with patch(target, return_value=payload):
        response = client.get(url, query_string=query, headers=headers)
    assert response.status_code == code
    assert response.get_json() == {
        "status": "error", "code": code, "message": "An error occurred",
    }


@pytest.mark.parametrize("url,target,query", ROUTES)
def test_dictionary_requires_token_before_service(client, url, target, query):
    with patch(target) as service:
        response = client.get(url, query_string=query)
    assert response.status_code == 401
    service.assert_not_called()


@pytest.mark.parametrize("url,target,query", ROUTES)
def test_dictionary_requires_assigned_role_before_service(
    app, client, persisted_user, url, target, query,
):
    user_id = persisted_user(role="user")
    with patch(target) as service:
        response = client.get(url, query_string=query, headers=bearer(app, user_id))
    assert response.status_code == 403
    service.assert_not_called()
