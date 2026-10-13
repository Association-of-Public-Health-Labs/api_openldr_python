from utilities.utils import (
    PROCESS_COMMON_PARAMS_VL,
    YEAR, MONTH, DATE_PART, TOTAL_ALL, TOTAL_NOT_NULL, TOTAL_NULL,
    SUPPRESSION, GENDER_SUPPRESSION,
    and_, or_, func, case, text,
)
from db.database import db
from dict.models.laboratories_model import Laboratories
from hiv.vl.models.vl import VlData
from hiv.vl.services.vl_common import (
    date_between,
    date_between_inclusive,
    lab_code_filters,
    parse_vl_params,
    rejected_condition,
    rejection_lab_code,
    tat_averages,
    tat_filters,
    testing_location_filters,
    year_month_columns,
)


def _error(e):
    return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


def _build_facility_filters(facilities, facility_type):
    """Build facility filter conditions based on facility_type."""
    if not facilities:
        return []
    if facility_type == "province":
        return [VlData.TestingProvinceName.in_(facilities)]
    elif facility_type == "district":
        return [VlData.TestingDistrictName.in_(facilities)]
    elif facility_type == "health_facility":
        return [VlData.TestingFacilityName.in_(facilities)]
    return []


def _year_month_group_order(date_field):
    """Return (group_by, order_by) tuples for year/month grouping."""
    cols = [YEAR(date_field), MONTH(date_field), DATE_PART("month", date_field)]
    return cols, cols


def _suppression_entities():
    """Standard suppression with_entities columns."""
    return [
        SUPPRESSION(VlData.ViralLoadResultCategory, "Suppressed").label("suppressed"),
        SUPPRESSION(VlData.ViralLoadResultCategory, "Not Suppressed").label("not_suppressed"),
    ]


def _gender_suppression_entities():
    """Standard gender-stratified suppression columns."""
    return [
        GENDER_SUPPRESSION(
            [VlData.ViralLoadResultCategory, VlData.HL7SexCode],
            ["Suppressed", "M"],
        ).label("male_suppressed"),
        GENDER_SUPPRESSION(
            [VlData.ViralLoadResultCategory, VlData.HL7SexCode],
            ["Not Suppressed", "M"],
        ).label("male_not_suppressed"),
        GENDER_SUPPRESSION(
            [VlData.ViralLoadResultCategory, VlData.HL7SexCode],
            ["Suppressed", "F"],
        ).label("female_suppressed"),
        GENDER_SUPPRESSION(
            [VlData.ViralLoadResultCategory, VlData.HL7SexCode],
            ["Not Suppressed", "F"],
        ).label("female_not_suppressed"),
    ]


def _totals_entities():
    """Standard total/not_null/null columns."""
    return [
        TOTAL_ALL,
        TOTAL_NOT_NULL(VlData.ViralLoadResultCategory).label("total_not_null"),
        TOTAL_NULL(VlData.ViralLoadResultCategory).label("total_null"),
    ]



