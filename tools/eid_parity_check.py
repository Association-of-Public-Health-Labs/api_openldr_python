"""
Compare the legacy EID API (openldr-api, api-ts.openldr.org.mz) with api_openldr_python on real data.

    python -m tools.eid_parity_check --legacy https://api-ts.openldr.org.mz \\
        --python https://dev.openldr.org.mz --token-file token.txt [--year 2025] [--lab PMB="Lab name"]

token.txt holds a token from POST /auth/login on the Python API (valid for 60 minutes); it is
never printed. The legacy API is public. ``--lab CODE=NAME`` adds the lab-filtered checks: the
Python API filters a lab by code, the legacy by name, so give both (the name exactly as the
legacy stores it, e.g. its TestingFacilityName / ReceivingFacilityName).

For every legacy route a dashboard card used (spec Appendix A) the script fetches one closed
year and its last quarter from both APIs, normalises the keys and compares field by field.
A difference explained by a documented ✱ (spec §4.4) is printed with its size and marked
"EXPECTED ✱"; any other difference is "DIFF". Exit code 0 means no DIFF and no ERROR.

    ✱2  the lab rejected cards now apply the lab filter (the legacy card sent the wrong parameter)
    ✱3  "Positividade das Amostras" is positive ÷ tested (legacy card: conventional ÷ total)
    ✱5  the end day of the window is included (legacy: cut at 00:00), so counts can only grow
    ✱6  summary conventional / PoC use the lab-type rule (legacy: RequestID digits)
    ✱7  results and pending read FinalResult (legacy: PCR_Result / POC_Result patterns)
    ✱8  equipment groups add the analyzer codes the legacy lists missed (C680A, M200C, ...)
"""
import argparse
import sys
from collections import namedtuple
from datetime import date

import requests

from tools.vl_parity_check import (
    compare,
    default_windows,
    http_fetch,
    index_rows,
    node_query,
    python_query,
    read_token,
    same_value,
)

LEGACY_PREFIX = "/eid"
LABELS = ("legacy", "python")
ALL = "all fields"

Check = namedtuple(
    "Check",
    "legacy_path python_path python_params legacy_keys python_keys fields "
    "legacy_params legacy_aggregate stars legacy_derive",
    defaults=(None, False, None, None),
)
Check.__doc__ = """One legacy route compared with one Python route.

legacy_path: relative to /eid. python_params: as the dashboard sends them; the legacy query is
their translation (``legacy_query``), with ``legacy_params`` merged on top (None drops a
translated parameter). fields: (legacy field, python field) pairs. legacy_aggregate: sum legacy
rows sharing a key (the legacy grouped finer). stars: {✱: python fields or ALL} beyond the
automatic ✱5 and ✱7. legacy_derive: adds computed fields to each legacy row.
"""

STARS = {
    "✱2": "the lab filter now applies to the lab rejected cards",
    "✱3": "positivity = positive ÷ tested (legacy card: conventional ÷ total)",
    "✱5": "inclusive end day (legacy cut the last day at 00:00)",
    "✱6": "conventional / PoC by the lab-type rule (legacy: RequestID digits)",
    "✱7": "results and pending from FinalResult (legacy: PCR_Result / POC_Result)",
    "✱8": "equipment groups include the analyzer codes the legacy missed",
}

# --------------------------------------------------------------------------- field maps

MONTH = (["Year", "Month"], ["year", "month"])
FACILITY = (["facility"], ["requesting_facility"])
TESTING_LAB = (["TestingFacilityName"], ["testing_facility"])

_TAT_PYTHON = [
    "collection_hub_reception", "hub_reception_hub_registration", "hub_registration_lab_reception",
    "lab_reception_lab_registration", "lab_registration_analysis", "analysis_validation",
]
TAT = list(zip([
    "collection_to_hub_reception", "hub_reception_to_hub_registration", "hub_registration_to_lab_reception",
    "lab_reception_to_registration", "lab_registration_to_analysis", "lab_analysis_to_validation",
], _TAT_PYTHON))
TAT_CLINIC = list(zip([
    "Colheita na US a Recepção no Hub", "Recepção ao Registo no Hub", "Registo no Hub a Recepção no Lab",
    "Recepção no Lab ao Registo no Lab", "Registo no Lab à Análise no Lab", "Análise no Lab à Validação no Lab",
], _TAT_PYTHON))
BRACKETS = [("<7", "lt_7"), ("7-15", "between_7_15"), ("16-21", "between_16_21"), (">21", "gt_21"),
            ("no_dates", "no_dates")]
