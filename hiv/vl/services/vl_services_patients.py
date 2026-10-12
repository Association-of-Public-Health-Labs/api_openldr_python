"""
HIV VL patient searches (Admin only).

Every search takes the same optional drill-down filters as the dashboard
cards. They are all bound parameters; never build SQL from request text.
"""
from math import ceil

from hiv.vl.models.vl import VlData
from hiv.vl.services.vl_common import (
    TRUTHY_VALUES,
    age_range_filters,
    breastfeeding_filter,
    date_between,
    parse_vl_params,
    pregnant_filter,
    rejected_condition,
    split_values,
)
from utilities.auth_helpers import (
    check_admin_access as _check_admin_access,
    get_user_role as _get_user_role,
)
from utilities.service_helpers import InvalidParameter
from utilities.utils import process_patients

MAX_PER_PAGE = 500

RESULT_TYPES = {"suppressed": "Suppressed", "not_suppressed": "Not Suppressed"}

TEST_REASONS = {
    "Reason Not Specified": ["Não preenchido", "No", "Reason Not Specified", "Yes", ""],
    "Routine": ["Routine"],
    "Repeat": ["Repeat after breastfeeding", "Repeat"],
    "Suspected treatment failure": ["Suspected treatment failure", "Suspeita de falha terapêutica"],
}

VL_PATIENT_ENTITIES = [
    VlData.RequestID,
    VlData.RequestingProvinceName,
    VlData.RequestingDistrictName,
    VlData.RequestingFacilityName,
    VlData.RequestingFacilityNationalCode,
    VlData.TestingProvinceName,
    VlData.TestingDistrictName,
    VlData.TestingFacilityName,
    VlData.FIRSTNAME,
    VlData.SURNAME,
    VlData.AgeInYears,
    VlData.HL7SexCode,
    VlData.TELHOME,
    VlData.TELWORK,
    VlData.MOBILE,
    VlData.HealthcareNo,
    VlData.REFNO,
    VlData.NATIONALID,
    VlData.UNIQUEID,
    VlData.ViralLoadResultCategory,
    VlData.HIVVL_ViralLoadResult,
    VlData.HIVVL_ViralLoadCAPCTM,
    VlData.HIVVL_VRLogValue,
    VlData.ReasonForTest,
    VlData.Pregnant,
    VlData.BreastFeeding,
    VlData.ARTRegimen,
    VlData.LIMSRejectionCode,
    VlData.LIMSRejectionDesc,
    VlData.LIMSSpecimenSourceCode,
    VlData.LIMSSpecimenSourceDesc,
    VlData.SpecimenDatetime,
    VlData.RegisteredDateTime,
    VlData.AnalysisDateTime,
    VlData.AuthorisedDateTime,
    VlData.FinalViralLoadResult,
    VlData.HL7ResultStatusCode,
]


def paginate_query(query, page, per_page):
    """Return (rows, total_count, total_pages) for a 1-indexed page."""
    query = query.order_by(VlData.RequestID)
    total_count = query.count()
    total_pages = ceil(total_count / per_page) if per_page > 0 else 0
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    return rows, total_count, total_pages


def _paging(req_args):
    raw_page, raw_per_page = req_args.get("page"), req_args.get("per_page")
    try:
        page = 1 if raw_page in (None, "") else int(raw_page)
        per_page = 50 if raw_per_page in (None, "") else int(raw_per_page)
    except (TypeError, ValueError):
        raise InvalidParameter("page and per_page must be whole numbers") from None
    if page < 1 or per_page < 1:
        raise InvalidParameter("page and per_page must be at least 1")
    return page, min(per_page, MAX_PER_PAGE)


def _truthy(value):
    return str(value or "").strip().lower() in TRUTHY_VALUES


def _clean(values):
    return [value.strip() for value in (values or []) if value and value.strip()]


def _result_values(raw):
    values = []
    for item in split_values(raw):
        key = item.lower()
        if key not in RESULT_TYPES:
            raise InvalidParameter(
                f"Invalid 'result_type' value: '{item}'. Valid values: suppressed, not_suppressed."
            )
        values.append(RESULT_TYPES[key])
    return values


def _test_reason_values(raw):
    values = []
    for item in split_values(raw):
        if item not in TEST_REASONS:
            raise InvalidParameter(
                f"Invalid 'test_reason' value: '{item}'. Valid values: {', '.join(TEST_REASONS)}."
            )
        values.extend(TEST_REASONS[item])
    return values


