"""
Tests for EID Facility endpoints (14 routes).
Each test mocks the corresponding service function at the controller layer
and verifies a 200 response with expected data structure.
"""
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Endpoint definitions: (url, service_function_name, mock_response)
# ---------------------------------------------------------------------------
EID_FACILITY_ENDPOINTS = [
    (
        "/hiv/eid/facilities/registered_samples/",
        "facility_registered_samples_service",
        [{"requesting_facility": "Gaza", "conventional": 120, "poc": 30, "total": 150}],
    ),
    (
        "/hiv/eid/facilities/registered_samples_by_month/",
        "facility_registered_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "conventional": 120, "poc": 30, "total": 150}],
    ),
    (
        "/hiv/eid/facilities/tested_samples/",
        "facility_tested_samples_service",
        [{"requesting_facility": "Gaza", "conventional": 150, "poc": 50,
          "total": 200, "positive": 15, "negative": 165}],
    ),
    (
        "/hiv/eid/facilities/tested_samples_by_month/",
        "facility_tested_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "conventional": 150, "poc": 50, "total": 200,
          "positive": 15, "negative": 165}],
    ),
    (
        "/hiv/eid/facilities/tested_samples_by_gender/",
        "facility_tested_samples_by_gender_service",
        [{"requesting_facility": "Gaza", "male_positive": 7, "male_negative": 80,
          "female_positive": 8, "female_negative": 85}],
    ),
    (
        "/hiv/eid/facilities/tested_samples_by_gender_by_month/",
        "facility_tested_samples_by_gender_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "male_positive": 7, "male_negative": 80,
          "female_positive": 8, "female_negative": 85}],
    ),
    (
        "/hiv/eid/facilities/tat_avg_by_month/",
        "facility_tat_avg_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "collection_hub_reception": 1, "hub_reception_hub_registration": 1,
          "hub_registration_lab_reception": 2, "lab_reception_lab_registration": 1,
          "lab_registration_analysis": 1, "analysis_validation": 1}],
    ),
    (
        "/hiv/eid/facilities/tat_avg/",
        "facility_tat_avg_service",
        [{"requesting_facility": "Health Center A",
          "collection_hub_reception": 1, "hub_reception_hub_registration": 1,
          "hub_registration_lab_reception": 2, "lab_reception_lab_registration": 1,
          "lab_registration_analysis": 1, "analysis_validation": 1}],
    ),
    (
        "/hiv/eid/facilities/tat_days_by_month/",
        "facility_tat_days_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "category": "collection_hub_reception", "lt_7": 100, "between_7_15": 50,
          "between_16_21": 20, "gt_21": 10, "no_dates": 3}],
    ),
    (
        "/hiv/eid/facilities/tat_days/",
        "facility_tat_days_service",
        [{"requesting_facility": "Health Center A",
          "category": "collection_hub_reception", "lt_7": 100, "between_7_15": 50,
          "between_16_21": 20, "gt_21": 10, "no_dates": 3}],
    ),
    (
        "/hiv/eid/facilities/rejected_samples_by_month/",
        "facility_rejected_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "repeat_test": 1, "insufficient_sample": 2,
          "request_without_sample": 3, "technical_problems": 4, "overlapping_blood": 0,
          "duplicate_registration": 1, "misidentified_sample": 0,
          "sample_over_30_days": 2, "other": 2, "total": 15}],
    ),
    (
        "/hiv/eid/facilities/rejected_samples/",
        "facility_rejected_samples_service",
        [{"requesting_facility": "Gaza", "repeat_test": 1, "insufficient_sample": 2,
          "request_without_sample": 3, "technical_problems": 4, "overlapping_blood": 0,
          "duplicate_registration": 1, "misidentified_sample": 0,
          "sample_over_30_days": 2, "other": 2, "total": 15}],
    ),
    (
        "/hiv/eid/facilities/key_indicators/",
        "facility_key_indicators_service",
        [{"requesting_facility": "Health Center A", "registered": 220,
          "tested": 200, "rejected": 15, "pending": 5,
          "positive": 15, "positivity": 7.5}],
    ),
    (
        "/hiv/eid/facilities/tested_samples_by_age/",
        "facility_tested_samples_by_age_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "age_group": "0-2 months", "total": 50}],
    ),
]


