"""
Shared controller helpers for Flask-RESTful endpoints.

This module centralizes the two patterns that were being duplicated across
every controller in the project:

1. reqparse configuration for the common query parameters
   (interval_dates, province, district, health_facility, facility_type,
   disaggregation) plus any endpoint-specific extras.

2. The JWT extraction + session population + try/except boilerplate that
   wraps every service call.

Usage example::

    from utilities.controller_helpers import (
        build_common_parser,
        run_reporting_endpoint,
    )

    _parser = build_common_parser(extra_args=[
        ("gene_xpert_result_type", {"type": str, "location": "args"}),
        ("type_of_laboratory", {"type": str, "location": "args"}),
    ])


    class tb_gx_registered_samples_by_lab_controller(Resource):
        def get(self):
            return run_reporting_endpoint(
                _parser.parse_args, registered_samples_by_lab_service
            )
"""

from flask import current_app, request, session
from functools import wraps
from flask_restful import reqparse
from werkzeug.exceptions import HTTPException

import logging

from utilities import report_cache
from auth.auth_service import get_user_by_id_service
from auth.roles import role_can_access_path
from utilities.service_helpers import InvalidParameter
from utilities.token_verification import TokenVerificationError, verify_bearer_token
from utilities.utils import get_token, get_user_token_info

logger = logging.getLogger(__name__)

# Argument definition reused for all "list-like" query parameters that may
# appear multiple times in the URL (e.g. ?province=A&province=B).
LIST_ARG = {"type": lambda x: x, "location": "args", "action": "append"}

# Argument definition for simple string query parameters.
STR_ARG = {"type": str, "location": "args"}

# Extra filters understood by the HIV VL reporting endpoints.
VL_FILTER_ARGS = [
    ("lab_code", LIST_ARG),
    ("age_range", LIST_ARG),
]

# Extra filters for the VL patient searches (drill-down from the cards).
VL_PATIENT_FILTER_ARGS = VL_FILTER_ARGS + [
    ("pregnant", STR_ARG),
    ("breastfeeding", STR_ARG),
    ("rejected", STR_ARG),
    ("date_basis", STR_ARG),
]

GENERIC_SERVER_ERROR = "An error occurred"


def build_common_parser(*, extra_args=None):
    """
    Build a ``reqparse.RequestParser`` pre-populated with the query
    parameters shared by all reporting endpoints.

    Parameters
    ----------
    extra_args : list[tuple[str, dict]] | None
        Optional list of ``(argument_name, kwargs)`` pairs that will be
        appended via ``parser.add_argument(name, **kwargs)``. Use this for
        endpoint-specific parameters such as ``gene_xpert_result_type``,
        ``lab_type``, ``page``, etc.

    Returns
    -------
    reqparse.RequestParser
        Parser ready to be invoked via ``.parse_args()``.
    """
    parser = reqparse.RequestParser()
    parser.add_argument("interval_dates", **LIST_ARG)
    parser.add_argument("province", **LIST_ARG)
    parser.add_argument("district", **LIST_ARG)
    parser.add_argument("health_facility", **STR_ARG)
    parser.add_argument("facility_type", **STR_ARG)
    parser.add_argument("disaggregation", **STR_ARG)

    for name, kwargs in extra_args or []:
        parser.add_argument(name, **kwargs)

    return parser


def error_response(exc, message="An error occurred", code=500):
    """
    Build a standardized JSON error response.

    Centralising this guarantees every endpoint returns the same payload
    shape (``status``, ``code``, ``message``, ``error``) with the correct
    HTTP status code.
    """
    return (
        {
            "status": "error",
            "code": code,
            "message": message,
            "error": str(exc),
        },
        code,
    )


def unauthorized_response():
    """Fixed 401 payload. Never include the verification failure reason."""
    return (
        {
            "status": "error",
            "code": 401,
            "message": "Invalid or missing token",
        },
        401,
    )


def _request_route():
    """Log the registered route pattern, never request values or query strings."""
    return request.url_rule.rule if request.url_rule is not None else "<unmatched>"


def authenticate_request():
    """
    Verify the JWT, resolve its subject's persisted role and authorize the route.
    Populate ``session['user_info']`` only after authorization. Missing local
    accounts and unassigned/unknown roles fail closed, before any report/cache.

    Returns
    -------
    tuple[str | None, tuple | None]
        A tuple ``(user_id, error_response)``. On success ``error_response``
        is ``None`` and ``user_id`` is a string. On failure ``user_id`` is
        ``None`` and ``error_response`` is a Flask response ready to be
        returned from the endpoint.
    """
    session.pop("user_info", None)
    token = get_token(request)

    try:
        token_payload = verify_bearer_token(token)
    except TokenVerificationError as exc:
        logger.warning("Rejected token on %s (%s)", _request_route(), type(exc).__name__)
        return None, unauthorized_response()

    # The verified subject identifies the account; custom claims cannot select
    # another user's persisted permissions or retain a revoked role.
    user_id = token_payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        return None, unauthorized_response()
    try:
        user = get_user_by_id_service(user_id)
    except Exception as exc:
        logger.error("Role lookup failed on %s (%s)", _request_route(), type(exc).__name__)
        return None, ({"status": "error", "code": 500, "message": GENERIC_SERVER_ERROR}, 500)

    if user is None:
        return None, unauthorized_response()
    role = user.role
    if not role_can_access_path(role, request.path):
        return None, forbidden_response()
    if role != "Admin" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        suggestion_paths = {
            "/hiv/send-suggestion", "/hiv/vl/send-suggestion", "/hiv/eid/send-suggestion",
            "/tb/send-suggestion", "/tb/gx/send-suggestion", "/tb/cultura/send-suggestion",
        }
        if request.method != "POST" or request.path.rstrip("/") not in suggestion_paths:
            return None, forbidden_response()
    # Preserve the existing restriction on identifiable patient searches.
    if "patients" in request.path.strip("/").split("/") and role != "Admin":
        return None, forbidden_response()

    user_info = get_user_token_info(token_payload)
    user_info.update(user_id=user_id, role=role)
    session["user_info"] = user_info
    return user_id, None