def _drill_down_filters(req_args, params):
    """Optional filters shared by every search (the card drill-downs)."""
    filters = []
    provinces = _clean(req_args.get("province"))
    districts = _clean(req_args.get("district"))
    if provinces:
        filters.append(VlData.RequestingProvinceName.in_(provinces))
    if districts:
        filters.append(VlData.RequestingDistrictName.in_(districts))
    if params.health_facility:
        filters.append(VlData.RequestingFacilityName == params.health_facility)
    if params.lab_codes:
        filters.append(VlData.TestingFacilityCode.in_(params.lab_codes))
    filters.extend(age_range_filters(params))
    if _truthy(req_args.get("pregnant")):
        filters.append(pregnant_filter())
    if _truthy(req_args.get("breastfeeding")):
        filters.append(breastfeeding_filter())
    if _truthy(req_args.get("rejected")):
        filters.append(rejected_condition())
    result_values = _result_values(req_args.get("result_type"))
    if result_values:
        filters.append(VlData.ViralLoadResultCategory.in_(result_values))
    return filters


def _admin_only(req_args):
    user_id, user_role = _get_user_role(req_args)
    return _check_admin_access(user_id, user_role)


def _bad_request(message):
    return {"status": "error", "code": 400, "message": message}


def _search(req_args, params, date_column, filters):
    page, per_page = _paging(req_args)
    filters = [
        date_between(date_column, params.dates),
        *filters,
        *_drill_down_filters(req_args, params),
    ]
    try:
        query = VlData.query.with_entities(*VL_PATIENT_ENTITIES).filter(*filters)
        rows, total_count, total_pages = paginate_query(query, page, per_page)
        return {
            "status": "success",
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "data": process_patients(rows, params.dates, params.facility_type, None, "vl", None, None),
        }
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An error occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 1. get_patients_by_name_service
# ---------------------------------------------------------------------------
def get_patients_by_name_service(req_args):
    """Patients whose first name or surname contains the given text (registration date)."""
    denied = _admin_only(req_args)
    if denied:
        return denied
    params = parse_vl_params(req_args)
    first_name = (req_args.get("first_name") or "").strip()
    surname = (req_args.get("surname") or "").strip()
    if not first_name and not surname:
        return _bad_request("At least one of 'first_name' or 'surname' must be provided.")
    filters = []
    if first_name:
        filters.append(VlData.FIRSTNAME.ilike(f"%{first_name}%"))
    if surname:
        filters.append(VlData.SURNAME.ilike(f"%{surname}%"))
    return _search(req_args, params, VlData.RegisteredDateTime, filters)


# ---------------------------------------------------------------------------
# 2. get_patients_by_facility_service
# ---------------------------------------------------------------------------
def get_patients_by_facility_service(req_args):
    """Patients registered at one health facility (the card drill-down)."""
    denied = _admin_only(req_args)
    if denied:
        return denied
    params = parse_vl_params(req_args)
    if not params.health_facility:
        return _bad_request("The 'health_facility' parameter is required.")
    return _search(req_args, params, VlData.RegisteredDateTime, [])


# ---------------------------------------------------------------------------
# 3. get_patients_by_result_type_service
# ---------------------------------------------------------------------------
def get_patients_by_result_type_service(req_args):
    """Patients by result category (analysis date)."""
    denied = _admin_only(req_args)
    if denied:
        return denied
    params = parse_vl_params(req_args)
    if not split_values(req_args.get("result_type")):
        return _bad_request(
            "The 'result_type' parameter is required. Valid values: suppressed, not_suppressed."
        )
    return _search(req_args, params, VlData.AnalysisDateTime, [VlData.AnalysisDateTime.is_not(None)])


# ---------------------------------------------------------------------------
# 4. get_patients_by_test_reason_service
# ---------------------------------------------------------------------------
def get_patients_by_test_reason_service(req_args):
    """Patients by reason for test (registration date)."""
    denied = _admin_only(req_args)
    if denied:
        return denied
    params = parse_vl_params(req_args)
    reasons = _test_reason_values(req_args.get("test_reason"))
    if not reasons:
        return _bad_request("The 'test_reason' parameter is required.")
    return _search(req_args, params, VlData.RegisteredDateTime, [VlData.ReasonForTest.in_(reasons)])
