"""run_reporting_endpoint retries a report once when SQL Server drops the connection.

The services catch database errors and return ``{"status": "error", "code": 500, "error": str(e)}``,
so a dropped connection reaches the controller either as that dict or, rarely, as a raised
SQLAlchemy error. Reports are read-only, so running the query again on a fresh connection is safe.
"""
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError, ProgrammingError

URL = "/hiv/vl/summary/samples_history/"
TARGET = "hiv.vl.controllers.vl_controller_summary.samples_history_service_by_month"

RESET = (
    "(pyodbc.OperationalError) ('08S01', '[08S01] [Microsoft][ODBC Driver 18 for SQL Server]"
    "TCP Provider: Error code 0x68 (104) (SQLExecDirectW)')\n[SQL: SELECT [VlData].[RequestID] FROM VlData]"
)
TIMEOUT = (
    "(pyodbc.OperationalError) ('08S01', '[08S01] [Microsoft][ODBC Driver 18 for SQL Server]"
    "TCP Provider: Error code 0x274C (10060) (SQLExecDirectW)')"
)


def _error_dict(text):
    return {"status": "error", "code": 500, "message": "An Error Occurred", "error": text}


def _operational_error(text):
    return OperationalError("SELECT 1", {}, Exception(text))


def test_dropped_connection_error_dict_is_retried_once(client, auth_headers):
    service = MagicMock(side_effect=[_error_dict(RESET), [{"year": 2025}]])
    with patch(TARGET, service):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == [{"year": 2025}]
    assert service.call_count == 2


def test_connection_timeout_error_dict_is_retried(client, auth_headers):
    service = MagicMock(side_effect=[_error_dict(TIMEOUT), [{"year": 2025}]])
    with patch(TARGET, service):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 200
    assert service.call_count == 2


def test_raised_dropped_connection_is_retried(client, auth_headers):
    service = MagicMock(side_effect=[_operational_error(RESET), [{"year": 2025}]])
    with patch(TARGET, service):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 200
    assert service.call_count == 2


def test_second_dropped_connection_returns_generic_500(client, auth_headers):
    service = MagicMock(side_effect=[_error_dict(RESET), _error_dict(RESET), [{"year": 2025}]])
    with patch(TARGET, service):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "code": 500, "message": "An error occurred"}
    assert b"SELECT" not in response.data and b"08S01" not in response.data
    assert service.call_count == 2


def test_other_database_errors_are_not_retried(client, auth_headers):
    other = _error_dict("(pyodbc.ProgrammingError) ('42000', 'Cannot open database \"EidData\"')")
    service = MagicMock(side_effect=[other, [{"year": 2025}]])
    with patch(TARGET, service):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 500
    assert service.call_count == 1


def test_other_raised_database_errors_are_not_retried(client, auth_headers):
    service = MagicMock(side_effect=[ProgrammingError("SELECT 1", {}, Exception("42000")), [{"year": 2025}]])
    with patch(TARGET, service):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 500
    assert service.call_count == 1


def test_retry_gets_its_own_copy_of_the_arguments(client, auth_headers):
    seen = []

    def service(req_args):
        seen.append(dict(req_args))
        req_args["mutated"] = True
        return _error_dict(RESET) if len(seen) == 1 else [{"year": 2025}]

    with patch(TARGET, side_effect=service):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 200
    assert seen[0] == seen[1]
    assert "mutated" not in seen[1]


def test_service_receives_the_parser_namespace_type(client, auth_headers):
    from flask_restful.reqparse import Namespace

    seen = []
    with patch(TARGET, side_effect=lambda req_args: seen.append(type(req_args)) or [{"year": 2025}]):
        client.get(URL, headers=auth_headers)
    assert seen == [Namespace]


def test_session_is_reset_before_the_retry(client, auth_headers):
    order = []
    service = MagicMock(side_effect=lambda _: order.append("service") or (
        _error_dict(RESET) if order.count("service") == 1 else [{"year": 2025}]
    ))
    with patch(TARGET, service), patch(
        "utilities.controller_helpers._reset_db_session", side_effect=lambda: order.append("reset")
    ):
        response = client.get(URL, headers=auth_headers)
    assert response.status_code == 200
    assert order == ["service", "reset", "service"]


def test_retry_log_has_no_sql_or_driver_text(client, auth_headers, caplog):
    service = MagicMock(side_effect=[_error_dict(RESET), [{"year": 2025}]])
    with patch(TARGET, service), caplog.at_level("WARNING"):
        client.get(URL, headers=auth_headers)
    retry_logs = [r.getMessage() for r in caplog.records if "retry" in r.getMessage().lower()]
    assert retry_logs, "the retry should be logged"
    assert all("SELECT" not in m and "08S01" not in m and "TCP" not in m for m in retry_logs)
