"""
Tests for EID Summary/Dashboard endpoints (10 routes).
Each test mocks the corresponding service function at the controller layer
and verifies a 200 response with the spec §4.3 response keys.
"""
import pytest
from unittest.mock import patch

from tests.hiv.sql_capture import captured_queries

MONTH = {"year": 2024, "month": 1, "month_name": "January"}
TAT_KEYS = [
    "collection_hub_reception", "hub_reception_hub_registration",
    "hub_registration_lab_reception", "lab_reception_lab_registration",
    "lab_registration_analysis", "analysis_validation",
]
BRACKET_KEYS = ["lt_7", "between_7_15", "between_16_21", "gt_21", "no_dates"]
REJECTION_KEYS = [
    "repeat_test", "insufficient_sample", "request_without_sample", "technical_problems",
    "overlapping_blood", "duplicate_registration", "misidentified_sample",
    "sample_over_30_days", "other", "total",
]
EQUIPMENT_KEYS = ["tested", "CAPCTM", "ALINITY", "M2000", "C6800", "PANTHER", "MPIMA", "MANUAL"]


def _row(keys, base=None):
    return {**(base or {}), **{key: 1 for key in keys}}


# (url, service_function_name, mock_response)
EID_SUMMARY_ENDPOINTS = [
    ("/hiv/eid/summary/indicators/", "summary_indicators_service",
     [_row(["registered", "tested", "rejected", "pending"], MONTH)]),
    ("/hiv/eid/summary/tat/", "summary_tat_service", [_row(TAT_KEYS, MONTH)]),
    ("/hiv/eid/summary/tat_samples/", "summary_tat_samples_service",
     [_row(BRACKET_KEYS, {**MONTH, "category": "collection_hub_reception"})]),
    ("/hiv/eid/summary/positivity/", "summary_positivity_service",
     [_row(["tested", "positive", "negative", "indeterminate",
            "conventional_positive", "poc_positive", "positivity"], MONTH)]),
    ("/hiv/eid/summary/number_of_samples/", "summary_number_of_samples_service",
     [_row(["total", "conventional", "poc"], MONTH)]),
    ("/hiv/eid/summary/indicators_by_province/", "summary_indicators_by_province_service",
     [_row(["registered", "tested", "rejected", "pending", "conventional", "poc",
            "positive", "positivity"], {"province": "Gaza"})]),
    ("/hiv/eid/summary/samples_positivity/", "summary_samples_positivity_service",
     _row(["tested", "positive", "negative", "indeterminate", "female_positive",
           "male_positive", "female_negative", "male_negative"])),
    ("/hiv/eid/summary/rejected_samples_by_month/", "summary_rejected_samples_by_month_service",
     [_row(REJECTION_KEYS, MONTH)]),
    ("/hiv/eid/summary/samples_by_equipment/", "summary_samples_by_equipment_service",
     [_row(EQUIPMENT_KEYS, {"testing_facility": "Laboratorio X"})]),
    ("/hiv/eid/summary/samples_by_equipment_by_month/",
     "summary_samples_by_equipment_by_month_service", [_row(EQUIPMENT_KEYS, MONTH)]),
]


@pytest.mark.parametrize("url,service_name,mock_data", EID_SUMMARY_ENDPOINTS)
def test_endpoint_returns_service_data(client, auth_headers, url, service_name, mock_data):
    with patch(
        f"hiv.eid.controllers.eid_controller_summary.{service_name}",
        return_value=mock_data,
    ):
        response = client.get(url, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == mock_data


@pytest.mark.parametrize("url,service_name,mock_data", EID_SUMMARY_ENDPOINTS)
def test_empty_window_returns_empty_list(client, auth_headers, url, service_name, mock_data):
    """The real service, with no rows in the window: HTTP 200 and []."""
    if isinstance(mock_data, dict):
        pytest.skip("single-row route")
    with captured_queries():
        response = client.get(url, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == []


def test_tat_samples_rejects_category_out_of_range(client, auth_headers):
    response = client.get("/hiv/eid/summary/tat_samples/?category=6", headers=auth_headers)
    assert response.status_code == 400
