"""
Tests for TB GeneXpert Facility endpoints (20 routes).

Each test mocks the corresponding service function imported by
``tb.gxpert.controllers.tb_gx_controller_facility`` and verifies a 200
response with the expected JSON list shape.
"""
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Endpoint definitions: (url, service_function_name, mock_response)
# Service names must match the symbols imported in
# tb/gxpert/controllers/tb_gx_controller_facility.py.
# ---------------------------------------------------------------------------
TB_FACILITY_ENDPOINTS = [
    (
        "/tb/gx/facilities/registered_samples/",
        "registered_samples_by_facility_service",
        [{"requesting_facility": "Health Center A", "total": 150}],
    ),
    (
        "/tb/gx/facilities/registered_samples_by_month/",
        "registered_samples_by_month_by_facility_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "requesting_facility": "Health Center A", "total": 150}],
    ),
    (
        "/tb/gx/facilities/tested_samples/",
        "tested_samples_by_facility_service",
        [{"requesting_facility": "Health Center A",
          "total": 200, "positive": 30, "negative": 160, "indeterminate": 10}],
    ),
    (
        "/tb/gx/facilities/tested_samples_by_month/",
        "tested_samples_by_month_by_facility_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "requesting_facility": "Health Center A",
          "total": 200, "positive": 30, "negative": 160}],
    ),
    (
        "/tb/gx/facilities/tested_samples_disaggregated/",
        "tested_samples_by_facility_disaggregated_service",
        [{"requesting_facility": "Health Center A",
          "rifampicin_resistance": 5, "rifampicin_sensitive": 25}],
    ),
    (
        "/tb/gx/facilities/tested_samples_disaggregated_by_gender/",
        "tested_samples_by_facility_disaggregated_by_gender_service",
        [{"requesting_facility": "Health Center A",
          "male": 110, "female": 90}],
    ),
    (
        "/tb/gx/facilities/tested_samples_disaggregated_by_age/",
        "tested_samples_by_facility_disaggregated_by_age_service",
        [{"requesting_facility": "Health Center A",
          "age_group": "15-19", "total": 25}],
    ),
    (
        "/tb/gx/facilities/tested_samples_by_sample_types/",
        "tested_samples_by_sample_types_by_facility_service",
        [{"requesting_facility": "Health Center A",
          "sputum": 150, "feces": 10, "urine": 5, "blood": 35}],
    ),
    (
        "/tb/gx/facilities/tested_samples_types_disaggregated_by_age/",
        "tested_samples_types_by_facility_disaggregated_by_age_service",
        [{"requesting_facility": "Health Center A",
          "age_group": "15-19", "sputum": 20, "blood": 5}],
    ),
    (
        "/tb/gx/facilities/tested_samples_disaggregated_by_drug_type/",
        "tested_samples_by_facility_disaggregated_by_drug_type_service",
        [{"requesting_facility": "Health Center A",
          "rifampicin": 30, "isoniazid": 5, "fluoroquinolona": 2}],
    ),
    (
        "/tb/gx/facilities/tested_samples_disaggregated_by_drug_type_by_age/",
        "tested_samples_by_facility_disaggregated_by_drug_type_by_age_service",
        [{"requesting_facility": "Health Center A",
          "age_group": "15-19", "rifampicin": 5}],
    ),
    (
        "/tb/gx/facilities/rejected_samples/",
        "rejected_samples_by_facility_service",
        [{"requesting_facility": "Health Center A", "total": 15}],
    ),
    (
        "/tb/gx/facilities/rejected_samples_by_month/",
        "rejected_samples_by_facility_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "requesting_facility": "Health Center A", "total": 15}],
    ),
    (
        "/tb/gx/facilities/rejected_samples_by_reason/",
        "rejected_samples_by_facility_by_reason_service",
        [{"requesting_facility": "Health Center A",
          "reason": "Insufficient sample", "total": 5}],
    ),
    (
        "/tb/gx/facilities/rejected_samples_by_reason_by_month/",
        "rejected_samples_by_facility_by_reason_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "requesting_facility": "Health Center A",
          "reason": "Insufficient sample", "total": 5}],
    ),
    (
        "/tb/gx/facilities/trl_samples_by_days/",
        "trl_samples_by_facility_by_days_service",
        [{"requesting_facility": "Health Center A",
          "0_2_days": 50, "3_5_days": 80, "6_10_days": 40, "above_10_days": 30}],
    ),
    (
        "/tb/gx/facilities/trl_samples_by_days_by_month/",
        "trl_samples_by_facility_by_days_by_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "requesting_facility": "Health Center A",
          "0_2_days": 50, "3_5_days": 80}],
    ),
    (
        "/tb/gx/facilities/trl_samples_avg_by_days/",
        "trl_samples_avg_by_facility_service",
        [{"requesting_facility": "Health Center A", "avg_days": 4.2}],
    ),
    (
        "/tb/gx/facilities/trl_samples_avg_by_days_by_month/",
        "trl_samples_avg_by_facility_month_service",
        [{"year": 2024, "month": 1, "month_name": "January",
          "requesting_facility": "Health Center A", "avg_days": 4.2}],
    ),
    (
        "/tb/gx/facilities/trl_samples_by_days_tb/",
        "trl_samples_by_facility_by_days_tb_service",
        [{"requesting_facility": "Health Center A",
          "0_2_days": 30, "3_5_days": 50}],
    ),
]


class TestTbFacilityEndpoints:
    """Smoke-test all 20 TB GeneXpert facility endpoints."""

    @pytest.mark.parametrize("url,service_name,mock_data", TB_FACILITY_ENDPOINTS)
    def test_endpoint_returns_200(self, client, auth_headers, url, service_name, mock_data):
        with patch(
            f"tb.gxpert.controllers.tb_gx_controller_facility.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            assert response.status_code == 200

    @pytest.mark.parametrize("url,service_name,mock_data", TB_FACILITY_ENDPOINTS)
    def test_endpoint_returns_json_list(self, client, auth_headers, url, service_name, mock_data):
        with patch(
            f"tb.gxpert.controllers.tb_gx_controller_facility.{service_name}",
            return_value=mock_data,
        ):
            response = client.get(url, headers=auth_headers)
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0


class TestTbFacilityRegisteredSamplesResponse:
    """Test response structure for facility registered_samples endpoint."""

    def test_response_has_expected_keys(self, client, auth_headers):
        mock_data = [
            {"requesting_facility": "Health Center A", "total": 150}
        ]
        with patch(
            "tb.gxpert.controllers.tb_gx_controller_facility.registered_samples_by_facility_service",
            return_value=mock_data,
        ):
            response = client.get(
                "/tb/gx/facilities/registered_samples/",
                headers=auth_headers,
            )
            data = response.get_json()
            assert len(data) == 1
            row = data[0]
            assert "requesting_facility" in row
            assert "total" in row


class TestTbFacilityQueryParameters:
    """Verify query parameters are forwarded into the service layer."""

    def test_service_receives_query_params(self, client, auth_headers):
        captured = {}

        def fake_service(req_args):
            captured.update(req_args)
            return []

        with patch(
            "tb.gxpert.controllers.tb_gx_controller_facility.registered_samples_by_facility_service",
            side_effect=fake_service,
        ):
            client.get(
                "/tb/gx/facilities/registered_samples/",
                query_string={
                    "interval_dates": "2024-01-01,2024-06-30",
                    "facility_type": "province",
                    "province": "Maputo",
                },
                headers=auth_headers,
            )

        assert captured.get("facility_type") == "province"
        assert captured.get("province") == ["Maputo"]
        assert "user_id" in captured