REJECTION_LEGACY = list(zip([
    "Repetir Teste", "Amostra Insuficiente", "Requisição Sem Amostra", "Problemas Técnicos",
    "Sangue Sobreposto", "Registo Duplicado", "Amostra Mal Identificada", "Amostra com +30 dias de Colheita",
], [
    "repeat_test", "insufficient_sample", "request_without_sample", "technical_problems",
    "overlapping_blood", "duplicate_registration", "misidentified_sample", "sample_over_30_days",
]))
REJECTION = REJECTION_LEGACY + [("Outros Motivos", "other")]
EQUIPMENT = [(name, name) for name in ("CAPCTM", "ALINITY", "M2000", "C6800", "PANTHER", "MPIMA", "MANUAL")]
GENDER = [("Masculino Positivo", "male_positive"), ("Masculino Negativo", "male_negative"),
          ("Feminino Positivo", "female_positive"), ("Feminino Negativo", "female_negative")]
INDICATORS = [("Registados", "registered"), ("Testados", "tested"), ("Rejeitados", "rejected"),
              ("Pendentes", "pending")]
KEY_INDICATORS = [("Registadas", "registered"), ("Testadas", "tested"), ("Rejeitadas", "rejected"),
                  ("Pendentes", "pending"), ("Positividade", "positive")]
REGISTERED = [("Total", "total"), ("Conventional", "conventional"), ("Poc", "poc")]

# Python fields that are averages or percentages: the inclusive end day (✱5) can move them
# either way. Every other field is a count, which ✱5 can only increase.
NON_COUNT_FIELDS = set(_TAT_PYTHON) | {"positivity"}
# ✱7 applies to every field that reads a result.
RESULT_WORDS = ("positive", "negative", "indeterminate", "pending", "positivity")

PY_FACILITY = {"facility_type": "province", "disaggregation": "false"}
EQUIPMENT_STAR = {"✱8": [python for _, python in EQUIPMENT]}


def _legacy_card_positivity(row):
    """The legacy card's line: conventional positives ÷ total (✱3)."""
    total = row.get("Total") or 0
    return {**row, "positivity": round(100.0 * (row.get("Conventional") or 0) / total, 1) if total else 0}


