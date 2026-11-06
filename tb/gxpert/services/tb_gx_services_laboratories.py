from tb.gxpert.models.tb_gx_model import TBMaster
from utilities.utils import *
from sqlalchemy import and_, or_, func, case
from auth.auth_service import get_user_by_id_service
from utilities.permissions import patient_access_role


def GET_COLUMNS(disaggregation, facility_type, Model, flag):
    if disaggregation is True:
        if facility_type == "province":
            return Model.ReceivingDistrictName
        elif facility_type == "district":
            return Model.ReceivingFacilityName
        else:
            return Model.ReceivingProvinceName
    else:
        if facility_type == "province":
            return Model.ReceivingProvinceName
        elif facility_type == "district":
            return Model.ReceivingDistrictName
        else:
            return Model.ReceivingProvinceName


def registered_samples_by_lab_service(req_args):
    """
    Retrieve the number of registered samples by lab
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMNS(
        disaggregation, facility_type, TBMaster, "laboratories")
    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.RegisteredDateTime.is_not(None),
        TBMaster.ReceivingProvinceName.is_not(None),
        TBMaster.ReceivingDistrictName.is_not(None),
        TBMaster.ReceivingFacilityName.is_not(None),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.ReceivingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.ReceivingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.ReceivingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.RegisteredDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=None,
                year=None,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", None, None
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data
        query = (
            TBMaster.query.with_entities(
                ColumnNames.label("laboratory"),
                TOTAL_ALL.label("total"),
            )
            .filter(*filters)
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        # Serialize de data to JSON
        response = [
            {
                "Testing_Facility": row.laboratory,
                "Resgistered_Samples": row.total,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Type_Of_Result": gx_result_type or "All",
                "Lab_Type": lab_type,
                "Role": user_role,
            }
            for row in data
        ]

        # Return the response
        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def registered_samples_by_lab_by_month_service(req_args):
    """
    Retrieve the number of registered samples by month
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

    user_role = patient_access_role(user)

    month = req_args.get("month") if req_args.get("month") != "" else None
    year = req_args.get("year") if req_args.get("year") != "" else None

    # print(dates[1], datetime.fromisoformat(dates[1]).year)
    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    grouping = []

    ordering = []

    ColumnNames = GET_COLUMNS(
        disaggregation, facility_type, TBMaster, "laboratories")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.ReceivingProvinceName.is_not(None),
        TBMaster.ReceivingDistrictName.is_not(None),
        TBMaster.ReceivingFacilityName.is_not(None),
    ]

    fields = [
        TOTAL_ALL.label("total"),
    ]

    # If after cleaning it's empty, reset it to an empty list
    # if not facilities:
    #     facilities = []

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

    if month is not None:
        fields.append(ColumnNames.label("laboratory"))
        filters.append(
            DATE_PART("MONTH", TBMaster.RegisteredDateTime) == month)
        filters.append(DATE_PART("YEAR", TBMaster.RegisteredDateTime) == year)
        filters.append(ColumnNames.isnot(None))
        grouping.append(ColumnNames)
        ordering.append(ColumnNames)
    else:
        fields.append(YEAR(TBMaster.RegisteredDateTime).label("Year"))
        fields.append(MONTH(TBMaster.RegisteredDateTime).label("Month"))
        fields.append(
            DATE_PART("MONTH", TBMaster.RegisteredDateTime).label("Month_Name")
        )
        filters.append(TBMaster.RegisteredDateTime.isnot(None))
        grouping.append(YEAR(TBMaster.RegisteredDateTime))
        grouping.append(MONTH(TBMaster.RegisteredDateTime))
        grouping.append(DATE_PART("MONTH", TBMaster.RegisteredDateTime))
        ordering.append(YEAR(TBMaster.RegisteredDateTime))
        ordering.append(MONTH(TBMaster.RegisteredDateTime))

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.RegisteredDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=month,
                year=year,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", month, year
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data
        query = (
            TBMaster.query.with_entities(*fields)
            .filter(*filters)
            .group_by(*grouping)
            .order_by(*ordering)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        if month and year:
            response = [
                {
                    "Testing_Facility": row.laboratory,
                    "Resgistered_Samples": row.total,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Type_Of_Result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Month": month,
                    "Year": year,
                    "Role": user_role,
                }
                for row in data
            ]
        else:
            # Serialize de data to JSON
            response = [
                {
                    "Year": row.Year,
                    "Month": row.Month,
                    "Month_Name": row.Month_Name,
                    "Resgistered_Samples": row.total,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Type_Of_Result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Facilities": facilities,
                    "Role": user_role,
                }
                for row in data
            ]

        # Return the response
        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def tested_samples_by_lab_service(req_args):
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

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories"
    )

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

    user_role = patient_access_role(user)

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.AnalysisDateTime.is_not(None),
        TBMaster.TestingProvinceName.is_not(None),
        TBMaster.TestingDistrictName.is_not(None),
        TBMaster.TestingFacilityName.is_not(None),
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
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AnalysisDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=None,
                year=None,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", None, None
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data
        query = (
            TBMaster.query.with_entities(
                ColumnNames.label("laboratory"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_INVALID_VALUES),
                            1,
                        )
                    ),
                ).label("invalid_results"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_NOT_DETECTED_VALUES),
                            1,
                        )
                    ),
                ).label("tb_not_detected"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_DETECTED_VALUES),
                            1,
                        )
                    ),
                ).label("tb_detected"),
                func.count(
                    case(
                        (
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_ERROR_DETECTED_VALUES
                            ),
                            1,
                        )
                    )
                ).label("errors"),
                TOTAL_ALL.label("total"),
            )
            .filter(*filters)
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        # Serialize de data to JSON
        response = [
            {
                "Testing_Facility": row.laboratory,
                "Tested_Samples": row.total,
                "Invalid_Results": row.invalid_results,
                "TB_Not_Detected": row.tb_not_detected,
                "TB_Detected": row.tb_detected,
                "Errors": row.errors,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Type_Of_Result": gx_result_type or "All",
                "Lab_Type": lab_type,
                "Role": user_role,
            }
            for row in data
        ]

        # Return the response
        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def tested_samples_by_lab_by_month_service(req_args):
    """
    Retrieve the number of tested samples by month
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

    user_role = patient_access_role(user)

    month = req_args.get("month") if req_args.get("month") != "" else None
    year = req_args.get("year") if req_args.get("year") != "" else None

    # print(dates[1], datetime.fromisoformat(dates[1]).year)
    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    grouping = []

    ordering = []

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories"
    )

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.TestingProvinceName.is_not(None),
        TBMaster.TestingDistrictName.is_not(None),
        TBMaster.TestingFacilityName.is_not(None),
    ]

    fields = [
        TOTAL_ALL.label("total"),
    ]

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

    if month is not None:
        fields.append(ColumnNames.label("laboratory"))
        filters.append(DATE_PART("MONTH", TBMaster.AnalysisDateTime) == month)
        filters.append(DATE_PART("YEAR", TBMaster.AnalysisDateTime) == year)
        filters.append(ColumnNames.isnot(None))
        grouping.append(ColumnNames)
        ordering.append(ColumnNames)
    else:
        fields.append(YEAR(TBMaster.AnalysisDateTime).label("Year"))
        fields.append(MONTH(TBMaster.AnalysisDateTime).label("Month"))
        fields.append(
            DATE_PART("MONTH", TBMaster.AnalysisDateTime).label("Month_Name"))
        filters.append(TBMaster.AnalysisDateTime.isnot(None))
        grouping.append(YEAR(TBMaster.AnalysisDateTime))
        grouping.append(MONTH(TBMaster.AnalysisDateTime))
        grouping.append(DATE_PART("MONTH", TBMaster.AnalysisDateTime))
        ordering.append(YEAR(TBMaster.AnalysisDateTime))
        ordering.append(MONTH(TBMaster.AnalysisDateTime))

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AnalysisDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=month,
                year=year,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", month, year
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data
        query = (
            TBMaster.query.with_entities(*fields)
            .filter(*filters)
            .group_by(*grouping)
            .order_by(*ordering)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        if month and year:
            response = [
                {
                    "Testing_Facility": row.laboratory,
                    "Tested_Samples": row.total,
                    "Start_date": dates[0],
                    "End_date": dates[1],
                    "Type_of_result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Month": month,
                    "Year": year,
                    "Role": user_role,
                }
                for row in data
            ]
        else:
            # Serialize de data to JSON
            response = [
                {
                    "Year": row.Year,
                    "Month": row.Month,
                    "Month_Name": row.Month_Name,
                    "Tested_Samples": row.total,
                    "Start_date": dates[0],
                    "End_date": dates[1],
                    "Type_of_result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Facilities": facilities,
                    "Role": user_role,
                }
                for row in data
            ]

        # Return the response
        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def tested_samples_by_sample_types_by_laboratory_service(req_args):
    """
    Get the number of samples tested by laboratory between two dates, disaggregated by sample types.
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

    user_role = patient_access_role(user)

    # Retrieve the column names based on the disaggregation and facility type
    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories")

    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.AnalysisDateTime.is_not(None),
        TBMaster.TestingProvinceName.is_not(None),
        TBMaster.TestingDistrictName.is_not(None),
        TBMaster.TestingFacilityName.is_not(None),
    ]

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

    SPECIMEN_TYPES = {
        "Sputum": TB_SPUTUM_SPECIMEN_SOURCE_CODES,
        "Feces": TB_FECES_SPECIMEN_SOURCE_CODES,
        "Urine": TB_URINE_SPECIMEN_SOURCE_CODES,
        "Blood": TB_BLOOD_SPECIMEN_SOURCE_CODES,
    }

    ALL_SPECIMEN_CODES = (
        TB_SPUTUM_SPECIMEN_SOURCE_CODES
        + TB_FECES_SPECIMEN_SOURCE_CODES
        + TB_URINE_SPECIMEN_SOURCE_CODES
        + TB_BLOOD_SPECIMEN_SOURCE_CODES
    )

    # Generate count columns dynamically
    count_columns = [ColumnNames.label("Laboratory")]

    # print(SPECIMEN_TYPES)

    for spec_name, spec_codes in SPECIMEN_TYPES.items():
        count_columns.append(
            TOTAL_IN(TBMaster.LIMSSpecimenSourceCode,
                     spec_codes).label(spec_name),
        )

    other_conditions = [
        func.count(
            case(
                (
                    (
                        and_(
                            TBMaster.LIMSSpecimenSourceCode.notin_(
                                ALL_SPECIMEN_CODES),
                        ),
                        1,
                    )
                ),
                else_=None,
            )
        ).label("Other")
    ]

    count_columns.extend(other_conditions)

    # print(count_columns)

    try:

        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AnalysisDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=None,
                year=None,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", None, None
            )

            return response

        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data

        query = (
            TBMaster.query.with_entities(*count_columns)
            .filter(*filters)
            .group_by(ColumnNames)
        )

        data = query.all()

        response = [
            {
                "Laboratory": row.Laboratory,
                "Sputum": row.Sputum,
                "Feces": row.Feces,
                "Urine": row.Urine,
                "Blood": row.Blood,
                "Other": row.Other,
                "Start_date": dates[0],
                "End_date": dates[1],
                "Type_of_result": gx_result_type or "All",
                "Lab_Type": lab_type,
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


def tested_samples_by_samples_types_by_laboratory_by_month_service(req_args):
    """
    Retrieve the number of tested samples by samples types by laboratory by month
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

    user_role = patient_access_role(user)

    month = req_args.get("month") if req_args.get("month") != "" else None
    year = req_args.get("year") if req_args.get("year") != "" else None

    # print(dates[1], datetime.fromisoformat(dates[1]).year)
    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    grouping = []

    ordering = []

    fields = []

    # Retrieve the column names based on the disaggregation and facility type
    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories")

    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.AnalysisDateTime.is_not(None),
        TBMaster.TestingProvinceName.is_not(None),
        TBMaster.TestingDistrictName.is_not(None),
        TBMaster.TestingFacilityName.is_not(None),
    ]

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

    if month is not None:
        fields.append(ColumnNames.label("Laboratory"))
        filters.append(DATE_PART("MONTH", TBMaster.AnalysisDateTime) == month)
        filters.append(DATE_PART("YEAR", TBMaster.AnalysisDateTime) == year)
        filters.append(ColumnNames.isnot(None))
        grouping.append(ColumnNames)
        ordering.append(ColumnNames)
    else:
        fields.append(YEAR(TBMaster.AnalysisDateTime).label("Year"))
        fields.append(MONTH(TBMaster.AnalysisDateTime).label("Month"))
        fields.append(
            DATE_PART("MONTH", TBMaster.AnalysisDateTime).label("Month_Name"))
        filters.append(TBMaster.AnalysisDateTime.isnot(None))
        grouping.append(YEAR(TBMaster.AnalysisDateTime))
        grouping.append(MONTH(TBMaster.AnalysisDateTime))
        grouping.append(DATE_PART("MONTH", TBMaster.AnalysisDateTime))
        ordering.append(YEAR(TBMaster.AnalysisDateTime))
        ordering.append(MONTH(TBMaster.AnalysisDateTime))

    SPECIMEN_TYPES = {
        "Sputum": TB_SPUTUM_SPECIMEN_SOURCE_CODES,
        "Feces": TB_FECES_SPECIMEN_SOURCE_CODES,
        "Urine": TB_URINE_SPECIMEN_SOURCE_CODES,
        "Blood": TB_BLOOD_SPECIMEN_SOURCE_CODES,
    }

    ALL_SPECIMEN_CODES = (
        TB_SPUTUM_SPECIMEN_SOURCE_CODES
        + TB_FECES_SPECIMEN_SOURCE_CODES
        + TB_URINE_SPECIMEN_SOURCE_CODES
        + TB_BLOOD_SPECIMEN_SOURCE_CODES
    )

    # print(SPECIMEN_TYPES)

    for spec_name, spec_codes in SPECIMEN_TYPES.items():
        fields.append(
            TOTAL_IN(TBMaster.LIMSSpecimenSourceCode,
                     spec_codes).label(spec_name),
        )

    other_conditions = [
        func.count(
            case(
                (
                    (
                        and_(
                            TBMaster.LIMSSpecimenSourceCode.notin_(
                                ALL_SPECIMEN_CODES),
                        ),
                        1,
                    )
                ),
                else_=None,
            )
        ).label("Other")
    ]

    fields.extend(other_conditions)

    # print(count_columns)

    try:

        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AnalysisDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=month,
                year=year,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", month, year
            )

            return response

        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data

        query = (
            TBMaster.query.with_entities(*fields)
            .filter(*filters)
            .group_by(*grouping)
            .order_by(*ordering)
        )

        # Print the query
        print(query)

        data = query.all()

        if month and year:
            response = [
                {
                    "Laboratory": row.Laboratory,
                    "Sputum": row.Sputum,
                    "Feces": row.Feces,
                    "Urine": row.Urine,
                    "Blood": row.Blood,
                    "Other": row.Other,
                    "Start_date": dates[0],
                    "End_date": dates[1],
                    "Type_of_result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Month": month,
                    "Year": year,
                    "Role": user_role,
                }
                for row in data
            ]
        else:
            response = [
                {
                    "Month": row.Month,
                    "Month_Name": row.Month_Name,
                    "Year": row.Year,
                    "Sputum": row.Sputum,
                    "Feces": row.Feces,
                    "Urine": row.Urine,
                    "Blood": row.Blood,
                    "Other": row.Other,
                    "Start_date": dates[0],
                    "End_date": dates[1],
                    "Type_of_result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Facilities": facilities,
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


def rejected_samples_by_lab_service(req_args):
    """
    Retrieve the number of rejected samples by lab
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

    user_role = patient_access_role(user)

    # Retrieve the column names based on the disaggregation and facility type
    ColumnNames = GET_COLUMNS(
        disaggregation, facility_type, TBMaster, "laboratories")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.RegisteredDateTime.is_not(None),
        TBMaster.ReceivingProvinceName.is_not(None),
        TBMaster.ReceivingDistrictName.is_not(None),
        TBMaster.ReceivingFacilityName.is_not(None),
        or_(
            func.length(TBMaster.LIMSRejectionCode) > 0,
            func.length(TBMaster.LIMSRejectionDesc) > 0,
        ),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.ReceivingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.ReceivingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.ReceivingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.RegisteredDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=None,
                year=None,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", None, None
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data
        query = (
            TBMaster.query.with_entities(
                ColumnNames.label("laboratory"),
                TOTAL_ALL.label("total"),
            )
            .filter(*filters)
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        # Serialize de data to JSON
        response = [
            {
                "Testing_Facility": row.laboratory,
                "Rejected_Samples": row.total,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Type_Of_Result": gx_result_type or "All",
                "Lab_Type": lab_type,
                "Facilities": facilities,
                "Role": user_role,
            }
            for row in data
        ]
        # Return the response
        return response
    except Exception as e:
        # Prepare the error response
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def rejected_samples_by_lab_by_month_service(req_args):
    """
    Retrieve the number of rejected samples by month
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

    user_role = patient_access_role(user)

    month = req_args.get("month") if req_args.get("month") != "" else None
    year = req_args.get("year") if req_args.get("year") != "" else None

    # print(dates[1], datetime.fromisoformat(dates[1]).year)
    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    grouping = []

    ordering = []

    ColumnNames = GET_COLUMNS(
        disaggregation, facility_type, TBMaster, "laboratories")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.ReceivingProvinceName.is_not(None),
        TBMaster.ReceivingDistrictName.is_not(None),
        TBMaster.ReceivingFacilityName.is_not(None),
        or_(
            func.length(TBMaster.LIMSRejectionCode) > 0,
            func.length(TBMaster.LIMSRejectionDesc) > 0,
        ),
    ]

    fields = [
        TOTAL_ALL.label("total"),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.ReceivingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.ReceivingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.ReceivingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    if month is not None:
        fields.append(ColumnNames.label("laboratory"))
        filters.append(
            DATE_PART("MONTH", TBMaster.RegisteredDateTime) == month)
        filters.append(DATE_PART("YEAR", TBMaster.RegisteredDateTime) == year)
        filters.append(ColumnNames.isnot(None))
        grouping.append(ColumnNames)
        ordering.append(ColumnNames)
    else:
        fields.append(YEAR(TBMaster.RegisteredDateTime).label("Year"))
        fields.append(MONTH(TBMaster.RegisteredDateTime).label("Month"))
        fields.append(
            DATE_PART("MONTH", TBMaster.RegisteredDateTime).label("Month_Name")
        )
        filters.append(TBMaster.RegisteredDateTime.isnot(None))
        grouping.append(YEAR(TBMaster.RegisteredDateTime))
        grouping.append(MONTH(TBMaster.RegisteredDateTime))
        grouping.append(DATE_PART("MONTH", TBMaster.RegisteredDateTime))
        ordering.append(YEAR(TBMaster.RegisteredDateTime))
        ordering.append(MONTH(TBMaster.RegisteredDateTime))

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.RegisteredDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=month,
                year=year,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", month, year
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data
        query = (
            TBMaster.query.with_entities(*fields)
            .filter(*filters)
            .group_by(*grouping)
            .order_by(*ordering)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        if month and year:
            response = [
                {
                    "Testing_Facility": row.laboratory,
                    "Month": month,
                    "Year": year,
                    "Rejected_Samples": row.total,
                    "Start_date": dates[0],
                    "End_date": dates[1],
                    "Type_of_result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Role": user_role,
                }
                for row in data
            ]
        else:
            response = [
                {
                    "Year": row.Year,
                    "Month": row.Month,
                    "Month_Name": row.Month_Name,
                    "Rejected_Samples": row.total,
                    "Start_date": dates[0],
                    "End_date": dates[1],
                    "Type_of_result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Facilities": facilities,
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


def rejected_samples_by_lab_by_reason_service(req_args):
    """
    Retrieve the number of rejected samples by lab
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

    user_role = patient_access_role(user)

    # Retrieve the column names based on the disaggregation and facility type
    ColumnNames = GET_COLUMNS(
        disaggregation, facility_type, TBMaster, "laboratories")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.RegisteredDateTime.is_not(None),
        TBMaster.ReceivingProvinceName.is_not(None),
        TBMaster.ReceivingDistrictName.is_not(None),
        TBMaster.ReceivingFacilityName.is_not(None),
        or_(
            func.length(TBMaster.LIMSRejectionCode) > 0,
            func.length(TBMaster.LIMSRejectionDesc) > 0,
        ),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.ReceivingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.ReceivingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.ReceivingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    rejection_labels = {
        "Isuficient_Specimen": "INSUFICIENT_SPECIMEN",
        "Specimen_Not_Received": "SPECIMEN_NOT_RECEIVED",
        "Specimen_Unsuitable_For_Testing": "SPECIMEN_UNSUITABLE_FOR_TESTING",
        "Equipment_Failure": "EQUIPMENT_FAILURE",
        "Repeat_Specimen_Collection": "REPEAT_SPECIMEN_COLLECTION",
        "Laboratory_Acident": "LABORATORY_ACIDENT",
        "Missing_Reagent": "MISSING_REAGENT",
        "Double_Registration": "DOUBLE_REGISTRATION",
        "Technical_Error": "TECHNICAL_ERROR",
        "Other": "OTHER",
    }

    try:

        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.RegisteredDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=None,
                year=None,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", None, None
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }

        query = (
            TBMaster.query.with_entities(
                ColumnNames.label("laboratory"),
                *[
                    func.count(
                        case(
                            (
                                TBMaster.LIMSRejectionCode.in_(
                                    SPECIMEN_REJECTION_CODES[value]
                                ),
                                1,
                            )
                        )
                    ).label(key)
                    for key, value in rejection_labels.items()
                ],
                func.count(
                    case(
                        (
                            TBMaster.LIMSRejectionCode.notin_(
                                sum(
                                    (
                                        SPECIMEN_REJECTION_CODES[v]
                                        for v in rejection_labels.values()
                                    ),
                                    [],
                                )
                            ),
                            1,
                        )
                    )
                ).label("Other"),
                TOTAL_ALL.label("total"),
            )
            .filter(*filters)
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Testing_Facility": row.laboratory,
                "Rejected_Samples": row.total,
                **{key: getattr(row, key) for key in rejection_labels},
                "Other": row.Other,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Type_Of_Result": gx_result_type or "All",
                "Lab_Type": lab_type,
                "Facilities": facilities,
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


def rejected_samples_by_lab_by_reason_by_month_service(req_args):
    """
    Retrieve the number of rejected samples by lab
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

    user_role = patient_access_role(user)

    month = req_args.get("month") if req_args.get("month") != "" else None
    year = req_args.get("year") if req_args.get("year") != "" else None

    # print(dates[1], datetime.fromisoformat(dates[1]).year)
    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    grouping = []

    ordering = []

    # Retrieve the column names based on the disaggregation and facility type
    ColumnNames = GET_COLUMNS(
        disaggregation, facility_type, TBMaster, "laboratories")

    rejection_labels = {
        "Isuficient_Specimen": "INSUFICIENT_SPECIMEN",
        "Specimen_Not_Received": "SPECIMEN_NOT_RECEIVED",
        "Specimen_Unsuitable_For_Testing": "SPECIMEN_UNSUITABLE_FOR_TESTING",
        "Equipment_Failure": "EQUIPMENT_FAILURE",
        "Repeat_Specimen_Collection": "REPEAT_SPECIMEN_COLLECTION",
        "Laboratory_Acident": "LABORATORY_ACIDENT",
        "Missing_Reagent": "MISSING_REAGENT",
        "Double_Registration": "DOUBLE_REGISTRATION",
        "Technical_Error": "TECHNICAL_ERROR",
        "Other": "OTHER",
    }

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.ReceivingProvinceName.is_not(None),
        TBMaster.ReceivingDistrictName.is_not(None),
        TBMaster.ReceivingFacilityName.is_not(None),
        or_(
            func.length(TBMaster.LIMSRejectionCode) > 0,
            func.length(TBMaster.LIMSRejectionDesc) > 0,
        ),
    ]

    fields = [
        *[
            func.count(
                case(
                    (
                        TBMaster.LIMSRejectionCode.in_(
                            SPECIMEN_REJECTION_CODES[value]),
                        1,
                    )
                )
            ).label(key)
            for key, value in rejection_labels.items()
        ],
        func.count(
            case(
                (
                    TBMaster.LIMSRejectionCode.notin_(
                        sum(
                            (
                                SPECIMEN_REJECTION_CODES[v]
                                for v in rejection_labels.values()
                            ),
                            [],
                        )
                    ),
                    1,
                )
            )
        ).label("Other"),
        TOTAL_ALL.label("total"),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.ReceivingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.ReceivingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.ReceivingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    if month is not None:
        fields.append(ColumnNames.label("laboratory"))
        filters.append(
            DATE_PART("MONTH", TBMaster.RegisteredDateTime) == month)
        filters.append(DATE_PART("YEAR", TBMaster.RegisteredDateTime) == year)
        filters.append(ColumnNames.isnot(None))
        grouping.append(ColumnNames)
        ordering.append(ColumnNames)
    else:
        fields.append(YEAR(TBMaster.RegisteredDateTime).label("Year"))
        fields.append(MONTH(TBMaster.RegisteredDateTime).label("Month"))
        fields.append(
            DATE_PART("MONTH", TBMaster.RegisteredDateTime).label("Month_Name")
        )
        filters.append(TBMaster.RegisteredDateTime.isnot(None))
        grouping.append(YEAR(TBMaster.RegisteredDateTime))
        grouping.append(MONTH(TBMaster.RegisteredDateTime))
        grouping.append(DATE_PART("MONTH", TBMaster.RegisteredDateTime))
        ordering.append(YEAR(TBMaster.RegisteredDateTime))
        ordering.append(MONTH(TBMaster.RegisteredDateTime))

    try:

        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.RegisteredDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=month,
                year=year,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", month, year
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data
        query = (
            TBMaster.query.with_entities(*fields)
            .filter(*filters)
            .group_by(*grouping)
            .order_by(*ordering)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        if month and year:
            response = [
                {
                    "Testing_Facility": row.laboratory,
                    "Month": month,
                    "Month_Name": year,
                    "Rejected_Samples": row.total,
                    **{key: getattr(row, key) for key in rejection_labels},
                    "Other": row.Other,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Type_Of_Result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Role": user_role,
                }
                for row in data
            ]
            return response
        else:
            response = [
                {
                    "Year": row.Year,
                    "Month": row.Month,
                    "Month_Name": row.Month_Name,
                    "Rejected_Samples": row.total,
                    **{key: getattr(row, key) for key in rejection_labels},
                    "Other": row.Other,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Type_Of_Result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Facilities": facilities,
                    "Role": user_role,
                }
                for row in data
            ]
        # Return the response
        return response
    except Exception as e:
        # Prepare the error response
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def tested_samples_by_lab_by_drug_type_service(req_args):
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories"
    )

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip() for f in facilities if f.strip()]

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.AnalysisDateTime.is_not(None),
        TBMaster.TestingProvinceName.is_not(None),
        TBMaster.TestingDistrictName.is_not(None),
        TBMaster.TestingFacilityName.is_not(None),
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

    # Define the drugs and their cases
    drugs = [
        "Rifampicin",
        "Isoniazid",
        "Fluoroquinolona",
        "Kanamicin",
        "Amikacina",
        "Capreomicin",
        "Ethionamida",
    ]

    cases = [
        func.count(
            case(
                (
                    and_(
                        TBMaster.Rifampicin.is_(None),
                        TBMaster.Isoniazid.isnot(None),
                        TBMaster.Fluoroquinolona.isnot(None),
                        TBMaster.Kanamicin.isnot(None),
                        TBMaster.Amikacina.isnot(None),
                        TBMaster.Capreomicin.isnot(None),
                        TBMaster.Ethionamida.isnot(None),
                    ),
                    1,
                )
            )
        ).label("Rifampicin_Null")
    ]

    for drug in drugs:
        cases.extend(generate_drug_cases(TBMaster, drug))

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AnalysisDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=None,
                year=None,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", None, None
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data
        query = (
            TBMaster.query.with_entities(
                ColumnNames.label("laboratory"),
                *cases,
                TOTAL_ALL.label("total"),
            )
            .filter(*filters)
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        # Serialize de data to JSON
        response = [
            {
                "Testing_Facility": row.laboratory,
                "Tested_Samples": row.total,
                "Rifampicin_Null": row.Rifampicin_Null,
                **{
                    drug: {
                        "Resistance_Detected": getattr(
                            row, f"{drug}_Resistance_Detected"
                        ),
                        "Resistance_Not_Detected": getattr(
                            row, f"{drug}_Resistance_Not_Detected"
                        ),
                        "Resistance_Indeterminate": getattr(
                            row, f"{drug}_Resistance_Indeterminate"
                        ),
                    }
                    for drug in drugs
                },
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Type_Of_Result": gx_result_type or "All",
                "Lab_Type": lab_type,
                "Facilities": facilities,
                "Role": user_role,
            }
            for row in data
        ]
        # Return the response
        return response
    except Exception as e:
        # Prepare the error response
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def tested_samples_by_lab_by_drug_type_by_month_service(req_args):
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

    user_role = patient_access_role(user)

    month = req_args.get("month") if req_args.get("month") != "" else None
    year = req_args.get("year") if req_args.get("year") != "" else None

    # print(dates[1], datetime.fromisoformat(dates[1]).year)
    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    grouping = []

    ordering = []

    drugs = [
        "Rifampicin",
        "Isoniazid",
        "Fluoroquinolona",
        "Kanamicin",
        "Amikacina",
        "Capreomicin",
        "Ethionamida",
    ]

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories"
    )

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.TestingProvinceName.is_not(None),
        TBMaster.TestingDistrictName.is_not(None),
        TBMaster.TestingFacilityName.is_not(None),
    ]

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

    cases = [
        func.count(
            case(
                (
                    and_(
                        TBMaster.Rifampicin.is_(None),
                        TBMaster.Isoniazid.isnot(None),
                        TBMaster.Fluoroquinolona.isnot(None),
                        TBMaster.Kanamicin.isnot(None),
                        TBMaster.Amikacina.isnot(None),
                        TBMaster.Capreomicin.isnot(None),
                        TBMaster.Ethionamida.isnot(None),
                    ),
                    1,
                )
            )
        ).label("Rifampicin_Null")
    ]

    for drug in drugs:
        cases.extend(generate_drug_cases(TBMaster, drug))

    fields = [
        *cases,
        TOTAL_ALL.label("total"),
    ]

    if month is not None:
        fields.append(ColumnNames.label("laboratory"))
        filters.append(DATE_PART("MONTH", TBMaster.AnalysisDateTime) == month)
        filters.append(DATE_PART("YEAR", TBMaster.AnalysisDateTime) == year)
        filters.append(ColumnNames.isnot(None))
        grouping.append(ColumnNames)
        ordering.append(ColumnNames)
    else:
        fields.append(YEAR(TBMaster.AnalysisDateTime).label("Year"))
        fields.append(MONTH(TBMaster.AnalysisDateTime).label("Month"))
        fields.append(
            DATE_PART("MONTH", TBMaster.AnalysisDateTime).label("Month_Name"))
        filters.append(TBMaster.AnalysisDateTime.isnot(None))
        grouping.append(YEAR(TBMaster.AnalysisDateTime))
        grouping.append(MONTH(TBMaster.AnalysisDateTime))
        grouping.append(DATE_PART("MONTH", TBMaster.AnalysisDateTime))
        ordering.append(YEAR(TBMaster.AnalysisDateTime))
        ordering.append(MONTH(TBMaster.AnalysisDateTime))

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AnalysisDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=month,
                year=year,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", month, year
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }

        # Get the data
        query = (
            TBMaster.query.with_entities(*fields)
            .filter(*filters)
            .group_by(*grouping)
            .order_by(*ordering)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        if month and year:
            response = [
                {
                    "Testing_Facility": row.laboratory,
                    "Year": year,
                    "Month": month,
                    "Tested_Samples": row.total,
                    "Rifampicin_Null": row.Rifampicin_Null,
                    "Role": user_role,
                    **{
                        drug: {
                            "Resistance_Detected": getattr(
                                row, f"{drug}_Resistance_Detected"
                            ),
                            "Resistance_Not_Detected": getattr(
                                row, f"{drug}_Resistance_Not_Detected"
                            ),
                            "Resistance_Indeterminate": getattr(
                                row, f"{drug}_Resistance_Indeterminate"
                            ),
                        }
                        for drug in drugs
                    },
                }
                for row in data
            ]
        else:
            # Serialize de data to JSON
            response = [
                {
                    "Year": row.Year,
                    "Month": row.Month,
                    "Month_Name": row.Month_Name,
                    "Tested_Samples": row.total,
                    "Rifampicin_Null": row.Rifampicin_Null,
                    "Role": user_role,
                    **{
                        drug: {
                            "Resistance_Detected": getattr(
                                row, f"{drug}_Resistance_Detected"
                            ),
                            "Resistance_Not_Detected": getattr(
                                row, f"{drug}_Resistance_Not_Detected"
                            ),
                            "Resistance_Indeterminate": getattr(
                                row, f"{drug}_Resistance_Indeterminate"
                            ),
                        }
                        for drug in drugs
                    },
                    "Start_date": dates[0],
                    "End_date": dates[1],
                    "Type_of_result": gx_result_type or "All",
                    "Lab_Type": lab_type,
                    "Facilities": facilities,
                }
                for row in data
            ]
        # Return the response
        return response
    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def trl_samples_by_lab_by_days_service(req_args):
    """
    Retrieve the turnaround time samples tested in days
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories"
    )

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AuthorisedDateTime.between(dates[0], dates[1]),
        TBMaster.AuthorisedDateTime.is_not(None),
        TBMaster.TestingProvinceName.is_not(None),
        TBMaster.TestingDistrictName.is_not(None),
        TBMaster.TestingFacilityName.is_not(None),
    ]

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

    trl_functions = trl_by_lab_by_days(TBMaster)

    days_groups = [
        (
            func.count(case(((value.between(min_age, max_age), 1)))).label(
                f"{key}_between_{min_age}_{max_age}"
            )
            if min_age is not None and max_age is not None
            else (
                func.count(case(((value < max_age), 1))).label(
                    f"{key}_less_than_{max_age}"
                )
                if min_age is None
                else (
                    func.count(case(((value > min_age), 1))).label(
                        f"{key}_greater_than_{min_age}"
                    )
                )
            )
        )
        for key, value in trl_functions.items()
        for min_age, max_age in TRL_DAYS
    ]

    # print(select(*age_groups))

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AuthorisedDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=None,
                year=None,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", None, None
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        # Get the data
        query = (
            TBMaster.query.with_entities(
                ColumnNames.label("laboratory"),
                *days_groups,
                func.count(case(((TBMaster.SpecimenDatetime.is_(None), 1)))).label(
                    "specimen_datetime_null"
                ),
                func.count(case(((TBMaster.ReceivedDateTime.is_(None), 1)))).label(
                    "received_datetime_null"
                ),
                func.count(case(((TBMaster.AuthorisedDateTime.is_(None), 1)))).label(
                    "authorised_datetime_null"
                ),
                TOTAL_ALL.label("total"),
            )
            .filter(*filters)
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Testing_Facility": row.laboratory,
                "Total": row.total,
                "Role": user_role,
                "Specimen_Datetime_Null": row.specimen_datetime_null,
                "Received_Datetime_Null": row.received_datetime_null,
                "Authorised_Datetime_Null": row.authorised_datetime_null,
                **{
                    key: {
                        # Replaces the key name from the key and maintains the ages structure
                        # in the subdictionary
                        age_group.name.replace(f"{key}_", ""): getattr(
                            row, age_group.name
                        )
                        for age_group in days_groups
                        if age_group.name.startswith(f"{key}_")
                    }
                    for key, value in trl_functions.items()
                },
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Type_Of_Result": gx_result_type or "All",
            }
            for row in data
        ]

        # Return the response
        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def trl_samples_by_lab_by_days_by_month_service(req_args):
    """
    Retrieve the turnaround time tested samples in days by month
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

    user_role = patient_access_role(user)

    month = req_args.get("month") if req_args.get("month") != "" else None
    year = req_args.get("year") if req_args.get("year") != "" else None

    # print(dates[1], datetime.fromisoformat(dates[1]).year)
    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    grouping = []

    ordering = []

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories"
    )

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AuthorisedDateTime.between(dates[0], dates[1]),
        TBMaster.TestingProvinceName.is_(None),
        TBMaster.TestingDistrictName.is_(None),
        TBMaster.TestingFacilityName.is_(None),
    ]

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

    trl_functions = trl_by_lab_by_days(TBMaster)

    days_groups = [
        (
            func.count(case(((value.between(min_age, max_age), 1)))).label(
                f"{key}_between_{min_age}_{max_age}"
            )
            if min_age is not None and max_age is not None
            else (
                func.count(case(((value < max_age), 1))).label(
                    f"{key}_less_than_{max_age}"
                )
                if min_age is None
                else (
                    func.count(case(((value > min_age), 1))).label(
                        f"{key}_greater_than_{min_age}"
                    )
                )
            )
        )
        for key, value in trl_functions.items()
        for min_age, max_age in TRL_DAYS
    ]

    fields = [
        *days_groups,
        func.count(case(((TBMaster.SpecimenDatetime.is_(None), 1)))).label(
            "specimen_datetime_null"
        ),
        func.count(case(((TBMaster.ReceivedDateTime.is_(None), 1)))).label(
            "received_datetime_null"
        ),
        func.count(case(((TBMaster.AuthorisedDateTime.is_(None), 1)))).label(
            "authorised_datetime_null"
        ),
        TOTAL_ALL.label("total"),
    ]

    if month is not None:
        fields.append(ColumnNames.label("laboratory"))
        filters.append(DATE_PART("MONTH", TBMaster.AnalysisDateTime) == month)
        filters.append(DATE_PART("YEAR", TBMaster.AnalysisDateTime) == year)
        filters.append(ColumnNames.isnot(None))
        grouping.append(ColumnNames)
        ordering.append(ColumnNames)
    else:
        fields.append(YEAR(TBMaster.AnalysisDateTime).label("Year"))
        fields.append(MONTH(TBMaster.AnalysisDateTime).label("Month"))
        fields.append(
            DATE_PART("MONTH", TBMaster.AnalysisDateTime).label("Month_Name"))
        filters.append(TBMaster.AnalysisDateTime.isnot(None))
        grouping.append(YEAR(TBMaster.AnalysisDateTime))
        grouping.append(MONTH(TBMaster.AnalysisDateTime))
        grouping.append(DATE_PART("MONTH", TBMaster.AnalysisDateTime))
        ordering.append(YEAR(TBMaster.AnalysisDateTime))
        ordering.append(MONTH(TBMaster.AnalysisDateTime))

    try:
        # Get the data
        query = (
            TBMaster.query.with_entities(
                *fields,
            )
            .filter(*filters)
            .group_by(*grouping)
            .order_by(*ordering)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        if facility_type == "health_facility" and user_role == "Admin":

            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AnalysisDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=month,
                year=year,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", month, year
            )

            return response
        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }

        if month and year:
            # Get the data
            response = [
                {
                    "Testing_Facility": row.laboratory,
                    "Month": month,
                    "Year": year,
                    "Total": row.total,
                    "Role": user_role,
                    "Specimen_Datetime_Null": row.specimen_datetime_null,
                    "Received_Datetime_Null": row.received_datetime_null,
                    "Authorised_Datetime_Null": row.authorised_datetime_null,
                    **{
                        key: {
                            # Replaces the key name from the key and maintains the ages structure
                            # in the subdictionary
                            age_group.name.replace(f"{key}_", ""): getattr(
                                row, age_group.name
                            )
                            for age_group in days_groups
                            if age_group.name.startswith(f"{key}_")
                        }
                        for key, value in trl_functions.items()
                    },
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Type_Of_Result": gx_result_type or "All",
                }
                for row in data
            ]
        else:
            # Get the data
            response = [
                {
                    "Year": row.Year,
                    "Month": row.Month,
                    "Month_Name": row.Month_Name,
                    "Total": row.total,
                    "Role": user_role,
                    "Specimen_Datetime_Null": row.specimen_datetime_null,
                    "Received_Datetime_Null": row.received_datetime_null,
                    "Authorised_Datetime_Null": row.authorised_datetime_null,
                    **{
                        key: {
                            # Replaces the key name from the key and maintains the ages structure
                            # in the subdictionary
                            age_group.name.replace(f"{key}_", ""): getattr(
                                row, age_group.name
                            )
                            for age_group in days_groups
                            if age_group.name.startswith(f"{key}_")
                        }
                        for key, value in trl_functions.items()
                    },
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Type_Of_Result": gx_result_type or "All",
                    "Facilities": facilities,
                }
                for row in data
            ]

        # Return the response
        return response

    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def trl_samples_avg_by_lab_service(req_args):
    """
    Retrieve the average turnaround time tested samples in days by lab
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories")

    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AuthorisedDateTime.between(dates[0], dates[1]),
        TBMaster.AuthorisedDateTime.is_not(None),
        TBMaster.TestingProvinceName.is_not(None),
        TBMaster.TestingDistrictName.is_not(None),
        TBMaster.TestingFacilityName.is_not(None),
    ]

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

    trl_avg_days = trl_by_lab_avg_days(TBMaster)

    avg_days_group = [
        case(((value == 0, 1)), else_=value).label(key)
        for key, value in trl_avg_days.items()
    ]

    try:

        if facility_type == "health_facility" and user_role == "Admin":
            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AuthorisedDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=None,
                year=None,
            )

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", None, None
            )

            return response

        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }

        query = (
            TBMaster.query.with_entities(
                ColumnNames.label("laboratory"),
                *avg_days_group,
            )
            .filter(*filters)
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Testing_Facility": row.laboratory,
                "Role": user_role,
                "colheita_us__recepcao_lab": row.colheita_us__recepcao_lab,
                "recepcao_lab__registo_no_lab": row.recepcao_lab__registo_no_lab,
                "registo_no_lab__analise_no_lab": row.registo_no_lab__analise_no_lab,
                "analise_no_lab__validacao_no_lab": row.analise_no_lab__validacao_no_lab,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Type_Of_Result": gx_result_type or "All",
            }
            for row in data
        ]

        return response
    except Exception as e:
        # Prepare the error response
        response = {
            "status": "error",
            "code": 500,
            "message": f"An error occurred: {str(e)}",
        }

        return response


