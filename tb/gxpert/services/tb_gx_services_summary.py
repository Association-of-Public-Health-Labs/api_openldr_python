from tb.gxpert.models.tb_gx_model import TBMaster
from utilities.utils import *
from sqlalchemy import and_, func, case, text
from auth.auth_service import get_user_by_id_service


def dashboard_header_component_summary_service(req_args):
    """
    Retrieve the number of tested samples by lab
    """
    (
        dates,
        disaggregation,
        facility_type,
        gx_result_type,
        facilities,
        lab,
        health_facility,
    ) = PROCESS_COMMON_PARAMS_FACILITY(req_args)

    user_id = req_args.get("user_id")

    try:
        user = get_user_by_id_service(user_id)
    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": "An Error Occurred",
            "error": str(e),
        }

    user_role = user.role if user else "Unknown"

    try:
        query = TBMaster.query.with_entities(
            func.count(
                case((TBMaster.TypeOfResult == "Ultra 6 Cores", 1), else_=None)
            ).label("Registered_Samples_Ultra_6_Cores"),
            func.count(
                case((TBMaster.TypeOfResult == "XDR 10 Cores", 1), else_=None)
            ).label("Registered_Samples_XDR_10_Cores"),
            func.count(
                case((TBMaster.TypeOfResult == "Ultra 6 Cores", 1), else_=None)
            ).label("Analyzed_Samples_Ultra_6_Cores"),
            func.count(
                case((TBMaster.TypeOfResult == "XDR 10 Cores", 1), else_=None)
            ).label("Analyzed_Samples_XDR_10_Cores"),
            func.count(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "Ultra 6 Cores",
                            TBMaster.FinalResult.in_(FINAL_RESULT_DETECTED_VALUES),
                        ),
                        1,
                    ),
                    else_=None,
                )
            ).label("Detected_Samples_Ultra_6_Cores"),
            func.count(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "XDR 10 Cores",
                            TBMaster.FinalResult.in_(FINAL_RESULT_DETECTED_VALUES),
                        ),
                        1,
                    ),
                    else_=None,
                )
            ).label("Detected_Samples_XDR_10_Cores"),
            func.count(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "Ultra 6 Cores",
                            TBMaster.FinalResult.in_(FINAL_RESULT_NOT_DETECTED_VALUES),
                        ),
                        1,
                    ),
                    else_=None,
                )
            ).label("Not_Detected_Samples_Ultra_6_Cores"),
            func.count(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "XDR 10 Cores",
                            TBMaster.FinalResult.in_(FINAL_RESULT_NOT_DETECTED_VALUES),
                        ),
                        1,
                    ),
                    else_=None,
                )
            ).label("Not_Detected_Samples_XDR_10_Cores"),
            func.avg(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "Ultra 6 Cores",
                            TBMaster.SpecimenDatetime.isnot(None),
                        ),
                        func.datediff(
                            text("day"),
                            TBMaster.SpecimenDatetime,
                            TBMaster.AuthorisedDateTime,
                        ),
                    ),
                    else_=None,
                )
            ).label("Avg_Response_Time_Days_Ultra_6_Cores_Collection_To_Validation"),
            func.avg(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "XDR 10 Cores",
                            TBMaster.SpecimenDatetime.isnot(None),
                        ),
                        func.datediff(
                            text("day"),
                            TBMaster.SpecimenDatetime,
                            TBMaster.AuthorisedDateTime,
                        ),
                    ),
                    else_=None,
                )
            ).label("Avg_Response_Time_Days_XDR_10_Cores_Collection_To_Validation"),
            func.count(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "Ultra 6 Cores",
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_ERROR_DETECTED_VALUES
                            ),
                        ),
                        1,
                    ),
                    else_=None,
                )
            ).label("Errors_Ultra_6_Cores"),
            func.count(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "XDR 10 Cores",
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_ERROR_DETECTED_VALUES
                            ),
                        ),
                        1,
                    ),
                    else_=None,
                )
            ).label("Errors_XDR_10_Cores"),
            func.count(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "Ultra 6 Cores",
                            TBMaster.FinalResult.in_(FINAL_RESULT_INVALID_VALUES),
                        ),
                        1,
                    ),
                    else_=None,
                )
            ).label("Invalid_Ultra_6_Cores"),
            func.count(
                case(
                    (
                        and_(
                            TBMaster.TypeOfResult == "XDR 10 Cores",
                            TBMaster.FinalResult.in_(FINAL_RESULT_INVALID_VALUES),
                        ),
                        1,
                    ),
                    else_=None,
                )
            ).label("Invalid_XDR_10_Cores"),
        ).filter(TBMaster.RegisteredDateTime.between(dates[0], dates[1]))

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Registered_Samples_Ultra_6_Cores": row.Registered_Samples_Ultra_6_Cores,
                "Registered_Samples_XDR_10_Cores": row.Registered_Samples_XDR_10_Cores,
                "Analyzed_Samples_Ultra_6_Cores": row.Analyzed_Samples_Ultra_6_Cores,
                "Analyzed_Samples_XDR_10_Cores": row.Analyzed_Samples_XDR_10_Cores,
                "Detected_Samples_Ultra_6_Cores": row.Detected_Samples_Ultra_6_Cores,
                "Detected_Samples_XDR_10_Cores": row.Detected_Samples_XDR_10_Cores,
                "Not_Detected_Samples_Ultra_6_Cores": row.Not_Detected_Samples_Ultra_6_Cores,
                "Not_Detected_Samples_XDR_10_Cores": row.Not_Detected_Samples_XDR_10_Cores,
                "AVG_TRL_Days_Ultra_6_Cores": row.Avg_Response_Time_Days_Ultra_6_Cores_Collection_To_Validation,
                "AVG_TRL_Days_XDR_10_Cores": row.Avg_Response_Time_Days_XDR_10_Cores_Collection_To_Validation,
                "Errors_Ultra_6_Cores": row.Errors_Ultra_6_Cores,
                "Errors_XDR_10_Cores": row.Errors_XDR_10_Cores,
                "Invalid_Ultra_6_Cores": row.Invalid_Ultra_6_Cores,
                "Invalid_XDR_10_Cores": row.Invalid_XDR_10_Cores,
                "Type_Of_Result": gx_result_type or "All",
                "Lab": lab,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Role": user_role,
            }
            for row in data
        ]

        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def dashboard_summary_positivity_by_month_service(req_args):
    """
    Retrieve the number of tested samples by lab
    """
    (
        dates,
        disaggregation,
        facility_type,
        gx_result_type,
        facilities,
        lab_type,
        health_facility,
    ) = PROCESS_COMMON_PARAMS_FACILITY(req_args)

    user_id = req_args.get("user_id")

    try:
        user = get_user_by_id_service(user_id)
    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": "An Error Occurred",
            "error": str(e),
        }

    user_role = user.role if user else "Unknown"

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip() for f in facilities if f.strip()]

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.RegisteredDateTime.is_not(None),
    ]

    # If after cleaning it's empty, reset it to an empty list
    if not facilities:
        facilities = []

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    try:
        query = (
            TBMaster.query.with_entities(
                MONTH(TBMaster.RegisteredDateTime).label("Month"),
                DATE_PART("month", TBMaster.RegisteredDateTime).label("Month_Name"),
                YEAR(TBMaster.RegisteredDateTime),
                TOTAL_NOT_NULL(TBMaster.RegisteredDateTime).label("Registered_Samples"),
                TOTAL_NOT_NULL(TBMaster.AnalysisDateTime).label("Analysed_Samples"),
                # func.count(TBMaster.RegisteredDateTime).label("Registered_Samples"),
                # func.count(TBMaster.AnalysisDateTime).label("Analysed_Samples"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(FINAL_RESULT_DETECTED_VALUES),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Detected_Samples"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(FINAL_RESULT_NOT_DETECTED_VALUES),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Not_Detected_Samples"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_ERROR_DETECTED_VALUES
                            ),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Errors"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(FINAL_RESULT_INVALID_VALUES),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Invalid_Samples"),
            )
            .filter(*filters)
            .group_by(
                MONTH(TBMaster.RegisteredDateTime),
                DATE_PART("month", TBMaster.RegisteredDateTime),
                YEAR(TBMaster.RegisteredDateTime),
            )
            .order_by(
                YEAR(TBMaster.RegisteredDateTime),
                MONTH(TBMaster.RegisteredDateTime),
            )
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Month": row.Month,
                "Month_Name": row.Month_Name,
                "Year": row.year,
                "Registered_Samples": row.Registered_Samples,
                "Analysed_Samples": row.Analysed_Samples,
                "Detected_Samples": row.Detected_Samples,
                "Not_Detected_Samples": row.Not_Detected_Samples,
                "Errors": row.Errors,
                "Facilities": facilities,
                "Invalid_Samples": row.Invalid_Samples,
                "Type_Of_Result": gx_result_type or "All",
                "Lab": lab_type,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Role": user_role,
            }
            for row in data
        ]

        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }


