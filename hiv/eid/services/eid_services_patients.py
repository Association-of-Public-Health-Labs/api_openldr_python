"""
HIV EID patient searches (Admin only).

Same shape as the VL patient searches: optional drill-down filters, all bound
parameters, paging capped at 500. The model's key (RequestID) may repeat, so
explicit labelled columns are selected, never ORM entities.

The rows carry third-party contact details (the caregiver's phone and the
mother's PTV id). This module must never log them or any row.
"""
import logging
from math import ceil

from sqlalchemy import case, func, or_

from hiv.eid.models.eid_master_model import EIDMaster
from hiv.eid.services.eid_common import (
    RESULT_VALUES,
    conventional_condition,
    date_between_inclusive,
    lab_type_condition,
    parse_eid_params,
    pending_condition,
    poc_condition,
    rejected_condition,
    split_values,
)
from utilities.auth_helpers import (
    check_admin_access as _check_admin_access,
    get_user_role as _get_user_role,
)
from utilities.service_helpers import InvalidParameter

logger = logging.getLogger(__name__)

MAX_PER_PAGE = 500

RESULT_TYPES = ("positive", "negative", "indeterminate", "rejected", "pending")


def _clean_text(column):
    """Trimmed text, NULL when empty."""
    return func.nullif(func.ltrim(func.rtrim(column)), "")


_FULL_NAME = func.ltrim(func.rtrim(
    func.concat(func.coalesce(EIDMaster.FIRSTNAME, ""), " ", func.coalesce(EIDMaster.SURNAME, ""))
))

EID_PATIENT_COLUMNS = [
    EIDMaster.RequestID.label("request_id"),
    func.nullif(_FULL_NAME, "").label("name"),
    EIDMaster.HL7SexCode.label("sex"),
    EIDMaster.AgeInDays.label("age_in_days"),
    EIDMaster.RequestingProvinceName.label("requesting_province"),
    EIDMaster.RequestingDistrictName.label("requesting_district"),
    EIDMaster.RequestingFacilityName.label("requesting_facility"),
    EIDMaster.TestingFacilityName.label("testing_facility"),
    EIDMaster.SpecimenDatetime.label("specimen_date"),
    EIDMaster.RegisteredDateTime.label("registered_date"),
    EIDMaster.AnalysisDateTime.label("analysis_date"),
    EIDMaster.AuthorisedDateTime.label("authorised_date"),
    case(
        (poc_condition(), "poc"),
        (conventional_condition(), "conventional"),
        else_=None,
    ).label("lab_type"),
    EIDMaster.FinalResult.label("result"),
    func.coalesce(
        _clean_text(EIDMaster.LIMSRejectionDesc), _clean_text(EIDMaster.LIMSRejectionCode)
    ).label("rejection_reason"),
    EIDMaster.CaregiverMobileContact.label("caregiver_phone"),
    EIDMaster.PtvMother.label("mother_ptv_id"),
]

_DATE_KEYS = ("specimen_date", "registered_date", "analysis_date", "authorised_date")


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


def _clean(values):
    if isinstance(values, str):
        values = [values]
    return [value.strip() for value in (values or []) if value and value.strip()]


def _result_type_filter(raw):
    """OR of the requested result classes; ``None`` when none were asked for."""
    conditions = []
    for item in split_values(raw):
        key = item.strip().lower()
        if key in RESULT_VALUES:
            conditions.append(EIDMaster.FinalResult.in_(RESULT_VALUES[key]))
        elif key == "rejected":
            conditions.append(rejected_condition())
        elif key == "pending":
            conditions.append(pending_condition())
        else:
            raise InvalidParameter(
                f"Invalid 'result_type' value: '{item}'. Valid values: {', '.join(RESULT_TYPES)}."
            )
    return or_(*conditions) if conditions else None


def _drill_down_filters(req_args, params):
    filters = []
    provinces = _clean(req_args.get("province"))
    districts = _clean(req_args.get("district"))
    if provinces:
        filters.append(EIDMaster.RequestingProvinceName.in_(provinces))
    if districts:
        filters.append(EIDMaster.RequestingDistrictName.in_(districts))
    if params.health_facility:
        filters.append(EIDMaster.RequestingFacilityName == params.health_facility)
    if params.lab_codes:
        filters.append(EIDMaster.TestingFacilityCode.in_(params.lab_codes))
    lab_type = lab_type_condition(params.lab_type)
    if lab_type is not None:
        filters.append(lab_type)
    result_type = _result_type_filter(req_args.get("result_type"))
    if result_type is not None:
        filters.append(result_type)
    return filters


def _admin_only(req_args):
    user_id, user_role = _get_user_role(req_args)
    return _check_admin_access(user_id, user_role)


def _bad_request(message):
    return {"status": "error", "code": 400, "message": message}


def _serialise(row):
    record = row._asdict()
    for key in _DATE_KEYS:
        if record[key] is not None:
            record[key] = record[key].isoformat()
    return record


def _search(req_args, params, filters):
    page, per_page = _paging(req_args)
    filters = [
        date_between_inclusive(EIDMaster.RegisteredDateTime, params.dates),
        *filters,
        *_drill_down_filters(req_args, params),
    ]
    try:
        query = EIDMaster.query.with_entities(*EID_PATIENT_COLUMNS).filter(*filters)
        query = query.order_by(EIDMaster.RequestID)
        total_count = query.count()
        rows = query.offset((page - 1) * per_page).limit(per_page).all()
        return {
            "status": "success",
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": ceil(total_count / per_page),
            "data": [_serialise(row) for row in rows],
        }
    except Exception as exc:
        # Only the exception class: the message and the rows hold contact details.
        logger.error("EID patient search failed: %s", type(exc).__name__)
        return {"status": "error", "code": 500, "message": "An error occurred"}


def get_patients_by_facility_service(req_args):
    """Patients registered in the window, optionally at one health facility."""
    denied = _admin_only(req_args)
    if denied:
        return denied
    return _search(req_args, parse_eid_params(req_args), [])


def get_patients_by_name_service(req_args):
    """Patients whose first name and surname contain the given text."""
    denied = _admin_only(req_args)
    if denied:
        return denied
    params = parse_eid_params(req_args)
    name = (req_args.get("name") or "").strip()
    if not name:
        return _bad_request("The 'name' parameter is required.")
    return _search(req_args, params, [_FULL_NAME.icontains(name, autoescape=True)])


def get_patients_by_result_type_service(req_args):
    """Patients by result class (positive, negative, indeterminate, rejected, pending)."""
    denied = _admin_only(req_args)
    if denied:
        return denied
    params = parse_eid_params(req_args)
    if not split_values(req_args.get("result_type")):
        return _bad_request(
            f"The 'result_type' parameter is required. Valid values: {', '.join(RESULT_TYPES)}."
        )
    return _search(req_args, params, [])
