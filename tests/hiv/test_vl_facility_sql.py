"""SQL-compilation tests for the VL facility (Província/Distrito/US) services."""
from unittest.mock import patch

from tests.hiv.sql_capture import service_sql
from hiv.vl.services import vl_services_facilities as fac

ARGS = {"interval_dates": ["2025-01-01,2025-12-31"]}
NOT_NULL_TEXT = "[VlData].[RequestingProvinceName] != 'null'"
TAT_RULE = (
    "[VlData].[ViralLoadResultCategory] NOT LIKE '' AND "
    "datediff(day, [VlData].[SpecimenDatetime], [VlData].[ReceivedDateTime]) >= 0"
)
OR_RULE = "[VlData].[LIMSRejectionCode] != '' OR [VlData].[HIVVL_LIMSRejectionCode] IS NOT NULL"
INCLUSIVE = "CAST([VlData].[RegisteredDateTime] AS DATE) <= '2025-12-31'"
YES_LIST = "IN ('YES', 'Yes', 'yes', 'Sim', 'SIM', 'sim')"


def sql_for(app, service, extra=None):
    result, [sql] = service_sql(app, service, {**ARGS, **(extra or {})})
    assert not isinstance(result, dict), result
    return sql


def test_registered_samples_by_registration_date_with_null_exclusion(app):
    sql = sql_for(app, fac.facility_registered_samples_service)
    assert "[VlData].[RegisteredDateTime] BETWEEN '2025-01-01' AND '2025-12-31'" in sql
    assert NOT_NULL_TEXT in sql
    assert "[VlData].[RequestingDistrictName] IS NOT NULL" not in sql
    assert "[VlData].[RequestingFacilityName] IS NOT NULL" not in sql
    assert "GROUP BY [VlData].[RequestingProvinceName]" in sql


def test_location_filter_replaces_null_exclusion(app):
    sql = sql_for(app, fac.facility_tested_samples_by_facility_service, {"province": ["Gaza"]})
    assert "[VlData].[RequestingProvinceName] IN ('Gaza')" in sql
    assert NOT_NULL_TEXT not in sql


def test_disaggregation_groups_one_level_down(app):
    sql = sql_for(
        app, fac.facility_tested_samples_by_facility_service,
        {"province": ["Gaza"], "disaggregation": "1"},
    )
    assert "GROUP BY [VlData].[RequestingDistrictName]" in sql


def test_gender_by_month_has_no_null_exclusion_and_a_total(app):
    sql = sql_for(app, fac.facility_tested_samples_by_month_by_gender_service)
    assert NOT_NULL_TEXT not in sql
    assert "count(*) AS total" in sql


def test_tested_by_month_has_no_null_exclusion(app):
    sql = sql_for(app, fac.facility_tested_samples_by_month_service)
    assert NOT_NULL_TEXT not in sql


def test_gender_by_facility_groups_by_facility_only(app):
    sql = sql_for(app, fac.facility_tested_samples_by_gender_by_facility_service)
    assert "GROUP BY [VlData].[RequestingProvinceName]" in sql
    assert "year(" not in sql
    assert "count(*) AS total" in sql


def test_tat_services_apply_tat_rule(app):
    for service in (fac.facility_tat_by_month_service, fac.facility_tat_by_facility_service):
        sql = sql_for(app, service)
        assert TAT_RULE in sql and NOT_NULL_TEXT in sql
        assert "< 90" not in sql


def test_rejection_services_use_or_rule_and_inclusive_dates(app):
    for service in (fac.facility_rejected_samples_by_month_service,
                    fac.facility_rejected_samples_by_facility_service):
        sql = sql_for(app, service)
        assert OR_RULE in sql and INCLUSIVE in sql and NOT_NULL_TEXT in sql


def test_pregnant_and_breastfeeding_value_lists(app):
    assert f"[VlData].[Pregnant] {YES_LIST}" in sql_for(app, fac.facility_tested_samples_pregnant_service)
    assert f"[VlData].[BreastFeeding] {YES_LIST}" in sql_for(app, fac.facility_tested_samples_breastfeeding_service)


def test_age_by_facility_accepts_age_range_and_counts_suppression(app):
    sql = sql_for(app, fac.facility_tested_samples_by_age_by_facility_service, {"age_range": "15,49"})
    assert "[VlData].[AgeInYears] BETWEEN 15 AND 49" in sql
    assert "AS suppressed" in sql and "AS not_suppressed" in sql
    assert NOT_NULL_TEXT in sql


def test_age_by_month_accepts_age_range(app):
    sql = sql_for(app, fac.facility_tested_samples_by_age_by_month_service, {"age_range": "0,14"})
    assert "[VlData].[AgeInYears] BETWEEN 0 AND 14" in sql
    assert "AS suppressed" in sql


def test_test_reason_by_facility_excludes_null_provinces(app):
    sql = sql_for(app, fac.facility_tested_samples_by_test_reason_by_facility_service)
    assert NOT_NULL_TEXT in sql and "AS routine" in sql


def test_facility_level_is_admin_only(app):
    args = {**ARGS, "facility_type": "health_facility", "health_facility": "CS X"}
    with patch.object(fac, "_get_user_role", return_value=("u1", "Viewer")):
        result, sql = service_sql(app, fac.facility_tested_samples_by_facility_service, args)
    assert result["code"] == 403 and sql == []


def test_admin_at_facility_level_gets_aggregates_not_patients(app):
    args = {**ARGS, "facility_type": "health_facility", "health_facility": "CS X"}
    with patch.object(fac, "_get_user_role", return_value=("u1", "Admin")):
        result, [sql] = service_sql(app, fac.facility_tested_samples_by_facility_service, args)
    assert result == []
    assert "[VlData].[RequestingFacilityName] IN ('CS X')" in sql


def test_role_is_not_looked_up_above_facility_level(app):
    with patch.object(fac, "_get_user_role") as lookup:
        sql_for(app, fac.facility_tested_samples_by_facility_service)
    lookup.assert_not_called()


def test_pregnant_by_facility(app):
    sql = sql_for(app, fac.facility_tested_samples_pregnant_by_facility_service)
    assert f"[VlData].[Pregnant] {YES_LIST}" in sql
    assert "GROUP BY [VlData].[RequestingProvinceName]" in sql
    assert NOT_NULL_TEXT in sql
    assert "AS suppressed" in sql and "AS not_suppressed" in sql


def test_breastfeeding_by_facility_drills_down(app):
    sql = sql_for(
        app, fac.facility_tested_samples_breastfeeding_by_facility_service,
        {"facility_type": "district", "district": ["Chibuto"], "disaggregation": "true"},
    )
    assert f"[VlData].[BreastFeeding] {YES_LIST}" in sql
    assert "[VlData].[RequestingDistrictName] IN ('Chibuto')" in sql
    assert "GROUP BY [VlData].[RequestingFacilityName]" in sql


def test_new_facility_routes(client, auth_headers):
    for path, name in [
        ("tested_samples_pregnant_by_facility", "facility_tested_samples_pregnant_by_facility_service"),
        ("tested_samples_breastfeeding_by_facility", "facility_tested_samples_breastfeeding_by_facility_service"),
    ]:
        with patch(f"hiv.vl.controllers.vl_controller_facility.{name}", return_value=[]):
            response = client.get(f"/hiv/vl/facilities/{path}/", headers=auth_headers)
        assert response.status_code == 200, path
