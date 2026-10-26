from hiv.eid.services.eid_common import parse_eid_params
from utilities.utils import (
    PROCESS_COMMON_PARAMS_VL,
    YEAR, MONTH, DATE_PART, TOTAL_ALL, TOTAL_NOT_NULL,
    POSITIVITY, LAB_TYPE_EID, EQUIPMENT_COUNT,
    DATE_DIFF_AVG, TOTAL_IN,
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
        POSITIVITY(EIDMaster.PCR_Result, "Positivo").label("positive"),
        POSITIVITY(EIDMaster.PCR_Result, "Negativo").label("negative"),
    ]


_EQUIPMENT_TYPES = ["CAPCTM", "ALINITY", "M2000", "C6800", "PANTHER", "MPIMA", "MANUAL"]

_TAT_CATEGORIES = {
    1: ("collection_receiveHub", EIDMaster.SpecimenDatetime, EIDMaster.LIMSPreReg_ReceivedDateTime),
    2: ("receiveHub_registrationHub", EIDMaster.LIMSPreReg_ReceivedDateTime, EIDMaster.LIMSPreReg_RegistrationDateTime),
    3: ("registrationHub_receiveLab", EIDMaster.LIMSPreReg_RegistrationDateTime, EIDMaster.ReceivedDateTime),
    4: ("receiveLab_registrationLab", EIDMaster.ReceivedDateTime, EIDMaster.RegisteredDateTime),
    5: ("registrationLab_analyseLab", EIDMaster.RegisteredDateTime, EIDMaster.AnalysisDateTime),
    6: ("analyseLab_validationLab", EIDMaster.AnalysisDateTime, EIDMaster.AuthorisedDateTime),
}