# ---------------------------------------------------------------------------
# 1. registered_samples_service
# ---------------------------------------------------------------------------
def registered_samples_service(req_args):
    """Registered samples grouped by year/month with suppression and gender splits."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        VlData.RegisteredDateTime.between(dates[0], dates[1]),
        VlData.RegisteredDateTime.isnot(None),
        VlData.TestingFacilityName.isnot(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    try:
        query = (
            VlData.query.with_entities(
                VlData.TestingFacilityName.label("testing_facility"),
                *_suppression_entities(),
                *_gender_suppression_entities(),
                *_totals_entities(),
            )
            .filter(and_(*filters))
            .group_by(VlData.TestingFacilityName)
            .order_by(VlData.TestingFacilityName)
        )

        data = query.all()
        return [
            dict(
                testing_facility=row.testing_facility,
                total_not_null=row.total_not_null,
                total_null=row.total_null, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
                male_suppressed=row.male_suppressed,
                male_not_suppressed=row.male_not_suppressed,
                female_suppressed=row.female_suppressed,
                female_not_suppressed=row.female_not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 2. registered_samples_by_month_service
# ---------------------------------------------------------------------------
def registered_samples_by_month_service(req_args):
    """Registered samples grouped by year/month AND TestingFacilityName."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        VlData.RegisteredDateTime.between(dates[0], dates[1]),
        VlData.RegisteredDateTime.isnot(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    group_cols, order_cols = _year_month_group_order(VlData.RegisteredDateTime)

    try:
        query = (
            VlData.query.with_entities(
                *group_cols,
                VlData.TestingFacilityName.label("testing_facility"),
                *_suppression_entities(),
                *_gender_suppression_entities(),
                *_totals_entities(),
            )
            .filter(and_(*filters))
            .group_by(*group_cols, VlData.TestingFacilityName)
            .order_by(*order_cols, VlData.TestingFacilityName)
        )
        data = query.all()
        return [
            dict(
                year=row.year, month=row[1], month_name=row[2],
                testing_facility=row.testing_facility,
                total=row.total, total_not_null=row.total_not_null,
                total_null=row.total_null, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
                male_suppressed=row.male_suppressed,
                male_not_suppressed=row.male_not_suppressed,
                female_suppressed=row.female_suppressed,
                female_not_suppressed=row.female_not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}

# ---------------------------------------------------------------------------
# 3. tested_samples_service   (legacy /lab_samples_tested_by_lab)
# ---------------------------------------------------------------------------
def tested_samples_service(req_args):
    """Tested samples per lab; conventional labs only unless filtered."""
    params = parse_vl_params(req_args)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        VlData.TestingFacilityName.is_not(None),
        *testing_location_filters(params),
        *lab_code_filters(params, conventional_default=True),
    ]
    try:
        data = (
            VlData.query.with_entities(
                VlData.TestingFacilityName.label("testing_facility"),
                *_suppression_entities(),
                *_totals_entities(),
            )
            .filter(and_(*filters))
            .group_by(VlData.TestingFacilityName)
            .order_by(VlData.TestingFacilityName)
            .all()
        )
        return [
            dict(
                testing_facility=row.testing_facility,
                total=row.total, total_not_null=row.total_not_null,
                total_null=row.total_null, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 4. tested_samples_by_month_service   (legacy /lab_samples_tested_by_month)
# ---------------------------------------------------------------------------
def tested_samples_by_month_service(req_args):
    """Tested samples per month; no conventional-lab default (as in Node)."""
    params = parse_vl_params(req_args)
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *testing_location_filters(params),
        *lab_code_filters(params, conventional_default=False),
    ]
    try:
        data = (
            VlData.query.with_entities(
                *month_cols,
                *_suppression_entities(),
                *_gender_suppression_entities(),
                *_totals_entities(),
            )
            .filter(and_(*filters))
            .group_by(*month_cols)
            .order_by(month_cols[0], month_cols[1])
            .all()
        )
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                total=row.total, total_not_null=row.total_not_null,
                total_null=row.total_null, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
                male_suppressed=row.male_suppressed,
                male_not_suppressed=row.male_not_suppressed,
                female_suppressed=row.female_suppressed,
                female_not_suppressed=row.female_not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 5. tested_samples_by_gender_service
# ---------------------------------------------------------------------------
def tested_samples_by_gender_service(req_args):
    """Tested samples grouped by year/month with gender-stratified suppression."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        VlData.AnalysisDateTime.between(dates[0], dates[1]),
        VlData.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    group_cols, order_cols = _year_month_group_order(VlData.AnalysisDateTime)

    try:
        query = (
            VlData.query.with_entities(
                *group_cols,
                *_gender_suppression_entities(),
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, month=row[1], month_name=row[2],
                male_suppressed=row.male_suppressed,
                male_not_suppressed=row.male_not_suppressed,
                female_suppressed=row.female_suppressed,
                female_not_suppressed=row.female_not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 6. tested_samples_by_gender_by_lab_service
# ---------------------------------------------------------------------------
def tested_samples_by_gender_by_lab_service(req_args):
    """Tested samples grouped by year/month and TestingFacilityName with gender splits."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        VlData.AnalysisDateTime.between(dates[0], dates[1]),
        VlData.AnalysisDateTime.is_not(None),
        VlData.TestingFacilityName.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    try:
        query = (
            VlData.query.with_entities(
                VlData.TestingFacilityName.label("testing_facility"),
                *_gender_suppression_entities(),
            )
            .filter(and_(*filters))
            .group_by(VlData.TestingFacilityName)
            .order_by(VlData.TestingFacilityName)
        )
        data = query.all()
        return [
            dict(
                testing_facility=row.testing_facility,
                male_suppressed=row.male_suppressed,
                male_not_suppressed=row.male_not_suppressed,
                female_suppressed=row.female_suppressed,
                female_not_suppressed=row.female_not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 7. tested_samples_by_age_service
# ---------------------------------------------------------------------------
def tested_samples_by_age_service(req_args):
    """Tested samples grouped by year/month with age group classification."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        VlData.AnalysisDateTime.between(dates[0], dates[1]),
        VlData.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    age_case = case(
        (VlData.AgeInYears.between(0, 14), "0-14"),
        (VlData.AgeInYears.between(15, 19), "15-19"),
        (VlData.AgeInYears.between(20, 24), "20-24"),
        (VlData.AgeInYears.between(25, 29), "25-29"),
        (VlData.AgeInYears.between(30, 34), "30-34"),
        (VlData.AgeInYears.between(35, 39), "35-39"),
        (VlData.AgeInYears.between(40, 44), "40-44"),
        (VlData.AgeInYears.between(45, 49), "45-49"),
        (VlData.AgeInYears >= 50, "50+"),
        else_="Unknown",
    ).label("age_group")

    try:
        # Use subquery to work around SQL Server parameterized CASE in GROUP BY
        subq = (
            db.session.query(
                VlData.AnalysisDateTime,
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


# ---------------------------------------------------------------------------
# 8. tested_samples_by_test_reason_service
# ---------------------------------------------------------------------------
def tested_samples_by_test_reason_service(req_args):
    """Tested samples grouped by year/month with test reason counts."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        VlData.AnalysisDateTime.between(dates[0], dates[1]),
        VlData.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    group_cols, order_cols = _year_month_group_order(VlData.AnalysisDateTime)

    try:
        query = (
            VlData.query.with_entities(
                *group_cols,
                func.count(case((VlData.ReasonForTest == "Routine", 1))).label("routine"),
                func.count(case((
                    VlData.ReasonForTest.in_([
                        "Suspected treatment failure",
                        "Suspeita de falha terapêutica",
                    ]), 1
                ))).label("treatment_failure"),
                func.count(case((
                    VlData.ReasonForTest.in_([
                        "Não preenchido",
                        "Reason Not Specified",
                    ]), 1
                ))).label("reason_not_specified"),
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, month=row[1], month_name=row[2],
                routine=row.routine, treatment_failure=row.treatment_failure,
                reason_not_specified=row.reason_not_specified, total=row.total,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 9. tested_samples_pregnant_service
# ---------------------------------------------------------------------------
def tested_samples_pregnant_service(req_args):
    """Tested samples for pregnant women grouped by year/month."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        VlData.AnalysisDateTime.between(dates[0], dates[1]),
        VlData.AnalysisDateTime.is_not(None),
        VlData.Pregnant == "Yes",
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    group_cols, order_cols = _year_month_group_order(VlData.AnalysisDateTime)

    try:
        query = (
            VlData.query.with_entities(
                *group_cols,
                *_suppression_entities(),
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, month=row[1], month_name=row[2],
                total=row.total, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}


# ---------------------------------------------------------------------------
# 10. tested_samples_breastfeeding_service
# ---------------------------------------------------------------------------
def tested_samples_breastfeeding_service(req_args):
    """Tested samples for breastfeeding women grouped by year/month."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        VlData.AnalysisDateTime.between(dates[0], dates[1]),
        VlData.AnalysisDateTime.is_not(None),
        VlData.BreastFeeding == "Yes",
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    group_cols, order_cols = _year_month_group_order(VlData.AnalysisDateTime)

    try:
        query = (
            VlData.query.with_entities(
                *group_cols,
                *_suppression_entities(),
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, month=row[1], month_name=row[2],
                total=row.total, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}

# ---------------------------------------------------------------------------
# 11. rejected_samples_service   (legacy /lab_samples_rejected)
# ---------------------------------------------------------------------------
def lab_names(codes):
    """Map lab codes to their dictionary LabName, skipping blank names."""
    wanted = sorted({code.strip() for code in codes if code and code.strip()})
    if not wanted:
        return {}
    rows = (
        Laboratories.query.with_entities(Laboratories.LabCode, Laboratories.LabName)
        .filter(
            Laboratories.LabCode.in_(wanted),
            Laboratories.LabName.is_not(None),
            Laboratories.LabName != "",
        )
        .all()
    )
    return {row.LabCode.strip(): row.LabName.strip() for row in rows}


def _rejection_filters(params):
    filters = [
        rejected_condition(),
        date_between_inclusive(VlData.RegisteredDateTime, params.dates),
        *testing_location_filters(params),
    ]
    if params.lab_codes:
        filters.append(rejection_lab_code().in_(params.lab_codes))
    return filters


def rejected_samples_service(req_args):
    """Rejected samples per lab code (characters 7-9 of RequestID).

    Names come from the dictionary database in a second query (no
    cross-database join). Codes with no named lab are dropped, as Node's
    INNER JOIN does.
    """
    params = parse_vl_params(req_args)
    lab_code = rejection_lab_code()
    filters = _rejection_filters(params)
    try:
        rows = (
            VlData.query.with_entities(lab_code.label("lab_code"), TOTAL_ALL)
            .filter(and_(*filters))
            .group_by(lab_code)
            .all()
        )
        names = lab_names([row.lab_code for row in rows])
        result = []
        for row in rows:
            code = (row.lab_code or "").strip()
            if code in names:
                result.append(dict(lab_code=code, testing_facility=names[code], total=row.total))
        return sorted(result, key=lambda item: (item["testing_facility"], item["lab_code"]))
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 12. rejected_samples_by_month_service   (legacy /lab_samples_rejected_by_month)
# ---------------------------------------------------------------------------
def rejected_samples_by_month_service(req_args):
    """Rejected samples per registration month (end date inclusive)."""
    params = parse_vl_params(req_args)
    month_cols = year_month_columns(VlData.RegisteredDateTime)
    filters = _rejection_filters(params)
    try:
        data = (
            VlData.query.with_entities(*month_cols, TOTAL_ALL)
            .filter(and_(*filters))
            .group_by(*month_cols)
            .order_by(month_cols[0], month_cols[1])
            .all()
        )
        return [
            dict(year=row.year, month=row.month, month_name=row.month_name, total=row.total)
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 13. tat_by_lab_service   (legacy /lab_tat)
# ---------------------------------------------------------------------------
def tat_by_lab_service(req_args):
    """TAT per lab; ✱ no 90-day cap; conventional labs only unless filtered."""
    params = parse_vl_params(req_args)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *tat_filters(),
        *testing_location_filters(params),
        *lab_code_filters(params, conventional_default=True),
    ]
    try:
        data = (
            VlData.query.with_entities(
                VlData.TestingFacilityName.label("testing_facility"),
                *tat_averages(),
            )
            .filter(and_(*filters))
            .group_by(VlData.TestingFacilityName)
            .order_by(VlData.TestingFacilityName)
            .all()
        )
        return [
            dict(
                testing_facility=row.testing_facility,
                collection_reception=row.collection_reception,
                reception_registration=row.reception_registration,
                registration_analysis=row.registration_analysis,
                analysis_validation=row.analysis_validation,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# 14. tat_by_month_service   (legacy /lab_tat_by_month)
# ---------------------------------------------------------------------------
def tat_by_month_service(req_args):
    """TAT per month; ✱ no 90-day cap; conventional labs only unless filtered."""
    params = parse_vl_params(req_args)
    month_cols = year_month_columns(VlData.AnalysisDateTime)
    filters = [
        date_between(VlData.AnalysisDateTime, params.dates),
        *tat_filters(),
        *testing_location_filters(params),
        *lab_code_filters(params, conventional_default=True),
    ]
    try:
        data = (
            VlData.query.with_entities(*month_cols, *tat_averages())
            .filter(and_(*filters))
            .group_by(*month_cols)
            .order_by(month_cols[0], month_cols[1])
            .all()
        )
        return [
            dict(
                year=row.year, month=row.month, month_name=row.month_name,
                collection_reception=row.collection_reception,
                reception_registration=row.reception_registration,
                registration_analysis=row.registration_analysis,
                analysis_validation=row.analysis_validation,
            )
            for row in data
        ]
    except Exception as e:
        return _error(e)



# ---------------------------------------------------------------------------
# 15. suppression_service
# ---------------------------------------------------------------------------
def suppression_service(req_args):
    """Monthly suppression trend (suppressed, not_suppressed, total)."""
    dates, facilities, facility_type, disaggregation, health_facility = PROCESS_COMMON_PARAMS_VL(req_args)

    filters = [
        VlData.AnalysisDateTime.between(dates[0], dates[1]),
        VlData.AnalysisDateTime.is_not(None),
    ]
    filters.extend(_build_facility_filters(facilities, facility_type))

    group_cols, order_cols = _year_month_group_order(VlData.AnalysisDateTime)

    try:
        query = (
            VlData.query.with_entities(
                *group_cols,
                *_suppression_entities(),
                TOTAL_ALL,
            )
            .filter(and_(*filters))
            .group_by(*group_cols)
            .order_by(*order_cols)
        )
        data = query.all()
        return [
            dict(
                year=row.year, month=row[1], month_name=row[2],
                total=row.total, suppressed=row.suppressed,
                not_suppressed=row.not_suppressed,
            )
            for row in data
        ]
    except Exception as e:
        return {"status": "error", "code": 500, "message": "An Error Occurred", "error": str(e)}