class TestEidFacilityEndpoints:
    """Test all 14 EID facility endpoints return 200 with mocked service."""

    @pytest.mark.parametrize("url,service_name,mock_data", EID_FACILITY_ENDPOINTS)
    def test_endpoint_returns_200(self, client, auth_headers, url, service_name, mock_data):
        """Each endpoint should return 200 when authenticated and service returns data."""
        with patch(
            f"hiv.eid.controllers.eid_controller_facility.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            assert response.status_code == 200

    @pytest.mark.parametrize("url,service_name,mock_data", EID_FACILITY_ENDPOINTS)
    def test_endpoint_returns_json_list(self, client, auth_headers, url, service_name, mock_data):
        """Each endpoint should return a JSON list."""
        with patch(
            f"hiv.eid.controllers.eid_controller_facility.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0


class TestEidFacilityTestedSamplesResponse:
    """Test response structure for facility tested_samples endpoint."""

    def test_response_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"requesting_facility": "Gaza", "conventional": 150, "poc": 50,
             "total": 200, "positive": 15, "negative": 165}
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_facility.facility_tested_samples_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/facilities/tested_samples/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert len(data) == 1
            row = data[0]
            expected_keys = {
                "requesting_facility", "conventional", "poc", "total",
                "positive", "negative",
            }
            assert expected_keys == set(row.keys())


class TestEidFacilityKeyIndicatorsResponse:
    """Test response structure for facility key_indicators endpoint."""

    def test_response_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"requesting_facility": "Health Center A", "registered": 220,
             "tested": 200, "rejected": 15, "pending": 5,
             "positive": 15, "positivity": 7.5}
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_facility.facility_key_indicators_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/facilities/key_indicators/",
                headers=auth_headers,
            )
            data = response.get_json()
            row = data[0]
            expected_keys = {
                "requesting_facility", "registered", "tested",
                "rejected", "pending", "positive", "positivity",
            }
            assert expected_keys == set(row.keys())


class TestEidFacilityTatResponse:
    """Test response structure for facility TAT endpoints."""

    def test_tat_avg_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"requesting_facility": "Health Center A",
             "collection_hub_reception": 1, "hub_reception_hub_registration": 1,
             "hub_registration_lab_reception": 2, "lab_reception_lab_registration": 1,
             "lab_registration_analysis": 1, "analysis_validation": 1}
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_facility.facility_tat_avg_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/facilities/tat_avg/",
                headers=auth_headers,
            )
            data = response.get_json()
            row = data[0]
            expected_keys = {
                "requesting_facility",
                "collection_hub_reception", "hub_reception_hub_registration",
                "hub_registration_lab_reception", "lab_reception_lab_registration",
                "lab_registration_analysis", "analysis_validation",
            }
            assert expected_keys == set(row.keys())


class TestEidFacilityLabTypeParameter:
    """Test that lab_type parameter is accepted."""

    def test_lab_type_conventional(self, client, auth_headers):
        mock_data = [{"requesting_facility": "Health Center A", "total": 100,
                       "positive": 5, "negative": 85}]
        with patch(
            "hiv.eid.controllers.eid_controller_facility.facility_tested_samples_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/facilities/tested_samples/?lab_type=conventional",
                headers=auth_headers,
            )
            assert response.status_code == 200

    def test_lab_type_poc(self, client, auth_headers):
        mock_data = [{"requesting_facility": "Health Center A", "total": 100,
                       "positive": 10, "negative": 80}]
        with patch(
            "hiv.eid.controllers.eid_controller_facility.facility_tested_samples_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/facilities/tested_samples/?lab_type=poc",
                headers=auth_headers,
            )
            assert response.status_code == 200
