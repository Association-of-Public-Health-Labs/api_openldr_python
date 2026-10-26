"""Unit tests for the legacy (openldr-api) vs Python EID parity script (no network)."""
import re
from urllib.parse import urlencode

import pytest

from tools import eid_parity_check as parity

WINDOW = ("2025-01-01", "2025-12-31")


def _legacy_routes():
    """Every route registered in the legacy openldr-api src/routes/eid.ts (relative to /eid)."""
    return {
        # Laboratory
        "/lab/all/samples_tested_by_month", "/lab/all/samples_registered_by_month",
        "/lab/conventional/samples_tested_by_month", "/lab/poc/samples_tested_by_month",
        "/lab/conventional/samples_tested", "/lab/poc/samples_tested", "/lab/conventional/tat",
        "/lab/tat_samples", "/lab/poc/tat", "/lab/sample_routes", "/lab/rejected_samples",
        "/lab/rejected_samples_monthly", "/lab/samples_by_equipment",
        "/lab/samples_by_equipment_monthly", "/lab/sample_routes_viewport",
        # Dashboard
        "/dash/pcr/indicators", "/dash/poc/indicators", "/dash/pcr/tat", "/dash/pcr/positivity",
        "/dash/poc/positivity", "/dash/pcr/number_of_samples", "/dash/poc/number_of_samples",
        "/dash/indicators_by_province", "/dash/samples_positivity", "/dash/pcr/tat_samples",
        "/dash/rejected_samples_monthly", "/dash/samples_by_equipment",
        "/dash/samples_by_equipment_monthly",
        # Clinic
        "/clinic/samples_registered_province", "/clinic/samples_registered_month",
        "/clinic/samples_tested_province", "/clinic/samples_tested_month",
        "/clinic/samples_tested_gender_province", "/clinic/samples_tested_gender_month",
        "/clinic/samples_tat_avg_month", "/clinic/samples_tat_avg_province",
        "/clinic/samples_tat_days_month", "/clinic/samples_tat_days_province",
        "/clinic/samples_rejected_by_month", "/clinic/samples_rejected_by_facility",
        "/clinic/conventional/key_indicators", "/clinic/poc/key_indicators",
    }


def _check(legacy_path, python_params=None):
    return next(
        c for c in parity.CHECKS
        if c.legacy_path == legacy_path and (python_params is None or c.python_params == python_params)
    )


def _run_main(tmp_path, fetch, extra=()):
    token = tmp_path / "token.txt"
    token.write_text("secret-token\n", encoding="utf-8")
    return parity.main(
        ["--legacy", "legacy", "--python", "python", "--token-file", str(token), "--year", "2025", *extra],
        fetch=fetch,
    )


# --------------------------------------------------------------------------- parameters


def test_param_translation():
    params = {"lab_code": ["PMB", "PNP"], "facility_type": "province", "disaggregation": "false",
              "province": ["Gaza"], "category": "0", "lab_type": "poc"}
    query = parity.legacy_query(*WINDOW, params, lab_names={"PMB": "Lab Ref Maputo"})
    assert urlencode(query) == (
        "dates%5B0%5D=2025-01-01&dates%5B1%5D=2025-12-31"
        "&labCodes%5B0%5D=Lab+Ref+Maputo&labCodes%5B1%5D=PNP"
        "&facilityType=province&disaggregation=false"
        "&facilityCodes%5B0%5D=Gaza&category=0"
    )


def test_health_facility_becomes_clinic_and_names_become_facility_codes():
    query = parity.legacy_query(*WINDOW, {"facility_type": "health_facility", "health_facility": "CS 1"})
    assert query[2:] == [("facilityType", "clinic"), ("facilityCodes[0]", "CS 1")]


def test_legacy_params_override_the_translation():
    query = parity.legacy_query(*WINDOW, {"facility_type": "province"}, extra={"facilityType": None, "labType": "poc"})
    assert query[2:] == [("labType", "poc")]


def test_unknown_parameter_has_no_silent_translation():
    with pytest.raises(ValueError):
        parity.legacy_query(*WINDOW, {"age_range": "15,49"})