S, L, F = "/hiv/eid/summary", "/hiv/eid/laboratories", "/hiv/eid/facilities"
CHECKS = [
    # Sumário
    Check("/dash/pcr/indicators", f"{S}/indicators/", {"lab_type": "conventional"}, *MONTH, INDICATORS,
          stars={"✱6": ALL}),
    Check("/dash/poc/indicators", f"{S}/indicators/", {"lab_type": "poc"}, *MONTH, INDICATORS,
          stars={"✱6": ALL}),
    Check("/dash/samples_positivity", f"{S}/positivity/", {}, *MONTH,
          [("Total", "tested"), ("Conventional", "conventional_positive"), ("Poc", "poc_positive"),
           ("positivity", "positivity")],
          stars={"✱3": ["positivity"]}, legacy_derive=_legacy_card_positivity),
    Check("/dash/indicators_by_province", f"{S}/indicators_by_province/", {},
          ["RequestingProvinceName"], ["province"],
          INDICATORS + [("Conventional", "conventional"), ("Poc", "poc"), ("Positivity", "positive")]),
    Check("/dash/pcr/tat", f"{S}/tat/", {}, *MONTH, TAT),
    Check("/dash/pcr/tat_samples", f"{S}/tat_samples/", {"category": "0"}, *MONTH, BRACKETS),
    Check("/dash/rejected_samples_monthly", f"{S}/rejected_samples_by_month/", {}, *MONTH, REJECTION),
    Check("/dash/samples_by_equipment_monthly", f"{S}/samples_by_equipment_by_month/", {}, *MONTH,
          [("Tested", "tested"), *EQUIPMENT], stars=EQUIPMENT_STAR),
    # Laboratório
    Check("/lab/conventional/samples_tested", f"{L}/tested_samples/", {"lab_type": "conventional"},
          *TESTING_LAB, [("Total", "total"), ("Positivity", "positive")]),
    # The legacy PoC card opens per province (ruling R18): Python lab_type=poc&facility_type=province.
    Check("/lab/poc/samples_tested", f"{L}/tested_samples/", {"lab_type": "poc", "facility_type": "province"},
          ["RequestingProvinceName"], ["requesting_facility"], [("Total", "total"), ("Positivity", "positive")],
          legacy_params={"facilityType": None}),
    Check("/lab/all/samples_tested_by_month", f"{L}/tested_samples_by_month/", {}, *MONTH,
          [("Total", "total"), ("Positivity", "positive")]),
    Check("/lab/tat_samples", f"{L}/tat_samples/", {"category": "0"}, *TESTING_LAB, BRACKETS),
    Check("/lab/conventional/tat", f"{L}/tat/", {}, *TESTING_LAB, TAT),
    Check("/lab/all/samples_registered_by_month", f"{L}/registered_samples_by_month/", {}, *MONTH, REGISTERED),
    Check("/lab/samples_by_equipment_monthly", f"{L}/samples_by_equipment_by_month/", {}, *MONTH,
          [("Tested", "tested"), *EQUIPMENT], stars=EQUIPMENT_STAR),
    Check("/lab/samples_by_equipment", f"{L}/samples_by_equipment/", {}, *TESTING_LAB,
          [("Tested", "tested"), *EQUIPMENT], stars=EQUIPMENT_STAR),
    Check("/lab/rejected_samples_monthly", f"{L}/rejected_samples_by_month/", {}, *MONTH, REJECTION),
    Check("/lab/rejected_samples", f"{L}/rejected_samples/", {},
          ["ReceivingFacilityName"], ["receiving_facility"], REJECTION),
    # Província/Distrito/US
    Check("/clinic/samples_registered_province", f"{F}/registered_samples/", PY_FACILITY, *FACILITY,
          [("Conventional", "conventional"), ("Poc", "poc"), ("total", "total")]),
    Check("/clinic/samples_registered_month", f"{F}/registered_samples_by_month/", PY_FACILITY, *MONTH,
          [("Conventional", "conventional"), ("Poc", "poc"), ("total", "total")]),
    Check("/clinic/samples_tested_province", f"{F}/tested_samples/", PY_FACILITY, *FACILITY,
          [("Convencional", "conventional"), ("Poc", "poc"), ("total", "total")]),
    Check("/clinic/samples_tested_month", f"{F}/tested_samples_by_month/", PY_FACILITY, *MONTH,
          [("Convencional", "conventional"), ("Poc", "poc"), ("total", "total")]),
    Check("/clinic/samples_rejected_by_facility", f"{F}/rejected_samples/", PY_FACILITY, *FACILITY,
          REJECTION_LEGACY + [("Outros", "other"), ("Total", "total")]),
    Check("/clinic/samples_rejected_by_month", f"{F}/rejected_samples_by_month/", PY_FACILITY, *MONTH,
          REJECTION + [("Total", "total")]),
    Check("/clinic/samples_tested_gender_province", f"{F}/tested_samples_by_gender/", PY_FACILITY, *FACILITY,
          GENDER),
    Check("/clinic/samples_tested_gender_month", f"{F}/tested_samples_by_gender_by_month/", PY_FACILITY,
          *MONTH, GENDER),
    Check("/clinic/samples_tat_avg_province", f"{F}/tat_avg/", PY_FACILITY, *FACILITY, TAT_CLINIC),
    Check("/clinic/samples_tat_avg_month", f"{F}/tat_avg_by_month/", PY_FACILITY, *MONTH, TAT_CLINIC),
    Check("/clinic/samples_tat_days_province", f"{F}/tat_days/", PY_FACILITY, *FACILITY, BRACKETS),
    Check("/clinic/samples_tat_days_month", f"{F}/tat_days_by_month/", PY_FACILITY, *MONTH, BRACKETS),
    # The legacy grouped key indicators by province, district and facility: summed per province.
    Check("/clinic/conventional/key_indicators", f"{F}/key_indicators/", {**PY_FACILITY, "lab_type": "conventional"},
          ["RequestingProvinceName"], ["requesting_facility"], KEY_INDICATORS, legacy_aggregate=True),
    Check("/clinic/poc/key_indicators", f"{F}/key_indicators/", {**PY_FACILITY, "lab_type": "poc"},
          ["RequestingProvinceName"], ["requesting_facility"], KEY_INDICATORS, legacy_aggregate=True),
]


def lab_checks(lab_code):
    """Checks filtered by one lab (``--lab CODE=NAME``): the lab rejected cards (✱2) and the
    monthly tested / registered cards, which filter the testing / receiving lab."""
    lab = {"lab_code": [lab_code]}
    return [
        Check("/lab/rejected_samples", f"{L}/rejected_samples/", lab,
              ["ReceivingFacilityName"], ["receiving_facility"], REJECTION, stars={"✱2": ALL}),
        Check("/lab/rejected_samples_monthly", f"{L}/rejected_samples_by_month/", lab, *MONTH, REJECTION,
              stars={"✱2": ALL}),
        Check("/lab/all/samples_tested_by_month", f"{L}/tested_samples_by_month/", lab, *MONTH,
              [("Total", "total"), ("Positivity", "positive")]),
        Check("/lab/all/samples_registered_by_month", f"{L}/registered_samples_by_month/", lab, *MONTH,
              REGISTERED),
    ]


