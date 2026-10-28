"""
HIV EID laboratory (Laboratório) services.

Each card function reproduces the legacy openldr-api LaboratoryController
route named in its docstring (src/modules/eid/controllers/
LaboratoryController.ts): same date column, same exclusions. The counting
rules come from hiv/eid/services/eid_common.py. Differences from the legacy
are the spec's ✱ fixes only (docs/superpowers/specs/
2026-10-26-eid-dashboard-migration-design.md §4.4):

- ✱2: the rejection routes apply the lab filter (the legacy card sent the
  wrong parameter, so it was ignored).
- ✱4/✱7: every result count reads FinalResult (the legacy read PCR_Result,
  also for PoC).
- ✱5: every date window includes its end day.
- ✱8: equipment groups add the analyzer codes the legacy missed (C680A ->
  C6800, M200C -> M2000, PNTHC -> PANTHER, ALNTB -> ALINITY), compared
  trimmed; equipment counts are expected to be higher than the legacy.

Lab-level rows also carry the lab code (plan 2c, L2): ``testing_facility_code``
on tested_samples, tat, tat_samples and samples_by_equipment,
``receiving_facility_code`` on rejected_samples. They group by code + name, so
a name used under two codes gives one row per code. Existing keys and the
order by name are unchanged.

``lab_code`` filters ``TestingFacilityCode`` (the legacy filtered the lab
name), except on the routes that group by the receiving lab (registered and
rejected), where it filters ``ReceivingFacilityCode``. The legacy lab routes
had no location filter and no null-province exclusion; the location filters
apply only when given.
"""
from sqlalchemy import and_, case, func, literal_column, or_, text

from hiv.eid.models.eid_master_model import EIDMaster
from hiv.eid.services.eid_common import (
    EQUIPMENT_GROUPS,
    REJECTION_REASONS,
    TAT_SEGMENTS,
    conventional_condition,
    date_between_inclusive,
    equipment_counts,
    equipment_filters,
    group_column,
    location_filters,
    parse_eid_params,
    poc_condition,
    rejected_condition,
    rejection_reason_counts,
    result_count,
    tat_averages,
    tat_bracket_counts,
    tat_filters,
)
from utilities.utils import LAB_TYPE_EID, PROCESS_COMMON_PARAMS_VL, TOTAL_ALL

_REJECTION_KEYS = [key for key, _ in REJECTION_REASONS] + ["other"]
_EQUIPMENT_KEYS = [key for key, _ in EQUIPMENT_GROUPS]
_TAT_KEYS = [key for key, _, _ in TAT_SEGMENTS]
_BRACKET_KEYS = ["lt_7", "between_7_15", "between_16_21", "gt_21", "no_dates"]

# Drill levels of the by-level lab routes, from the column group_column picks.
_LEVEL_BY_COLUMN = {
    "TestingFacilityName": "lab",
    "RequestingProvinceName": "province",
    "RequestingDistrictName": "district",
    "RequestingFacilityName": "health_facility",
}
# The legacy lab TAT drill also grouped by (and returned) every level above.
_TAT_PARENT_COLUMNS = {
    "lab": [],
    "province": [],
    "district": [("province", EIDMaster.RequestingProvinceName)],
    "health_facility": [
        ("province", EIDMaster.RequestingProvinceName),
        ("district", EIDMaster.RequestingDistrictName),
    ],
}


def _error(e):
    return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


def _count(condition, label):
    return func.count(case((condition, 1), else_=None)).label(label)


def _total(label):
    return func.count(literal_column("1")).label(label)


def _month_columns(column):
    return [
        func.year(column).label("year"),
        func.month(column).label("month"),
        func.datename(text("month"), column).label("month_name"),
    ]


def _monthly(query, month_cols):
    return query.group_by(*month_cols).order_by(month_cols[0], month_cols[1]).all()


def _month_keys(row):
    return dict(year=row.year, month=row.month, month_name=row.month_name)


