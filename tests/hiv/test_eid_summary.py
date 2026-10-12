"""
Tests for EID Summary/Dashboard endpoints (10 routes).
Each test mocks the corresponding service function at the controller layer
and verifies a 200 response with expected data structure.
"""
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Endpoint definitions: (url, service_function_name, mock_response)
# ---------------------------------------------------------------------------
EID_SUMMARY_ENDPOINTS = [
    (
        "/hiv/eid/summary/indicators/",
        "summary_indicators_service",
        {
            "registered": 10000,
            "tested": 8500,
            "rejected": 300,
            "pending": 1200,
            "positive": 850,
            "negative": 7650,
        },
    ),
    (
        "/hiv/eid/summary/tat/",
        "summary_tat_service",
        [
            {
                "year": 2024,
                "month": 1,
                "month_name": "January",
                "collection_receiveHub": 1.5,
                "receiveHub_registrationHub": 0.5,
                "registrationHub_receiveLab": 2.0,
                "receiveLab_registrationLab": 0.3,
                "registrationLab_analyseLab": 1.0,
                "analyseLab_validationLab": 0.2,
            }
        ],
    ),
    (
        "/hiv/eid/summary/tat_samples/",
        "summary_tat_samples_service",
        [
            {
                "category": "collection_receiveHub",
                "less_7": 500,
                "between_7_14": 200,
                "between_15_21": 80,
                "greater_21": 20,
            }
        ],
    ),
    (
        "/hiv/eid/summary/positivity/",
        "summary_positivity_service",
        [
            {
                "year": 2024,
                "month": 1,
                "month_name": "January",
                "total": 900,
                "positive": 90,
                "negative": 810,
            }
        ],
    ),
    (
        "/hiv/eid/summary/number_of_samples/",
        "summary_number_of_samples_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 1000}],
    ),
    (
        "/hiv/eid/summary/indicators_by_province/",
        "summary_indicators_by_province_service",
        [
            {
                "province": "Maputo",
                "total": 2000,
                "tested": 1700,
                "positive": 170,
                "conventional": 1500,
                "poc": 200,
            }
        ],
    ),
    (
        "/hiv/eid/summary/samples_positivity/",
        "summary_samples_positivity_service",
        {
            "total": 8500,
            "positive": 850,
            "negative": 7650,
            "female_positive": 420,
            "male_positive": 430,
            "female_negative": 3800,
            "male_negative": 3850,
        },
    ),
    (
        "/hiv/eid/summary/rejected_samples_by_month/",
        "summary_rejected_samples_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 30}],
    ),
    (
        "/hiv/eid/summary/samples_by_equipment/",
        "summary_samples_by_equipment_service",
        [
            {
                "CAPCTM": 3000,
                "ALINITY": 1500,
                "M2000": 1200,
                "C6800": 800,
                "PANTHER": 600,
                "MPIMA": 400,
                "MANUAL": 1000,
            }
        ],
    ),
    (
        "/hiv/eid/summary/samples_by_equipment_by_month/",
        "summary_samples_by_equipment_by_month_service",
        [
            {
                "year": 2024,
                "month": 1,
                "month_name": "January",
                "CAPCTM": 250,
                "ALINITY": 125,
                "M2000": 100,
                "C6800": 67,
                "PANTHER": 50,
                "MPIMA": 33,
                "MANUAL": 83,
            }
        ],
    ),
]


class TestEidSummaryEndpoints:
    """Test all 10 EID summary endpoints return 200 with mocked service."""

    @pytest.mark.parametrize("url,service_name,mock_data", EID_SUMMARY_ENDPOINTS)
    def test_endpoint_returns_200(self, client, auth_headers, url, service_name, mock_data):
        """Each endpoint should return 200 when authenticated and service returns data."""
        with patch(
            f"hiv.eid.controllers.eid_controller_summary.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            assert response.status_code == 200


class TestEidSummaryIndicatorsResponse:
    """Test response structure for indicators endpoint."""

    def test_response_is_dict_with_expected_keys(self, client, auth_headers):
        mock_data = {
            "registered": 10000,
            "tested": 8500,
            "rejected": 300,
            "pending": 1200,
            "positive": 850,
            "negative": 7650,
        }
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_indicators_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/indicators/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, dict)
            expected_keys = {"registered", "tested", "rejected", "pending", "positive", "negative"}
            assert expected_keys == set(data.keys())