def test_lab_checks_translate_lab_code_to_the_legacy_lab_name():
    calls = {}

    def fetch(base, path, params, headers):
        calls[base] = (path, params)
        return []

    check = next(c for c in parity.lab_checks("PMB") if c.legacy_path == "/lab/rejected_samples")
    parity.run_check(check, WINDOW, fetch, "legacy", "python", {}, lab_names={"PMB": "Lab Ref Maputo"})
    assert calls["legacy"] == ("/eid/lab/rejected_samples", [
        ("dates[0]", "2025-01-01"), ("dates[1]", "2026-01-01"), ("labCodes[0]", "Lab Ref Maputo"),
    ])
    assert calls["python"] == ("/hiv/eid/laboratories/rejected_samples/", [
        ("interval_dates", "2025-01-01,2025-12-31"), ("lab_code", ["PMB"]),
    ])


# --------------------------------------------------------------------------- comparisons


def test_run_check_ok():
    check = _check("/dash/pcr/indicators")

    def fetch(base, path, params, headers):
        if base == "legacy":
            return [{"Year": 2025, "Month": 1, "MonthName": "January", "Registados": 5, "Testados": 4,
                     "Rejeitados": 1, "Pendentes": 0}]
        return [{"year": 2025, "month": 1, "month_name": "January", "registered": 5, "tested": 4,
                 "rejected": 1, "pending": 0}]

    assert parity.run_check(check, WINDOW, fetch, "legacy", "python", {}) == ("OK", [])


def test_legacy_rows_are_aggregated_where_the_shapes_differ():
    check = _check("/clinic/conventional/key_indicators")
    legacy = [
        {"RequestingProvinceName": "Gaza", "RequestingDistrictName": "A", "RequestingFacilityName": "x",
         "Registadas": 2, "Testadas": 1, "Rejeitadas": 0, "Pendentes": 1, "Positividade": 0},
        {"RequestingProvinceName": "Gaza", "RequestingDistrictName": "B", "RequestingFacilityName": "y",
         "Registadas": 3, "Testadas": 3, "Rejeitadas": 1, "Pendentes": 0, "Positividade": 1},
    ]
    python = [{"requesting_facility": "Gaza", "registered": 5, "tested": 4, "rejected": 1, "pending": 1,
               "positive": 1, "positivity": 25.0}]

    def fetch(base, path, params, headers):
        return legacy if base == "legacy" else python

    assert parity.run_check(check, WINDOW, fetch, "legacy", "python", {}) == ("OK", [])


def test_tat_samples_legacy_wrapper_is_unwrapped():
    check = _check("/lab/tat_samples")
    legacy = {"report": [{"TestingFacilityName": "Lab", "<7": 1, "7-15": 2, "16-21": 0, ">21": 0, "no_dates": 3}],
              "categories": {}, "category": "0"}
    python = [{"testing_facility": "Lab", "category": "collection_hub_reception", "lt_7": 1, "between_7_15": 2,
               "between_16_21": 0, "gt_21": 0, "no_dates": 3}]

    def fetch(base, path, params, headers):
        return legacy if base == "legacy" else python

    assert parity.run_check(check, WINDOW, fetch, "legacy", "python", {}) == ("OK", [])


def test_positivity_shift_is_expected_and_sized():
    check = _check("/dash/samples_positivity")

    def fetch(base, path, params, headers):
        if base == "legacy":
            return [{"Year": 2025, "Month": 1, "MonthName": "January", "Conventional": 10, "Poc": 2, "Total": 100}]
        return [{"year": 2025, "month": 1, "month_name": "January", "tested": 100, "positive": 12,
                 "negative": 80, "indeterminate": 1, "conventional_positive": 11, "poc_positive": 1,
                 "positivity": 12.0}]

    status, lines = parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
    assert status == "EXPECTED ✱"
    summary = "\n".join(lines)
    assert "✱7 conventional_positive: legacy 10 -> python 11 (+1, +10.0%) in 1 row(s)" in summary
    assert re.search(r"✱3.* positivity: legacy 10(\.0)? -> python 12(\.0)?", summary)


