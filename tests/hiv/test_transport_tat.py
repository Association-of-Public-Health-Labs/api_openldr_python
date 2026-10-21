"""Transport TAT (ReportData VLTransportTATPerWeek / EIDTransportTATPerWeek): SQL, rows, defaults."""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.hiv.sql_capture import service_sql
from hiv import transport_tat_service as transport
from hiv.vl.services import vl_services_transport as vl
from hiv.eid.services import eid_services_transport as eid
from utilities.service_helpers import InvalidParameter

WEEK = {"interval_dates": ["2026-09-27,2026-10-03"]}


# ---------------------------------------------------------------------------- windows


@pytest.mark.parametrize("today", [date(2026, 10, 11), date(2026, 10, 14), date(2026, 10, 17)])
def test_last_complete_week_is_the_previous_sunday_to_saturday(today):
    assert transport.last_complete_week(today) == ["2026-10-04", "2026-10-10"]


def test_recent_weeks_ends_with_the_last_complete_week():
    assert transport.recent_weeks(date(2026, 10, 21)) == ["2026-04-05", "2026-10-17"]
    assert transport.recent_weeks(date(2026, 10, 21), weeks=1) == ["2026-10-11", "2026-10-17"]


# ---------------------------------------------------------------------------- SQL


def test_vl_by_location_reads_the_spreadsheet_columns_and_filters(app):
    _, [sql] = service_sql(app, vl.transport_tat_by_location_service, WEEK)
    assert "FROM [VLTransportTATPerWeek]" in sql
    for column, name in [("lt_7", "lt_7"), ("7_15", "between_7_15"), ("16_21", "between_16_21"), ("gt_21", "gt_21"), ("no_data", "no_reception_date")]:
        assert f"[VLTransportTATPerWeek].collection_to_lab_reception_{column} AS {name}" in sql
        assert f"sum(latest.{name}) AS {name}" in sql
    assert "[VLTransportTATPerWeek].[TestedSamplesWithCollectionDate] AS samples" in sql
    # Weeks inside the window, as the spreadsheet: start >= window start, end <= window end.
    assert 'CAST([VLTransportTATPerWeek].[StartDate] AS DATE) >= \'2026-09-27\'' in sql
    assert 'CAST([VLTransportTATPerWeek].[EndDate] AS DATE) <= \'2026-10-03\'' in sql
    # Only Sunday–Saturday rows (the ETL's two extra June windows repeat regular weeks).
    assert "datediff(day, [VLTransportTATPerWeek].[StartDate], [VLTransportTATPerWeek].[EndDate]) = 6" in sql
    assert "datediff(day, '1900-01-07', [VLTransportTATPerWeek].[StartDate]) % 7 = 0" in sql
    # Rows without a requesting facility are dropped (api-weekly-reports-python filter_rows_with_facility).
    assert "[VLTransportTATPerWeek].[RequestingFacilityName] IS NOT NULL" in sql
    assert "ltrim(rtrim([VLTransportTATPerWeek].[RequestingFacilityName])) != ''" in sql
    assert "GROUP BY latest.province" in sql
    assert "TotalTestedSamples" not in sql  # VL's table has no total


def test_only_the_latest_copy_of_a_row_counts(app):
    # The ETL inserts a new copy of some rows on every run: one per facility, lab, test and week.
    _, [sql] = service_sql(app, vl.transport_tat_by_location_service, WEEK)
    assert ("row_number() OVER (PARTITION BY [VLTransportTATPerWeek].[RequestingFacilityCode], "
            "[VLTransportTATPerWeek].[RequestingFacilityName], [VLTransportTATPerWeek].[TestingFacilityName], "
            "[VLTransportTATPerWeek].[TypeOfTest], [VLTransportTATPerWeek].[StartDate], [VLTransportTATPerWeek].[EndDate] "
            "ORDER BY [VLTransportTATPerWeek].[UpdatedAt] DESC, [VLTransportTATPerWeek].id DESC) AS copy") in sql
    assert "WHERE latest.copy = 1" in sql
    _, [eid_sql] = service_sql(app, eid.transport_tat_by_location_service, WEEK)
    assert "ORDER BY [EIDTransportTATPerWeek].updated_at DESC) AS copy" in eid_sql


def test_eid_reads_its_own_dates_and_total(app):
    _, [sql] = service_sql(app, eid.transport_tat_by_location_service, WEEK)
    assert "FROM [EIDTransportTATPerWeek]" in sql
    assert "CAST([EIDTransportTATPerWeek].start_date AS DATE) >= '2026-09-27'" in sql
    assert "CAST([EIDTransportTATPerWeek].end_date AS DATE) <= '2026-10-03'" in sql
    assert "[EIDTransportTATPerWeek].[TotalTestedSamples] AS total_tested" in sql
    assert "sum(latest.total_tested) AS total_tested" in sql


def test_levels_and_filters(app):
    args = {**WEEK, "facility_type": "health_facility", "province": ["Gaza"], "district": ["Chokwe"], "type_of_test": "Convencional"}
    _, [sql] = service_sql(app, vl.transport_tat_by_location_service, args)
    assert "GROUP BY latest.province, latest.district, latest.health_facility ORDER BY" in sql
    # One row per facility, even when some weeks have no code.
    assert "max(ltrim(rtrim(latest.facility_code))) AS facility_code" in sql
    assert "[VLTransportTATPerWeek].[ProvinceName] IN ('Gaza')" in sql
    assert "[VLTransportTATPerWeek].[DistrictName] IN ('Chokwe')" in sql
    assert "[VLTransportTATPerWeek].[TypeOfTest] = 'Convencional'" in sql