_NO_CARD = "no dashboard card uses it (spec Appendix A)"
SKIPPED = {
    "/dash/pcr/positivity": _NO_CARD,
    "/dash/poc/positivity": _NO_CARD,
    "/dash/pcr/number_of_samples": _NO_CARD,
    "/dash/poc/number_of_samples": _NO_CARD,
    "/dash/samples_by_equipment": _NO_CARD,
    "/lab/conventional/samples_tested_by_month": _NO_CARD,
    "/lab/poc/samples_tested_by_month": _NO_CARD,
    "/lab/poc/tat": _NO_CARD,
    "/lab/sample_routes": _NO_CARD,
    "/lab/sample_routes_viewport": _NO_CARD,
}

# --------------------------------------------------------------------------- parameters

_LOCATION_PARAMS = ("province", "district", "health_facility")
_PASS_THROUGH = ("category", "disaggregation")


def translate_params(params, lab_names=None):
    """Python query parameters -> the legacy ones (lists stay lists)."""
    lab_names = lab_names or {}
    legacy = {}
    for name, value in params.items():
        values = value if isinstance(value, list) else [value]
        if name == "lab_code":
            legacy["labCodes"] = [lab_names.get(code, code) for code in values]
        elif name == "facility_type":
            legacy["facilityType"] = "clinic" if values[0] == "health_facility" else values[0]
        elif name in _LOCATION_PARAMS:
            legacy.setdefault("facilityCodes", []).extend(values)
        elif name in _PASS_THROUGH:
            legacy[name] = values[0]
        elif name == "lab_type":
            continue  # the legacy route variant (conventional/poc path) or an explicit legacy param
        else:
            raise ValueError(f"no legacy translation for parameter {name!r}")
    return legacy


def legacy_query(start, end, params, extra=None, lab_names=None):
    """The legacy query: ``dates[0]``/``dates[1]`` and the translated parameters (qs indices)."""
    legacy = translate_params(params, lab_names)
    legacy.update(extra or {})
    return node_query(start, end, {name: value for name, value in legacy.items() if value is not None})


# --------------------------------------------------------------------------- comparison


def _rows(data):
    """The list of rows of a response (the legacy TAT bracket routes wrap it in ``report``)."""
    if isinstance(data, dict) and isinstance(data.get("report"), list):
        data = data["report"]
    if not isinstance(data, list):
        raise ValueError(f"expected a list of rows, got {type(data).__name__}")
    return data


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _marks(check, field, legacy_value, python_value):
    """The expected ✱ that explain one field difference (empty: unexpected)."""
    marks = []
    if field in NON_COUNT_FIELDS or (
        _is_number(legacy_value) and _is_number(python_value) and python_value >= legacy_value
    ):
        marks.append("✱5")
    if any(word in field for word in RESULT_WORDS):
        marks.append("✱7")
    for mark, fields in (check.stars or {}).items():
        if fields == ALL or field in fields:
            marks.append(mark)
    return sorted(set(marks), key=lambda m: int(m[1:]))


def _number(value):
    return value if _is_number(value) else 0


def _shift(legacy_total, python_total):
    delta = python_total - legacy_total
    percent = f", {100.0 * delta / legacy_total:+.1f}%" if legacy_total else ""
    delta_text = f"{delta:+.1f}" if isinstance(delta, float) else f"{delta:+d}"
    return f"{delta_text}{percent}"


def field_summaries(check, legacy_index, python_index):
    """Per differing field: (expected?, summary line), over the rows both APIs returned."""
    summaries = []
    common = [key for key in legacy_index if key in python_index]
    for legacy_field, python_field in check.fields:
        rows = [(legacy_index[k].get(legacy_field), python_index[k].get(python_field)) for k in common]
        differing = [(a, b) for a, b in rows if not same_value(a, b)]
        if not differing:
            continue
        per_row = [_marks(check, python_field, a, b) for a, b in differing]
        expected = all(per_row)
        label = " ".join(sorted({m for marks in per_row for m in marks}, key=lambda m: int(m[1:])))
        legacy_total = sum(_number(a) for a, _ in rows)
        python_total = sum(_number(b) for _, b in rows)
        if python_field in NON_COUNT_FIELDS:
            legacy_total, python_total = (round(t / len(rows), 1) for t in (legacy_total, python_total))
            scope = f"average over {len(rows)} row(s), {len(differing)} differ"
        else:
            scope = f"in {len(differing)} row(s)"
        summaries.append((expected, (
            f"{label if expected else 'UNEXPECTED'} {python_field}: legacy {legacy_total} -> python "
            f"{python_total} ({_shift(legacy_total, python_total)}) {scope}"
        )))
    return summaries


