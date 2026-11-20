"""
Per-dashboard permissions for API requests.

Clerk session tokens carry an ``openldr`` claim, e.g.
``{"dashboards": ["vl", "tb"], "patientData": true, "admin": false}``. The gate in
``utilities.controller_helpers.authenticate_request`` turns it into ``g.permissions`` and, only when
``PERMISSIONS_ENFORCED`` is on, rejects requests to a dashboard's endpoints that the user lacks.
"""
import os
from dataclasses import dataclass

from flask import current_app, g

from configs import paths

KNOWN_DASHBOARDS = frozenset({"vl", "eid", "tb"})

# Path prefix (with trailing slash, so ``/hivex/`` never matches) -> dashboard id.
_DASHBOARD_PREFIXES = (
    ("/hiv/vl/", "vl"),
    ("/hiv/eid/", "eid"),
    ("/tb/", "tb"),
)


@dataclass(frozen=True)
class Permissions:
    dashboards: frozenset = frozenset()
    patient_data: bool = False
    admin: bool = False
    service: bool = False


NO_PERMISSIONS = Permissions()


def permissions_enforced():
    """``PERMISSIONS_ENFORCED`` in the app config wins (tests); otherwise the environment. Only ``1`` is on."""
    flag = current_app.config.get("PERMISSIONS_ENFORCED")
    if flag is not None:
        return flag in (True, "1")
    return os.environ.get("PERMISSIONS_ENFORCED") == "1"


def service_account_names():
    """The user_name values listed in ``API_SERVICE_ACCOUNTS`` (comma separated); empty when unset."""
    raw = paths.API_SERVICE_ACCOUNTS or ""
    return frozenset(name.strip() for name in raw.split(",") if name.strip())


def parse_claim(claims):
    """The ``openldr`` claim as Permissions. Any malformed shape gives no permissions, never an error."""
    section = claims.get("openldr") if isinstance(claims, dict) else None
    if not isinstance(section, dict):
        return NO_PERMISSIONS
    raw = section.get("dashboards")
    dashboards = (
        frozenset(d for d in raw if isinstance(d, str) and d in KNOWN_DASHBOARDS)
        if isinstance(raw, (list, tuple))
        else frozenset()
    )
    return Permissions(
        dashboards=dashboards,
        patient_data=section.get("patientData") is True,
        admin=section.get("admin") is True,
    )


def permissions_for_token(claims):
    """
    Clerk tokens carry ``iss`` and are read through ``parse_claim``. API tokens (HS256) have no
    ``iss`` and can't forge it without our secret: the signed ``user_name`` of a listed service
    account gets every dashboard (no patient rows, no admin); any other API token gets nothing.
    """
    if not isinstance(claims, dict):
        return NO_PERMISSIONS
    if claims.get("iss"):
        return parse_claim(claims)
    name = claims.get("user_name")
    if isinstance(name, str) and name in service_account_names():
        return Permissions(dashboards=KNOWN_DASHBOARDS, service=True)
    return NO_PERMISSIONS


def dashboard_for_path(path):
    """The dashboard that owns a request path, or None for paths outside the three dashboards."""
    for prefix, dashboard in _DASHBOARD_PREFIXES:
        if path.startswith(prefix):
            return dashboard
    return None


def current_permissions():
    return getattr(g, "permissions", None) or NO_PERMISSIONS


def forbidden_response():
    return {"status": "error", "code": 403, "message": "Forbidden"}, 403


def patient_access_role(user):
    """
    The role string the patient-row checks compare with ``"Admin"``.

    Flag off: the DB role, ``"Unknown"`` when there is no user. Flag on: ``"Admin"`` for a token
    with ``patientData``, else ``"User"``; the DB user (possibly None) is ignored.
    """
    if permissions_enforced():
        return "Admin" if current_permissions().patient_data else "User"
    return user.role if user else "Unknown"


def require_admin_claim():
    """
    None when the caller may use the admin endpoints, else the 403 response. Checks the ``admin`` claim
    whatever ``PERMISSIONS_ENFORCED`` says, and refuses service tokens. Call it after ``authenticate_request``.
    """
    permissions = current_permissions()
    if permissions.service or not permissions.admin:
        return forbidden_response()
    return None
