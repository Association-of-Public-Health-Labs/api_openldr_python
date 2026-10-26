"""
Compare the legacy Node VL API with api_openldr_python on real data.

Run it with the Node backend (openldr-backend) running locally against the
same ViralLoadData / ReportData databases as the Python API:

    python -m tools.vl_parity_check --node http://localhost:4444 \
        --python https://dev.openldr.org.mz --token-file token.txt

token.txt holds a token from POST /auth/login on the Python API (valid for
60 minutes). A Clerk session token expires after about 60 seconds, too soon
for a full run. The token is never printed.

For every legacy URL the dashboard calls, the script fetches one full year and
its last quarter from both APIs, normalises the keys and prints the
differences. Exit code 0 means every difference is a documented ✱ fix.
"""
import argparse
import sys
from collections import namedtuple
from datetime import date

import requests

FLOAT_TOLERANCE = 0.01

Check = namedtuple(
    "Check",
    "node_path node_params python_path python_params node_keys python_keys fields aggregate expected",
)

TAT = [(name, name) for name in (
    "collection_reception", "reception_registration", "registration_analysis", "analysis_validation",
)]
GENDER = [(name, name) for name in (
    "male_suppressed", "male_not_suppressed", "female_suppressed", "female_not_suppressed",
)]
WEEKLY = [("backlogs", "backlogs"), ("tests", "tests"), ("registrations", "registrations"),
          ("rejections", "rejections"), ("capacity", "capacity"), ("tat", "tat")]
REASONS = [("routine", "routine"), ("treatment_failure", "treatment_failure"),
           ("reason_not_specified", "reason_not_specified")]
PROVINCE = {"type": "province", "disaggregation": "false"}
PY_PROVINCE = {"facility_type": "province"}
MONTH = (["year", "month"], ["year", "month"])
FACILITY = (["facility"], ["requesting_facility"])
REJECTION_STAR = "✱ OR of both rejection codes and an inclusive end date (Node: AND, end day excluded)"