def test_by_week_groups_by_week_for_one_facility(app):
    _, [sql] = service_sql(app, vl.transport_tat_by_week_service, {**WEEK, "health_facility": "CS Ancuabe"})
    assert "GROUP BY latest.start, latest.[end]" in sql
    assert "ORDER BY latest.start" in sql
    assert "[VLTransportTATPerWeek].[RequestingFacilityName] = 'CS Ancuabe'" in sql


def test_defaults_last_complete_week_and_last_28_weeks(app):
    with patch.object(transport, "_today", return_value=date(2026, 10, 21)):
        _, [by_location] = service_sql(app, vl.transport_tat_by_location_service, {})
        _, [by_week] = service_sql(app, vl.transport_tat_by_week_service, {})
    assert "CAST([VLTransportTATPerWeek].[StartDate] AS DATE) >= '2026-10-11'" in by_location
    assert "CAST([VLTransportTATPerWeek].[EndDate] AS DATE) <= '2026-10-17'" in by_location
    assert "CAST([VLTransportTATPerWeek].[StartDate] AS DATE) >= '2026-04-05'" in by_week


@pytest.mark.parametrize(
    "args",
    [
        {"interval_dates": ["2026-10-01"]},
        {"interval_dates": ["2026-10-10,2026-10-01"]},
        {"interval_dates": ["oops,2026-10-01"]},
        {"facility_type": "lab"},
        {"type_of_test": "PCR"},
    ],
)
def test_invalid_parameters(app, args):
    with pytest.raises(InvalidParameter):
        service_sql(app, vl.transport_tat_by_location_service, args)


# ---------------------------------------------------------------------------- rows


def _row(**kw):
    base = dict(samples=44, lt_7=4, between_7_15=34, between_16_21=6, gt_21=0, no_reception_date=0)
    return SimpleNamespace(**{**base, **kw})


def test_vl_location_row_matches_the_spreadsheet(app):
    # CS Ancuabe, week 27 Sep - 3 Oct 2026, as in "Carga Viral - semana 27 Setembro - 03 Outubro.xlsx".
    row = _row(province="Cabo Delgado", district="Ancuabe", health_facility="CS Ancuabe", facility_code="01020206 ")
    result, _ = service_sql(app, vl.transport_tat_by_location_service, {**WEEK, "facility_type": "health_facility"}, results=[[row]])
    assert result == [dict(
        province="Cabo Delgado", district="Ancuabe", health_facility="CS Ancuabe", facility_code="01020206",
        start_date="2026-09-27", end_date="2026-10-03",
        samples_with_collection_date=44, lt_7=4, between_7_15=34, between_16_21=6, gt_21=0, no_reception_date=0,
        total_tested=None, no_collection_date=None,
    )]


def test_eid_rows_carry_the_samples_without_collection_date(app):
    row = _row(province="Gaza", total_tested=48)
    result, _ = service_sql(app, eid.transport_tat_by_location_service, WEEK, results=[[row]])
    assert result[0]["total_tested"] == 48
    assert result[0]["no_collection_date"] == 4
    assert set(result[0]) >= {"province", "lt_7", "gt_21"} and "district" not in result[0]


def test_week_rows_and_empty_sums(app):
    rows = [
        SimpleNamespace(start=datetime(2026, 9, 27), end=datetime(2026, 10, 3), samples=None, lt_7=None,
                        between_7_15=None, between_16_21=None, gt_21=None, no_reception_date=None),
    ]
    result, _ = service_sql(app, vl.transport_tat_by_week_service, WEEK, results=[rows])
    assert result == [dict(
        start_date="2026-09-27", end_date="2026-10-03", samples_with_collection_date=0, lt_7=0, between_7_15=0,
        between_16_21=0, gt_21=0, no_reception_date=0, total_tested=None, no_collection_date=None,
    )]


def test_database_errors_become_a_service_error(app):
    with app.app_context(), patch("sqlalchemy.orm.Query.all", side_effect=RuntimeError("connection lost")):
        result = vl.transport_tat_by_location_service(dict(WEEK))
    assert result["status"] == "error" and result["code"] == 500


# ---------------------------------------------------------------------------- routes


@pytest.mark.parametrize(
    "url, target",
    [
        ("/hiv/vl/transport/tat_by_location/", "hiv.vl.controllers.vl_controller_transport.transport_tat_by_location_service"),
        ("/hiv/vl/transport/tat_by_week/", "hiv.vl.controllers.vl_controller_transport.transport_tat_by_week_service"),
        ("/hiv/eid/transport/tat_by_location/", "hiv.eid.controllers.eid_controller_transport.transport_tat_by_location_service"),
        ("/hiv/eid/transport/tat_by_week/", "hiv.eid.controllers.eid_controller_transport.transport_tat_by_week_service"),
    ],
)
def test_routes_need_a_token_and_pass_type_of_test(client, auth_headers, url, target):
    assert client.get(url).status_code == 401
    with patch(target, return_value=[]) as service:
        response = client.get(url, query_string={"type_of_test": "Point-of-care"}, headers=auth_headers)
    assert response.status_code == 200
    assert service.call_args[0][0]["type_of_test"] == "Point-of-care"


def test_bad_parameter_is_a_400(client, auth_headers):
    response = client.get("/hiv/vl/transport/tat_by_location/", query_string={"facility_type": "lab"}, headers=auth_headers)
    assert response.status_code == 400
