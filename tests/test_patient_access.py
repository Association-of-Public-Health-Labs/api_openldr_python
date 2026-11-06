"""
Patient-row access follows the ``patientData`` permission when PERMISSIONS_ENFORCED is on.

With the flag on the DB ``role`` is ignored: ``patient_access_role`` answers "Admin" for a token
with ``patientData`` and "User" for one without. With the flag off the DB role decides, as before.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from configs import paths
from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
from utilities import token_verification as tv

PATIENT_URLS = [
    "/hiv/vl/patients/by_name/",
    "/hiv/eid/patients/by_name/",
    "/tb/gx/patients/by_name/",
]
VL_FACILITY_URL = "/hiv/vl/facilities/registered_samples/"
TB_LAB_URL = "/tb/gx/laboratories/registered_samples/"
TB_LABS = "tb.gxpert.services.tb_gx_services_laboratories"
LOOKUP = "utilities.auth_helpers.get_user_by_id_service"


@pytest.fixture
def clerk_config(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))


@pytest.fixture
def enforced(app, monkeypatch):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", True)


@pytest.fixture
def not_enforced(app, monkeypatch):
    monkeypatch.setitem(app.config, "PERMISSIONS_ENFORCED", False)


def bearer(patient_data):
    claim = {"dashboards": ["vl", "eid", "tb"], "patientData": patient_data}
    return {"Authorization": f"Bearer {make_clerk_token(openldr=claim)}"}


def db_user(role):
    return patch(LOOKUP, return_value=SimpleNamespace(role=role))


# --- flag on ---------------------------------------------------------------

@pytest.mark.parametrize("url", PATIENT_URLS)
def test_flag_on_patient_endpoint_403_without_patient_data(client, clerk_config, enforced, url):
    with patch(LOOKUP, return_value=None):
        response = client.get(url, headers=bearer(False))
    assert response.status_code == 403


@pytest.mark.parametrize("url", PATIENT_URLS)
def test_flag_on_patient_endpoint_passes_role_check_with_patient_data(client, clerk_config, enforced, url):
    # No first_name/surname, so a request past the role check is a 400, not a 403.
    with patch(LOOKUP, return_value=None):
        response = client.get(url, headers=bearer(True))
    assert response.status_code == 400


@pytest.mark.parametrize("url", PATIENT_URLS)
def test_flag_on_db_admin_without_patient_data_is_403(client, clerk_config, enforced, url):
    with db_user("Admin"):
        response = client.get(url, headers=bearer(False))
    assert response.status_code == 403


def test_flag_on_role_answer_does_not_touch_the_database(client, clerk_config, enforced):
    with patch(LOOKUP, side_effect=RuntimeError("db down")) as lookup:
        assert client.get(PATIENT_URLS[0], headers=bearer(True)).status_code == 400
        assert client.get(PATIENT_URLS[0], headers=bearer(False)).status_code == 403
    lookup.assert_not_called()


def tb_lab_request(client, headers, query):
    with patch(f"{TB_LABS}.get_user_by_id_service", return_value=None), \
         patch(f"{TB_LABS}.get_patients", return_value=MagicMock(all=lambda: [])), \
         patch(f"{TB_LABS}.process_patients", return_value=[]):
        return client.get(TB_LAB_URL, headers=headers, query_string=query)


def test_flag_on_tb_health_facility_param_alone_is_403_without_patient_data(client, clerk_config, enforced):
    # PROCESS_COMMON_PARAMS_FACILITY turns a health_facility param into facility_type=health_facility.
    response = tb_lab_request(client, bearer(False), {"health_facility": "X"})
    assert response.status_code == 403


def test_flag_on_tb_health_facility_param_passes_with_patient_data(client, clerk_config, enforced):
    response = tb_lab_request(client, bearer(True), {"health_facility": "X"})
    assert response.status_code == 200


def test_flag_on_vl_facility_level_aggregate_is_open_without_patient_data(client, clerk_config, enforced):
    with patch("hiv.vl.services.vl_services_facilities._by_group", return_value=[]), \
         patch(LOOKUP, return_value=None):
        response = client.get(
            VL_FACILITY_URL, headers=bearer(False),
            query_string={"facility_type": "health_facility"},
        )
    assert response.status_code == 200


# --- flag off: the DB role decides, as before -------------------------------

@pytest.mark.parametrize("url", PATIENT_URLS)
def test_flag_off_db_admin_passes(client, auth_headers, not_enforced, url):
    with db_user("Admin"):
        assert client.get(url, headers=auth_headers).status_code == 400


@pytest.mark.parametrize("url", PATIENT_URLS)
def test_flag_off_db_user_is_403(client, auth_headers, not_enforced, url):
    with db_user("User"):
        assert client.get(url, headers=auth_headers).status_code == 403


def test_flag_off_vl_health_facility_stays_403_for_db_user(client, auth_headers, not_enforced):
    with db_user("User"), patch("hiv.vl.services.vl_services_facilities._by_group", return_value=[]):
        response = client.get(
            VL_FACILITY_URL, headers=auth_headers,
            query_string={"facility_type": "health_facility"},
        )
    assert response.status_code == 403


def test_flag_off_vl_health_facility_passes_for_db_admin(client, auth_headers, not_enforced):
    with db_user("Admin"), patch("hiv.vl.services.vl_services_facilities._by_group", return_value=[]):
        response = client.get(
            VL_FACILITY_URL, headers=auth_headers,
            query_string={"facility_type": "health_facility"},
        )
    assert response.status_code == 200