def dashboard_summary_positivity_by_lab_service(req_args):
    """
    Retrieve the number of tested samples by lab
    """

    (
        dates,
        disaggregation,
        facility_type,
        gx_result_type,
        facilities,
        lab_type,
        health_facility,
    ) = PROCESS_COMMON_PARAMS_FACILITY(req_args)

    user_id = req_args.get("user_id")

    try:
        user = get_user_by_id_service(user_id)
    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": "An Error Occurred",
            "error": str(e),
        }

    user_role = user.role if user else "Unknown"

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories"
    )

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip() for f in facilities if f.strip()]

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.AnalysisDateTime.is_not(None),
    ]

    # If after cleaning it's empty, reset it to an empty list
    if not facilities:
        facilities = []

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.TestingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.TestingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.TestingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    try:
        query = (
            TBMaster.query.with_entities(
                ColumnNames.label("Lab_Name"),
                func.count(TBMaster.RegisteredDateTime).label("Registered_Samples"),
                func.count(TBMaster.AnalysisDateTime).label("Analysed_Samples"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(FINAL_RESULT_DETECTED_VALUES),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Detected_Samples"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(FINAL_RESULT_NOT_DETECTED_VALUES),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Not_Detected_Samples"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_ERROR_DETECTED_VALUES
                            ),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Errors"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(FINAL_RESULT_INVALID_VALUES),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Invalid_Samples"),
            )
            .filter(*filters)
            .group_by(ColumnNames)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Lab_Name": row.Lab_Name,
                "Registered_Samples": row.Registered_Samples,
                "Analysed_Samples": row.Analysed_Samples,
                "Detected_Samples": row.Detected_Samples,
                "Not_Detected_Samples": row.Not_Detected_Samples,
                "Errors": row.Errors,
                "Invalid_Samples": row.Invalid_Samples,
                "Type_Of_Result": gx_result_type or "All",
                "Lab": lab_type,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Role": user_role,
            }
            for row in data
        ]

        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def dashboard_summary_positivity_by_lab_by_age_service(req_args):
    """
    Retrieve the number of tested samples by lab by age
    """

    (
        dates,
        disaggregation,
        facility_type,
        gx_result_type,
        facilities,
        lab_type,
        health_facility,
    ) = PROCESS_COMMON_PARAMS_FACILITY(req_args)

    user_id = req_args.get("user_id")

    try:
        user = get_user_by_id_service(user_id)
    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": "An Error Occurred",
            "error": str(e),
        }

    user_role = user.role if user else "Unknown"

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip() for f in facilities if f.strip()]

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.RegisteredDateTime.is_not(None),
    ]

    # If after cleaning it's empty, reset it to an empty list
    if not facilities:
        facilities = []

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.TestingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.TestingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.TestingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    try:

        subquery = (
            TBMaster.query.with_entities(
                case(
                    (TBMaster.AgeInYears.between(0, 4), "0-4"),
                    (TBMaster.AgeInYears.between(5, 9), "5-9"),
                    (TBMaster.AgeInYears.between(10, 14), "10-14"),
                    (TBMaster.AgeInYears.between(15, 19), "15-19"),
                    (TBMaster.AgeInYears.between(20, 24), "20-24"),
                    (TBMaster.AgeInYears.between(25, 29), "25-29"),
                    (TBMaster.AgeInYears.between(30, 34), "30-34"),
                    (TBMaster.AgeInYears.between(35, 39), "35-39"),
                    (TBMaster.AgeInYears.between(40, 44), "40-44"),
                    (TBMaster.AgeInYears.between(45, 49), "45-49"),
                    (TBMaster.AgeInYears.between(50, 54), "50-54"),
                    (TBMaster.AgeInYears.between(55, 59), "55-59"),
                    (TBMaster.AgeInYears.between(60, 64), "60-64"),
                    (TBMaster.AgeInYears >= 65, "65+"),
                    else_="Not Specified",
                ).label("Faixa_Etaria"),
                TBMaster.RegisteredDateTime,
                TBMaster.AnalysisDateTime,
                TBMaster.FinalResult,
            )
            .filter(*filters)
            .subquery()
        )

        query = (
            TBMaster.query.with_entities(
                subquery.c.Faixa_Etaria,
                func.count(subquery.c.RegisteredDateTime).label("Registered_Samples"),
                func.count(subquery.c.AnalysisDateTime).label("Analysed_Samples"),
                func.count(
                    case(
                        (
                            subquery.c.FinalResult.in_(FINAL_RESULT_DETECTED_VALUES),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Detected_Samples"),
                func.count(
                    case(
                        (
                            subquery.c.FinalResult.in_(
                                FINAL_RESULT_NOT_DETECTED_VALUES
                            ),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Not_Detected_Samples"),
                func.count(
                    case(
                        (
                            subquery.c.FinalResult.in_(
                                FINAL_RESULT_ERROR_DETECTED_VALUES
                            ),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Errors"),
                func.count(
                    case(
                        (
                            subquery.c.FinalResult.in_(FINAL_RESULT_INVALID_VALUES),
                            1,
                        ),
                        else_=None,
                    )
                ).label("Invalid_Samples"),
            )
            .group_by(subquery.c.Faixa_Etaria)
            .order_by(subquery.c.Faixa_Etaria)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                row.Faixa_Etaria: {
                    "Registered_Samples": row.Registered_Samples,
                    "Analysed_Samples": row.Analysed_Samples,
                    "Detected_Samples": row.Detected_Samples,
                    "Not_Detected_Samples": row.Not_Detected_Samples,
                    "Errors": row.Errors,
                    "Invalid_Samples": row.Invalid_Samples,
                },
                "Type_Of_Result": gx_result_type or "All",
                "Lab": lab_type,
                "Facilities": facilities,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Role": user_role,
            }
            for row in data
        ]

        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def dashboard_summary_sample_types_by_month_by_age_service(req_args):
    """
    Retrieve the number of registered samples by month and by specimen type by age
    """

    (
        dates,
        disaggregation,
        facility_type,
        gx_result_type,
        facilities,
        lab_type,
        health_facility,
    ) = PROCESS_COMMON_PARAMS_FACILITY(req_args)

    user_id = req_args.get("user_id")

    try:
        user = get_user_by_id_service(user_id)
    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": "An Error Occurred",
            "error": str(e),
        }

    user_role = user.role if user else "Unknown"

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip() for f in facilities if f.strip()]

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.RegisteredDateTime.is_not(None),
    ]

    # If after cleaning it's empty, reset it to an empty list
    if not facilities:
        facilities = []

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.RequestingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.RequestingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.RequestingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    SPECIMEN_TYPES = {
        "Sputum": TB_SPUTUM_SPECIMEN_SOURCE_CODES,
        "Feces": TB_FECES_SPECIMEN_SOURCE_CODES,
        "Urine": TB_URINE_SPECIMEN_SOURCE_CODES,
        "Blood": TB_BLOOD_SPECIMEN_SOURCE_CODES,
        "PL": TB_PL_SPECIMEN_SOURCE_CODES,
    }

    ALL_SPECIMEN_CODES = (
        TB_SPUTUM_SPECIMEN_SOURCE_CODES
        + TB_FECES_SPECIMEN_SOURCE_CODES
        + TB_URINE_SPECIMEN_SOURCE_CODES
        + TB_BLOOD_SPECIMEN_SOURCE_CODES
        + TB_PL_SPECIMEN_SOURCE_CODES
    )

    count_columns = []

    for age_min, age_max in TB_AGE_RANGES:
        age_suffix = (
            f"{age_min}_to_{age_max}"
            if age_min is not None and age_max is not None
            else (
                "65_plus" if age_min == 65 and age_max is None else "Age_Not_Specified"
            )
        )

        for spec_name, spec_codes in SPECIMEN_TYPES.items():
            conditions = [
                TBMaster.AgeInYears.is_not(None),
                TBMaster.LIMSSpecimenSourceCode.in_(spec_codes),
            ]

            if age_min is not None and age_max is not None:
                conditions.append(TBMaster.AgeInYears.between(age_min, age_max))
            elif age_min == 65 and age_max is None:
                conditions.append(TBMaster.AgeInYears >= age_min)
            else:
                conditions = [
                    TBMaster.AgeInYears.is_(None),
                    TBMaster.LIMSSpecimenSourceCode.in_(spec_codes),
                ]

            count_columns.append(
                func.count(case(((and_(*conditions), 1)))).label(
                    f"{spec_name}_{age_suffix}"
                )
            )

        # Add count for other specimen types
        other_conditions = [
            TBMaster.AgeInYears.is_not(None),
            TBMaster.LIMSSpecimenSourceCode.notin_(ALL_SPECIMEN_CODES),
        ]

        if age_min is not None and age_max is not None:
            other_conditions.append(TBMaster.AgeInYears.between(age_min, age_max))
        elif age_min == 65 and age_max is None:
            other_conditions.append(TBMaster.AgeInYears >= age_min)
        else:
            other_conditions = [
                TBMaster.AgeInYears.is_(None),
                TBMaster.LIMSSpecimenSourceCode.notin_(ALL_SPECIMEN_CODES),
            ]

        count_columns.append(
            func.count(case(((and_(*other_conditions), 1)))).label(
                f"Other_{age_suffix}"
            )
        )

    try:
        query = (
            TBMaster.query.with_entities(
                MONTH(TBMaster.RegisteredDateTime).label("Month"),
                DATE_PART("month", TBMaster.RegisteredDateTime).label("Month_Name"),
                YEAR(TBMaster.RegisteredDateTime).label("Year"),
                *count_columns,
            )
            .filter(*filters)
            .group_by(
                MONTH(TBMaster.RegisteredDateTime),
                DATE_PART("month", TBMaster.RegisteredDateTime),
                YEAR(TBMaster.RegisteredDateTime),
            )
            .order_by(
                YEAR(TBMaster.RegisteredDateTime),
                MONTH(TBMaster.RegisteredDateTime),
            )
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = []
        for row in data:
            month_data = {
                "Month": row.Month,
                "Month_Name": row.Month_Name,
                "Year": row.Year,
                "Specimen_Types": {},
                "Role": user_role,
            }

            # Add specimen type counts for each age range
            for spec_name in list(SPECIMEN_TYPES.keys()) + ["Other"]:
                month_data["Specimen_Types"][spec_name] = {}
                for age_min, age_max in TB_AGE_RANGES:
                    age_suffix = (
                        f"{age_min}_to_{age_max}"
                        if age_min is not None and age_max is not None
                        else (
                            "65_plus"
                            if age_min == 65 and age_max is None
                            else "Age_Not_Specified"
                        )
                    )
                    month_data["Specimen_Types"][spec_name][age_suffix] = getattr(
                        row, f"{spec_name}_{age_suffix}", 0
                    )

            month_data.update(
                {
                    "Type_Of_Result": gx_result_type or "All",
                    "Lab": lab_type,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Facilities": facilities,
                }
            )

            response.append(month_data)

        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def dashboard_summary_sample_types_by_facility_by_age_service(req_args):
    """
    Retrieve the number of registered samples by facility by specimen type by age
    """

    (
        dates,
        disaggregation,
        facility_type,
        gx_result_type,
        facilities,
        lab_type,
        health_facility,
    ) = PROCESS_COMMON_PARAMS_FACILITY(req_args)

    user_id = req_args.get("user_id")

    try:
        user = get_user_by_id_service(user_id)
    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": "An Error Occurred",
            "error": str(e),
        }

    user_role = user.role if user else "Unknown"

    ColumnNames = GET_COLUMN_NAME(disaggregation, facility_type, TBMaster, "facilities")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip() for f in facilities if f.strip()]

    # print(facilities)

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.RegisteredDateTime.is_not(None),
    ]

    # If after cleaning it's empty, reset it to an empty list
    if not facilities:
        facilities = []

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.RequestingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.RequestingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.RequestingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    try:

        SPECIMEN_TYPES = {
            "Sputum": TB_SPUTUM_SPECIMEN_SOURCE_CODES,
            "Feces": TB_FECES_SPECIMEN_SOURCE_CODES,
            "Urine": TB_URINE_SPECIMEN_SOURCE_CODES,
            "Blood": TB_BLOOD_SPECIMEN_SOURCE_CODES,
            "PL": TB_PL_SPECIMEN_SOURCE_CODES,
        }

        ALL_SPECIMEN_CODES = (
            TB_SPUTUM_SPECIMEN_SOURCE_CODES
            + TB_FECES_SPECIMEN_SOURCE_CODES
            + TB_URINE_SPECIMEN_SOURCE_CODES
            + TB_BLOOD_SPECIMEN_SOURCE_CODES
            + TB_PL_SPECIMEN_SOURCE_CODES
        )

        # Generate count columns dynamically
        count_columns = [ColumnNames.label("Facility")]

        # print(facilities)

        for age_min, age_max in TB_AGE_RANGES:
            age_suffix = (
                f"{age_min}_to_{age_max}"
                if age_min is not None and age_max is not None
                else (
                    "65_plus"
                    if age_min == 65 and age_max is None
                    else "Age_Not_Specified"
                )
            )

            for spec_name, spec_codes in SPECIMEN_TYPES.items():
                conditions = [
                    TBMaster.AgeInYears.is_not(None),
                    TBMaster.LIMSSpecimenSourceCode.in_(spec_codes),
                ]

                if age_min is not None and age_max is not None:
                    conditions.append(TBMaster.AgeInYears.between(age_min, age_max))
                elif age_min == 65 and age_max is None:
                    conditions.append(TBMaster.AgeInYears >= age_min)
                else:
                    conditions = [
                        TBMaster.AgeInYears.is_(None),
                        TBMaster.LIMSSpecimenSourceCode.in_(spec_codes),
                    ]

                count_columns.append(
                    func.count(case(((and_(*conditions), 1)))).label(
                        f"{spec_name}_{age_suffix}"
                    )
                )

            # Add Other category
            other_conditions = [
                TBMaster.AgeInYears.is_not(None),
                TBMaster.LIMSSpecimenSourceCode.notin_(ALL_SPECIMEN_CODES),
            ]

            count_columns.append(
                func.count(case(((and_(*other_conditions), 1)))).label(
                    f"Other_{age_suffix}"
                )
            )

            query = (
                TBMaster.query.with_entities(*count_columns)
                .filter(*filters)
                .group_by(ColumnNames)
            )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Facility": row.Facility,
                "0_4": {
                    "sputum": row.Sputum_0_to_4,
                    "feces": row.Feces_0_to_4,
                    "urine": row.Urine_0_to_4,
                    "blood": row.Blood_0_to_4,
                    "pl": row.PL_0_to_4,
                    "other": row.Other_0_to_4,
                },
                "5_9": {
                    "sputum": row.Sputum_5_to_9,
                    "feces": row.Feces_5_to_9,
                    "urine": row.Urine_5_to_9,
                    "blood": row.Blood_5_to_9,
                    "pl": row.PL_5_to_9,
                    "other": row.Other_5_to_9,
                },
                "10_14": {
                    "sputum": row.Sputum_10_to_14,
                    "feces": row.Feces_10_to_14,
                    "urine": row.Urine_10_to_14,
                    "blood": row.Blood_10_to_14,
                    "pl": row.PL_10_to_14,
                    "other": row.Other_10_to_14,
                },
                "15_19": {
                    "sputum": row.Sputum_15_to_19,
                    "feces": row.Feces_15_to_19,
                    "urine": row.Urine_15_to_19,
                    "blood": row.Blood_15_to_19,
                    "pl": row.PL_15_to_19,
                    "other": row.Other_15_to_19,
                },
                "20_24": {
                    "sputum": row.Sputum_20_to_24,
                    "feces": row.Feces_20_to_24,
                    "urine": row.Urine_20_to_24,
                    "blood": row.Blood_20_to_24,
                    "pl": row.PL_20_to_24,
                    "other": row.Other_20_to_24,
                },
                "25_29": {
                    "sputum": row.Sputum_25_to_29,
                    "feces": row.Feces_25_to_29,
                    "urine": row.Urine_25_to_29,
                    "blood": row.Blood_25_to_29,
                    "pl": row.PL_25_to_29,
                    "other": row.Other_25_to_29,
                },
                "30_34": {
                    "sputum": row.Sputum_30_to_34,
                    "feces": row.Feces_30_to_34,
                    "urine": row.Urine_30_to_34,
                    "blood": row.Blood_30_to_34,
                    "pl": row.PL_30_to_34,
                    "other": row.Other_30_to_34,
                },
                "35_39": {
                    "sputum": row.Sputum_35_to_39,
                    "feces": row.Feces_35_to_39,
                    "urine": row.Urine_35_to_39,
                    "blood": row.Blood_35_to_39,
                    "pl": row.PL_35_to_39,
                    "other": row.Other_35_to_39,
                },
                "40_44": {
                    "sputum": row.Sputum_40_to_44,
                    "feces": row.Feces_40_to_44,
                    "urine": row.Urine_40_to_44,
                    "blood": row.Blood_40_to_44,
                    "pl": row.PL_40_to_44,
                    "other": row.Other_40_to_44,
                },
                "45_49": {
                    "sputum": row.Sputum_45_to_49,
                    "feces": row.Feces_45_to_49,
                    "urine": row.Urine_45_to_49,
                    "blood": row.Blood_45_to_49,
                    "pl": row.PL_45_to_49,
                    "other": row.Other_45_to_49,
                },
                "50_54": {
                    "sputum": row.Sputum_50_to_54,
                    "feces": row.Feces_50_to_54,
                    "urine": row.Urine_50_to_54,
                    "blood": row.Blood_50_to_54,
                    "pl": row.PL_50_to_54,
                    "other": row.Other_50_to_54,
                },
                "55_59": {
                    "sputum": row.Sputum_55_to_59,
                    "feces": row.Feces_55_to_59,
                    "urine": row.Urine_55_to_59,
                    "blood": row.Blood_55_to_59,
                    "pl": row.PL_55_to_59,
                    "other": row.Other_55_to_59,
                },
                "60_64": {
                    "sputum": row.Sputum_60_to_64,
                    "feces": row.Feces_60_to_64,
                    "urine": row.Urine_60_to_64,
                    "blood": row.Blood_60_to_64,
                    "pl": row.PL_60_to_64,
                    "other": row.Other_60_to_64,
                },
                "65+": {
                    "sputum": row.Sputum_65_plus,
                    "feces": row.Feces_65_plus,
                    "urine": row.Urine_65_plus,
                    "blood": row.Blood_65_plus,
                    "pl": row.PL_65_plus,
                    "other": row.Other_65_plus,
                },
                "Age_Not_Specified": {
                    "sputum": row.Sputum_Age_Not_Specified,
                    "feces": row.Feces_Age_Not_Specified,
                    "urine": row.Urine_Age_Not_Specified,
                    "blood": row.Blood_Age_Not_Specified,
                    "pl": row.PL_Age_Not_Specified,
                    "other": row.Other_Age_Not_Specified,
                },
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Type_Of_Result": gx_result_type or "All",
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type,
                "Role": user_role,
            }
            for row in data
        ]
        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response
