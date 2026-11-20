"""Pure dashboard role policy, shared by HTTP and authentication code.

Normalize administrator input before storing it. Access checks deliberately use
the stored canonical value: a legacy ``admin`` value must never become ``Admin``
merely because an authenticated request passes through this policy.
"""

CANONICAL_ROLES = ("Admin", "global", "vl", "dpi", "tb_gx", "tb_cl", "ad", "user")
DASHBOARD_ROLES = frozenset(CANONICAL_ROLES) - {"user"}

_ROLE_BY_NORMALIZED_NAME = {role.lower(): role for role in CANONICAL_ROLES}
_DIVISION_PREFIXES = (
    ("/hiv/vl", "vl"),
    ("/hiv/eid", "dpi"),
    ("/hiv/dpi", "dpi"),
    ("/tb/gx", "tb_gx"),
    ("/tb/cultura", "tb_cl"),
    ("/hiv/ad", "ad"),
)
_UNRESTRICTED_DASHBOARD_ROLES = frozenset({"Admin", "global"})
_FAMILY_SUGGESTION_ROLES = {
    "/hiv/send-suggestion": frozenset({"vl", "dpi", "ad"}),
    "/tb/send-suggestion": frozenset({"tb_gx", "tb_cl"}),
}


def normalize_role(raw):
    """Return a canonical role for string input, or ``None`` if invalid.

    This function is for validated role assignment, not runtime elevation of
    existing database roles. ``user`` remains a valid unassigned legacy role.
    """
    if not isinstance(raw, str):
        return None
    return _ROLE_BY_NORMALIZED_NAME.get(raw.strip().lower())


def _is_within(path, prefix):
    """Match one path component boundary, including the prefix itself."""
    return path == prefix or path.startswith(prefix + "/")


def path_is_protected(path):
    """Whether a decoded request path belongs to a dashboard policy root.

    Classify whole HIV/TB families, including unassigned subdivisions. New
    controllers must use authenticate_request/run_reporting_endpoint; this
    helper does not install a global HTTP hook. Authentication administration
    and API documentation are governed by their own policies.
    """
    if not isinstance(path, str):
        return False
    return any(
        _is_within(path, prefix)
        for prefix in ("/hiv", "/tb", "/dict", "/send-suggestion")
    )


def role_can_access_path(role, path):
    """Check a canonical stored role against a decoded request path.

    Admin/global can read every known dashboard subdivision. Each subdivision
    can also use dictionaries and its family's suggestion endpoint. Unknown or
    unassigned roles have no dashboard access. This check does not replace
    separate administrative or patient-level permission checks.
    """
    if not isinstance(role, str) or role not in DASHBOARD_ROLES:
        return False
    if not isinstance(path, str):
        return False

    for prefix, division in _DIVISION_PREFIXES:
        if _is_within(path, prefix):
            return role in _UNRESTRICTED_DASHBOARD_ROLES or role == division

    if _is_within(path, "/dict"):
        return True

    suggestion_path = path.rstrip("/")
    if suggestion_path == "/send-suggestion":
        return True
    family_roles = _FAMILY_SUGGESTION_ROLES.get(suggestion_path)
    if family_roles is not None:
        return role in _UNRESTRICTED_DASHBOARD_ROLES or role in family_roles

    return False
