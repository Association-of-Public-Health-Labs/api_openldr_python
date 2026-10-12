"""
Tests for VL Summary/Dashboard endpoints (6 routes).

Each test mocks the corresponding service function imported by
``hiv.vl.controllers.vl_controller_summary`` and verifies a 200 response
with the expected JSON shape.
"""
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Endpoint definitions: (url, service_function_name, mock_response)
# Names must match the symbols imported by vl_controller_summary.py.
# ---------------------------------------------------------------------------
VL_SUMMARY_ENDPOINTS = [
    (
        "/hiv/vl/summary/header_indicators_by_month/",
        "header_indicators_service_by_month",
        [{"year": 2024, "month": 1, "month_name": "January",
          "registered": 5000, "tested": 4500, "suppressed": 3800,
          "not_suppressed": 700, "rejected": 120}],
    ),
    (
        "/hiv/vl/summary/number_of_samples_by_month/",
        "number_of_samples_service_by_month",
        [{"year": 2024, "month": 1, "month_name": "January", "total": 450}],
    ),
    (
        "/hiv/vl/summary/viral_suppression_by_month/",
        "viral_suppression_service_by_month",
        [{"year": 2024, "month": 1, "month_name": "January",
          "suppressed": 360, "not_suppressed": 60}],
    ),
    (
        "/hiv/vl/summary/tat_by_month/",
        "tat_service_by_month",
        [{"year": 2024, "month": 1, "month_name": "January",
          "collection_reception": 2.5, "reception_registration": 1.0,
          "registration_analysis": 0.5, "analysis_validation": 0.3}],
    ),
    (
        "/hiv/vl/summary/suppression_by_province_by_month/",
        "suppression_by_province_service_by_month",
        [{"province": "Maputo", "suppressed": 1200, "not_suppressed": 200}],
    ),
    (
        "/hiv/vl/summary/samples_history/",
        "samples_history_service_by_month",
        [{"year": 2023, "month": 6, "month_name": "June", "total": 380}],
    ),
]


class TestVlSummaryEndpoints:
    """Smoke-test all 6 VL summary endpoints with a mocked service."""

    @pytest.mark.parametrize("url,service_name,mock_data", VL_SUMMARY_ENDPOINTS)
    def test_endpoint_returns_200(self, client, auth_headers, url, service_name, mock_data):
        with patch(
            f"hiv.vl.controllers.vl_controller_summary.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            assert response.status_code == 200

    @pytest.mark.parametrize("url,service_name,mock_data", VL_SUMMARY_ENDPOINTS)
    def test_endpoint_returns_json(self, client, auth_headers, url, service_name, mock_data):
        with patch(
            f"hiv.vl.controllers.vl_controller_summary.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            data = response.get_json()
            assert data is not None
