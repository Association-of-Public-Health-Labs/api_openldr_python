"""
Tests for EID Laboratory endpoints (12 routes).
Each test mocks the corresponding service function at the controller layer
and verifies a 200 response with expected data structure.
"""
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Endpoint definitions: (url, service_function_name, mock_response)
# ---------------------------------------------------------------------------
EID_LAB_ENDPOINTS = [
    (
        "/hiv/eid/laboratories/tested_samples_by_month/",
        "tested_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 200,
          "positive": 15, "negative": 165}],
    ),
    (
        "/hiv/eid/laboratories/registered_samples_by_month/",
        "registered_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 220,
          "conventional": 200, "poc": 20}],
    ),
    (
        "/hiv/eid/laboratories/labs/",
        "laboratory_labs_service",
        [{"code": "PJV", "name": "Lab A", "lab_type": "conventional"}],
    ),
    (
        "/hiv/eid/laboratories/tested_samples/",
        "tested_samples_service",
        [{"testing_facility": "Lab A", "testing_facility_code": "PJV", "total": 200,
          "positive": 15, "negative": 165}],
    ),
    (
        "/hiv/eid/laboratories/tat/",
        "tat_service",
        [{"testing_facility": "Lab A", "testing_facility_code": "PJV",
          "collection_hub_reception": 1, "hub_reception_hub_registration": 1,
          "hub_registration_lab_reception": 2, "lab_reception_lab_registration": 1,
          "lab_registration_analysis": 1, "analysis_validation": 1}],
    ),
    (
        "/hiv/eid/laboratories/tat_samples/",
        "tat_samples_service",
        [{"testing_facility": "Lab A", "testing_facility_code": "PJV",
          "category": "collection_hub_reception",
          "lt_7": 100, "between_7_15": 50, "between_16_21": 20, "gt_21": 10, "no_dates": 0}],
    ),
    (
        "/hiv/eid/laboratories/rejected_samples/",
        "rejected_samples_service",
        [{"receiving_facility": "Lab A", "receiving_facility_code": "PJV",
          "repeat_test": 1, "insufficient_sample": 2, "request_without_sample": 0,
          "technical_problems": 3, "overlapping_blood": 0, "duplicate_registration": 1,
          "misidentified_sample": 0, "sample_over_30_days": 2, "other": 1, "total": 10}],
    ),
    (
        "/hiv/eid/laboratories/rejected_samples_by_month/",
        "rejected_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "repeat_test": 1, "insufficient_sample": 2, "request_without_sample": 0,
          "technical_problems": 3, "overlapping_blood": 0, "duplicate_registration": 1,
          "misidentified_sample": 0, "sample_over_30_days": 2, "other": 1, "total": 10}],
    ),
    (
        "/hiv/eid/laboratories/samples_by_equipment/",
        "samples_by_equipment_service",
        [{"testing_facility": "Lab A", "testing_facility_code": "PJV",
          "tested": 120, "CAPCTM": 50, "ALINITY": 30, "M2000": 20, "C6800": 10,
          "PANTHER": 5, "MPIMA": 3, "MANUAL": 2}],
    ),
    (
        "/hiv/eid/laboratories/samples_by_equipment_by_month/",
        "samples_by_equipment_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "tested": 120, "CAPCTM": 50, "ALINITY": 30, "M2000": 20, "C6800": 10,
          "PANTHER": 5, "MPIMA": 3, "MANUAL": 2}],
    ),
    (
        "/hiv/eid/laboratories/sample_routes/",
        "sample_routes_service",
        [{"requesting_facility": "Facility A", "testing_facility": "Lab A",
          "requesting_latitude": "-25.9", "requesting_longitude": "32.5",
          "testing_latitude": "-25.8", "testing_longitude": "32.6", "total": 50}],
    ),
    (
        "/hiv/eid/laboratories/sample_routes_viewport/",
        "sample_routes_viewport_service",
        [{"requesting_facility": "Facility A", "testing_facility": "Lab A",
          "requesting_latitude": "-25.9", "requesting_longitude": "32.5",
          "testing_latitude": "-25.8", "testing_longitude": "32.6", "total": 50}],
    ),
]


