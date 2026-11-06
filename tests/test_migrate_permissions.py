from tools import migrate_permissions as mp


def clerk_user(user_id, email, public_metadata=None):
    return {
        "id": user_id,
        "primary_email_address_id": f"idn_{user_id}",
        "email_addresses": [{"id": f"idn_{user_id}", "email_address": email}],
        "public_metadata": public_metadata or {},
    }


def plan(users, roles=None, admins=()):
    return mp.plan_changes(users, roles or {}, set(admins))


def test_every_user_gets_all_three_dashboards():
    [change] = plan([clerk_user("u1", "a@x.org")])
    assert change.public_metadata["dashboards"] == ["vl", "eid", "tb"]


def test_db_admin_role_gives_patient_data_anything_else_does_not():
    users = [clerk_user("u1", "a@x.org"), clerk_user("u2", "b@x.org"), clerk_user("u3", "c@x.org"), clerk_user("u4", "d@x.org")]
    roles = {"u1": "Admin", "u2": "admin", "u3": "user"}
    flags = {c.user_id: c.public_metadata["patientData"] for c in plan(users, roles)}
    assert flags == {"u1": True, "u2": False, "u3": False, "u4": False}


def test_admin_only_for_listed_emails_case_insensitive():
    users = [clerk_user("u1", "Boss@X.org"), clerk_user("u2", "other@x.org")]
    admins = {c.user_id: c.public_metadata["admin"] for c in plan(users, admins={"boss@x.ORG"})}
    assert admins == {"u1": True, "u2": False}


def test_other_public_metadata_keys_are_preserved():
    [change] = plan([clerk_user("u1", "a@x.org", {"locale": "pt", "admin": "junk"})])
    assert change.public_metadata["locale"] == "pt"
    assert change.public_metadata["admin"] is False
    assert set(change.public_metadata) == {"locale", "dashboards", "patientData", "admin"}


def test_user_with_dashboards_is_skipped():
    users = [clerk_user("u1", "a@x.org", {"dashboards": []}), clerk_user("u2", "b@x.org")]
    assert [c.user_id for c in plan(users)] == ["u2"]


def test_unmatched_admin_emails_are_reported():
    users = [clerk_user("u1", "a@x.org", {"dashboards": ["vl"]})]
    assert mp.unmatched_admins(users, {"A@x.org", "ghost@x.org"}) == ["ghost@x.org"]


def test_secondary_address_in_admins_file_is_reported_as_unmatched():
    user = clerk_user("u1", "a@x.org")
    user["email_addresses"].append({"id": "idn_other", "email_address": "second@x.org"})
    assert mp.unmatched_admins([user], {"second@x.org", "a@x.org"}) == ["second@x.org"]
    assert plan([user], admins={"second@x.org"})[0].public_metadata["admin"] is False


def test_malformed_users_are_those_with_dashboards_but_not_all_three_keys():
    good = clerk_user("u1", "a@x.org", {"dashboards": ["vl"], "patientData": False, "admin": False})
    partial = clerk_user("u2", "b@x.org", {"dashboards": ["vl"]})
    wrong_type = clerk_user("u3", "c@x.org", {"dashboards": "vl", "patientData": False, "admin": False})
    string_flag = clerk_user("u4", "d@x.org", {"dashboards": [], "patientData": "true", "admin": False})
    fresh = clerk_user("u5", "e@x.org")
    assert [u["id"] for u in mp.malformed_users([good, partial, wrong_type, string_flag, fresh])] == ["u2", "u3", "u4"]


def test_grant_admin_keeps_other_keys_and_skips_unmigrated():
    migrated = clerk_user("u1", "A@x.org", {"locale": "pt", "dashboards": ["vl"], "patientData": True, "admin": False})
    fresh = clerk_user("u2", "b@x.org")
    [change] = mp.plan_grants([migrated, fresh], {"a@x.org", "b@x.org"})
    assert change.user_id == "u1"
    assert change.public_metadata == {"locale": "pt", "dashboards": ["vl"], "patientData": True, "admin": True}


def test_read_admins_file_ignores_blanks_and_comments(tmp_path):
    f = tmp_path / "admins.txt"
    f.write_text("A@x.org\n\n# note\n  b@x.org  \n")
    assert mp.read_admins(str(f)) == {"a@x.org", "b@x.org"}


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


