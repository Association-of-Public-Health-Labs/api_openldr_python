from hiv.eid.services.eid_common import parse_eid_params
from utilities.utils import (
    PROCESS_COMMON_PARAMS_VL,
    YEAR, MONTH, DATE_PART, TOTAL_ALL,
    POSITIVITY, LAB_TYPE_EID, EQUIPMENT_COUNT, DATE_DIFF_AVG,
    and_, or_, func, case, text,
)
from hiv.eid.models.eid_master_model import EIDMaster


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


def _year_month_group_order(date_field):
    """Return (group_by, order_by) tuples for year/month grouping."""
    cols = [YEAR(date_field), MONTH(date_field), DATE_PART("month", date_field)]
    return cols, cols


def _apply_lab_type_filter(filters, lab_type):
    """Append LAB_TYPE_EID filter if lab_type is not 'all'."""
    lab_filter = LAB_TYPE_EID(EIDMaster, lab_type)
    if lab_filter is not None:
        filters.append(lab_filter)


def _positivity_entities():
    """Standard positivity with_entities columns for EID."""
    return [
        POSITIVITY(EIDMaster.PCR_Result, "Positive").label("positive"),
        POSITIVITY(EIDMaster.PCR_Result, "Negative").label("negative"),
    ]


def _gender_entities():
    """Gender count columns for EID."""
    return [
        func.count(case((EIDMaster.HL7SexCode == "F", 1))).label("female"),
        func.count(case((EIDMaster.HL7SexCode == "M", 1))).label("male"),
    ]


