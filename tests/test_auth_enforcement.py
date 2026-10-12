"""
Endpoint-level authentication contract.

Every reporting endpoint must reject unverified tokens with a fixed 401 body
and accept valid API-issued tokens. One endpoint per module is enough because
all of them go through utilities.controller_helpers.authenticate_request.
"""
import time
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest

from configs import paths
from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
from utilities import token_verification as tv
from utilities.utils import get_token

UNAUTHORIZED_BODY = {
    "status": "error",
    "code": 401,
    "message": "Invalid or missing token",
}

# (url, symbol patched in the controller module, mocked service result)
ENDPOINTS = [
    ("/hiv/vl/summary/tat_by_month/",
     "hiv.vl.controllers.vl_controller_summary.tat_service_by_month", []),
    ("/hiv/vl/patients/by_name/",
     "hiv.vl.controllers.vl_controller_patients.get_patients_by_name_service", []),
    ("/hiv/eid/laboratories/tested_samples_by_month/",
     "hiv.eid.controllers.eid_controller_laboratory.tested_samples_by_month_service", []),
    ("/tb/gx/laboratories/registered_samples/",
     "tb.gxpert.controllers.tb_gx_controller_laboratory.registered_samples_by_lab_service", []),
    ("/tb/gx/patients/by_name/",
     "tb.gxpert.controllers.tb_gx_controller_patients.get_patients_by_name_service", []),
]


def forged_admin_token():
    """Unsigned-by-us token claiming to be an Admin, the attack the fix closes."""
    now = int(time.time())
    return jwt.encode(
        {"sub": "admin", "user_id": "admin-1", "role": "Admin",
         "type": "access", "jti": "x", "fresh": False,
         "iat": now, "nbf": now, "exp": now + 600},
        "attacker-secret",
        algorithm="HS256",
    )


@pytest.mark.parametrize("url,service,result", ENDPOINTS)
def test_valid_api_token_is_accepted(client, auth_headers, url, service, result):
    with patch(service, return_value=result):
        response = client.get(url, headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.parametrize("url,service,result", ENDPOINTS)
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": f"Bearer {forged_admin_token()}"},
    ],
    ids=["no-header", "bearer-no-token", "basic", "garbage", "forged-admin"],
)
def test_rejected_requests_return_fixed_401_body(client, url, service, result, headers):
    with patch(service, return_value=result) as service_mock:
        response = client.get(url, headers=headers)
    assert response.status_code == 401
    assert response.get_json() == UNAUTHORIZED_BODY
    service_mock.assert_not_called()


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("bearer abc.def.ghi", "abc.def.ghi"),
        ("  Bearer   abc.def.ghi  ", "abc.def.ghi"),
        ("Basic dXNlcjpwYXNz", None),
        ("Bearer", None),
        ("Bearer    ", None),
        ("", None),
        (None, None),
    ],
)
def test_get_token_parses_authorization_header(header, expected):
    headers = {} if header is None else {"Authorization": header}
    assert get_token(SimpleNamespace(headers=headers)) == expected


# --- Clerk (RS256) session tokens at endpoint level -------------------------

CLERK_ENDPOINTS = [ENDPOINTS[0], ENDPOINTS[3]]  # one VL, one TB


@pytest.fixture
def clerk_config(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))


@pytest.mark.parametrize("url,service,result", CLERK_ENDPOINTS)
def test_valid_clerk_token_is_accepted(client, clerk_config, url, service, result):
    token = make_clerk_token(sub="user_clerk_42")
    with patch(service, return_value=result) as service_mock:
        response = client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    service_mock.assert_called_once()
    req_args = service_mock.call_args.args[0]
    assert req_args["user_id"] == "user_clerk_42"


@pytest.mark.parametrize("url,service,result", CLERK_ENDPOINTS)
def test_clerk_token_from_unauthorized_party_rejected(client, clerk_config, url, service, result):
    token = make_clerk_token(azp="https://evil.example")
    with patch(service, return_value=result) as service_mock:
        response = client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.get_json() == UNAUTHORIZED_BODY
    service_mock.assert_not_called()
