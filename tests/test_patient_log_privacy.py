"""Patient searches keep synthetic clinical details out of logs and errors.

HTTP tests retain real JWT verification and persisted SQLite roles. Direct
service tests build real SQLAlchemy expressions and replace database execution
only; no clinical database, real credentials or patient data are used.
"""
from contextlib import ExitStack
from importlib import import_module
import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import request
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Query
from werkzeug.routing import Rule

from utilities import controller_helpers
from utilities.token_verification import TokenVerificationError


NAME = "PRIVACY_SYNTHETIC_NAME_7F3"
PHONE = "PRIVACY_SYNTHETIC_PHONE_7F3"
CLINICAL_ID = "PRIVACY_SYNTHETIC_CLINICAL_ID_7F3"
TOKEN = "PRIVACY_SYNTHETIC_TOKEN_7F3"
SQL = "SELECT private_contact FROM synthetic_patient WHERE clinical_id = :clinical_id"
DETAIL = f"{NAME} {PHONE} {CLINICAL_ID} {TOKEN}"
MARKERS = (NAME, PHONE, CLINICAL_ID, TOKEN, SQL, "private_contact", "clinical_id =")
GENERIC_ERROR = {"status": "error", "code": 500, "message": "An error occurred"}

MODULES = {
    "vl": ("hiv.vl.controllers.vl_controller_patients", "hiv.vl.services.vl_services_patients"),
    "eid": ("hiv.eid.controllers.eid_controller_patients", "hiv.eid.services.eid_services_patients"),
    "tb": ("tb.gxpert.controllers.tb_gx_controller_patients", "tb.gxpert.services.tb_gx_services_patients"),
}
PREFIXES = {"vl": "/hiv/vl", "eid": "/hiv/eid", "tb": "/tb/gx"}
SEARCHES = {
    "vl": [
        ("name", {"first_name": NAME}),
        ("facility", {"health_facility": NAME}),
        ("result_type", {"result_type": ["suppressed"]}),
        ("test_reason", {"test_reason": ["Routine"]}),
    ],
    "eid": [
        ("name", {"name": NAME}),
        ("facility", {}),
        ("result_type", {"result_type": ["positive"]}),
    ],
    "tb": [
        ("name", {"first_name": NAME}),
        ("facility", {"health_facility": NAME}),
        ("result_type", {"result_type": ["detected"]}),
        ("sample_type", {"sample_type": ["sputum"]}),
    ],
}
CASES = [
    pytest.param(domain, search, filters, id=f"{domain}-{search}")
    for domain, searches in SEARCHES.items()
    for search, filters in searches
]


class UnprintableError(RuntimeError):
    """A logger must not attempt to stringify arbitrary exception objects."""

    def __str__(self):
        raise AssertionError("Exception text must never be evaluated")


def failure(kind):
    if kind == "statement":
        return StatementError(DETAIL, SQL, {"clinical_id": CLINICAL_ID, "phone": PHONE}, RuntimeError(TOKEN))
    if kind == "unprintable":
        return UnprintableError(DETAIL)
    return RuntimeError(DETAIL)


def assert_private_output(caplog, capsys):
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    for record in caplog.records:
        assert record.exc_info is None, "A traceback retains exception messages and SQL parameters"
        assert record.stack_info is None
        retained = f"{record.msg!r} {record.args!r} {record.getMessage()}"
        assert all(marker not in retained for marker in MARKERS)
    assert all(marker not in caplog.text for marker in MARKERS)


def service_name(search):
    return f"get_patients_by_{search}_service"


def url(domain, search):
    return f"{PREFIXES[domain]}/patients/by_{search}/"


def paginated(rows):
    return {"status": "success", "page": 2, "per_page": 25, "total_count": 26, "total_pages": 2, "data": rows}


