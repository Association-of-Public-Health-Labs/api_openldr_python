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

from flask import request, session
from flask_restful import reqparse
from werkzeug.exceptions import HTTPException

import logging

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

    for name, kwargs in (extra_args or []):
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


def authenticate_request():
    """
    Verify the signature of the incoming request's JWT and populate ``session['user_info']``.

    Returns
    -------
    tuple[str | None, tuple | None]
        A tuple ``(user_id, error_response)``. On success ``error_response``
        is ``None`` and ``user_id`` is a string. On failure ``user_id`` is
        ``None`` and ``error_response`` is a Flask response ready to be
        returned from the endpoint.
    """
    token = get_token(request)

    try:
        token_payload = verify_bearer_token(token)
    except TokenVerificationError as exc:
        logger.warning("Rejected token on %s: %r", request.path, str(exc))
        return None, unauthorized_response()

    session["user_info"] = get_user_token_info(token_payload)
    user_id = str(session["user_info"].get("user_id"))
    return user_id, None


def service_result_response(result):
    """
    Turn a service's error dict into a real HTTP status.

    Services return ``{"status": "error", "code": N, ...}`` on failure. 4xx
    bodies are returned as they are. For 5xx the exception text (``error``)
    is logged and dropped, and the message is replaced with a generic one,
    so SQL and driver details never reach the caller.
    """
    if not (isinstance(result, dict) and result.get("status") == "error"):
        return result

    code = result.get("code")
    if not isinstance(code, int) or not 400 <= code <= 599:
        code = 500

    if result.get("error"):
        logger.error("Service error on %s: %s", request.path, result["error"])

    body = {key: value for key, value in result.items() if key != "error"}
    body["code"] = code
    if code >= 500:
        body["message"] = GENERIC_SERVER_ERROR
    return body, code


def run_reporting_endpoint(parse_fn, service_fn):
    """
    Execute the standard pipeline shared by every reporting endpoint.

    1. Authenticate the request and populate the session.
    2. Parse the request arguments via ``parse_fn``.
    3. Inject ``user_id`` into the parsed arguments.
    4. Invoke ``service_fn(req_args)``.
    5. Map the outcome to an HTTP response: ``InvalidParameter`` -> 400,
       service error dicts -> their own status, anything unexpected -> a
       generic 500 (details are logged, never returned).
    """
    user_id, err = authenticate_request()
    if err is not None:
        return err

    try:
        req_args = parse_fn()
        req_args["user_id"] = user_id
        result = service_fn(req_args)
    except HTTPException:
        raise
    except InvalidParameter as exc:
        return {"status": "error", "code": 400, "message": str(exc)}, 400
    except Exception:
        logger.exception("Unhandled error on %s", request.path)
        return {"status": "error", "code": 500, "message": GENERIC_SERVER_ERROR}, 500

    return service_result_response(result)