class FakeHttp:
    def __init__(self, users, fail_ids=()):
        self.users, self.fail_ids = users, set(fail_ids)
        self.gets, self.patches = [], []

    def get(self, url, headers=None, params=None, **kw):
        self.gets.append(params["offset"])
        return FakeResponse(200, self.users[params["offset"]: params["offset"] + params["limit"]])

    def patch(self, url, headers=None, json=None, **kw):
        self.patches.append((url, json))
        return FakeResponse(500 if url.split("/")[-2] in self.fail_ids else 200, {})


def run(http, apply, roles=None, admins=(), page_size=2):
    return mp.run(http, "https://clerk.test/v1", "sk_secret", roles or {}, set(admins), apply, page_size=page_size)


def test_fetch_all_users_pages_until_a_short_page():
    users = [clerk_user(f"u{i}", f"{i}@x.org") for i in range(5)]
    http = FakeHttp(users)
    assert len(mp.fetch_all_users(http, "https://clerk.test/v1", "sk", page_size=2)) == 5
    assert http.gets == [0, 2, 4]


def test_fetch_all_users_stops_on_empty_page_after_full_one():
    http = FakeHttp([clerk_user(f"u{i}", f"{i}@x.org") for i in range(4)])
    assert len(mp.fetch_all_users(http, "https://clerk.test/v1", "sk", page_size=2)) == 4
    assert http.gets == [0, 2, 4]


def test_dry_run_writes_nothing():
    http = FakeHttp([clerk_user("u1", "a@x.org"), clerk_user("u2", "b@x.org")])
    assert run(http, apply=False) == 0
    assert http.patches == []


def test_apply_writes_full_three_keys_per_user():
    http = FakeHttp([clerk_user("u1", "a@x.org")])
    assert run(http, apply=True, roles={"u1": "Admin"}, admins={"a@x.org"}) == 0
    [(url, body)] = http.patches
    assert url == "https://clerk.test/v1/users/u1/metadata"
    assert body == {"public_metadata": {"dashboards": ["vl", "eid", "tb"], "patientData": True, "admin": True}}


def test_failed_write_is_reported_run_continues_exit_nonzero(capsys):
    http = FakeHttp([clerk_user("u1", "a@x.org"), clerk_user("u2", "b@x.org"), clerk_user("u3", "c@x.org")], fail_ids={"u2"})
    assert run(http, apply=True) == 1
    assert len(http.patches) == 3
    out = capsys.readouterr()
    assert "b@x.org" in out.out + out.err
    assert "sk_secret" not in out.out + out.err


def test_dry_run_lists_who_gets_admin_and_patient_data(capsys):
    http = FakeHttp([clerk_user("u1", "boss@x.org"), clerk_user("u2", "b@x.org"), clerk_user("u3", "c@x.org")])
    assert run(http, apply=False, roles={"u2": "Admin"}, admins={"boss@x.org"}) == 0
    out = capsys.readouterr().out
    assert "admin: boss@x.org" in out
    assert "patientData: b@x.org" in out
    assert "sk_secret" not in out


def test_malformed_users_are_warned_and_never_written(capsys):
    http = FakeHttp([clerk_user("u1", "half@x.org", {"dashboards": ["vl"]}), clerk_user("u2", "new@x.org")])
    assert run(http, apply=True) == 0
    assert [url.split("/")[-2] for url, _ in http.patches] == ["u2"]
    assert "half@x.org" in capsys.readouterr().out


def test_grant_admin_writes_only_that_user_with_other_keys_untouched():
    migrated = clerk_user("u1", "a@x.org", {"dashboards": ["tb"], "patientData": True, "admin": False})
    other = clerk_user("u2", "b@x.org", {"dashboards": ["tb"], "patientData": False, "admin": False})
    http = FakeHttp([migrated, other])
    assert mp.run(http, "https://clerk.test/v1", "sk_secret", {}, set(), True, page_size=5, grant_emails=["a@x.org"]) == 0
    [(url, body)] = http.patches
    assert url.endswith("/users/u1/metadata")
    assert body == {"public_metadata": {"dashboards": ["tb"], "patientData": True, "admin": True}}


def test_grant_admin_needs_apply(capsys):
    import pytest
    with pytest.raises(SystemExit):
        mp.main(["--admins", "x.txt", "--grant-admin", "a@x.org"])