# ---------------------------------------------------------------------------
# 1. tested_samples_by_month_service
# ---------------------------------------------------------------------------
def tested_samples_by_month_service(req_args):
    """Tested samples grouped by year/month with positivity and gender splits."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_cols, order_cols = _year_month_group_order(EIDMaster.AnalysisDateTime)

    try:
        query = (
            EIDMaster.query.with_entities(
                *group_cols,
                TOTAL_ALL,
                *_positivity_entities(),
                *_gender_entities(),
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, month=row[1], month_name=row[2],
                total=row.total, positive=row.positive, negative=row.negative,
                female=row.female, male=row.male,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 2. registered_samples_by_month_service
# ---------------------------------------------------------------------------
def registered_samples_by_month_service(req_args):
    """Registered samples grouped by year/month."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [EIDMaster.RegisteredDateTime.between(dates[0], dates[1])]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_cols, order_cols = _year_month_group_order(EIDMaster.RegisteredDateTime)

    try:
        query = (
            EIDMaster.query.with_entities(
                *group_cols,
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(year=row.year, month=row[1], month_name=row[2], total=row.total)
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 3. tested_samples_service
# ---------------------------------------------------------------------------
def tested_samples_service(req_args):
    """Tested samples grouped by TestingFacilityName."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                EIDMaster.TestingFacilityName.label("testing_facility"),
                TOTAL_ALL,
                *_positivity_entities(),
            )
            .filter(and_(*filters))
            .group_by(EIDMaster.TestingFacilityName)
            .order_by(EIDMaster.TestingFacilityName)
        )
        data = query.all()
        return [
            dict(
                testing_facility=row.testing_facility,
                total=row.total, positive=row.positive, negative=row.negative,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 4. tat_service
# ---------------------------------------------------------------------------
def tat_service(req_args):
    """TAT with 6 hub-chain segments grouped by TestingFacilityName."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                EIDMaster.TestingFacilityName.label("testing_facility"),
                DATE_DIFF_AVG([EIDMaster.SpecimenDatetime, EIDMaster.LIMSPreReg_ReceivedDateTime]).label("collection_receiveHub"),
                DATE_DIFF_AVG([EIDMaster.LIMSPreReg_ReceivedDateTime, EIDMaster.LIMSPreReg_RegistrationDateTime]).label("receiveHub_registrationHub"),
                DATE_DIFF_AVG([EIDMaster.LIMSPreReg_RegistrationDateTime, EIDMaster.ReceivedDateTime]).label("registrationHub_receiveLab"),
                DATE_DIFF_AVG([EIDMaster.ReceivedDateTime, EIDMaster.RegisteredDateTime]).label("receiveLab_registrationLab"),
                DATE_DIFF_AVG([EIDMaster.RegisteredDateTime, EIDMaster.AnalysisDateTime]).label("registrationLab_analyseLab"),
                DATE_DIFF_AVG([EIDMaster.AnalysisDateTime, EIDMaster.AuthorisedDateTime]).label("analyseLab_validationLab"),
            )
            .filter(and_(*filters))
            .group_by(EIDMaster.TestingFacilityName)
            .order_by(EIDMaster.TestingFacilityName)
        )
        data = query.all()
        return [
            dict(
                testing_facility=row.testing_facility,
                collection_receiveHub=row.collection_receiveHub,
                receiveHub_registrationHub=row.receiveHub_registrationHub,
                registrationHub_receiveLab=row.registrationHub_receiveLab,
                receiveLab_registrationLab=row.receiveLab_registrationLab,
                registrationLab_analyseLab=row.registrationLab_analyseLab,
                analyseLab_validationLab=row.analyseLab_validationLab,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 5. tat_samples_service
# ---------------------------------------------------------------------------
_TAT_CATEGORIES = {
    1: ("collection_receiveHub", EIDMaster.SpecimenDatetime, EIDMaster.LIMSPreReg_ReceivedDateTime),
    2: ("receiveHub_registrationHub", EIDMaster.LIMSPreReg_ReceivedDateTime, EIDMaster.LIMSPreReg_RegistrationDateTime),
    3: ("registrationHub_receiveLab", EIDMaster.LIMSPreReg_RegistrationDateTime, EIDMaster.ReceivedDateTime),
    4: ("receiveLab_registrationLab", EIDMaster.ReceivedDateTime, EIDMaster.RegisteredDateTime),
    5: ("registrationLab_analyseLab", EIDMaster.RegisteredDateTime, EIDMaster.AnalysisDateTime),
    6: ("analyseLab_validationLab", EIDMaster.AnalysisDateTime, EIDMaster.AuthorisedDateTime),
}


def tat_samples_service(req_args):
    """TAT distribution: count samples in time brackets for a specific TAT category."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"
    category = parse_eid_params(req_args).category or 1

    if category not in _TAT_CATEGORIES:
        category = 1

    cat_name, field_start, field_end = _TAT_CATEGORIES[category]
    diff_expr = func.datediff(text("day"), field_start, field_end)

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                func.count(case((diff_expr < 7, 1))).label("less_7"),
                func.count(case((and_(diff_expr >= 7, diff_expr <= 14), 1))).label("between_7_14"),
                func.count(case((and_(diff_expr >= 15, diff_expr <= 21), 1))).label("between_15_21"),
                func.count(case((diff_expr > 21, 1))).label("greater_21"),
            )
            .filter(and_(*filters))
        )
        data = query.all()
        return [
            dict(
                category=cat_name,
                less_7=row.less_7,
                between_7_14=row.between_7_14,
                between_15_21=row.between_15_21,
                greater_21=row.greater_21,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 6. rejected_samples_service
# ---------------------------------------------------------------------------
def rejected_samples_service(req_args):
    """Rejected samples grouped by TestingFacilityName."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        and_(EIDMaster.LIMSRejectionCode.is_not(None), EIDMaster.LIMSRejectionCode != ""),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    
    _apply_lab_type_filter(filters, lab_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                EIDMaster.TestingFacilityName.label("testing_facility"),
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(EIDMaster.TestingFacilityName)
            .order_by(EIDMaster.TestingFacilityName)
        )
        data = query.all()
        return [
            dict(testing_facility=row.testing_facility, total=row.total)
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 7. rejected_samples_by_month_service
# ---------------------------------------------------------------------------
def rejected_samples_by_month_service(req_args):
    """Rejected samples grouped by year/month."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        and_(EIDMaster.LIMSRejectionCode.is_not(None), EIDMaster.LIMSRejectionCode != ""),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_cols, order_cols = _year_month_group_order(EIDMaster.AnalysisDateTime)

    try:
        query = (
            EIDMaster.query.with_entities(
                *group_cols,
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(year=row.year, month=row[1], month_name=row[2], total=row.total)
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 8. samples_by_equipment_service
# ---------------------------------------------------------------------------
_EQUIPMENT_TYPES = ["CAPCTM", "ALINITY", "M2000", "C6800", "PANTHER", "MPIMA", "MANUAL"]


def samples_by_equipment_service(req_args):
    """Equipment counts grouped by TestingFacilityName."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    equipment_entities = [
        EQUIPMENT_COUNT(EIDMaster, eq).label(eq) for eq in _EQUIPMENT_TYPES
    ]

    try:
        query = (
            EIDMaster.query.with_entities(
                EIDMaster.TestingFacilityName.label("testing_facility"),
                *equipment_entities,
            )
            .filter(and_(*filters))
            .group_by(EIDMaster.TestingFacilityName)
            .order_by(EIDMaster.TestingFacilityName)
        )
        data = query.all()
        return [
            dict(
                testing_facility=row.testing_facility,
                **{eq: getattr(row, eq) for eq in _EQUIPMENT_TYPES},
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 9. samples_by_equipment_by_month_service
# ---------------------------------------------------------------------------
def samples_by_equipment_by_month_service(req_args):
    """Equipment counts grouped by year/month."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_cols, order_cols = _year_month_group_order(EIDMaster.AnalysisDateTime)
    equipment_entities = [
        EQUIPMENT_COUNT(EIDMaster, eq).label(eq) for eq in _EQUIPMENT_TYPES
    ]

    try:
        query = (
            EIDMaster.query.with_entities(
                *group_cols,
                *equipment_entities,
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, month=row[1], month_name=row[2],
                **{eq: getattr(row, eq) for eq in _EQUIPMENT_TYPES},
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


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
