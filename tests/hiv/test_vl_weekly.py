"""Weekly ReportData reports: default windows and SQL.

The SQL Server dialect leaves lowercase column names unbracketed
(``[Resume].labcode``), hence the mixed quoting below.
"""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.hiv.sql_capture import service_sql
from hiv.vl.services import vl_services_weekly as weekly

ARGS = {"interval_dates": ["2025-01-01,2025-12-31"]}


@pytest.mark.parametrize("today", [date(2026, 10, 11), date(2026, 10, 12), date(2026, 10, 17)])
def test_current_week_is_sunday_to_saturday(today):
    # Sunday 11, Monday 12 and Saturday 17 October 2026 share one week.
    assert weekly.current_week(today) == ["2026-10-11", "2026-10-17"]


def test_last_12_weeks_matches_node_default():
    assert weekly.last_12_weeks(date(2026, 10, 12)) == ["2026-07-20", "2026-10-12"]


def test_weekly_report_sql_by_lab(app):
    _, [sql] = service_sql(app, weekly.weekly_report_service, {**ARGS, "lab_code": ["PCD"]})
    assert "FROM [Resume]" in sql
    assert "CAST([Resume].start_date AS DATE) >= '2025-01-01'" in sql
    assert "CAST([Resume].start_date AS DATE) <= '2025-12-31'" in sql
    assert "[Resume].labcode IN ('PCD')" in sql
    assert "sum([Resume].registered) AS registrations" in sql
    assert "sum([Resume].rejected) AS rejections" in sql
    assert "avg([Resume].tat) AS tat" in sql
    assert ("GROUP BY [Resume].labcode, [Resume].labname, [Resume].week, "
            "[Resume].start_date, [Resume].end_date") in sql
    assert "ORDER BY [Resume].start_date" in sql


def test_weekly_report_national_sql_has_no_lab_grouping(app):
    _, [sql] = service_sql(app, weekly.weekly_report_national_service, ARGS)
    assert "GROUP BY [Resume].week, [Resume].start_date, [Resume].end_date" in sql
    assert "labname" not in sql


def test_weekly_report_defaults_to_current_week(app):
    with patch.object(weekly, "_today", return_value=date(2026, 10, 12)):
        _, [sql] = service_sql(app, weekly.weekly_report_service, {})
    assert "CAST([Resume].start_date AS DATE) >= '2026-10-11'" in sql
    assert "CAST([Resume].start_date AS DATE) <= '2026-10-17'" in sql


def test_weekly_report_national_defaults_to_last_12_weeks(app):
    with patch.object(weekly, "_today", return_value=date(2026, 10, 12)):
        _, [sql] = service_sql(app, weekly.weekly_report_national_service, {})
    assert "CAST([Resume].start_date AS DATE) >= '2026-07-20'" in sql


def test_weekly_report_row_shape(app):
    row = SimpleNamespace(
        labcode="PCD", labname="Cabo Delgado", week="W41",
        start_date=datetime(2026, 10, 11), end_date=datetime(2026, 10, 17),
        backlogs=5, tests=100, registrations=110, rejections=2, capacity=500, tat=3.5,
    )
    result, _ = service_sql(app, weekly.weekly_report_service, ARGS, results=[[row]])
    assert result == [dict(
        lab_code="PCD", lab_name="Cabo Delgado", week="W41", start="2026-10-11",
        end="2026-10-17", backlogs=5, tests=100, registrations=110, rejections=2,
        capacity=500, tat=3.5,
    )]


def test_weekly_routes_exist(client, auth_headers):
    target = "hiv.vl.controllers.vl_controller_laboratory.weekly_report_service"
    with patch(target, return_value=[]):
        assert client.get("/hiv/vl/laboratories/weekly_report/", headers=auth_headers).status_code == 200
    target = "hiv.vl.controllers.vl_controller_laboratory.weekly_report_national_service"
    with patch(target, return_value=[]):
        assert client.get("/hiv/vl/laboratories/weekly_report_national/", headers=auth_headers).status_code == 200
