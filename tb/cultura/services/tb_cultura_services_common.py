from sqlalchemy import and_, case, func, text

from auth.auth_service import get_user_by_id_service
from tb.cultura.models.tb_cultura_model import TBCultura
from utilities.utils import (
    DATE_PART,
    GET_COLUMN_NAME,
    LAB_TYPE,
    MONTH,
    PROCESS_COMMON_PARAMS_FACILITY,
    YEAR,
)


CULTURE_POSITIVE_VALUES = (
    "POSITIVE",
    "MTB DETECTED",
    "DETECTED",
    "MTB COMPLEX DETECTED",
    "GROWTH",
)
CULTURE_NEGATIVE_VALUES = (
    "NEGATIVE",
    "NO GROWTH",
    "MTB NOT DETECTED",
    "NOT DETECTED",
)
RESISTANCE_DETECTED_VALUES = (
    "DETECTED",
    "RESISTANCE DETECTED",
    "RESISTANT",
    "R",
)
RESISTANCE_NOT_DETECTED_VALUES = (
    "NOT DETECTED",
    "RESISTANCE NOT DETECTED",
    "SUSCEPTIBLE",
    "S",
)


def get_request_context(req_args):
    (
        dates,
        disaggregation,
        facility_type,
        result_type,
        facilities,
        lab_type,
        health_facility,
    ) = PROCESS_COMMON_PARAMS_FACILITY(req_args)

    user_id = req_args.get("user_id")
    user_role = "Unknown"
    if user_id is not None:
        user = get_user_by_id_service(user_id)
        user_role = user.role if user else "Unknown"

    return {
        "dates": dates,
        "disaggregation": disaggregation,
        "facility_type": facility_type,
        "result_type": result_type,
        "facilities": [f.strip() for f in (facilities or []) if f and f.strip()],
        "lab_type": lab_type or "All",
        "health_facility": health_facility,
        "user_role": user_role,
    }


def error_payload(exc):
    return {
        "status": "error",
        "code": 500,
        "message": "An Error Occurred",
        "error": str(exc),
    }


def culture_result_expression():
    return func.upper(
        func.coalesce(
            TBCultura.FinalMGITCultureResult,
            TBCultura.FinalLJCultureResult,
            TBCultura.InterpretedLiquidCultureResult,
            TBCultura.InterpretedSolidCultureResult,
            TBCultura.LiquidCultureResult,
            TBCultura.SolidCultureResult,
            "",
        )
    )


def count_if(condition, label):
    return func.count(case((condition, 1), else_=None)).label(label)


def count_not_null(column, label):
    return func.count(case((column.isnot(None), 1), else_=None)).label(label)


def base_filters(ctx, *, date_column=None, facility_flag=None):
    date_column = date_column or TBCultura.RegisteredDateTime
    filters = [date_column.between(ctx["dates"][0], ctx["dates"][1])]

    facilities = ctx["facilities"]
    if facilities and facility_flag:
        filters.append(
            GET_COLUMN_NAME(
                False,
                ctx["facility_type"],
                TBCultura,
                facility_flag,
            ).in_(facilities)
        )

    lab_type = ctx["lab_type"]
    if lab_type and lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBCultura, lab_type))

    return filters


def common_response_fields(ctx):
    return {
        "Start_Date": ctx["dates"][0],
        "End_Date": ctx["dates"][1],
        "Disaggregation": ctx["disaggregation"],
        "Facility_Type": ctx["facility_type"],
        "Facilities": ctx["facilities"],
        "Lab": ctx["lab_type"],
        "Role": ctx["user_role"],
    }


def culture_result_columns():
    result_expr = culture_result_expression()
    return [
        count_if(result_expr.in_(CULTURE_POSITIVE_VALUES), "Positive"),
        count_if(result_expr.in_(CULTURE_NEGATIVE_VALUES), "Negative"),
        count_if(result_expr.like("%CONTAM%"), "Contaminated"),
        count_if(
            and_(
                TBCultura.LIMSRejectionCode.is_(None),
                TBCultura.AuthorisedDateTime.is_(None),
            ),
            "Pending",
        ),
        count_if(TBCultura.LIMSRejectionCode.isnot(None), "Rejected"),
    ]


def tat_days():
    return func.datediff(
        text("day"),
        TBCultura.SpecimenDateTime,
        TBCultura.AuthorisedDateTime,
    )