def test_legacy_request_asks_for_the_day_after_the_end():
    """R21: legacy BETWEEN start AND end+1 covers the whole end day, as Python's inclusive window."""
    sent = {}

    def fetch(base, path, params, headers):
        sent[base] = params
        return []

    for check in parity.CHECKS:
        parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
        assert sent["legacy"][:2] == [("dates[0]", "2025-01-01"), ("dates[1]", "2026-01-01")], check.legacy_path
        assert sent["python"][0] == ("interval_dates", "2025-01-01,2025-12-31")
    assert parity.legacy_end("2024-02-28") == "2024-02-29"


@pytest.mark.parametrize("python_total", [12, 8])
def test_a_count_difference_with_no_star_fails_either_way(python_total):
    check = _check("/lab/all/samples_registered_by_month")

    def fetch(base, path, params, headers):
        if base == "legacy":
            return [{"Year": 2025, "Month": 12, "MonthName": "December", "Total": 10, "Conventional": 10, "Poc": 0}]
        return [{"year": 2025, "month": 12, "month_name": "December", "total": python_total,
                 "conventional": python_total, "poc": 0}]

    status, lines = parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
    assert status == "DIFF"
    assert any(line.startswith("UNEXPECTED total") for line in lines)


def test_a_row_only_python_has_is_unexpected():
    check = _check("/lab/all/samples_registered_by_month")

    def fetch(base, path, params, headers):
        if base == "legacy":
            return []
        return [{"year": 2026, "month": 1, "month_name": "January", "total": 1, "conventional": 1, "poc": 0}]

    assert parity.run_check(check, WINDOW, fetch, "legacy", "python", {}) == ("DIFF", ["(2026, 1) missing in legacy"])


def test_lab_checks_carry_no_expected_star():
    """R23: the legacy route filters correctly given labCodes, so lab-filtered checks must match."""
    assert all(not check.stars for check in parity.lab_checks("PMB"))


def test_a_row_missing_in_python_is_unexpected():
    check = _check("/lab/rejected_samples")

    def fetch(base, path, params, headers):
        if base == "legacy":
            return [{"ReceivingFacilityName": "Lab", **{label: 0 for label, _ in parity.REJECTION_LEGACY}}]
        return []

    status, lines = parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
    assert status == "DIFF"
    assert "('Lab',) missing in python" in lines


def test_equipment_groups_are_expected_star_8():
    check = _check("/dash/samples_by_equipment_monthly")

    def fetch(base, path, params, headers):
        groups = {key: 0 for key, _ in parity.EQUIPMENT}
        if base == "legacy":
            return [{"Year": 2025, "Month": 1, **groups, "Tested": 5, "C6800": 1}]
        return [{"year": 2025, "month": 1, **groups, "tested": 5, "C6800": 4}]

    status, lines = parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
    assert status == "EXPECTED ✱"
    assert any(line.startswith("✱8 C6800") for line in lines)


# --------------------------------------------------------------------------- main


def _positivity_only_fetch(python_positive, python_tested=100):
    """Every route empty except dash/samples_positivity."""

    def fetch(base, path, params, headers):
        if path == "/eid/dash/samples_positivity":
            return [{"Year": 2025, "Month": 3, "MonthName": "March", "Conventional": 10, "Poc": 0, "Total": 100}]
        if path == "/hiv/eid/summary/positivity/":
            return [{"year": 2025, "month": 3, "month_name": "March", "tested": python_tested,
                     "positive": python_positive, "negative": 0, "indeterminate": 0,
                     "conventional_positive": python_positive, "poc_positive": 0,
                     "positivity": round(100.0 * python_positive / python_tested, 1)}]
        return []

    return fetch


def test_expected_star_difference_does_not_fail(tmp_path, capsys):
    assert _run_main(tmp_path, _positivity_only_fetch(python_positive=13)) == 0
    out = capsys.readouterr().out
    assert "EXPECTED ✱" in out
    assert "secret-token" not in out
    assert "0 check(s) with unexpected differences" in out


def test_unexpected_difference_fails(tmp_path, capsys):
    assert _run_main(tmp_path, _positivity_only_fetch(python_positive=10, python_tested=90)) == 1
    out = capsys.readouterr().out
    assert "UNEXPECTED tested" in out
    assert "2 check(s) with unexpected differences" in out  # the 12- and the 3-month window