class TestEidSummaryTatResponse:
    """Test response structure for tat endpoint."""

    def test_response_is_list_with_expected_keys(self, client, auth_headers):
        mock_data = [
            {
                "year": 2024,
                "month": 1,
                "month_name": "January",
                "collection_receiveHub": 1.5,
                "receiveHub_registrationHub": 0.5,
                "registrationHub_receiveLab": 2.0,
                "receiveLab_registrationLab": 0.3,
                "registrationLab_analyseLab": 1.0,
                "analyseLab_validationLab": 0.2,
            }
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_tat_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/tat/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0
            row = data[0]
            expected_keys = {
                "year", "month", "month_name",
                "collection_receiveHub", "receiveHub_registrationHub",
                "registrationHub_receiveLab", "receiveLab_registrationLab",
                "registrationLab_analyseLab", "analyseLab_validationLab",
            }
            assert expected_keys == set(row.keys())


class TestEidSummaryTatSamplesResponse:
    """Test response structure for tat_samples endpoint."""

    def test_response_is_list_with_expected_keys(self, client, auth_headers):
        mock_data = [
            {
                "category": "collection_receiveHub",
                "less_7": 500,
                "between_7_14": 200,
                "between_15_21": 80,
                "greater_21": 20,
            }
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_tat_samples_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/tat_samples/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0
            row = data[0]
            expected_keys = {"category", "less_7", "between_7_14", "between_15_21", "greater_21"}
            assert expected_keys == set(row.keys())


class TestEidSummaryPositivityResponse:
    """Test response structure for positivity endpoint."""

    def test_response_is_list_with_expected_keys(self, client, auth_headers):
        mock_data = [
            {
                "year": 2024,
                "month": 1,
                "month_name": "January",
                "total": 900,
                "positive": 90,
                "negative": 810,
            }
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_positivity_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/positivity/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0
            row = data[0]
            expected_keys = {"year", "month", "month_name", "total", "positive", "negative"}
            assert expected_keys == set(row.keys())


class TestEidSummaryNumberOfSamplesResponse:
    """Test response structure for number_of_samples endpoint."""

    def test_response_is_list_with_expected_keys(self, client, auth_headers):
        mock_data = [{"year": 2024, "month": 1, "month_name": "January", "total": 1000}]
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_number_of_samples_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/number_of_samples/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0
            row = data[0]
            expected_keys = {"year", "month", "month_name", "total"}
            assert expected_keys == set(row.keys())


class TestEidSummaryIndicatorsByProvinceResponse:
    """Test response structure for indicators_by_province endpoint."""

    def test_response_is_list_with_expected_keys(self, client, auth_headers):
        mock_data = [
            {
                "province": "Maputo",
                "total": 2000,
                "tested": 1700,
                "positive": 170,
                "conventional": 1500,
                "poc": 200,
            }
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_indicators_by_province_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/indicators_by_province/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0
            row = data[0]
            expected_keys = {"province", "total", "tested", "positive", "conventional", "poc"}
            assert expected_keys == set(row.keys())


class TestEidSummarySamplesPositivityResponse:
    """Test response structure for samples_positivity endpoint."""

    def test_response_is_dict_with_expected_keys(self, client, auth_headers):
        mock_data = {
            "total": 8500,
            "positive": 850,
            "negative": 7650,
            "female_positive": 420,
            "male_positive": 430,
            "female_negative": 3800,
            "male_negative": 3850,
        }
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_samples_positivity_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/samples_positivity/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, dict)
            expected_keys = {
                "total", "positive", "negative",
                "female_positive", "male_positive",
                "female_negative", "male_negative",
            }
            assert expected_keys == set(data.keys())


class TestEidSummaryRejectedSamplesByMonthResponse:
    """Test response structure for rejected_samples_by_month endpoint."""

    def test_response_is_list_with_expected_keys(self, client, auth_headers):
        mock_data = [{"year": 2024, "month": 1, "month_name": "January", "total": 30}]
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_rejected_samples_by_month_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/rejected_samples_by_month/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0
            row = data[0]
            expected_keys = {"year", "month", "month_name", "total"}
            assert expected_keys == set(row.keys())


class TestEidSummarySamplesByEquipmentResponse:
    """Test response structure for samples_by_equipment endpoint."""

    def test_response_is_list_with_expected_keys(self, client, auth_headers):
        mock_data = [
            {
                "CAPCTM": 3000,
                "ALINITY": 1500,
                "M2000": 1200,
                "C6800": 800,
                "PANTHER": 600,
                "MPIMA": 400,
                "MANUAL": 1000,
            }
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_samples_by_equipment_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/samples_by_equipment/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0
            row = data[0]
            expected_keys = {"CAPCTM", "ALINITY", "M2000", "C6800", "PANTHER", "MPIMA", "MANUAL"}
            assert expected_keys == set(row.keys())


class TestEidSummarySamplesByEquipmentByMonthResponse:
    """Test response structure for samples_by_equipment_by_month endpoint."""

    def test_response_is_list_with_expected_keys(self, client, auth_headers):
        mock_data = [
            {
                "year": 2024,
                "month": 1,
                "month_name": "January",
                "CAPCTM": 250,
                "ALINITY": 125,
                "M2000": 100,
                "C6800": 67,
                "PANTHER": 50,
                "MPIMA": 33,
                "MANUAL": 83,
            }
        ]
        with patch(
            "hiv.eid.controllers.eid_controller_summary.summary_samples_by_equipment_by_month_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/hiv/eid/summary/samples_by_equipment_by_month/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0
            row = data[0]
            expected_keys = {
                "year", "month", "month_name",
                "CAPCTM", "ALINITY", "M2000", "C6800", "PANTHER", "MPIMA", "MANUAL",
            }
            assert expected_keys == set(row.keys())