def run_check(check, window, fetch, legacy_base, python_base, headers, lab_names=None):
    """(status, lines): status OK, "EXPECTED ✱" or DIFF; lines = field summaries, then row details."""
    start, end = window
    legacy_rows = _rows(fetch(
        legacy_base, LEGACY_PREFIX + check.legacy_path,
        legacy_query(start, end, check.python_params, check.legacy_params, lab_names), {},
    ))
    python_rows = _rows(fetch(python_base, check.python_path, python_query(start, end, check.python_params), headers))
    if check.legacy_derive:
        legacy_rows = [check.legacy_derive(row) for row in legacy_rows]

    legacy_index = index_rows(legacy_rows, check.legacy_keys, [f for f, _ in check.fields],
                              aggregate=check.legacy_aggregate)
    python_index = index_rows(python_rows, check.python_keys, [f for _, f in check.fields])
    missing = compare(legacy_index, python_index, [], labels=LABELS)
    # A row only in Python can come from the included end day (✱5); a row Python lost cannot.
    unexpected_rows = [line for line in missing if line.endswith(f"missing in {LABELS[1]}")]
    summaries = field_summaries(check, legacy_index, python_index)
    details = compare(legacy_index, python_index, check.fields, labels=LABELS)
    if not details:
        return "OK", []
    lines = [line for _, line in summaries] + [
        f"{line} (✱5)" if line in missing and line not in unexpected_rows else line for line in details
    ]
    if unexpected_rows or not all(expected for expected, _ in summaries):
        return "DIFF", lines
    return "EXPECTED ✱", lines


# --------------------------------------------------------------------------- main


def _lab_names(values):
    names = {}
    for value in values or []:
        code, sep, name = value.partition("=")
        if not sep or not code.strip() or not name.strip():
            raise argparse.ArgumentTypeError(f"--lab expects CODE=NAME, got {value!r}")
        names[code.strip()] = name.strip()
    return names


def main(argv=None, fetch=http_fetch):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legacy", required=True, help="Legacy EID API base URL, e.g. https://api-ts.openldr.org.mz")
    parser.add_argument("--python", required=True, help="Python API base URL, e.g. https://dev.openldr.org.mz")
    parser.add_argument("--token-file", required=True, help="File holding a Python API bearer token")
    parser.add_argument("--year", type=int, default=date.today().year - 1, help="Closed year to compare")
    parser.add_argument("--lab", action="append", metavar="CODE=NAME",
                        help="Also run the lab-filtered checks for this lab (code for Python, name for legacy)")
    args = parser.parse_args(argv)
    try:
        lab_names = _lab_names(args.lab)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    checks = CHECKS + [check for code in lab_names for check in lab_checks(code)]
    headers = {"Authorization": f"Bearer {read_token(args.token_file)}"}
    unexpected = 0
    for label, window in default_windows(args.year).items():
        print(f"\n== {label}: {window[0]} .. {window[1]} ==")
        for check in checks:
            try:
                status, lines = run_check(check, window, fetch, args.legacy, args.python, headers, lab_names)
            except (requests.RequestException, ValueError) as exc:
                status, lines = "ERROR", [str(exc)]
            params = "&".join(
                f"{k}={','.join(v) if isinstance(v, list) else v}" for k, v in check.python_params.items()
            )
            print(f"{status:11} {LEGACY_PREFIX}{check.legacy_path} -> {check.python_path}{'?' + params if params else ''}")
            # Field summaries first (all of them), then the first rows that differ.
            summaries = [line for line in lines if not line.startswith("(")]
            details = [line for line in lines if line.startswith("(")]
            for line in summaries + details[:5]:
                print(f"            {line}")
            if len(details) > 5:
                print(f"            ... {len(details) - 5} more")
            if status in ("DIFF", "ERROR"):
                unexpected += 1
    for path, reason in SKIPPED.items():
        print(f"SKIPPED     {LEGACY_PREFIX}{path}: {reason}")
    print("\nExpected differences (spec §4.4):")
    for mark, note in STARS.items():
        print(f"  {mark} {note}")
    print(f"\n{unexpected} check(s) with unexpected differences")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