def trl_samples_avg_by_lab_month_service(req_args):
    """
    Retrieve the average turnaround time tested samples in days by lab
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

    user_role = patient_access_role(user)

    month = req_args.get("month")
    year = req_args.get("year")

    # print(dates[1], datetime.fromisoformat(dates[1]).year)
    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    grouping = []

    ordering = []

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "laboratories")

    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AuthorisedDateTime.between(dates[0], dates[1]),
        TBMaster.AuthorisedDateTime.is_not(None),
        TBMaster.TestingProvinceName.is_not(None),
        TBMaster.TestingDistrictName.is_not(None),
        TBMaster.TestingFacilityName.is_not(None),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.TestingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.TestingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.TestingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    trl_avg_days = trl_by_lab_avg_days(TBMaster)

    avg_days_group = [
        case(((value == 0, 1)), else_=value).label(key)
        for key, value in trl_avg_days.items()
    ]

    fields = [
        *avg_days_group,
    ]

    if month is not None and year is not None:
        fields.append(ColumnNames.label("laboratory"))
        filters.append(
            DATE_PART("month", TBMaster.AuthorisedDateTime) == month)
        filters.append(DATE_PART("year", TBMaster.AuthorisedDateTime) == year)
        filters.append(ColumnNames.isnot(None))
        grouping.append(ColumnNames)
        ordering.append(ColumnNames)
    else:
        fields.append(YEAR(TBMaster.AuthorisedDateTime).label("Year"))
        fields.append(MONTH(TBMaster.AuthorisedDateTime).label("Month"))
        fields.append(
            DATE_PART("MONTH", TBMaster.AuthorisedDateTime).label("Month_Name")
        )
        filters.append(TBMaster.AuthorisedDateTime.isnot(None))
        grouping.append(YEAR(TBMaster.AuthorisedDateTime))
        grouping.append(MONTH(TBMaster.AuthorisedDateTime))
        grouping.append(DATE_PART("MONTH", TBMaster.AuthorisedDateTime))
        ordering.append(YEAR(TBMaster.AuthorisedDateTime))
        ordering.append(MONTH(TBMaster.AuthorisedDateTime))

    try:
        query = (
            TBMaster.query.with_entities(
                *fields,
            )
            .filter(*filters)
            .group_by(*grouping)
            .order_by(*ordering)
        )

        data = query.all()

        if facility_type == "health_facility" and user_role == "Admin":

            query = get_patients(
                health_facility=None,  # No facility is required here
                lab=health_facility,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AuthorisedDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=month,
                year=year,
            )

            data = query.all()

            print(query.statement.compile(
                compile_kwargs={"literal_binds": True}))

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", month, year
            )

            return response

        if facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }

        if month and year:
            response = [
                {
                    "Testing_Facility": row.laboratory,
                    "Role": user_role,
                    "colheita_us__recepcao_lab": row.colheita_us__recepcao_lab,
                    "recepcao_lab__registo_no_lab": row.recepcao_lab__registo_no_lab,
                    "registo_no_lab__analise_no_lab": row.registo_no_lab__analise_no_lab,
                    "analise_no_lab__validacao_no_lab": row.analise_no_lab__validacao_no_lab,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Month": month,
                    "Year": year,
                    "Type_Of_Result": gx_result_type or "All",
                }
                for row in data
            ]

            return response
        else:
            response = [
                {
                    "Year": row.Year,
                    "Month": row.Month,
                    "Month_Name": row.Month_Name,
                    "Role": user_role,
                    "colheita_us__recepcao_lab": row.colheita_us__recepcao_lab,
                    "recepcao_lab__registo_no_lab": row.recepcao_lab__registo_no_lab,
                    "registo_no_lab__analise_no_lab": row.registo_no_lab__analise_no_lab,
                    "analise_no_lab__validacao_no_lab": row.analise_no_lab__validacao_no_lab,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Type_Of_Result": gx_result_type or "All",
                    "Facilities": facilities,
                }
                for row in data
            ]

            return response
    except Exception as e:
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response
