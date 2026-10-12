"""
Tests for VL Laboratory endpoints (15 routes).
Each test mocks the corresponding service function at the controller layer
and verifies a 200 response with expected data structure.
"""
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Endpoint definitions: (url, service_function_name, mock_response)
# ---------------------------------------------------------------------------
VL_LAB_ENDPOINTS = [
    (
        "/hiv/vl/laboratories/registered_samples/",
        "registered_samples_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 150,
          "total_not_null": 140, "total_null": 10, "suppressed": 120,
          "not_suppressed": 20, "male_suppressed": 60, "male_not_suppressed": 10,
          "female_suppressed": 60, "female_not_suppressed": 10}],
    ),
    (
        "/hiv/vl/laboratories/registered_samples_by_month/",
        "registered_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "testing_facility": "Lab A", "total": 100, "total_not_null": 90,
          "total_null": 10, "suppressed": 80, "not_suppressed": 10,
          "male_suppressed": 40, "male_not_suppressed": 5,
          "female_suppressed": 40, "female_not_suppressed": 5}],
    ),
    (
        "/hiv/vl/laboratories/tested_samples/",
        "tested_samples_service",
        [{"testing_facility": "Lab A", "total": 200, "total_not_null": 190,
          "total_null": 10, "suppressed": 160, "not_suppressed": 30}],
    ),
    (
        "/hiv/vl/laboratories/tested_samples_by_month/",
        "tested_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 200,
          "total_not_null": 190, "total_null": 10, "suppressed": 160,
          "not_suppressed": 30, "male_suppressed": 80, "male_not_suppressed": 15,
          "female_suppressed": 80, "female_not_suppressed": 15}],
    ),
    (
        "/hiv/vl/laboratories/tested_samples_by_gender/",
        "tested_samples_by_gender_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "male_suppressed": 80, "male_not_suppressed": 15,
          "female_suppressed": 80, "female_not_suppressed": 15}],
    ),
    (
        "/hiv/vl/laboratories/tested_samples_by_gender_by_lab/",
        "tested_samples_by_gender_by_lab_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "testing_facility": "Lab A",
          "male_suppressed": 40, "male_not_suppressed": 8,
          "female_suppressed": 40, "female_not_suppressed": 7}],
    ),
    (
        "/hiv/vl/laboratories/tested_samples_by_age/",
        "tested_samples_by_age_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "age_group": "15-19", "total": 50}],
    ),
    (
        "/hiv/vl/laboratories/tested_samples_by_test_reason/",
        "tested_samples_by_test_reason_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "routine": 100, "treatment_failure": 20, "reason_not_specified": 10}],
    ),
    (
        "/hiv/vl/laboratories/tested_samples_pregnant/",
        "tested_samples_pregnant_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "total": 50, "suppressed": 40, "not_suppressed": 10}],
    ),
    (
        "/hiv/vl/laboratories/tested_samples_breastfeeding/",
        "tested_samples_breastfeeding_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "total": 30, "suppressed": 25, "not_suppressed": 5}],
    ),
    (
        "/hiv/vl/laboratories/rejected_samples/",
        "rejected_samples_service",
        [{"testing_facility": "Lab A", "total": 15}],
    ),
    (
        "/hiv/vl/laboratories/rejected_samples_by_month/",
        "rejected_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 15}],
    ),
    (
        "/hiv/vl/laboratories/tat_by_lab/",
        "tat_by_lab_service",
        [{"testing_facility": "Lab A",
          "collection_reception": 2.5, "reception_registration": 1.0,
          "registration_analysis": 0.5, "analysis_validation": 0.3}],
    ),
    (
        "/hiv/vl/laboratories/tat_by_month/",
        "tat_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "collection_reception": 2.5, "reception_registration": 1.0,
          "registration_analysis": 0.5, "analysis_validation": 0.3}],
    ),
    (
        "/hiv/vl/laboratories/suppression/",
        "suppression_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "total": 200, "suppressed": 160, "not_suppressed": 40}],
    ),
]


class TestVlLaboratoryEndpoints:
    """Test all 15 VL laboratory endpoints return 200 with mocked service."""

    @pytest.mark.parametrize("url,service_name,mock_data", VL_LAB_ENDPOINTS)
    def test_endpoint_returns_200(self, client, auth_headers, url, service_name, mock_data):
        """Each endpoint should return 200 when authenticated and service returns data."""
        with patch(
            f"hiv.vl.controllers.vl_controller_laboratory.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            assert response.status_code == 200

    @pytest.mark.parametrize("url,service_name,mock_data", VL_LAB_ENDPOINTS)
    def test_endpoint_returns_json_list(self, client, auth_headers, url, service_name, mock_data):
        """Each endpoint should return a JSON list."""
        with patch(
            f"hiv.vl.controllers.vl_controller_laboratory.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0


class TestVlRegisteredSamplesResponse:
    """Test response structure for registered_samples endpoint."""

    def test_response_has_expected_keys(self, client, auth_headers, mock_vl_service_response):
        with patch(
            "hiv.vl.controllers.vl_controller_laboratory.registered_samples_service",
            return_value=mock_vl_service_response,
        ):
            response = client.get(
                "/hiv/vl/laboratories/registered_samples/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert len(data) == 1
            row = data[0]
            expected_keys = {
                "year", "month", "month_name", "total", "total_not_null",
                "total_null", "suppressed", "not_suppressed",
                "male_suppressed", "male_not_suppressed",
                "female_suppressed", "female_not_suppressed",
            }
            assert expected_keys == set(row.keys())


class TestVlTestedSamplesResponse:
    """Test response structure for tested_samples endpoint."""

    def test_response_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"testing_facility": "Lab A", "total": 200,
             "total_not_null": 190, "total_null": 10,
             "suppressed": 160, "not_suppressed": 30}
        ]
        with patch(
            "hiv.vl.controllers.vl_controller_laboratory.tested_samples_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/vl/laboratories/tested_samples/",
                headers=auth_headers,
            )
            data = response.get_json()
            row = data[0]
            expected_keys = {
                "testing_facility", "total", "total_not_null",
                "total_null", "suppressed", "not_suppressed",
            }
            assert expected_keys == set(row.keys())


class TestVlTatResponse:
    """Test response structure for TAT endpoints."""

    def test_tat_by_lab_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"testing_facility": "Lab A",
             "collection_reception": 2.5, "reception_registration": 1.0,
             "registration_analysis": 0.5, "analysis_validation": 0.3}
        ]
        with patch(
            "hiv.vl.controllers.vl_controller_laboratory.tat_by_lab_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/vl/laboratories/tat_by_lab/",
                headers=auth_headers,
            )
            data = response.get_json()
            row = data[0]
            expected_keys = {
                "testing_facility", "collection_reception",
                "reception_registration", "registration_analysis",
                "analysis_validation",
            }
            assert expected_keys == set(row.keys())