V = "/hiv/vl"
CHECKS = [
    # Sumário
    Check("/dash_number_of_samples", {}, f"{V}/summary/number_of_samples_by_month/", {},
          *MONTH, [("total", "total")], False, None),
    Check("/dash_viral_suppression", {}, f"{V}/summary/viral_suppression_by_month/", {},
          *MONTH, [("total", "total"), ("suppressed", "suppressed")], False, None),
    Check("/dash_tat", {}, f"{V}/summary/tat_by_month/", {}, *MONTH, TAT, False, None),
    Check("/dash_map", {}, f"{V}/summary/suppression_by_province_by_month/", {},
          ["province"], ["province"], [("total", "total"), ("suppressed", "suppressed"), *REASONS], False, None),
    Check("/dash_indicators", {}, f"{V}/summary/samples_history/", {}, *MONTH,
          [(n, n) for n in ("registered", "tested", "suppressed", "rejected", "non_validated")], False, None),
    Check("/dash_tat_vs_disalinks", {}, f"{V}/summary/tat_vs_disalinks/", {},
          ["semester"], ["semester"], [("disalinks", "disalinks"), ("tat", "tat")], False, None),
    # Laboratório
    Check("/lab_weekly_report", {}, f"{V}/laboratories/weekly_report/", {},
          ["labcode", "start"], ["lab_code", "start"], WEEKLY, False, None),
    Check("/lab_weekly_report_national", {}, f"{V}/laboratories/weekly_report_national/", {},
          ["start"], ["start"], WEEKLY, False, None),
    Check("/lab_samples_tested_by_lab", {}, f"{V}/laboratories/tested_samples/", {},
          ["lab"], ["testing_facility"],
          [("total", "total"), ("suppressed", "suppressed"), ("non_suppressed", "not_suppressed")], False, None),
    Check("/lab_samples_tested_by_month", {}, f"{V}/laboratories/tested_samples_by_month/", {}, *MONTH,
          [("total", "total"), ("suppressed", "suppressed"), ("non_suppressed", "not_suppressed")], False, None),
    Check("/lab_tat", {}, f"{V}/laboratories/tat_by_lab/", {}, ["lab"], ["testing_facility"], TAT, False, None),
    Check("/lab_tat_by_month", {}, f"{V}/laboratories/tat_by_month/", {}, *MONTH, TAT, False, None),
    Check("/lab_samples_rejected", {}, f"{V}/laboratories/rejected_samples/", {},
          ["LabName"], ["testing_facility"], [("rejected", "total")], True, None),
    Check("/lab_samples_rejected_by_month", {}, f"{V}/laboratories/rejected_samples_by_month/", {}, *MONTH,
          [("rejected", "total")], False, None),
    # Província/Distrito/US
    Check("/clinic_registered_samples_by_facility", PROVINCE, f"{V}/facilities/registered_samples/", PY_PROVINCE,
          *FACILITY, [("total", "total")], False, None),
    Check("/clinic_samples_tested_by_facility", PROVINCE, f"{V}/facilities/tested_samples_by_facility/",
          PY_PROVINCE, *FACILITY,
          [("total", "total"), ("suppressed", "suppressed"), ("non_suppressed", "not_suppressed")], False, None),
    Check("/clinic_samples_tested_by_gender_and_facility", PROVINCE,
          f"{V}/facilities/tested_samples_by_gender_by_facility/", PY_PROVINCE, *FACILITY,
          [("total", "total"), *GENDER], False, None),
    Check("/clinic_samples_tested_by_gender", {"type": "province"},
          f"{V}/facilities/tested_samples_by_gender_by_month/", PY_PROVINCE, *MONTH,
          [("total", "total"), *GENDER], False, None),
    Check("/clinic_tat", {}, f"{V}/facilities/tat_by_month/", PY_PROVINCE, *MONTH, TAT, False, None),
    Check("/clinic_tat_by_facility", PROVINCE, f"{V}/facilities/tat_by_facility/", PY_PROVINCE,
          *FACILITY, TAT, False, None),
    Check("/clinic_samples_tested_by_age_and_facility", {**PROVINCE, "age": ["15", "49"]},
          f"{V}/facilities/tested_samples_by_age_by_facility/", {**PY_PROVINCE, "age_range": "15,49"},
          *FACILITY,
          [("total", "total"), ("suppressed", "suppressed"), ("non_suppressed", "not_suppressed")], True, None),
    Check("/clinic_tests_by_pregnancy", PROVINCE, f"{V}/facilities/tested_samples_pregnant_by_facility/",
          PY_PROVINCE, *FACILITY,
          [("total", "total"), ("suppressed", "suppressed"), ("non_suppressed", "not_suppressed")], False, None),
    Check("/clinic_tests_by_breastfeeding", PROVINCE, f"{V}/facilities/tested_samples_breastfeeding_by_facility/",
          PY_PROVINCE, *FACILITY,
          [("total", "total"), ("suppressed", "suppressed"), ("non_suppressed", "not_suppressed")], False, None),
    Check("/clinic_samples_by_test_reason", {"type": "province"},
          f"{V}/facilities/tested_samples_by_test_reason_by_facility/", PY_PROVINCE,
          [], [], [("total", "total"), *REASONS], True, None),
    Check("/clinic_samples_rejected_by_month", {"type": "province"},
          f"{V}/facilities/rejected_samples_by_month/", PY_PROVINCE, *MONTH,
          [("rejected", "total")], False, REJECTION_STAR),
    Check("/clinic_samples_rejected_by_facility", PROVINCE, f"{V}/facilities/rejected_samples_by_facility/",
          PY_PROVINCE, *FACILITY, [("total", "total")], False, REJECTION_STAR),
]

SKIPPED = {"/weeklyreports/instrument": "no Python endpoint (out of scope, ruling R7)"}


def default_windows(year):
    return {
        "12 months": (f"{year}-01-01", f"{year}-12-31"),
        "3 months": (f"{year}-10-01", f"{year}-12-31"),
    }


