"""Database-independent coverage of the dashboard role policy."""

import pytest

from auth.roles import (
    CANONICAL_ROLES,
    DASHBOARD_ROLES,
    normalize_role,
    path_is_protected,
    role_can_access_path,
)


DIVISION_PATHS = {
    "vl": "/hiv/vl/summary",
    "dpi": "/hiv/eid/summary",
    "tb_gx": "/tb/gx/summary",
    "tb_cl": "/tb/cultura/summary",
    "ad": "/hiv/ad/summary",
}


@pytest.mark.parametrize("role", CANONICAL_ROLES)
def test_role_assignment_normalizes_case_and_whitespace(role):
    assert normalize_role(role) == role
    assert normalize_role("  " + role.upper() + "  ") == role


@pytest.mark.parametrize("raw", [None, "", " ", "unknown", "superadmin", [], {}, 1])
def test_role_assignment_rejects_invalid_values(raw):
    assert normalize_role(raw) is None


@pytest.mark.parametrize("role", sorted(DASHBOARD_ROLES))
@pytest.mark.parametrize("division,path", DIVISION_PATHS.items())
def test_dashboard_access_matrix(role, division, path):
    assert role_can_access_path(role, path) == (
        role in {"Admin", "global", division}
    )


@pytest.mark.parametrize("prefix", ["/hiv/eid", "/hiv/dpi"])
@pytest.mark.parametrize("suffix", ["", "/", "/summary", "/send-suggestion"])
def test_dpi_role_supports_existing_and_future_route_names(prefix, suffix):
    assert role_can_access_path("dpi", prefix + suffix)
    assert not role_can_access_path("vl", prefix + suffix)


@pytest.mark.parametrize("division,path", DIVISION_PATHS.items())
def test_division_root_and_trailing_slash_are_allowed(division, path):
    prefix = path.rsplit("/", 1)[0]
    assert role_can_access_path(division, prefix)
    assert role_can_access_path(division, prefix + "/")


@pytest.mark.parametrize(
    "path",
    [
        "/hiv/vl-other/summary",
        "/hiv/eidx/summary",
        "/hiv/dpix/summary",
        "/hiv/ad-other/summary",
        "/tb/gx-other/summary",
        "/tb/cultura-other/summary",
        "/dict-other/laboratories",
        "/hiv/unknown/summary",
        "/tb/unknown/summary",
        "/send-suggestion-other",
        "/hiv/send-suggestion/unknown",
        "/tb/send-suggestion/unknown",
        "/auth/users",
        "/apispec_1.json",
        "/",
    ],
)
@pytest.mark.parametrize("role", sorted(DASHBOARD_ROLES))
def test_unknown_roots_and_prefix_lookalikes_do_not_grant_access(role, path):
    assert not role_can_access_path(role, path)


@pytest.mark.parametrize("role", ["user", "User", "admin", "ADMIN", "Global", "VL", "unknown", None, [], {}])
@pytest.mark.parametrize("path", ["/hiv/vl/summary", "/dict/laboratories", "/hiv/send-suggestion"])
def test_noncanonical_or_unassigned_stored_roles_are_denied(role, path):
    assert not role_can_access_path(role, path)


@pytest.mark.parametrize("role", sorted(DASHBOARD_ROLES))
@pytest.mark.parametrize("path", ["/dict", "/dict/", "/dict/laboratories/", "/send-suggestion", "/send-suggestion/"])
def test_shared_dictionary_and_general_suggestion_access(role, path):
    assert role_can_access_path(role, path)


@pytest.mark.parametrize("role", sorted(DASHBOARD_ROLES))
@pytest.mark.parametrize(
    "path,family_roles",
    [
        ("/hiv/send-suggestion", {"vl", "dpi", "ad"}),
        ("/tb/send-suggestion/", {"tb_gx", "tb_cl"}),
    ],
)
def test_family_suggestions_require_family_membership(role, path, family_roles):
    assert role_can_access_path(role, path) == (
        role in {"Admin", "global"} or role in family_roles
    )


@pytest.mark.parametrize("division,path", DIVISION_PATHS.items())
def test_division_suggestions_follow_division_access(division, path):
    prefix = path.rsplit("/", 1)[0]
    for role in DASHBOARD_ROLES:
        assert role_can_access_path(role, prefix + "/send-suggestion") == (
            role in {"Admin", "global", division}
        )


@pytest.mark.parametrize("path", ["/hiv", "/hiv/", "/hiv/vl/summary", "/hiv/unknown", "/tb/unknown", "/tb", "/dict", "/dict/laboratories", "/send-suggestion", "/send-suggestion/new"])
def test_dashboard_roots_are_protected_even_when_route_is_unknown(path):
    assert path_is_protected(path)


@pytest.mark.parametrize("path", ["/hiv-other", "/tb-other", "/dict-other", "/send-suggestion-other", "/auth/users", "/apidocs/", "/", "", None, [], {}])
def test_unrelated_roots_are_outside_the_dashboard_policy(path):
    assert not path_is_protected(path)


@pytest.mark.parametrize("path", [None, [], {}, 1])
def test_access_rejects_non_string_paths(path):
    assert not role_can_access_path("Admin", path)