def forbidden_response():
    return {"status": "error", "code": 403, "message": "Access denied for this role"}, 403


def authenticated_resource_method(method):
    """Apply the same verified, persisted role policy to shared dictionaries."""
    @wraps(method)
    def wrapped(*args, **kwargs):
        _, error = authenticate_request()
        if error is not None:
            return error
        return method(*args, **kwargs)
    return wrapped


def service_result_response(result):
    """
    Turn a service's error dict into a real HTTP status.

    Services return ``{"status": "error", "code": N, ...}`` on failure. 4xx
    bodies keep their public fields, without the internal ``error`` detail.
    For 5xx only the status, code and a generic message are returned: other
    fields may also contain SQL, driver details or partial report data.
    Diagnostics contain only the registered route and validated HTTP code;
    the internal error is never formatted or retained in a log record.
    """
    if not (isinstance(result, dict) and result.get("status") == "error"):
        return result

    code = result.get("code")
    if not isinstance(code, int) or not 400 <= code <= 599:
        code = 500

    if code >= 500 or "error" in result:
        # Driver errors can carry SQL and bound patient/contact identifiers.
        # Never retain the error object or its text in the LogRecord either.
        logger.error("Service error on %s (HTTP %s)", _request_route(), code)

    if code >= 500:
        return {"status": "error", "code": code, "message": GENERIC_SERVER_ERROR}, code
    body = {key: value for key, value in result.items() if key != "error"}
    body["code"] = code
    return body, code


# Set by tools/warm_report_cache.py in its own process: recompute even when a fresh entry exists.
FORCE_REFRESH = False


def _report_cache_active():
    """``REPORT_CACHE_ENABLED`` in the app config wins (tests); otherwise the environment, never in tests."""
    flag = current_app.config.get("REPORT_CACHE_ENABLED")
    if flag is not None:
        return bool(flag)
    return report_cache.enabled() and not current_app.testing


def _cache_headers(state, computed_at):
    return {"X-Report-Cache": state, "X-Report-Computed-At": computed_at}


def run_reporting_endpoint(parse_fn, service_fn):
    """
    Execute the standard pipeline shared by every reporting endpoint.

    1. Authenticate and authorize using the current database role, then populate the session.
    2. Serve a dashboard default report ("last 12 months") from the shared
       report cache when it holds a fresh copy (see ``utilities/report_cache.py``).
    3. Parse the request arguments via ``parse_fn``.
    4. Inject ``user_id`` into the parsed arguments.
    5. Invoke ``service_fn(req_args)``.
    6. Map the outcome to an HTTP response: ``InvalidParameter`` -> 400,
       service error dicts -> their own status, anything unexpected -> a
       generic 500. Diagnostics log only the exception class and registered
       route, without its message or traceback. A successful default report
       is stored in the cache.
    """
    user_id, err = authenticate_request()
    if err is not None:
        return err

    # Authorization is checked against the database before any cached response.
    cache_key = None
    try:
        if _report_cache_active():
            cache_key = report_cache.cache_key(request.path, dict(request.args.lists()))
        if cache_key is not None and not FORCE_REFRESH:
            entry = report_cache.read(cache_key)
            if entry is not None:
                return entry["data"], 200, _cache_headers("HIT", entry["computed_at"])
    except Exception as exc:
        # The cache is optional. Its failure must not interrupt a live report
        # or turn an internal cache exception into a public error response.
        logger.warning("Report cache lookup failed on %s (%s)", _request_route(), type(exc).__name__)
        cache_key = None

    try:
        req_args = parse_fn()
        req_args["user_id"] = user_id
        result = service_fn(req_args)
    except HTTPException as exc:
        if exc.code is not None and exc.code >= 500:
            logger.error("Reporting HTTP error on %s (%s)", _request_route(), type(exc).__name__)
            return {"status": "error", "code": exc.code, "message": GENERIC_SERVER_ERROR}, exc.code
        raise
    except InvalidParameter as exc:
        return {"status": "error", "code": 400, "message": str(exc)}, 400
    except Exception as exc:
        logger.error("Unhandled error on %s (%s)", _request_route(), type(exc).__name__)
        return {"status": "error", "code": 500, "message": GENERIC_SERVER_ERROR}, 500

    response = service_result_response(result)
    # Errors come back as (body, code); only a successful report is cached.
    if cache_key is not None and not isinstance(response, tuple):
        try:
            entry = report_cache.write(cache_key, response)
        except Exception as exc:
            logger.warning("Report cache write failed on %s (%s)", _request_route(), type(exc).__name__)
            entry = None
        if entry is not None:
            return response, 200, _cache_headers("MISS", entry["computed_at"])
    return response
