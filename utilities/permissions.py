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
    """``PERMISSIONS_ENFORCED`` in the app config wins (tests); otherwise the environment."""
    flag = current_app.config.get("PERMISSIONS_ENFORCED")
    if flag is not None:
        return bool(flag)
    return os.environ.get("PERMISSIONS_ENFORCED", "0").strip().lower() in ("1", "true", "yes", "on")


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
    ``iss`` and can't forge it without our secret; they get no permissions until Task A6.
    """
    if isinstance(claims, dict) and claims.get("iss"):
        return parse_claim(claims)
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