def _base_filters(params, date_column, lab_code_column=EIDMaster.TestingFacilityCode):
    """Inclusive window (✱5), optional location filter and ``lab_code``."""
    filters = [date_between_inclusive(date_column, params.dates)]
    filters += location_filters(params, exclude_null_province=False)
    if params.lab_codes:
        filters.append(lab_code_column.in_(params.lab_codes))
    return filters


def _not_rejected():
    """Legacy lab routes: ``LIMSRejectionCode`` NULL or ''."""
    return or_(EIDMaster.LIMSRejectionCode.is_(None), EIDMaster.LIMSRejectionCode == "")


def _is_poc_condition(lab_type):
    """``IsPoc`` alone, as the legacy lab/all routes split on ``labType``."""
    if lab_type == "conventional":
        return EIDMaster.IsPoc == "No"
    if lab_type == "poc":
        return EIDMaster.IsPoc == "Yes"
    return None


def _lab_level(params):
    """(group column, level name) of a by-level lab route."""
    column = group_column(params, "lab")
    return column, _LEVEL_BY_COLUMN[column.key]


def _group_key(level):
    return "testing_facility" if level == "lab" else "requesting_facility"


# ---------------------------------------------------------------------------
# 0. laboratories/labs/   (new, plan 2c L1)
# ---------------------------------------------------------------------------
def laboratory_labs_service(req_args):
    """The EID labs and PoC sites with a testing lab code: code, name, lab_type.

    Distinct ``TestingFacilityCode`` / ``TestingFacilityName`` with a code,
    per lab type: ``conventional`` (the conventional rule) and ``poc`` (the
    PoC rule). A code seen under both appears once per type. Sorted by name,
    then lab type. No date window, no other filter.
    """
    parse_eid_params(req_args)
    code, name = EIDMaster.TestingFacilityCode, EIDMaster.TestingFacilityName
    try:
        labs = []
        for lab_type, condition in (
            ("conventional", conventional_condition()),
            ("poc", poc_condition()),
        ):
            rows = (
                EIDMaster.query.with_entities(code.label("code"), name.label("name"))
                .filter(and_(code.is_not(None), condition))
                .distinct()
                .order_by(name)
                .all()
            )
            labs += [dict(code=row.code, name=row.name, lab_type=lab_type) for row in rows]
        # Stable sort: conventional stays before poc within a name.
        return sorted(labs, key=lambda lab: lab["name"] or "")
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 1. laboratories/tested_samples_by_month/   (lab/all/samples_tested_by_month)
# ---------------------------------------------------------------------------
def tested_samples_by_month_service(req_args):
    """Monthly tested ``total``, ``positive`` and ``negative``, by analysis month.

    Legacy: AnalysisDateTime window and month, not rejected
    (``LIMSRejectionCode`` NULL or ''); ``lab_type`` splits on ``IsPoc``
    alone, as the lab/all route did. ✱4/✱7 results read FinalResult.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.AnalysisDateTime)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime)
    filters.append(_not_rejected())
    lab_type = _is_poc_condition(params.lab_type)
    if lab_type is not None:
        filters.append(lab_type)
    try:
        query = EIDMaster.query.with_entities(
            *month_cols,
            _total("total"),
            result_count("positive", "positive"),
            result_count("negative", "negative"),
        ).filter(and_(*filters))
        return [
            dict(**_month_keys(row), total=row.total, positive=row.positive,
                 negative=row.negative)
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 2. laboratories/registered_samples_by_month/   (lab/all/samples_registered_by_month)
# ---------------------------------------------------------------------------
def registered_samples_by_month_service(req_args):
    """Monthly registered ``total``, ``conventional`` and ``poc``, by registration month.

    Legacy: RegisteredDateTime window and month; conventional / poc and
    ``lab_type`` split on ``IsPoc`` alone. ``lab_code`` filters the receiving
    lab (``ReceivingFacilityCode``), as the legacy filtered its name.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.RegisteredDateTime)
    filters = _base_filters(
        params, EIDMaster.RegisteredDateTime, lab_code_column=EIDMaster.ReceivingFacilityCode
    )
    lab_type = _is_poc_condition(params.lab_type)
    if lab_type is not None:
        filters.append(lab_type)
    try:
        query = EIDMaster.query.with_entities(
            *month_cols,
            _total("total"),
            _count(EIDMaster.IsPoc == "No", "conventional"),
            _count(EIDMaster.IsPoc == "Yes", "poc"),
        ).filter(and_(*filters))
        return [
            dict(**_month_keys(row), total=row.total, conventional=row.conventional,
                 poc=row.poc)
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 3. laboratories/tested_samples/   (lab/conventional/samples_tested + lab/poc/samples_tested)
# ---------------------------------------------------------------------------
def _tested_lab_type(lab_type):
    """The lab-type rows of the legacy conventional / PoC samples_tested routes.

    Conventional: the conventional rule and ``TestingFacilityCode <> 'PBC'``
    (which drops a NULL code too). PoC: the PoC rule and a testing lab code.
    ``all`` (no legacy route) is either of the two.
    """
    conventional = and_(conventional_condition(), EIDMaster.TestingFacilityCode != "PBC")
    poc = and_(poc_condition(), EIDMaster.TestingFacilityCode.is_not(None))
    if lab_type == "conventional":
        return conventional
    if lab_type == "poc":
        return poc
    return or_(conventional, poc)


def tested_samples_service(req_args):
    """Tested ``total``, ``positive`` and ``negative`` per drill level.

    Legacy: AnalysisDateTime window, not rejected, a testing lab name, and
    the lab-type rows of ``_tested_lab_type``. The level follows
    ``facility_type`` (lab by default, province, district, health_facility)
    and ``disaggregation`` drills one level down (lab -> province ->
    district -> health_facility). The legacy drill (facilityType = the
    clicked level, facilityCodes = its name) maps to ``facility_type`` = the
    clicked level, its name in ``lab_code`` / ``province`` / ``district``,
    and ``disaggregation=true``. Rows carry ``testing_facility`` (and
    ``testing_facility_code``) at the lab level, ``requesting_facility`` at
    the other levels. The lab level groups by code + name: a name under two
    codes gives one row per code. ✱4/✱7 results read
    FinalResult.
    """
    params = parse_eid_params(req_args)
    column, level = _lab_level(params)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime)
    filters += [
        _not_rejected(),
        EIDMaster.TestingFacilityName.is_not(None),
        _tested_lab_type(params.lab_type),
    ]
    key = _group_key(level)
    # Lab level only: also group by (and return) the lab code (L2).
    code_cols = [EIDMaster.TestingFacilityCode] if level == "lab" else []
    try:
        rows = (
            EIDMaster.query.with_entities(
                column.label(key),
                *[col.label("testing_facility_code") for col in code_cols],
                _total("total"),
                result_count("positive", "positive"),
                result_count("negative", "negative"),
            )
            .filter(and_(*filters))
            .group_by(*code_cols, column)
            .order_by(column)
            .all()
        )
        return [
            {key: getattr(row, key),
             **({"testing_facility_code": row.testing_facility_code} if code_cols else {}),
             "total": row.total, "positive": row.positive, "negative": row.negative}
            for row in rows
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 4. laboratories/tat/   (lab/conventional/tat)
# ---------------------------------------------------------------------------
def tat_service(req_args):
    """Average days of the six TAT segments per drill level (conventional).

    Legacy: AnalysisDateTime window, ``tat_filters("lab_tat")`` (not
    rejected, conventional, no PBC / PEM, 0-90 days hub registration -> lab
    reception, ...), integer averages with 0 counted as 1. Levels as
    ``laboratories/tested_samples/``; as in the legacy, the district level
    also groups by (and returns) ``province``, and the health facility level
    ``province`` and ``district``. The lab level also returns
    ``testing_facility_code`` (grouped by code + name). ``lab_type`` does not
    apply (conventional only).
    """
    params = parse_eid_params(req_args)
    column, level = _lab_level(params)
    key = _group_key(level)
    parents = _TAT_PARENT_COLUMNS[level]
    code_cols = [EIDMaster.TestingFacilityCode] if level == "lab" else []
    group_cols = [col for _, col in parents] + [column]
    filters = _base_filters(params, EIDMaster.AnalysisDateTime) + tat_filters("lab_tat")
    try:
        rows = (
            EIDMaster.query.with_entities(
                *[col.label(name) for name, col in parents],
                column.label(key),
                *[col.label("testing_facility_code") for col in code_cols],
                *tat_averages(zero_as_one=True),
            )
            .filter(and_(*filters))
            .group_by(*code_cols, *group_cols)
            .order_by(*group_cols)
            .all()
        )
        names = ([name for name, _ in parents] + [key]
                 + (["testing_facility_code"] if code_cols else []) + _TAT_KEYS)
        return [{name: getattr(row, name) for name in names} for row in rows]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 5. laboratories/tat_samples/   (lab/tat_samples)
# ---------------------------------------------------------------------------
def tat_samples_service(req_args):
    """Day brackets of TAT segment ``category`` (0-5), per testing lab.

    Legacy: AnalysisDateTime window, ``tat_filters("lab_tat_samples")``
    (IsPoc 'No', no PBC / UEM, no 90-day limit); brackets <7, 7-15, 16-21,
    >21 and no dates. Rows add ``testing_facility_code`` (grouped by code +
    name).
    """
    params = parse_eid_params(req_args)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime) + tat_filters("lab_tat_samples")
    segment = TAT_SEGMENTS[params.category][0]
    try:
        rows = (
            EIDMaster.query.with_entities(
                EIDMaster.TestingFacilityName.label("testing_facility"),
                EIDMaster.TestingFacilityCode.label("testing_facility_code"),
                *tat_bracket_counts(params.category),
            )
            .filter(and_(*filters))
            .group_by(EIDMaster.TestingFacilityCode, EIDMaster.TestingFacilityName)
            .order_by(EIDMaster.TestingFacilityName)
            .all()
        )
        return [
            dict(testing_facility=row.testing_facility,
                 testing_facility_code=row.testing_facility_code, category=segment,
                 **{key: getattr(row, key) for key in _BRACKET_KEYS})
            for row in rows
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 6. laboratories/rejected_samples/   (lab/rejected_samples)
# ---------------------------------------------------------------------------
def _rejected_filters(params):
    filters = _base_filters(
        params, EIDMaster.RegisteredDateTime, lab_code_column=EIDMaster.ReceivingFacilityCode
    )
    return filters + [rejected_condition(), EIDMaster.IsPoc == "No"]


def rejected_samples_service(req_args):
    """Rejected samples by reason (9 buckets) and ``total``, per receiving lab.

    Legacy: RegisteredDateTime window, ``IsPoc = 'No'``, grouped by
    ReceivingFacilityName; reasons of the default variant (REJOL and PRTLA
    count as ``other``). ``total`` counts every rejected row (code or
    description); a row rejected by description only is in no reason.
    ✱2 ``lab_code`` applies, on ``ReceivingFacilityCode``. Rows add
    ``receiving_facility_code`` (grouped by code + name).
    """
    params = parse_eid_params(req_args)
    try:
        rows = (
            EIDMaster.query.with_entities(
                EIDMaster.ReceivingFacilityName.label("receiving_facility"),
                EIDMaster.ReceivingFacilityCode.label("receiving_facility_code"),
                *rejection_reason_counts("default"),
                _total("total"),
            )
            .filter(and_(*_rejected_filters(params)))
            .group_by(EIDMaster.ReceivingFacilityCode, EIDMaster.ReceivingFacilityName)
            .order_by(EIDMaster.ReceivingFacilityName)
            .all()
        )
        return [
            dict(receiving_facility=row.receiving_facility,
                 receiving_facility_code=row.receiving_facility_code,
                 **{key: getattr(row, key) for key in _REJECTION_KEYS}, total=row.total)
            for row in rows
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 7. laboratories/rejected_samples_by_month/   (lab/rejected_samples_monthly)
# ---------------------------------------------------------------------------
def rejected_samples_by_month_service(req_args):
    """Monthly rejected samples by reason (9 buckets) and ``total``.

    Legacy: RegisteredDateTime window and month, ``IsPoc = 'No'``; as
    ``laboratories/rejected_samples/``. ✱2 ``lab_code`` applies, on
    ``ReceivingFacilityCode``.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.RegisteredDateTime)
    try:
        query = EIDMaster.query.with_entities(
            *month_cols, *rejection_reason_counts("default"), _total("total")
        ).filter(and_(*_rejected_filters(params)))
        return [
            dict(**_month_keys(row), **{key: getattr(row, key) for key in _REJECTION_KEYS},
                 total=row.total)
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 8. laboratories/samples_by_equipment/   (lab/samples_by_equipment)
# ---------------------------------------------------------------------------
def samples_by_equipment_service(req_args):
    """Tested samples per analyzer group, per testing lab.

    Legacy: AnalysisDateTime window, ``HL7ResultStatusCode = 'F'``,
    ``IsPoc = 'No'``, ``TestingFacilityCode <> 'PBC'``, grouped by
    TestingFacilityName. Rows add ``testing_facility_code`` (grouped by code +
    name).
    """
    params = parse_eid_params(req_args)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime)
    filters += equipment_filters(exclude_pbc=True)
    try:
        rows = (
            EIDMaster.query.with_entities(
                EIDMaster.TestingFacilityName.label("testing_facility"),
                EIDMaster.TestingFacilityCode.label("testing_facility_code"),
                *equipment_counts(),
            )
            .filter(and_(*filters))
            .group_by(EIDMaster.TestingFacilityCode, EIDMaster.TestingFacilityName)
            .order_by(EIDMaster.TestingFacilityName)
            .all()
        )
        return [
            dict(testing_facility=row.testing_facility,
                 testing_facility_code=row.testing_facility_code, tested=row.tested,
                 **{key: getattr(row, key) for key in _EQUIPMENT_KEYS})
            for row in rows
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 9. laboratories/samples_by_equipment_by_month/   (lab/samples_by_equipment_monthly)
# ---------------------------------------------------------------------------
def samples_by_equipment_by_month_service(req_args):
    """Monthly tested samples per analyzer group, by analysis month.

    Legacy: AnalysisDateTime window and month, ``HL7ResultStatusCode = 'F'``,
    ``IsPoc = 'No'``, no PBC exclusion.
    """
    params = parse_eid_params(req_args)
    month_cols = _month_columns(EIDMaster.AnalysisDateTime)
    filters = _base_filters(params, EIDMaster.AnalysisDateTime)
    filters += equipment_filters(exclude_pbc=False)
    try:
        query = EIDMaster.query.with_entities(*month_cols, *equipment_counts()).filter(
            and_(*filters)
        )
        return [
            dict(**_month_keys(row), tested=row.tested,
                 **{key: getattr(row, key) for key in _EQUIPMENT_KEYS})
            for row in _monthly(query, month_cols)
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# Routes no card uses (spec §4.3): only renamed to the rebuilt columns.
# ---------------------------------------------------------------------------
def _build_facility_filters(facilities, facility_type):
    """Build facility filter conditions based on facility_type."""
    if not facilities:
        return []
    if facility_type == "province":
        return [EIDMaster.RequestingProvinceName.in_(facilities)]
    elif facility_type == "district":
        return [EIDMaster.RequestingDistrictName.in_(facilities)]
    elif facility_type == "health_facility":
        return [EIDMaster.RequestingFacilityName.in_(facilities)]
    return []


def _apply_lab_type_filter(filters, lab_type):
    """Append LAB_TYPE_EID filter if lab_type is not 'all'."""
    lab_filter = LAB_TYPE_EID(EIDMaster, lab_type)
    if lab_filter is not None:
        filters.append(lab_filter)


# ---------------------------------------------------------------------------
# 10. sample_routes_service
# ---------------------------------------------------------------------------
def sample_routes_service(req_args):
    """Requesting/testing facility pairs with coordinates."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_fields = [
        EIDMaster.RequestingFacilityName,
        EIDMaster.TestingFacilityName,
        EIDMaster.RequestingFacilityLatitude,
        EIDMaster.RequestingFacilityLongitude,
        EIDMaster.TestingFacilityLatitude,
        EIDMaster.TestingFacilityLongitude,
    ]

    try:
        query = (
            EIDMaster.query.with_entities(
                EIDMaster.RequestingFacilityName.label("requesting_facility"),
                EIDMaster.TestingFacilityName.label("testing_facility"),
                EIDMaster.RequestingFacilityLatitude.label("requesting_latitude"),
                EIDMaster.RequestingFacilityLongitude.label("requesting_longitude"),
                EIDMaster.TestingFacilityLatitude.label("testing_latitude"),
                EIDMaster.TestingFacilityLongitude.label("testing_longitude"),
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(*group_fields)
            .order_by(EIDMaster.RequestingFacilityName)
        )
        data = query.all()
        return [
            dict(
                requesting_facility=row.requesting_facility,
                testing_facility=row.testing_facility,
                requesting_latitude=row.requesting_latitude,
                requesting_longitude=row.requesting_longitude,
                testing_latitude=row.testing_latitude,
                testing_longitude=row.testing_longitude,
                total=row.total,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 11. sample_routes_viewport_service
# ---------------------------------------------------------------------------
def sample_routes_viewport_service(req_args):
    """Sample routes filtered by viewport bounding box."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"
    viewport = req_args.get("viewport")

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    # Parse viewport bounding box: "south,west,north,east"
    if viewport:
        try:
            parts = [float(x.strip()) for x in viewport.split(",")]
            if len(parts) == 4:
                south, west, north, east = parts
                filters.append(
                    func.cast(EIDMaster.RequestingFacilityLatitude, db_float()).between(south, north)
                )
                filters.append(
                    func.cast(EIDMaster.RequestingFacilityLongitude, db_float()).between(west, east)
                )
        except (ValueError, TypeError):
            pass

    group_fields = [
        EIDMaster.RequestingFacilityName,
        EIDMaster.TestingFacilityName,
        EIDMaster.RequestingFacilityLatitude,
        EIDMaster.RequestingFacilityLongitude,
        EIDMaster.TestingFacilityLatitude,
        EIDMaster.TestingFacilityLongitude,
    ]

    try:
        query = (
            EIDMaster.query.with_entities(
                EIDMaster.RequestingFacilityName.label("requesting_facility"),
                EIDMaster.TestingFacilityName.label("testing_facility"),
                EIDMaster.RequestingFacilityLatitude.label("requesting_latitude"),
                EIDMaster.RequestingFacilityLongitude.label("requesting_longitude"),
                EIDMaster.TestingFacilityLatitude.label("testing_latitude"),
                EIDMaster.TestingFacilityLongitude.label("testing_longitude"),
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(*group_fields)
            .order_by(EIDMaster.RequestingFacilityName)
        )
        data = query.all()
        return [
            dict(
                requesting_facility=row.requesting_facility,
                testing_facility=row.testing_facility,
                requesting_latitude=row.requesting_latitude,
                requesting_longitude=row.requesting_longitude,
                testing_latitude=row.testing_latitude,
                testing_longitude=row.testing_longitude,
                total=row.total,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


def db_float():
    """Return SQLAlchemy Float type for casting."""
    from sqlalchemy import Float
    return Float
