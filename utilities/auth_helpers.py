"""
Shared authorization helpers for service-layer functions.

Centralises the user role lookup + admin-only gate that was duplicated in
multiple service modules (``hiv/vl/services/*`` and
``tb/gxpert/services/tb_gx_services_patients.py``).
"""

from auth.auth_service import get_user_by_id_service
from utilities.permissions import patient_access_role, permissions_enforced


def get_user_role(req_args):
    """
    Return ``(user_id, user_role)`` for the caller.

    ``user_role`` defaults to ``"Unknown"`` when the user cannot be
    resolved (no ``user_id`` in ``req_args`` or the DB lookup fails).
    This mirrors the original behaviour of the inline implementations.
    With PERMISSIONS_ENFORCED on, the role comes from the token's ``patientData``
    permission and the DB is not consulted.
    """
    user_id = req_args.get("user_id")
    if permissions_enforced():
        return user_id, patient_access_role(None)
    if user_id is None:
        return None, "Unknown"

    try:
        user = get_user_by_id_service(user_id)
    except Exception:
        return user_id, "Unknown"

    user_role = patient_access_role(user)
    return user_id, user_role


def check_admin_access(user_id, user_role):
    """
    Gate helper. Returns an error dict when the user is not an Admin,
    otherwise ``None``.

    The returned shape matches the one historically produced by the
    service layer so that callers can simply ``return`` it.
    """
    if user_role != "Admin":
        return {
            "status": "error",
            "code": 403,
            "message": (
                f"Forbidden - User with id {user_id} and role {user_role} "
                "is not authorized to access this resource."
            ),
        }
    return None


def require_admin(req_args):
    """
    Convenience wrapper combining :func:`get_user_role` and
    :func:`check_admin_access`.

    Returns
    -------
    tuple[str | None, dict | None]
        ``(user_id, error_dict)``. ``error_dict`` is ``None`` when the
        caller is an Admin; otherwise it carries the 403 payload to return
        verbatim from the service.
    """
    user_id, user_role = get_user_role(req_args)
    return user_id, check_admin_access(user_id, user_role)