def test_rejected_token_logs_only_exception_class_without_request_secrets(client, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    with patch.object(
        controller_helpers, "verify_bearer_token", side_effect=TokenVerificationError(DETAIL)
    ) as verify, patch(
        "hiv.vl.controllers.vl_controller_patients.get_patients_by_name_service"
    ) as service:
        response = client.get(
            "/hiv/vl/patients/by_name/",
            headers={"Authorization": f"Bearer {TOKEN}"},
            query_string={"first_name": NAME, "phone": PHONE, "clinical_id": CLINICAL_ID},
        )
    assert response.status_code == 401
    assert response.get_json() == {"status": "error", "code": 401, "message": "Invalid or missing token"}
    verify.assert_called_once_with(TOKEN)
    service.assert_not_called()
    assert "TokenVerificationError" in caplog.text
    assert_private_output(caplog, capsys)


def test_service_error_logs_route_pattern_without_dynamic_patient_id(app, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    route_pattern = "/hiv/vl/patients/<patient_id>/"
    actual_path = f"/hiv/vl/patients/{CLINICAL_ID}/"
    with app.test_request_context(actual_path, query_string={"first_name": NAME, "token": TOKEN}):
        request.url_rule = Rule(route_pattern)
        response = controller_helpers.service_result_response({
            **GENERIC_ERROR, "message": DETAIL, "error": failure("statement")
        })
    assert response == (GENERIC_ERROR, 500)
    assert route_pattern in caplog.text
    assert actual_path not in caplog.text
    assert "first_name=" not in caplog.text
    assert_private_output(caplog, capsys)


@pytest.mark.parametrize("domain,search,filters", CASES)
@pytest.mark.parametrize("kind", ["returned", "returned_unprintable", "runtime", "statement", "unprintable"])
def test_patient_http_failures_are_generic_without_sensitive_logs(
    client, auth_headers, caplog, capsys, domain, search, filters, kind
):
    caplog.set_level(logging.DEBUG)
    target = f"{MODULES[domain][0]}.{service_name(search)}"
    mock_args = (
        {"return_value": {
            **GENERIC_ERROR,
            "message": DETAIL,
            "error": failure("unprintable" if kind == "returned_unprintable" else "statement"),
            "data": [DETAIL],
        }}
        if kind.startswith("returned") else {"side_effect": failure(kind)}
    )
    with patch(target, **mock_args) as service:
        response = client.get(url(domain, search), headers=auth_headers, query_string=filters)
    assert response.status_code == 500
    assert response.get_json() == GENERIC_ERROR
    service.assert_called_once()
    assert_private_output(caplog, capsys)


@pytest.mark.parametrize("domain,search,filters", CASES)
def test_patient_http_success_keeps_pagination_and_is_never_cached(
    app, client, auth_headers, monkeypatch, caplog, capsys, domain, search, filters
):
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    row = {"name": NAME, "phone": PHONE, "clinical_id": CLINICAL_ID}
    expected = paginated([row])
    query = {**filters, "page": 2, "per_page": 25}
    with patch(f"{MODULES[domain][0]}.{service_name(search)}", return_value=expected) as service, \
            patch("utilities.report_cache.read") as cache_read, \
            patch("utilities.report_cache.write") as cache_write:
        response = client.get(url(domain, search), headers=auth_headers, query_string=query)
    assert response.status_code == 200
    assert response.get_json() == expected
    assert "X-Report-Cache" not in response.headers
    assert service.call_args.args[0]["user_id"] == "test-123"
    assert int(service.call_args.args[0]["page"]) == 2
    assert int(service.call_args.args[0]["per_page"]) == 25
    cache_read.assert_not_called()
    cache_write.assert_not_called()
    assert_private_output(caplog, capsys)


@pytest.mark.parametrize("domain,search,filters", CASES)
@pytest.mark.parametrize("role", [None, "global", "vl", "dpi", "tb_gx"])
def test_patient_http_denial_precedes_service_and_cache(
    app, client, persisted_user, monkeypatch, domain, search, filters, role
):
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    headers = {}
    if role is not None:
        user_id = persisted_user(role=role)
        with app.app_context():
            token = create_access_token(identity=user_id, additional_claims={"role": "Admin"})
        headers = {"Authorization": f"Bearer {token}"}
    with patch(f"{MODULES[domain][0]}.{service_name(search)}") as service, \
            patch("utilities.report_cache.read") as cache_read, \
            patch("utilities.report_cache.write") as cache_write:
        response = client.get(url(domain, search), headers=headers, query_string=filters)
    assert response.status_code == (401 if role is None else 403)
    service.assert_not_called()
    cache_read.assert_not_called()
    cache_write.assert_not_called()


def direct_service_setup(stack, module, domain):
    if domain == "tb":
        stack.enter_context(patch.object(module, "require_admin", return_value=("synthetic-admin", None)))
    else:
        stack.enter_context(patch.object(module, "_get_user_role", return_value=("synthetic-admin", "Admin")))


@pytest.mark.parametrize("domain,search,filters", CASES)
@pytest.mark.parametrize("stage", ["database", "serialization", "unprintable"])
def test_patient_service_errors_do_not_retain_sensitive_details(
    app, caplog, capsys, domain, search, filters, stage
):
    caplog.set_level(logging.DEBUG)
    module = import_module(MODULES[domain][1])
    args = {"interval_dates": ["2025-01-01,2025-12-31"], **filters}
    with app.app_context(), ExitStack() as stack:
        direct_service_setup(stack, module, domain)
        count = stack.enter_context(patch.object(Query, "count", return_value=1))
        stack.enter_context(patch.object(Query, "all", return_value=[SimpleNamespace()]))
        if stage in {"database", "unprintable"}:
            count.side_effect = failure("statement" if stage == "database" else "unprintable")
        else:
            serializer = "_serialise" if domain == "eid" else "process_patients"
            stack.enter_context(patch.object(module, serializer, side_effect=failure("runtime")))
        result = getattr(module, service_name(search))(args)
    assert result == GENERIC_ERROR
    assert_private_output(caplog, capsys)


def patient_row(module, domain):
    if domain == "eid":
        record = {column.key: None for column in module.EID_PATIENT_COLUMNS}
        record.update(request_id=CLINICAL_ID, name=NAME, caregiver_phone=PHONE, mother_ptv_id=CLINICAL_ID)
        return SimpleNamespace(_asdict=lambda: dict(record))
    model = module.VlData if domain == "vl" else module.TBMaster
    values = {column.key: None for column in model.__table__.columns}
    values.update(RequestID=CLINICAL_ID, FIRSTNAME=NAME, TELHOME=PHONE)
    if domain == "vl":
        values["HealthcareNo"] = CLINICAL_ID
    return SimpleNamespace(**values)


@pytest.mark.parametrize("domain,search,filters", CASES)
def test_patient_service_success_returns_records_without_debug_output(
    app, caplog, capsys, domain, search, filters
):
    caplog.set_level(logging.DEBUG)
    module = import_module(MODULES[domain][1])
    args = {"interval_dates": ["2025-01-01,2025-12-31"], "page": 2, "per_page": 25, **filters}
    with app.app_context(), ExitStack() as stack:
        direct_service_setup(stack, module, domain)
        stack.enter_context(patch.object(Query, "count", return_value=26))
        stack.enter_context(patch.object(Query, "all", return_value=[patient_row(module, domain)]))
        result = getattr(module, service_name(search))(args)
    assert result == paginated(result["data"])
    assert len(result["data"]) == 1
    record = result["data"][0]
    assert record["request_id"] == CLINICAL_ID
    assert record["name" if domain == "eid" else "first_name"] == NAME
    assert record["caregiver_phone" if domain == "eid" else "telephone"] == PHONE
    assert_private_output(caplog, capsys)
