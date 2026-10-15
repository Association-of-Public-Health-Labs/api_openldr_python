"""SQL-compilation tests for the VL summary (Sumário) services."""
from tests.hiv.sql_capture import service_sql
from hiv.vl.services import vl_services_summary as summary

ARGS = {"interval_dates": ["2025-01-01,2025-12-31"]}
OR_RULE = (
    "[VlData].[LIMSRejectionCode] != '' OR [VlData].[HIVVL_LIMSRejectionCode] IS NOT NULL"
)
TAT_RULE = (
    "[VlData].[ViralLoadResultCategory] NOT LIKE '' AND "
    "datediff(day, [VlData].[SpecimenDatetime], [VlData].[ReceivedDateTime]) >= 0"
)


def test_number_of_samples_uses_analysis_date(app):
    _, [sql] = service_sql(app, summary.number_of_samples_service_by_month, ARGS)
    assert "WHERE [VlData].[AnalysisDateTime] BETWEEN '2025-01-01' AND '2025-12-31'" in sql
    assert "GROUP BY year([VlData].[AnalysisDateTime])" in sql
    assert "RegisteredDateTime" not in sql


def test_viral_suppression_counts_rows_with_a_result(app):
    _, [sql] = service_sql(app, summary.viral_suppression_service_by_month, ARGS)
    assert "[VlData].[ViralLoadResultCategory] NOT LIKE ''" in sql
    assert "count(*) AS total" in sql


def test_tat_by_month_applies_tat_rule(app):
    _, [sql] = service_sql(app, summary.tat_service_by_month, ARGS)
    assert TAT_RULE in sql
    assert "< 90" not in sql


def test_map_groups_by_requesting_province_without_null_exclusion(app):
    _, [sql] = service_sql(app, summary.suppression_by_province_service_by_month, ARGS)
    assert "GROUP BY [VlData].[RequestingProvinceName]" in sql
    assert "!= 'null'" not in sql
    assert "AS routine" in sql and "AS treatment_failure" in sql and "AS reason_not_specified" in sql
    assert "[VlData].[ViralLoadResultCategory] NOT LIKE ''" in sql


def test_map_filters_on_requesting_columns(app):
    _, [sql] = service_sql(app, summary.suppression_by_province_service_by_month, {**ARGS, "province": ["Gaza"]})
    assert "[VlData].[RequestingProvinceName] IN ('Gaza')" in sql
    assert "TestingProvinceName" not in sql


def test_samples_history_is_the_monthly_indicators_table(app):
    _, [sql] = service_sql(app, summary.samples_history_service_by_month, ARGS)
    assert "WHERE [VlData].[RegisteredDateTime] BETWEEN '2025-01-01' AND '2025-12-31'" in sql
    assert "GROUP BY year([VlData].[RegisteredDateTime])" in sql
    for label in ("registered", "tested", "suppressed", "rejected", "non_validated"):
        assert f"AS {label}" in sql
    assert OR_RULE in sql


def test_header_indicators_use_or_rejection_rule(app):
    _, [sql] = service_sql(app, summary.header_indicators_service_by_month, ARGS)
    assert OR_RULE in sql


def test_samples_history_rows_shape(app):
    row = type("Row", (), dict(year=2025, month=1, month_name="January", registered=10,
                               tested=8, suppressed=6, rejected=1, non_validated=2))()
    result, _ = service_sql(app, summary.samples_history_service_by_month, ARGS, results=[[row]])
    assert result == [dict(year=2025, month=1, month_name="January", registered=10,
                           tested=8, suppressed=6, rejected=1, non_validated=2)]


def test_tat_vs_disalinks_serves_the_legacy_file():
    data = summary.tat_vs_disalinks_service({})
    assert len(data) == 7
    assert data[0] == {"semester": "17S1", "disalinks": 28, "tat": 46}
    assert data[-1] == {"semester": "20S1", "disalinks": 169, "tat": 12}


def test_tat_vs_disalinks_route(client, auth_headers):
    response = client.get("/hiv/vl/summary/tat_vs_disalinks/", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.get_json()) == 7


def test_bad_dates_return_400(client, auth_headers):
    response = client.get(
        "/hiv/vl/summary/samples_history/?interval_dates=2025-13-01,2025-12-31",
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_map_groups_by_district_when_disaggregated(app):
    args = {**ARGS, "province": ["Gaza"], "facility_type": "province", "disaggregation": "true"}
    _, [sql] = service_sql(app, summary.suppression_by_province_service_by_month, args)
    assert "GROUP BY [VlData].[RequestingDistrictName]" in sql
    assert "[VlData].[RequestingProvinceName] IN ('Gaza')" in sql
    assert "[VlData].[ViralLoadResultCategory] NOT LIKE ''" in sql


def test_map_ignores_facility_type_without_disaggregation(app):
    # Existing callers may send facility_type; without disaggregation the grouping stays by province.
    args = {**ARGS, "facility_type": "district", "district": ["Chokwe"]}
    _, [sql] = service_sql(app, summary.suppression_by_province_service_by_month, args)
    assert "GROUP BY [VlData].[RequestingProvinceName]" in sql


def test_map_rows_carry_location_and_keep_a_null_label(app):
    from types import SimpleNamespace

    def db_row(location):
        return SimpleNamespace(location=location, total=10, suppressed=9, not_suppressed=1,
                               routine=7, treatment_failure=2, reason_not_specified=1)

    args = {**ARGS, "province": ["Gaza"], "facility_type": "province", "disaggregation": "true"}
    result, _ = service_sql(app, summary.suppression_by_province_service_by_month, args,
                            results=[[db_row("Chokwe"), db_row(None)]])
    assert [(r["province"], r["location"]) for r in result] == [("Chokwe", "Chokwe"), (None, None)]
    assert result[0]["suppressed"] == 9 and result[0]["routine"] == 7