# ---------------------------------------------------------------------------
# 1. summary_indicators_service
# ---------------------------------------------------------------------------
def summary_indicators_service(req_args):
    """Single-row summary: registered, tested, rejected, pending, positive, negative. Filter by lab_type."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    base_filters = [EIDMaster.RegisteredDateTime.between(dates[0], dates[1])]
    base_filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(base_filters, lab_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                TOTAL_ALL,
                TOTAL_NOT_NULL(EIDMaster.AnalysisDateTime).label("tested"),
                func.count(
                    case(
                        (
                            and_(EIDMaster.LIMSRejectionCode.is_not(None), EIDMaster.LIMSRejectionCode != ""),
                            1,
                        )
                    )
                ).label("rejected"),
                func.count(
                    case(
                        (
                            and_(
                                EIDMaster.AnalysisDateTime.is_(None),
                                or_(
                                    EIDMaster.LIMSRejectionCode.is_(None),
                                    EIDMaster.LIMSRejectionCode == "",
                                ),
                                or_(
                                    EIDMaster.LIMSRejectionCode.is_(None),
                                    EIDMaster.LIMSRejectionCode == "",
                                ),
                            ),
                            1,
                        )
                    )
                ).label("pending"),
                POSITIVITY(EIDMaster.PCR_Result, "Positive").label("positive"),
                POSITIVITY(EIDMaster.PCR_Result, "Negative").label("negative"),
            )
            .filter(and_(*base_filters))
        )
        row = query.one()
        return dict(
            registered=row.total,
            tested=row.tested,
            rejected=row.rejected,
            pending=row.pending,
            positive=row.positive,
            negative=row.negative,
            start_date=dates[0],
            end_date=dates[1],
        )
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 2. summary_tat_service
# ---------------------------------------------------------------------------
def summary_tat_service(req_args):
    """Monthly TAT averages (6 hub segments). Group by year/month."""
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
                DATE_DIFF_AVG([EIDMaster.SpecimenDatetime, EIDMaster.LIMSPreReg_ReceivedDateTime]).label("collection_receiveHub"),
                DATE_DIFF_AVG([EIDMaster.LIMSPreReg_ReceivedDateTime, EIDMaster.LIMSPreReg_RegistrationDateTime]).label("receiveHub_registrationHub"),
                DATE_DIFF_AVG([EIDMaster.LIMSPreReg_RegistrationDateTime, EIDMaster.ReceivedDateTime]).label("registrationHub_receiveLab"),
                DATE_DIFF_AVG([EIDMaster.ReceivedDateTime, EIDMaster.RegisteredDateTime]).label("receiveLab_registrationLab"),
                DATE_DIFF_AVG([EIDMaster.RegisteredDateTime, EIDMaster.AnalysisDateTime]).label("registrationLab_analyseLab"),
                DATE_DIFF_AVG([EIDMaster.AnalysisDateTime, EIDMaster.AuthorisedDateTime]).label("analyseLab_validationLab"),
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, 
                month=row[1], 
                month_name=row[2],
                collection_receiveHub=row.collection_receiveHub,
                receiveHub_registrationHub=row.receiveHub_registrationHub,
                registrationHub_receiveLab=row.registrationHub_receiveLab,
                receiveLab_registrationLab=row.receiveLab_registrationLab,
                registrationLab_analyseLab=row.registrationLab_analyseLab,
                analyseLab_validationLab=row.analyseLab_validationLab,
                start_date=dates[0],
                end_date=dates[1],
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 3. summary_tat_samples_service
# ---------------------------------------------------------------------------
def summary_tat_samples_service(req_args):
    """TAT distribution by time brackets for a specific category."""
    params = parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"
    # The request's category runs 0-5; the old table is keyed 1-6.
    category = params.category + 1

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
                start_date=dates[0],
                end_date=dates[1],
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 4. summary_positivity_service
# ---------------------------------------------------------------------------
def summary_positivity_service(req_args):
    """Monthly positivity: total tested, positive, negative counts. Filter by lab_type. Group by year/month."""
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
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, 
                month=row[1], 
                month_name=row[2],
                total=row.total, 
                positive=row.positive, 
                negative=row.negative,
                start_date=dates[0],
                end_date=dates[1],
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 5. summary_number_of_samples_service
# ---------------------------------------------------------------------------
def summary_number_of_samples_service(req_args):
    """Monthly sample counts. Filter by lab_type."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.RegisteredDateTime.between(dates[0], dates[1]),
        EIDMaster.RequestingProvinceName.isnot(None),
    ]
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
            dict(
                year=row.year, 
                month=row[1], 
                month_name=row[2], 
                total=row.total,
                start_date=dates[0],
                end_date=dates[1],
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 6. summary_indicators_by_province_service
# ---------------------------------------------------------------------------
def summary_indicators_by_province_service(req_args):
    """Indicators per province: total, tested, positive, conventional count, poc count."""
    parse_eid_params(req_args)
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        EIDMaster.RegisteredDateTime.between(dates[0], dates[1]),
        EIDMaster.RequestingProvinceName.isnot(None), 
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    try:
        query = (
            EIDMaster.query.with_entities(
                EIDMaster.RequestingProvinceName.label("province"),
                TOTAL_ALL,
                TOTAL_NOT_NULL(EIDMaster.AnalysisDateTime).label("tested"),
                TOTAL_IN(EIDMaster.PCR_Result, ["Positivo"]).label("conventional_positive"),
                TOTAL_IN(EIDMaster.PCR_Result, ["Negativo"]).label("conventional_negative"),
                TOTAL_IN(EIDMaster.PCR_Result, ["Indeterminado"]).label("conventional_indeterminate"),
                TOTAL_IN(EIDMaster.POC_Result, ["Positivo"]).label("poc_positive"),
                TOTAL_IN(EIDMaster.POC_Result, ["Negativo"]).label("poc_negative"),
                TOTAL_IN(EIDMaster.PCR_Result, ["Positivo", "Negativo"]).label("total_conventional"),
                TOTAL_IN(EIDMaster.POC_Result, ["Negativo", "Positivo"]).label("total_poc"),
            )
            .filter(and_(*filters))
            .group_by(EIDMaster.RequestingProvinceName)
            .order_by(EIDMaster.RequestingProvinceName)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()
        return [
            dict(
                province=row.province,
                total=row.total,
                tested=row.tested,
                conventional_positive=row.conventional_positive,
                conventional_negative=row.conventional_negative,
                conventional_indeterminate=row.conventional_indeterminate,
                total_conventional=row.total_conventional,
                poc_positive=row.poc_positive,
                poc_negative=row.poc_negative,
                total_poc=row.total_poc,
                start_date=dates[0],
                end_date=dates[1],
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 7. summary_samples_positivity_service
# ---------------------------------------------------------------------------
def summary_samples_positivity_service(req_args):
    """Positivity breakdown: total, positive, negative with gender splits."""
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
                TOTAL_ALL,
                POSITIVITY(EIDMaster.PCR_Result, "Positive").label("positive"),
                POSITIVITY(EIDMaster.PCR_Result, "Negative").label("negative"),
                func.count(
                    case((and_(EIDMaster.HL7SexCode == "F", EIDMaster.PCR_Result.like("%Positive%")), 1))
                ).label("female_positive"),
                func.count(
                    case((and_(EIDMaster.HL7SexCode == "M", EIDMaster.PCR_Result.like("%Positive%")), 1))
                ).label("male_positive"),
                func.count(
                    case((and_(EIDMaster.HL7SexCode == "F", EIDMaster.PCR_Result.like("%Negative%")), 1))
                ).label("female_negative"),
                func.count(
                    case((and_(EIDMaster.HL7SexCode == "M", EIDMaster.PCR_Result.like("%Negative%")), 1))
                ).label("male_negative"),
            )
            .filter(and_(*filters))
        )

        print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        row = query.one()


        return dict(
            total=row.total,
            positive=row.positive,
            negative=row.negative,
            female_positive=row.female_positive,
            male_positive=row.male_positive,
            female_negative=row.female_negative,
            male_negative=row.male_negative,
            start_date=dates[0],
            end_date=dates[1],
        )
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 8. summary_rejected_samples_by_month_service
# ---------------------------------------------------------------------------
def summary_rejected_samples_by_month_service(req_args):
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
            dict(
                year=row.year, 
                month=row[1], 
                month_name=row[2], 
                total=row.total,
                start_date=dates[0],
                end_date=dates[1],
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 9. summary_samples_by_equipment_service
# ---------------------------------------------------------------------------
def summary_samples_by_equipment_service(req_args):
    """Equipment counts: CAPCTM, ALINITY, M2000, C6800, PANTHER, MPIMA, MANUAL."""
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
                *equipment_entities,
            )
            .filter(and_(*filters))
        )
        data = query.all()
        return [
            dict(
                **{eq: getattr(row, eq) for eq in _EQUIPMENT_TYPES},
                start_date=dates[0],
                end_date=dates[1],
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 10. summary_samples_by_equipment_by_month_service
# ---------------------------------------------------------------------------
def summary_samples_by_equipment_by_month_service(req_args):
    """Equipment counts by year/month: CAPCTM, ALINITY, M2000, C6800, PANTHER, MPIMA, MANUAL."""
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
                year=row.year, 
                month=row[1], 
                month_name=row[2],
                **{eq: getattr(row, eq) for eq in _EQUIPMENT_TYPES},
                start_date=dates[0],
                end_date=dates[1],
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}