def node_query(start, end, extra):
    """Node expects qs 'indices' arrays: dates[0]=..&codes[1]=.."""
    params = [("dates[0]", start), ("dates[1]", end)]
    for name, value in extra.items():
        if isinstance(value, list):
            params.extend((f"{name}[{i}]", item) for i, item in enumerate(value))
        else:
            params.append((name, value))
    return params


def python_query(start, end, extra):
    return [("interval_dates", f"{start},{end}"), *extra.items()]


def _key_value(field, value):
    if field == "start" and isinstance(value, str):
        return value[:10]
    if isinstance(value, str):
        return value.strip()
    return value


def index_rows(rows, key_fields, value_fields, aggregate=False):
    """{key tuple: {field: value}}; with aggregate, rows sharing a key are summed."""
    index = {}
    for row in rows:
        key = tuple(_key_value(field, row.get(field)) for field in key_fields)
        values = {field: row.get(field) for field in value_fields}
        if aggregate and key in index:
            for field, value in values.items():
                index[key][field] = (index[key][field] or 0) + (value or 0)
        else:
            index[key] = values
    return index


def same_value(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= FLOAT_TOLERANCE
    return a == b


def compare(node_index, python_index, field_pairs, labels=("node", "python")):
    """Differences as text lines; ``labels`` names the two APIs (the EID check says "legacy")."""
    old, new = labels
    differences = []
    for key in sorted(set(node_index) | set(python_index), key=repr):
        if key not in python_index:
            differences.append(f"{key} missing in {new}")
            continue
        if key not in node_index:
            differences.append(f"{key} missing in {old}")
            continue
        for node_field, python_field in field_pairs:
            node_value = node_index[key].get(node_field)
            python_value = python_index[key].get(python_field)
            if not same_value(node_value, python_value):
                differences.append(f"{key} {node_field}: {old}={node_value} {new}={python_value}")
    return differences


def run_check(check, window, fetch, node_base, python_base, headers):
    start, end = window
    node_rows = fetch(node_base, check.node_path, node_query(start, end, check.node_params), {})
    python_rows = fetch(python_base, check.python_path, python_query(start, end, check.python_params), headers)
    node_fields = [pair[0] for pair in check.fields]
    python_fields = [pair[1] for pair in check.fields]
    differences = compare(
        index_rows(node_rows, check.node_keys, node_fields, aggregate=False),
        index_rows(python_rows, check.python_keys, python_fields, aggregate=check.aggregate),
        check.fields,
    )
    if not differences:
        return "OK", []
    return ("EXPECTED ✱" if check.expected else "DIFF"), differences


def http_fetch(base, path, params, headers):
    response = requests.get(base.rstrip("/") + path, params=params, headers=headers, timeout=300)
    response.raise_for_status()
    return response.json()


def read_token(path):
    with open(path, encoding="utf-8-sig") as handle:
        return handle.read().strip()


def main(argv=None, fetch=http_fetch):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--node", required=True, help="Legacy Node base URL, e.g. http://localhost:4444")
    parser.add_argument("--python", required=True, help="Python API base URL")
    parser.add_argument("--token-file", required=True, help="File holding a Python API bearer token")
    parser.add_argument("--year", type=int, default=date.today().year - 1, help="Closed year to compare")
    args = parser.parse_args(argv)

    headers = {"Authorization": f"Bearer {read_token(args.token_file)}"}
    unexpected = 0
    for label, window in default_windows(args.year).items():
        print(f"\n== {label}: {window[0]} .. {window[1]} ==")
        for check in CHECKS:
            try:
                status, differences = run_check(check, window, fetch, args.node, args.python, headers)
            except requests.RequestException as exc:
                status, differences = "ERROR", [str(exc)]
            print(f"{status:11} {check.node_path} -> {check.python_path}")
            if check.expected and differences:
                print(f"            {check.expected}")
            for line in differences[:5]:
                print(f"            {line}")
            if len(differences) > 5:
                print(f"            ... {len(differences) - 5} more")
            if status in ("DIFF", "ERROR"):
                unexpected += 1
    for path, reason in SKIPPED.items():
        print(f"SKIPPED     {path}: {reason}")
    print(f"\n{unexpected} check(s) with unexpected differences")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
