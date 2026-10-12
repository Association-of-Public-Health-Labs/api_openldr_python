"""
Tests for EID Laboratory endpoints (11 routes).
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
          "positive": 15, "negative": 165, "female": 95, "male": 85}],
    ),
    (
        "/hiv/eid/laboratories/registered_samples_by_month/",
        "registered_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 220}],
    ),
    (
        "/hiv/eid/laboratories/tested_samples/",
        "tested_samples_service",
        [{"testing_facility": "Lab A", "total": 200, "positive": 15, "negative": 165}],
    ),
    (
        "/hiv/eid/laboratories/tat/",
        "tat_service",
        [{"testing_facility": "Lab A",
          "collection_receiveHub": 1.5, "receiveHub_registrationHub": 0.5,
          "registrationHub_receiveLab": 2.0, "receiveLab_registrationLab": 0.3,
          "registrationLab_analyseLab": 1.0, "analyseLab_validationLab": 0.2}],
    ),
    (
        "/hiv/eid/laboratories/tat_samples/",
        "tat_samples_service",
        [{"category": "collection_receiveHub",
          "less_7": 100, "between_7_14": 50, "between_15_21": 20, "greater_21": 10}],
    ),
    (
        "/hiv/eid/laboratories/rejected_samples/",
        "rejected_samples_service",
        [{"testing_facility": "Lab A", "total": 15}],
    ),
    (
        "/hiv/eid/laboratories/rejected_samples_by_month/",
        "rejected_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 15}],
    ),
    (
        "/hiv/eid/laboratories/samples_by_equipment/",
        "samples_by_equipment_service",
        [{"testing_facility": "Lab A", "CAPCTM": 50, "ALINITY": 30,
          "M2000": 20, "C6800": 10, "PANTHER": 5, "MPIMA": 3, "MANUAL": 2}],
    ),
    (
        "/hiv/eid/laboratories/samples_by_equipment_by_month/",
        "samples_by_equipment_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "CAPCTM": 50, "ALINITY": 30, "M2000": 20, "C6800": 10,
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
    """Test all 11 EID laboratory endpoints return 200 with mocked service."""

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


class TestEidTestedSamplesByMonthResponse:
    """Test response structure for tested_samples_by_month endpoint."""

    def test_response_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"year": 2024, "month": 1, "month_name": "January",
             "total": 200, "positive": 15, "negative": 165,
             "female": 95, "male": 85}
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_laboratory.tested_samples_by_month_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/laboratories/tested_samples_by_month/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert len(data) == 1
            row = data[0]
            expected_keys = {
                "year", "month", "month_name", "total",
                "positive", "negative", "female", "male",
            }
            assert expected_keys == set(row.keys())


class TestEidTatResponse:
    """Test response structure for TAT endpoint."""

    def test_tat_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"testing_facility": "Lab A",
             "collection_receiveHub": 1.5, "receiveHub_registrationHub": 0.5,
             "registrationHub_receiveLab": 2.0, "receiveLab_registrationLab": 0.3,
             "registrationLab_analyseLab": 1.0, "analyseLab_validationLab": 0.2}
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_laboratory.tat_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/laboratories/tat/",
                headers=auth_headers,
            )
            data = response.get_json()
            row = data[0]
            expected_keys = {
                "testing_facility",
                "collection_receiveHub", "receiveHub_registrationHub",
                "registrationHub_receiveLab", "receiveLab_registrationLab",
                "registrationLab_analyseLab", "analyseLab_validationLab",
            }
            assert expected_keys == set(row.keys())


class TestEidLabTypeParameter:
    """Test that lab_type parameter is accepted."""

    def test_lab_type_conventional(self, client, auth_headers):
        mock_data = [{"year": 2024, "month": 1, "month_name": "January",
                       "total": 100, "positive": 5, "negative": 85,
                       "female": 45, "male": 40}]
        with patch(
            "hiv.eid.controllers.eid_controller_laboratory.tested_samples_by_month_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/laboratories/tested_samples_by_month/?lab_type=conventional",
                headers=auth_headers,
            )
            assert response.status_code == 200

    def test_lab_type_poc(self, client, auth_headers):
        mock_data = [{"year": 2024, "month": 1, "month_name": "January",
                       "total": 100, "positive": 10, "negative": 80,
                       "female": 50, "male": 40}]
        with patch(
            "hiv.eid.controllers.eid_controller_laboratory.tested_samples_by_month_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/laboratories/tested_samples_by_month/?lab_type=poc",
                headers=auth_headers,
            )
            assert response.status_code == 200
