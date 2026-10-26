from utilities.utils import (
    PROCESS_COMMON_PARAMS_VL,
    YEAR, MONTH, DATE_PART, TOTAL_ALL,
    POSITIVITY, LAB_TYPE_EID, DATE_DIFF_AVG,
    and_, or_, func, case, text,
)
from db.database import db
from hiv.eid.models.eid_master_model import EIDMaster


def _build_facility_filters(facilities, facility_type):
    """Build facility filter conditions based on facility_type (Requesting* columns)."""
    if not facilities:
        return []
    if facility_type == "province":
        return [EIDMaster.RequestingProvinceName.in_(facilities)]
    elif facility_type == "district":
        return [EIDMaster.RequestingDistrictName.in_(facilities)]
    elif facility_type == "health_facility":
        return [EIDMaster.RequestingFacilityName.in_(facilities)]
    return []


def _get_group_column(disaggregation, facility_type):
    """Determine the grouping column based on disaggregation and facility_type."""
    if disaggregation:
        if facility_type == "province":
            return EIDMaster.RequestingDistrictName
        elif facility_type == "district":
            return EIDMaster.RequestingFacilityName
        else:
            return EIDMaster.RequestingProvinceName
    else:
        if facility_type == "province":
            return EIDMaster.RequestingProvinceName
        elif facility_type == "district":
            return EIDMaster.RequestingDistrictName
        else:
            return EIDMaster.RequestingFacilityName


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
# 1. facility_registered_samples_service
# ---------------------------------------------------------------------------
def facility_registered_samples_service(req_args):
    """Registered samples grouped by requesting facility (with disaggregation)."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [EIDMaster.RegisteredDateTime.between(dates[0], dates[1])]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_col = _get_group_column(disaggregation, facility_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                group_col.label("requesting_facility"),
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(group_col)
            .order_by(group_col)
        )
        data = query.all()
        return [
            dict(requesting_facility=row.requesting_facility, total=row.total)
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 2. facility_registered_samples_by_month_service
# ---------------------------------------------------------------------------
def facility_registered_samples_by_month_service(req_args):
    """Registered samples grouped by year/month (facility)."""
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
# 3. facility_tested_samples_service
# ---------------------------------------------------------------------------
def facility_tested_samples_service(req_args):
    """Tested samples grouped by requesting facility with positivity."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_col = _get_group_column(disaggregation, facility_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                group_col.label("requesting_facility"),
                TOTAL_ALL,
                *_positivity_entities(),
            )
            .filter(and_(*filters))
            .group_by(group_col)
            .order_by(group_col)
        )
        data = query.all()
        return [
            dict(
                requesting_facility=row.requesting_facility,
                total=row.total, positive=row.positive, negative=row.negative,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 4. facility_tested_samples_by_month_service
# ---------------------------------------------------------------------------
def facility_tested_samples_by_month_service(req_args):
    """Tested samples grouped by year/month with positivity and gender (facility)."""
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
# 5. facility_tested_samples_by_gender_service
# ---------------------------------------------------------------------------
def facility_tested_samples_by_gender_service(req_args):
    """Tested samples grouped by requesting facility with gender counts."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_col = _get_group_column(disaggregation, facility_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                group_col.label("requesting_facility"),
                TOTAL_ALL,
                *_gender_entities(),
            )
            .filter(and_(*filters))
            .group_by(group_col)
            .order_by(group_col)
        )
        data = query.all()
        return [
            dict(
                requesting_facility=row.requesting_facility,
                total=row.total, female=row.female, male=row.male,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 6. facility_tested_samples_by_gender_by_month_service
# ---------------------------------------------------------------------------
def facility_tested_samples_by_gender_by_month_service(req_args):
    """Tested samples grouped by year/month with gender counts (facility)."""
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
                total=row.total, female=row.female, male=row.male,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 7. facility_tat_avg_by_month_service
# ---------------------------------------------------------------------------
def facility_tat_avg_by_month_service(req_args):
    """Average TAT (6 hub-chain segments) grouped by year/month (facility)."""
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
                year=row.year, month=row[1], month_name=row[2],
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
# 8. facility_tat_avg_service
# ---------------------------------------------------------------------------
def facility_tat_avg_service(req_args):
    """Average TAT (6 hub-chain segments) grouped by requesting facility."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_col = _get_group_column(disaggregation, facility_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                group_col.label("requesting_facility"),
                DATE_DIFF_AVG([EIDMaster.SpecimenDatetime, EIDMaster.LIMSPreReg_ReceivedDateTime]).label("collection_receiveHub"),
                DATE_DIFF_AVG([EIDMaster.LIMSPreReg_ReceivedDateTime, EIDMaster.LIMSPreReg_RegistrationDateTime]).label("receiveHub_registrationHub"),
                DATE_DIFF_AVG([EIDMaster.LIMSPreReg_RegistrationDateTime, EIDMaster.ReceivedDateTime]).label("registrationHub_receiveLab"),
                DATE_DIFF_AVG([EIDMaster.ReceivedDateTime, EIDMaster.RegisteredDateTime]).label("receiveLab_registrationLab"),
                DATE_DIFF_AVG([EIDMaster.RegisteredDateTime, EIDMaster.AnalysisDateTime]).label("registrationLab_analyseLab"),
                DATE_DIFF_AVG([EIDMaster.AnalysisDateTime, EIDMaster.AuthorisedDateTime]).label("analyseLab_validationLab"),
            )
            .filter(and_(*filters))
            .group_by(group_col)
            .order_by(group_col)
        )
        data = query.all()
        return [
            dict(
                requesting_facility=row.requesting_facility,
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
# 9. facility_tat_days_by_month_service
# ---------------------------------------------------------------------------
def facility_tat_days_by_month_service(req_args):
    """TAT in day brackets (<7, 7-15, 16-21, >21) grouped by year/month (facility)."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_cols, order_cols = _year_month_group_order(EIDMaster.AnalysisDateTime)
    diff_expr = func.datediff(text("day"), EIDMaster.SpecimenDatetime, EIDMaster.AnalysisDateTime)

    try:
        query = (
            EIDMaster.query.with_entities(
                *group_cols,
                func.count(case((diff_expr < 7, 1))).label("less_7"),
                func.count(case((and_(diff_expr >= 7, diff_expr <= 15), 1))).label("between_7_15"),
                func.count(case((and_(diff_expr >= 16, diff_expr <= 21), 1))).label("between_16_21"),
                func.count(case((diff_expr > 21, 1))).label("greater_21"),
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, month=row[1], month_name=row[2],
                less_7=row.less_7, between_7_15=row.between_7_15,
                between_16_21=row.between_16_21, greater_21=row.greater_21,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 10. facility_tat_days_service
# ---------------------------------------------------------------------------
def facility_tat_days_service(req_args):
    """TAT in day brackets (<7, 7-15, 16-21, >21) grouped by requesting facility."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_col = _get_group_column(disaggregation, facility_type)
    diff_expr = func.datediff(text("day"), EIDMaster.SpecimenDatetime, EIDMaster.AnalysisDateTime)

    try:
        query = (
            EIDMaster.query.with_entities(
                group_col.label("requesting_facility"),
                func.count(case((diff_expr < 7, 1))).label("less_7"),
                func.count(case((and_(diff_expr >= 7, diff_expr <= 15), 1))).label("between_7_15"),
                func.count(case((and_(diff_expr >= 16, diff_expr <= 21), 1))).label("between_16_21"),
                func.count(case((diff_expr > 21, 1))).label("greater_21"),
            )
            .filter(and_(*filters))
            .group_by(group_col)
            .order_by(group_col)
        )
        data = query.all()
        return [
            dict(
                requesting_facility=row.requesting_facility,
                less_7=row.less_7, between_7_15=row.between_7_15,
                between_16_21=row.between_16_21, greater_21=row.greater_21,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 11. facility_rejected_samples_by_month_service
# ---------------------------------------------------------------------------
def facility_rejected_samples_by_month_service(req_args):
    """Rejected samples grouped by year/month (facility)."""
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
# 12. facility_rejected_samples_service
# ---------------------------------------------------------------------------
def facility_rejected_samples_service(req_args):
    """Rejected samples grouped by requesting facility (with disaggregation)."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        and_(EIDMaster.LIMSRejectionCode.is_not(None), EIDMaster.LIMSRejectionCode != ""),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_col = _get_group_column(disaggregation, facility_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                group_col.label("requesting_facility"),
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(group_col)
            .order_by(group_col)
        )
        data = query.all()
        return [
            dict(requesting_facility=row.requesting_facility, total=row.total)
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 13. facility_key_indicators_service
# ---------------------------------------------------------------------------
def facility_key_indicators_service(req_args):
    """Key indicators: registered, tested, rejected, pending, positive, negative."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [EIDMaster.RegisteredDateTime.between(dates[0], dates[1])]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_col = _get_group_column(disaggregation, facility_type)

    try:
        query = (
            EIDMaster.query.with_entities(
                group_col.label("requesting_facility"),
                TOTAL_ALL.label("registered"),
                func.count(case((EIDMaster.AnalysisDateTime.is_not(None), 1))).label("tested"),
                func.count(case((and_(EIDMaster.LIMSRejectionCode.is_not(None), EIDMaster.LIMSRejectionCode != ""), 1))).label("rejected"),
                func.count(case((EIDMaster.AnalysisDateTime.is_(None), 1))).label("pending"),
                POSITIVITY(EIDMaster.PCR_Result, "Positive").label("positive"),
                POSITIVITY(EIDMaster.PCR_Result, "Negative").label("negative"),
            )
            .filter(and_(*filters))
            .group_by(group_col)
            .order_by(group_col)
        )
        data = query.all()
        return [
            dict(
                requesting_facility=row.requesting_facility,
                registered=row.registered, tested=row.tested,
                rejected=row.rejected, pending=row.pending,
                positive=row.positive, negative=row.negative,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 14. facility_tested_samples_by_age_service
# ---------------------------------------------------------------------------
def facility_tested_samples_by_age_service(req_args):
    """Tested samples grouped by year/month and EID age groups (using AgeInDays)."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)
    lab_type = req_args.get("lab_type") or "all"

    filters = [
        EIDMaster.AnalysisDateTime.between(dates[0], dates[1]),
        EIDMaster.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))
    _apply_lab_type_filter(filters, lab_type)

    group_cols, order_cols = _year_month_group_order(EIDMaster.AnalysisDateTime)

    # EID age groups based on AgeInDays:
    # 0-2 months (~0-60 days), 2-9 months (~61-270 days),
    # 9-18 months (~271-540 days), 18+ months (>540 days)
    age_case = case(
        (EIDMaster.AgeInDays.between(0, 60), "0-2 months"),
        (EIDMaster.AgeInDays.between(61, 270), "2-9 months"),
        (EIDMaster.AgeInDays.between(271, 540), "9-18 months"),
        (EIDMaster.AgeInDays > 540, "18+ months"),
        else_="Unknown",
    ).label("age_group")

    try:
        # Use subquery to work around SQL Server parameterized CASE in GROUP BY
        subq = (
            db.session.query(
                EIDMaster.AnalysisDateTime,
                age_case,
            )
            .filter(and_(*filters))
            .subquery()
        )
        query = (
            db.session.query(
                func.year(subq.c.AnalysisDateTime).label("year"),
                func.month(subq.c.AnalysisDateTime),
                func.datename(text("month"), subq.c.AnalysisDateTime),
                subq.c.age_group,
                func.count().label("total"),
            )
            .group_by(
                func.year(subq.c.AnalysisDateTime),
                func.month(subq.c.AnalysisDateTime),
                func.datename(text("month"), subq.c.AnalysisDateTime),
                subq.c.age_group,
            )
            .order_by(
                func.year(subq.c.AnalysisDateTime),
                func.month(subq.c.AnalysisDateTime),
                subq.c.age_group,
            )
        )
        data = query.all()
        return [
            dict(
                year=row[0], month=row[1], month_name=row[2],
                age_group=row.age_group, total=row.total,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}