def test_lab_checks_run_only_with_a_lab(tmp_path, capsys):
    calls = []

    def fetch(base, path, params, headers):
        calls.append((base, path, tuple(params)))
        return []

    assert _run_main(tmp_path, fetch) == 0
    assert not any(("labCodes[0]", "Lab X") in params for _, _, params in calls)
    assert _run_main(tmp_path, fetch, extra=["--lab", "PMB=Lab X"]) == 0
    assert any(("labCodes[0]", "Lab X") in params for _, _, params in calls)


def test_python_requests_carry_the_token_and_legacy_requests_do_not(tmp_path):
    headers_by_base = {}

    def fetch(base, path, params, headers):
        headers_by_base.setdefault(base, set()).add(tuple(sorted(headers.items())))
        return []

    _run_main(tmp_path, fetch)
    assert headers_by_base["legacy"] == {()}
    assert headers_by_base["python"] == {(("Authorization", "Bearer secret-token"),)}


def test_every_legacy_route_is_covered_or_skipped():
    covered = {check.legacy_path for check in parity.CHECKS}
    assert covered.isdisjoint(parity.SKIPPED)
    assert covered | set(parity.SKIPPED) == _legacy_routes()
    assert len(parity.CHECKS) == 37  # 32 card routes + KPI tiles + 4 lab/all Convencional/PoC selects


def test_every_check_points_at_a_registered_python_route():
    import hiv.eid.routes as routes_module

    with open(routes_module.__file__, encoding="utf-8") as handle:
        registered = set(re.findall(r'"(/hiv/eid/[^"]+)"', handle.read()))
    for check in parity.CHECKS + parity.lab_checks("PMB"):
        assert check.python_path in registered, check.python_path


# --------------------------------------------------------------------------- review fix round 1


def _month_row(legacy, **values):
    keys = {"Year": 2025, "Month": 1} if legacy else {"year": 2025, "month": 1}
    return {**keys, **values}


def test_a_starred_field_missing_in_legacy_is_unexpected():
    check = _check("/dash/pcr/indicators", {"lab_type": "conventional"})  # ✱6 on every field

    def fetch(base, path, params, headers):
        if base == "legacy":
            return [_month_row(True)]
        return [_month_row(False, registered=5, tested=4, rejected=1, pending=0)]

    status, lines = parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
    assert status == "DIFF"
    assert any(line.startswith("UNEXPECTED registered") and "field missing" in line for line in lines)


def test_a_starred_field_missing_in_python_is_unexpected():
    check = _check("/clinic/samples_tested_gender_province")  # ✱7 on every field

    def fetch(base, path, params, headers):
        if base == "legacy":
            return [{"facility": "Gaza", "Masculino Positivo": 10, "Masculino Negativo": 1,
                     "Feminino Positivo": 2, "Feminino Negativo": 3}]
        return [{"requesting_facility": "Gaza"}]

    status, lines = parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
    assert status == "DIFF"
    assert any(line.startswith("UNEXPECTED male_positive") for line in lines)


def _kpi_check():
    return next(c for c in parity.CHECKS if c.legacy_extra_paths == ("/dash/poc/indicators",))


def test_kpi_tiles_compare_python_all_with_legacy_pcr_plus_poc():
    check = _kpi_check()
    assert check.python_path == "/hiv/eid/summary/indicators/" and check.python_params == {}
    assert not check.stars  # registered, tested, rejected untagged; pending gets ✱7 by name
    calls = []

    def fetch(base, path, params, headers):
        calls.append(path)
        if path == "/eid/dash/pcr/indicators":
            return [_month_row(True, Registados=7, Testados=5, Rejeitados=1, Pendentes=1)]
        if path == "/eid/dash/poc/indicators":
            return [_month_row(True, Registados=3, Testados=3, Rejeitados=0, Pendentes=0)]
        return [_month_row(False, registered=10, tested=8, rejected=1, pending=2)]

    status, lines = parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
    assert calls == ["/eid/dash/pcr/indicators", "/eid/dash/poc/indicators", "/hiv/eid/summary/indicators/"]
    assert status == "EXPECTED ✱"
    assert lines[0].startswith("✱7 pending: legacy 1 -> python 2")


