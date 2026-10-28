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
"EXPECTED ✱"; any other difference is "DIFF". Exit code 0 means no DIFF, no ERROR and no EMPTY (both APIs returned no rows: nothing
was compared; ``--allow-empty`` tolerates it). Every check prints its row count per side.

✱5 (the Python window includes its end day; the legacy BETWEEN cut it at 00:00) is not a tag:
the legacy request asks for the end date + 1 day (ruling R21), so both sides cover the same whole
days. The legacy side then also counts rows stamped exactly at 00:00:00 of the following day;
such a residual difference shows as DIFF and must be read by a human (it is small and sits in the
last month / every per-place row).

    ✱3  "Positividade das Amostras" is positive ÷ tested (legacy card: conventional ÷ total)
    ✱6  summary conventional / PoC use the lab-type rule (legacy: RequestID digits)
    ✱7  results and pending read FinalResult (legacy: PCR_Result / POC_Result patterns)
    ✱8  equipment groups add the analyzer codes the legacy lists missed (C680A, M200C, ...)
"""
import argparse
import sys
from collections import namedtuple
from datetime import date, timedelta

import requests

from tools.vl_parity_check import (
    _key_value,
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
    "legacy_params legacy_aggregate stars legacy_derive legacy_extra_paths legacy_lab_type_param python_rows",
    defaults=(None, False, None, None, (), None, None),
)
Check.__doc__ = """One legacy route compared with one Python route.