class TestEidLaboratoryEndpoints:
    """Test all 12 EID laboratory endpoints return 200 with mocked service."""

    @pytest.mark.parametrize("url,service_name,mock_data", EID_LAB_ENDPOINTS)
    def test_endpoint_returns_200(self, client, auth_headers, url, service_name, mock_data):
        """Each endpoint should return 200 when authenticated and service returns data."""
        with patch(
            f"hiv.eid.controllers.eid_controller_laboratory.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            assert response.status_code == 200

    @pytest.mark.parametrize("url,service_name,mock_data", EID_LAB_ENDPOINTS)
    def test_endpoint_returns_json_list(self, client, auth_headers, url, service_name, mock_data):
        """Each endpoint should return a JSON list."""
        with patch(
            f"hiv.eid.controllers.eid_controller_laboratory.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0


TAT_KEYS = (
    "collection_hub_reception", "hub_reception_hub_registration",
    "hub_registration_lab_reception", "lab_reception_lab_registration",
    "lab_registration_analysis", "analysis_validation",
)


def _mock_data(service_name):
    return next(data for _, name, data in EID_LAB_ENDPOINTS if name == service_name)


def _get(client, auth_headers, url, service_name):
    with patch(
        f"hiv.eid.controllers.eid_controller_laboratory.{service_name}",
        return_value=_mock_data(service_name),
    ):
        return client.get(url, headers=auth_headers)


class TestEidTestedSamplesByMonthResponse:
    """Test response structure for tested_samples_by_month endpoint."""

    def test_response_has_expected_keys(self, client, auth_headers):
        response = _get(client, auth_headers, "/hiv/eid/laboratories/tested_samples_by_month/",
                        "tested_samples_by_month_service")
        data = response.get_json()
        assert len(data) == 1
        assert set(data[0]) == {"year", "month", "month_name", "total", "positive", "negative"}


class TestEidTatResponse:
    """Test response structure for TAT endpoint."""

    def test_tat_has_expected_keys(self, client, auth_headers):
        response = _get(client, auth_headers, "/hiv/eid/laboratories/tat/", "tat_service")
        assert set(response.get_json()[0]) == {"testing_facility", "testing_facility_code", *TAT_KEYS}


class TestEidTatSamplesResponse:
    def test_tat_samples_has_expected_keys(self, client, auth_headers):
        response = _get(client, auth_headers, "/hiv/eid/laboratories/tat_samples/?category=0",
                        "tat_samples_service")
        assert set(response.get_json()[0]) == {
            "testing_facility", "testing_facility_code", "category", "lt_7", "between_7_15", "between_16_21",
            "gt_21", "no_dates",
        }


class TestEidRejectedResponse:
    def test_rejected_has_reasons_and_total(self, client, auth_headers):
        response = _get(client, auth_headers, "/hiv/eid/laboratories/rejected_samples/",
                        "rejected_samples_service")
        assert set(response.get_json()[0]) == {
            "receiving_facility", "receiving_facility_code", "repeat_test", "insufficient_sample",
            "request_without_sample", "technical_problems", "overlapping_blood",
            "duplicate_registration", "misidentified_sample", "sample_over_30_days",
            "other", "total",
        }


class TestEidLabTypeParameter:
    """Test that lab_type parameter is accepted."""

    @pytest.mark.parametrize("lab_type", ["conventional", "poc"])
    def test_lab_type_accepted(self, client, auth_headers, lab_type):
        response = _get(
            client, auth_headers,
            f"/hiv/eid/laboratories/tested_samples_by_month/?lab_type={lab_type}",
            "tested_samples_by_month_service",
        )
        assert response.status_code == 200

    def test_invalid_lab_type_is_400(self, client, auth_headers):
        response = client.get(
            "/hiv/eid/laboratories/tested_samples/?lab_type=pcr", headers=auth_headers
        )
        assert response.status_code == 400


# summary/tat_samples/ is covered by tests/hiv/test_eid_summary_sql.py; the
# laboratory SQL by tests/hiv/test_eid_laboratory_sql.py.
@pytest.mark.parametrize(
    "category, segment",
    [("0", "collection_hub_reception"), ("5", "analysis_validation")],
)
def test_tat_samples_category_scale_is_zero_to_five(app, category, segment):
    """category 0 selects the first TAT segment (collection to hub reception), 5 the
    last; the brackets are per testing lab."""
    from tests.hiv.sql_capture import service_sql
    from hiv.eid.services.eid_services_laboratory import tat_samples_service

    row = type("Row", (), dict(testing_facility="Lab A", testing_facility_code="PJV", lt_7=1, between_7_15=0,
                               between_16_21=0, gt_21=0, no_dates=0))()
    result, _ = service_sql(
        app, tat_samples_service,
        {"interval_dates": ["2025-01-01,2025-12-31"], "category": category},
        results=[[row]],
    )
    assert isinstance(result, list), result
    assert result[0]["category"] == segment
    assert result[0]["testing_facility"] == "Lab A"


class TestEidLabsResponse:
    def test_labs_has_expected_keys(self, client, auth_headers):
        response = _get(client, auth_headers, "/hiv/eid/laboratories/labs/",
                        "laboratory_labs_service")
        assert response.status_code == 200
        assert set(response.get_json()[0]) == {"code", "name", "lab_type"}

    def test_labs_requires_auth(self, client):
        assert client.get("/hiv/eid/laboratories/labs/").status_code in (401, 422)