def test_kpi_tiles_registered_difference_fails():
    def fetch(base, path, params, headers):
        if base == "legacy":
            return [_month_row(True, Registados=5, Testados=4, Rejeitados=0, Pendentes=1)]
        return [_month_row(False, registered=11, tested=8, rejected=0, pending=2)]

    status, lines = parity.run_check(_kpi_check(), WINDOW, fetch, "legacy", "python", {})
    assert status == "DIFF"
    assert any(line.startswith("UNEXPECTED registered") for line in lines)


def test_legacy_month_after_the_window_is_dropped():
    """End + 1 day (R21) can give the legacy a month the window does not have."""
    check = _check("/lab/all/samples_registered_by_month", {})

    def fetch(base, path, params, headers):
        if base == "legacy":
            return [{"Year": 2025, "Month": 12, "Total": 3, "Conventional": 3, "Poc": 0},
                    {"Year": 2026, "Month": 1, "Total": 1, "Conventional": 1, "Poc": 0}]
        return [{"year": 2025, "month": 12, "total": 3, "conventional": 3, "poc": 0}]

    assert parity.run_check(check, WINDOW, fetch, "legacy", "python", {}) == ("OK", [])


def test_year_and_month_match_as_int_on_both_sides():
    check = _check("/lab/all/samples_registered_by_month", {})

    def fetch(base, path, params, headers):
        if base == "legacy":
            return [{"Year": "2025", "Month": "12", "Total": 3, "Conventional": 3, "Poc": 0}]
        return [{"year": 2025, "month": 12, "total": 3, "conventional": 3, "poc": 0}]

    assert parity.run_check(check, WINDOW, fetch, "legacy", "python", {}) == ("OK", [])


@pytest.mark.parametrize("lab_type", ["conventional", "poc"])
def test_lab_all_selects_send_labtype(lab_type):
    sent = {}

    def fetch(base, path, params, headers):
        sent[(base, path)] = params
        return []

    for path in ("/lab/all/samples_tested_by_month", "/lab/all/samples_registered_by_month"):
        check = _check(path, {"lab_type": lab_type})
        parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
        assert ("labType", lab_type) in sent[("legacy", "/eid" + path)]
        assert ("lab_type", lab_type) in sent[("python", check.python_path)]
    check = _check("/lab/all/samples_tested_by_month", {})
    parity.run_check(check, WINDOW, fetch, "legacy", "python", {})
    assert not any(name == "labType" for name, _ in sent[("legacy", "/eid/lab/all/samples_tested_by_month")])


def test_every_lab_type_reaches_the_legacy_side():
    """A lab_type is either the legacy route variant (path segment) or a legacy parameter."""
    for check in parity.CHECKS + parity.lab_checks("PMB"):
        lab_type = check.python_params.get("lab_type")
        if lab_type and lab_type != "all":
            segments = {"conventional": ("/conventional/", "/pcr/"), "poc": ("/poc/",)}[lab_type]
            assert check.legacy_lab_type_param or any(seg in check.legacy_path for seg in segments), check


# Fields the Python service computes after the query (not SQL column labels).
_COMPUTED = {"positivity", "category"}


def _service_for(app, path):
    """The service function the controller at ``path`` hands to run_reporting_endpoint."""
    import sys
    from unittest.mock import patch

    endpoint, _ = app.url_map.bind("localhost").match(path)
    view_class = app.view_functions[endpoint].view_class
    module = sys.modules[view_class.__module__]
    captured = {}
    with patch.object(module, "run_reporting_endpoint", lambda parse, service: captured.setdefault("s", service)):
        with app.test_request_context(path):
            view_class().get()
    return captured["s"]


def test_every_python_field_read_is_a_column_of_the_service_sql(app):
    from tests.hiv.sql_capture import service_sql

    for check in parity.CHECKS + parity.lab_checks("PMB"):
        service = _service_for(app, check.python_path)
        args = {"interval_dates": ["2025-01-01,2025-12-31"], **check.python_params}
        _, sql = service_sql(app, service, args)
        assert sql, check.python_path
        text = " ".join(sql)
        wanted = [f for _, f in check.fields] + list(check.python_keys)
        for field in wanted:
            if field in _COMPUTED:
                continue
            assert re.search(rf"AS \[?{re.escape(field)}\]?(\W|$)", text), (check.python_path, field)
