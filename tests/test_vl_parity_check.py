"""Unit tests for the Node vs Python VL parity script (no network)."""
from tools import vl_parity_check as parity


def test_node_query_uses_qs_index_format():
    assert parity.node_query("2025-01-01", "2025-12-31", {"codes": ["PCD", "PDD"], "type": "province"}) == [
        ("dates[0]", "2025-01-01"), ("dates[1]", "2025-12-31"),
        ("codes[0]", "PCD"), ("codes[1]", "PDD"), ("type", "province"),
    ]


def test_python_query_uses_csv_interval_dates():
    assert parity.python_query("2025-01-01", "2025-12-31", {"age_range": "15,49"}) == [
        ("interval_dates", "2025-01-01,2025-12-31"), ("age_range", "15,49"),
    ]


def test_default_windows_are_a_full_year_and_its_last_quarter():
    assert parity.default_windows(2025) == {
        "12 months": ("2025-01-01", "2025-12-31"),
        "3 months": ("2025-10-01", "2025-12-31"),
    }


def test_index_rows_aggregates_split_rows():
    rows = [
        {"requesting_facility": "Gaza", "age_group": "15-19", "total": 2},
        {"requesting_facility": "Gaza", "age_group": "20-24", "total": 3},
    ]
    assert parity.index_rows(rows, ["requesting_facility"], ["total"], aggregate=True) == {("Gaza",): {"total": 5}}


def test_index_rows_normalises_week_start_dates():
    rows = [{"start": "2025-01-05T00:00:00.000Z", "tests": 1}]
    assert parity.index_rows(rows, ["start"], ["tests"]) == {("2025-01-05",): {"tests": 1}}


def test_compare_reports_value_and_missing_rows():
    node = {("Gaza",): {"total": 5}, ("Tete",): {"total": 1}}
    python = {("Gaza",): {"total": 6}}
    differences = parity.compare(node, python, [("total", "total")])
    assert differences == ["('Gaza',) total: node=5 python=6", "('Tete',) missing in python"]


def test_compare_tolerates_float_noise():
    assert parity.compare({(1,): {"tat": 3}}, {(1,): {"tat": 3.004}}, [("tat", "tat")]) == []


def test_run_check_marks_expected_star_differences():
    check = next(c for c in parity.CHECKS if c.node_path == "/clinic_samples_rejected_by_facility")

    def fetch(base, path, params, headers):
        if base == "node":
            return [{"facility": "Gaza", "type": "province", "total": 1}]
        return [{"requesting_facility": "Gaza", "total": 4}]

    status, differences = parity.run_check(check, ("2025-01-01", "2025-12-31"), fetch, "node", "python", {})
    assert status == "EXPECTED ✱"
    assert differences


def test_run_check_ok():
    check = next(c for c in parity.CHECKS if c.node_path == "/dash_number_of_samples")

    def fetch(base, path, params, headers):
        return [{"year": 2025, "month": 1, "total": 7, "month_name": "January"}]

    assert parity.run_check(check, ("2025-01-01", "2025-12-31"), fetch, "node", "python", {}) == ("OK", [])


def test_every_legacy_url_is_covered_or_skipped():
    covered = {check.node_path for check in parity.CHECKS}
    assert len(covered) == 26
    assert parity.SKIPPED == {"/weeklyreports/instrument": "no Python endpoint (out of scope, ruling R7)"}
