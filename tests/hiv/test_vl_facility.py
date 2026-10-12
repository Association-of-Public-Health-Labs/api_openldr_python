"""
Tests for VL Facility endpoints (14 routes).
Each test mocks the corresponding service function at the controller layer
and verifies a 200 response with expected data structure.
"""
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Endpoint definitions: (url, service_function_name, mock_response)
# ---------------------------------------------------------------------------
VL_FACILITY_ENDPOINTS = [
    (
        "/hiv/vl/facilities/registered_samples/",
        "facility_registered_samples_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 150,
          "total_not_null": 140, "total_null": 10, "suppressed": 120,
          "not_suppressed": 20, "male_suppressed": 60, "male_not_suppressed": 10,
          "female_suppressed": 60, "female_not_suppressed": 10}],
    ),
    (
        "/hiv/vl/facilities/tested_samples_by_month/",
        "facility_tested_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 200,
          "total_not_null": 190, "total_null": 10, "suppressed": 160,
          "not_suppressed": 30, "male_suppressed": 80, "male_not_suppressed": 15,
          "female_suppressed": 80, "female_not_suppressed": 15}],
    ),
    (
        "/hiv/vl/facilities/tested_samples_by_facility/",
        "facility_tested_samples_by_facility_service",
        [{"requesting_facility": "Health Center A", "total": 200,
          "total_not_null": 190, "total_null": 10,
          "suppressed": 160, "not_suppressed": 30}],
    ),
    (
        "/hiv/vl/facilities/tested_samples_by_gender_by_month/",
        "facility_tested_samples_by_month_by_gender_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "male_suppressed": 80, "male_not_suppressed": 15,
          "female_suppressed": 80, "female_not_suppressed": 15}],
    ),
    (
        "/hiv/vl/facilities/tested_samples_by_gender_by_facility/",
        "facility_tested_samples_by_gender_by_facility_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "requesting_facility": "Health Center A",
          "male_suppressed": 40, "male_not_suppressed": 8,
          "female_suppressed": 40, "female_not_suppressed": 7}],
    ),
    (
        "/hiv/vl/facilities/tested_samples_by_age_by_month/",
        "facility_tested_samples_by_age_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "age_group": "15-19", "total": 50}],
    ),
    (
        "/hiv/vl/facilities/tested_samples_by_age_by_facility/",
        "facility_tested_samples_by_age_by_facility_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "requesting_facility": "Health Center A",
          "age_group": "15-19", "total": 25}],
    ),
    (
        "/hiv/vl/facilities/tested_samples_by_test_reason_by_month/",
        "facility_tested_samples_by_test_reason_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "routine": 100, "treatment_failure": 20,
          "reason_not_specified": 10, "total": 130}],
    ),
    (
        "/hiv/vl/facilities/tested_samples_pregnant/",
        "facility_tested_samples_pregnant_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "total": 50, "suppressed": 40, "not_suppressed": 10}],
    ),
    (
        "/hiv/vl/facilities/tested_samples_breastfeeding/",
        "facility_tested_samples_breastfeeding_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "total": 30, "suppressed": 25, "not_suppressed": 5}],
    ),
    (
        "/hiv/vl/facilities/rejected_samples_by_month/",
        "facility_rejected_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 15}],
    ),
    (
        "/hiv/vl/facilities/rejected_samples_by_facility/",
        "facility_rejected_samples_by_facility_service",
        [{"requesting_facility": "Health Center A", "total": 15}],
    ),
    (
        "/hiv/vl/facilities/tat_by_month/",
        "facility_tat_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "collection_reception": 2.5, "reception_registration": 1.0,
          "registration_analysis": 0.5, "analysis_validation": 0.3}],
    ),
    (
        "/hiv/vl/facilities/tat_by_facility/",
        "facility_tat_by_facility_service",
        [{"requesting_facility": "Health Center A",
          "collection_reception": 2.5, "reception_registration": 1.0,
          "registration_analysis": 0.5, "analysis_validation": 0.3}],
    ),
]


class TestVlFacilityEndpoints:
    """Test all 14 VL facility endpoints return 200 with mocked service."""

    @pytest.mark.parametrize("url,service_name,mock_data", VL_FACILITY_ENDPOINTS)
    def test_endpoint_returns_200(self, client, auth_headers, url, service_name, mock_data):
        """Each endpoint should return 200 when authenticated and service returns data."""
        with patch(
            f"hiv.vl.controllers.vl_controller_facility.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            assert response.status_code == 200

    @pytest.mark.parametrize("url,service_name,mock_data", VL_FACILITY_ENDPOINTS)
    def test_endpoint_returns_json_list(self, client, auth_headers, url, service_name, mock_data):
        """Each endpoint should return a JSON list."""
        with patch(
            f"hiv.vl.controllers.vl_controller_facility.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0


class TestVlFacilityRegisteredSamplesResponse:
    """Test response structure for facility registered_samples endpoint."""

    def test_response_has_expected_keys(self, client, auth_headers, mock_vl_service_response):
        with patch(
            "hiv.vl.controllers.vl_controller_facility.facility_registered_samples_service",
            return_value=mock_vl_service_response,
        ):
            response = client.get(
                "/hiv/vl/facilities/registered_samples/",
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


class TestVlFacilityTestedSamplesByFacilityResponse:
    """Test response structure for tested_samples_by_facility endpoint."""

    def test_response_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"requesting_facility": "Health Center A", "total": 200,
             "total_not_null": 190, "total_null": 10,
             "suppressed": 160, "not_suppressed": 30}
        ]
        with patch(
            "hiv.vl.controllers.vl_controller_facility.facility_tested_samples_by_facility_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/vl/facilities/tested_samples_by_facility/",
                headers=auth_headers,
            )
            data = response.get_json()
            row = data[0]
            expected_keys = {
                "requesting_facility", "total", "total_not_null",
                "total_null", "suppressed", "not_suppressed",
            }
            assert expected_keys == set(row.keys())


class TestVlFacilityTatResponse:
    """Test response structure for facility TAT endpoints."""

    def test_tat_by_facility_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"requesting_facility": "Health Center A",
             "collection_reception": 2.5, "reception_registration": 1.0,
             "registration_analysis": 0.5, "analysis_validation": 0.3}
        ]
        with patch(
            "hiv.vl.controllers.vl_controller_facility.facility_tat_by_facility_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/vl/facilities/tat_by_facility/",
                headers=auth_headers,
            )
            data = response.get_json()
            row = data[0]
            expected_keys = {
                "requesting_facility", "collection_reception",
                "reception_registration", "registration_analysis",
                "analysis_validation",
            }
            assert expected_keys == set(row.keys())