legacy_path: relative to /eid. python_params: as the dashboard sends them; the legacy query is
their translation (``legacy_query``), with ``legacy_params`` merged on top (None drops a
translated parameter). fields: (legacy field, python field) pairs. legacy_aggregate: sum legacy
rows sharing a key (the legacy grouped finer). stars: {✱: python fields or ALL} beyond the
automatic ✱7. legacy_derive: adds computed fields to each legacy row. legacy_extra_paths: more
legacy routes whose rows are added to legacy_path's (with legacy_aggregate, summed per key).
legacy_lab_type_param: the legacy query parameter that carries ``lab_type`` (the /lab/all/*
routes take ``labType``); without it ``lab_type`` must be the legacy route variant (a
conventional/poc path segment).
python_rows: how to read Python rows sharing a key (lab rows split by lab code when one name has
two codes): "sum" adds them per key (counts); "unique" keeps none silently, a repeated key is
reported as a ``DUPLICATE NAME`` line and the check is a DIFF (averages cannot be added).
"""

STARS = {
    "✱3": "positivity = positive ÷ tested (legacy card: conventional ÷ total)",
    "✱5": "inclusive end day: not a tag, the legacy is asked for end + 1 day (R21)",
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

# Python fields that are averages or percentages: summarised as means, not sums.
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
    # KPI tiles: Python with no lab_type = the legacy pcr + poc responses summed per month. The two
    # legacy RequestID-digit predicates (isnumeric(...) = 0 / = 1) split every row, so the sums do
    # not depend on ✱6. Rejected is compared too: the legacy pcr (pos_rejected) and poc
    # (pre_rejected) rules are the same SQL (code or description non-empty), as Python's rule.
    Check("/dash/pcr/indicators", f"{S}/indicators/", {}, *MONTH, INDICATORS,
          legacy_aggregate=True, legacy_extra_paths=("/dash/poc/indicators",)),
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
          *TESTING_LAB, [("Total", "total"), ("Positivity", "positive")],
          python_rows="sum"),
    # The legacy PoC card opens per province (ruling R18): Python lab_type=poc&facility_type=province.
    Check("/lab/poc/samples_tested", f"{L}/tested_samples/", {"lab_type": "poc", "facility_type": "province"},
          ["RequestingProvinceName"], ["requesting_facility"], [("Total", "total"), ("Positivity", "positive")],
          legacy_params={"facilityType": None}),
    *[Check("/lab/all/samples_tested_by_month", f"{L}/tested_samples_by_month/", params, *MONTH,
            [("Total", "total"), ("Positivity", "positive")], legacy_lab_type_param="labType")
      for params in ({}, {"lab_type": "conventional"}, {"lab_type": "poc"})],
    Check("/lab/tat_samples", f"{L}/tat_samples/", {"category": "0"}, *TESTING_LAB, BRACKETS,
          python_rows="sum"),
    Check("/lab/conventional/tat", f"{L}/tat/", {}, *TESTING_LAB, TAT, python_rows="unique"),
    *[Check("/lab/all/samples_registered_by_month", f"{L}/registered_samples_by_month/", params, *MONTH,
            REGISTERED, legacy_lab_type_param="labType")
      for params in ({}, {"lab_type": "conventional"}, {"lab_type": "poc"})],
    Check("/lab/samples_by_equipment_monthly", f"{L}/samples_by_equipment_by_month/", {}, *MONTH,
          [("Tested", "tested"), *EQUIPMENT], stars=EQUIPMENT_STAR),
    Check("/lab/samples_by_equipment", f"{L}/samples_by_equipment/", {}, *TESTING_LAB,
          [("Tested", "tested"), *EQUIPMENT], stars=EQUIPMENT_STAR,
          python_rows="sum"),
    Check("/lab/rejected_samples_monthly", f"{L}/rejected_samples_by_month/", {}, *MONTH, REJECTION),
    Check("/lab/rejected_samples", f"{L}/rejected_samples/", {},
          ["ReceivingFacilityName"], ["receiving_facility"], REJECTION, python_rows="sum"),
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
    """Checks filtered by one lab (``--lab CODE=NAME``): the lab rejected cards and the monthly
    tested / registered cards, which filter the receiving / testing lab.

    No ✱2 here (ruling R23): ✱2 was a legacy *card* bug (it sent ``facilities``); the legacy route
    filters correctly given ``labCodes`` (by lab name), so these must match exactly.
    """
    lab = {"lab_code": [lab_code]}
    return [
        Check("/lab/rejected_samples", f"{L}/rejected_samples/", lab,
              ["ReceivingFacilityName"], ["receiving_facility"], REJECTION),
        Check("/lab/rejected_samples_monthly", f"{L}/rejected_samples_by_month/", lab, *MONTH, REJECTION),
        Check("/lab/all/samples_tested_by_month", f"{L}/tested_samples_by_month/", lab, *MONTH,
              [("Total", "total"), ("Positivity", "positive")], legacy_lab_type_param="labType"),
        Check("/lab/all/samples_registered_by_month", f"{L}/registered_samples_by_month/", lab, *MONTH,
              REGISTERED, legacy_lab_type_param="labType"),
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


def translate_params(params, lab_names=None, lab_type_param=None):
    """Python query parameters -> the legacy ones (lists stay lists).

    ``lab_type`` goes to ``lab_type_param`` when the legacy route takes one (``all`` = not sent);
    otherwise the legacy route variant carries it.
    """
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
            if lab_type_param and values[0] != "all":
                legacy[lab_type_param] = values[0]
        else:
            raise ValueError(f"no legacy translation for parameter {name!r}")
    return legacy


def legacy_query(start, end, params, extra=None, lab_names=None, lab_type_param=None):
    """The legacy query: ``dates[0]``/``dates[1]`` and the translated parameters (qs indices)."""
    legacy = translate_params(params, lab_names, lab_type_param)
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


def _marks(check, field):
    """The expected ✱ that may explain a difference in ``field`` (empty: none)."""
    marks = []
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
        # A ✱ explains a value shift only: a field missing (or not a number) on either side is
        # never expected, whatever ✱ the field carries.
        per_row = [_marks(check, python_field) if _is_number(a) and _is_number(b) else []
                   for a, b in differing]
        expected = all(per_row)
        absent = sum(1 for a, b in differing if not (_is_number(a) and _is_number(b)))
        label = " ".join(sorted({m for marks in per_row for m in marks}, key=lambda m: int(m[1:])))
        legacy_total = sum(_number(a) for a, _ in rows)
        python_total = sum(_number(b) for _, b in rows)
        if python_field in NON_COUNT_FIELDS:
            legacy_total, python_total = (round(t / len(rows), 1) for t in (legacy_total, python_total))
            scope = f"average over {len(rows)} row(s), {len(differing)} differ"
        else:
            scope = f"in {len(differing)} row(s)"
        if absent:
            scope += f", {absent} with the field missing"
        summaries.append((expected, (
            f"{label if expected else 'UNEXPECTED'} {python_field}: legacy {legacy_total} -> python "
            f"{python_total} ({_shift(legacy_total, python_total)}) {scope}"
        )))
    return summaries


def legacy_end(end):
    """The legacy end date: ``end`` + 1 day, so its BETWEEN covers the whole end day (R21)."""
    return (date.fromisoformat(end) + timedelta(days=1)).isoformat()


_MONTH_KEYS = ("Year", "Month", "year", "month")


def _int_month_keys(rows, keys):
    """Year / month as int on both sides ("2025" and 2025 are the same row)."""
    month_keys = [k for k in keys if k in _MONTH_KEYS]
    if not month_keys:
        return rows
    out = []
    for row in rows:
        row = dict(row)
        for key in month_keys:
            value = row.get(key)
            if isinstance(value, str) and value.strip().isdigit():
                row[key] = int(value.strip())
        out.append(row)
    return out


def _within_window(rows, keys, end):
    """Drop legacy month rows after the window's end month: the extra day asked for (R21) can only
    add rows stamped at 00:00 of the next day, which would form a month Python never has."""
    if keys[:2] != ["Year", "Month"]:
        return rows
    last = date.fromisoformat(end)
    return [row for row in rows
            if not (_is_number(row.get("Year")) and _is_number(row.get("Month"))
                    and (row["Year"], row["Month"]) > (last.year, last.month))]


def run_check(check, window, fetch, legacy_base, python_base, headers, lab_names=None, counts=None):
    """(status, lines): status OK, "EXPECTED ✱", DIFF or EMPTY; lines = field summaries, then row details.

    EMPTY: neither API returned a row, so nothing was compared (a vacuous OK would hide a wrong
    window, lab or token). ``counts``, when given, receives the row count of each side.
    """
    start, end = window
    query = legacy_query(start, legacy_end(end), check.python_params, check.legacy_params, lab_names,
                         check.legacy_lab_type_param)
    legacy_rows = []
    for path in (check.legacy_path, *check.legacy_extra_paths):
        legacy_rows += _rows(fetch(legacy_base, LEGACY_PREFIX + path, query, {}))
    legacy_rows = _within_window(_int_month_keys(legacy_rows, check.legacy_keys), check.legacy_keys, end)
    python_rows = _int_month_keys(
        _rows(fetch(python_base, check.python_path, python_query(start, end, check.python_params), headers)),
        check.python_keys,
    )
    if check.legacy_derive:
        legacy_rows = [check.legacy_derive(row) for row in legacy_rows]
    if counts is not None:
        counts.update(legacy=len(legacy_rows), python=len(python_rows))
    if not legacy_rows and not python_rows:
        return "EMPTY", ["both APIs returned 0 rows: nothing was compared"]

    legacy_index = index_rows(legacy_rows, check.legacy_keys, [f for f, _ in check.fields],
                              aggregate=check.legacy_aggregate)
    python_index = index_rows(python_rows, check.python_keys, [f for _, f in check.fields],
                              aggregate=check.python_rows == "sum")
    # A row only one side has is never explained by a ✱.
    missing = compare(legacy_index, python_index, [], labels=LABELS)
    if check.python_rows == "unique":
        missing += _duplicate_names(python_rows, check.python_keys)
    summaries = field_summaries(check, legacy_index, python_index)
    details = compare(legacy_index, python_index, check.fields, labels=LABELS)
    if not details and not missing:
        return "OK", []
    lines = [line for _, line in summaries] + details + [m for m in missing if m not in details]
    if missing or not all(expected for expected, _ in summaries):
        return "DIFF", lines
    return "EXPECTED ✱", lines


def _duplicate_names(rows, key_fields):
    """``DUPLICATE NAME`` lines for Python rows sharing a key (a name under two lab codes)."""
    counts = {}
    for row in rows:
        key = tuple(_key_value(field, row.get(field)) for field in key_fields)
        counts[key] = counts.get(key, 0) + 1
    return [f"{key} DUPLICATE NAME: {n} python rows share it (one name, several codes)"
            for key, n in sorted(counts.items(), key=repr) if n > 1]


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
    parser.add_argument("--allow-empty", action="store_true",
                        help="Do not fail a check for which both APIs return no rows (still printed as EMPTY)")
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
        print(f"\n== {label}: {window[0]} .. {window[1]} (legacy asked to {legacy_end(window[1])}) ==")
        for check in checks:
            counts = {}
            try:
                status, lines = run_check(check, window, fetch, args.legacy, args.python, headers, lab_names,
                                          counts)
            except (requests.RequestException, ValueError) as exc:
                status, lines = "ERROR", [str(exc)]
            params = "&".join(
                f"{k}={','.join(v) if isinstance(v, list) else v}" for k, v in check.python_params.items()
            )
            legacy = " + ".join(LEGACY_PREFIX + path for path in (check.legacy_path, *check.legacy_extra_paths))
            print(f"{status:11} {legacy} -> {check.python_path}{'?' + params if params else ''}")
            if counts:
                print(f"            legacy {counts['legacy']} rows, python {counts['python']} rows")
            # Field summaries first (all of them), then the first rows that differ.
            summaries = [line for line in lines if not line.startswith("(")]
            details = [line for line in lines if line.startswith("(")]
            for line in summaries + details[:5]:
                print(f"            {line}")
            if len(details) > 5:
                print(f"            ... {len(details) - 5} more")
            if status in ("DIFF", "ERROR") or (status == "EMPTY" and not args.allow_empty):
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
