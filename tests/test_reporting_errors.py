"""run_reporting_endpoint maps service results to real HTTP status codes."""
from unittest.mock import patch

from utilities.service_helpers import InvalidParameter

URL = "/hiv/vl/summary/samples_history/"
TARGET = "hiv.vl.controllers.vl_controller_summary.samples_history_service_by_month"


def test_list_result_passes_through(client, auth_headers):
    with patch(TARGET, return_value=[{"year": 2025}]):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == [{"year": 2025}]


def test_service_error_dict_keeps_4xx_status_and_message(client, auth_headers):
    body = {"status": "error", "code": 403, "message": "Forbidden - not an Admin"}
    with patch(TARGET, return_value=dict(body)):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 403
    assert response.get_json() == body


def test_service_error_dict_500_hides_detail(client, auth_headers):
    leaked = {
        "status": "error", "code": 500, "message": "An Error Occurred",
        "error": "(pyodbc.OperationalError) [SQL: SELECT [VlData].[RequestID] FROM VlData]",
    }
    with patch(TARGET, return_value=leaked):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "code": 500, "message": "An error occurred"}
    assert b"SELECT" not in response.data and b"pyodbc" not in response.data


def test_service_error_dict_without_valid_code_becomes_500(client, auth_headers):
    with patch(TARGET, return_value={"status": "error", "code": "oops", "message": "x"}):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 500


def test_invalid_parameter_returns_400(client, auth_headers):
    with patch(TARGET, side_effect=InvalidParameter("age_range must be two whole numbers: min,max")):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error", "code": 400,
        "message": "age_range must be two whole numbers: min,max",
    }


def test_unexpected_exception_returns_generic_500(client, auth_headers):
    with patch(TARGET, side_effect=RuntimeError("pyodbc: SELECT secret FROM VlData")):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 500
    assert b"SELECT" not in response.data


def test_vl_parser_accepts_lab_code_age_range_and_repeated_dates(client, auth_headers):
    query = (
        "?lab_code=PCD&lab_code=PDD&age_range=15,49"
        "&interval_dates=2025-01-01&interval_dates=2025-03-31"
    )
    with patch(TARGET, return_value=[]) as service:
        response = client.get(URL + query, headers=auth_headers)
    assert response.status_code == 200
    req_args = service.call_args[0][0]
    assert req_args["lab_code"] == ["PCD", "PDD"]
    assert req_args["age_range"] == ["15,49"]
    assert req_args["interval_dates"] == ["2025-01-01", "2025-03-31"]


def test_patients_parser_accepts_drill_down_filters(client, auth_headers):
    target = "hiv.vl.controllers.vl_controller_patients.get_patients_by_facility_service"
    query = "?health_facility=CS%20X&pregnant=true&breastfeeding=false&rejected=1&lab_code=PCD&age_range=15,49"
    with patch(target, return_value={"status": "success", "data": []}) as service:
        response = client.get("/hiv/vl/patients/by_facility/" + query, headers=auth_headers)
    assert response.status_code == 200
    req_args = service.call_args[0][0]
    assert (req_args["pregnant"], req_args["breastfeeding"], req_args["rejected"]) == ("true", "false", "1")
    assert req_args["lab_code"] == ["PCD"] and req_args["age_range"] == ["15,49"]
