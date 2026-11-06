from tb.gxpert.models.tb_gx_model import TBMaster
from utilities.utils import *
from sqlalchemy import and_, or_, func, case, literal
from datetime import datetime
from auth.auth_service import get_user_by_id_service
from utilities.permissions import patient_access_role


def registered_samples_by_facility_service(req_args):
    """
    Get the total number of samples registered by facility between two dates.
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

    if user_id is not None:
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
    else:
        user_role = "Unknown"

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        ColumnNames.isnot(None),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=health_facility,
                lab=None,  # No lab is needed for this query
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
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        elif not facilities:
            # If no facilities are provided, query all facilities
            query = (
                TBMaster.query.with_entities(
                    ColumnNames.label("Facility"),
                    TOTAL_ALL.label("TotalSamples"),
                )
                .filter(
                    *filters,
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )
        else:
            # If facilities are provided, filter by the selected facility type
            query = (
                TBMaster.query.with_entities(
                    ColumnNames.label("Facility"),
                    TOTAL_ALL.label("TotalSamples"),
                )
                .filter(
                    *filters,
                    GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                        facilities
                    ),
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Facility": row.Facility,
                "Registered_Samples": row.TotalSamples,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type,
                "Type_Of_Result": gx_result_type if gx_result_type else "All",
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


def registered_samples_by_month_by_facility_service(req_args):
    """
    Get the total number of samples registered by month by facility between two dates.
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

    user_role = patient_access_role(user)

    month = req_args.get("month") if req_args.get("month") != "" else None
    year = req_args.get("year") if req_args.get("year") != "" else None

    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    fields = [
        TOTAL_ALL.label("TotalSamples"),
    ]

    grouping = []

    ordering = []

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    facilities = [f.strip() for f in facilities] if facilities else []

    filters = [TBMaster.RegisteredDateTime.between(dates[0], dates[1])]

    if facilities and any(facility.strip() for facility in facilities):
        filters.append(
            GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                facilities
            )
        )

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if month is not None:
        fields.append(ColumnNames.label("Facility"))
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
                health_facility=health_facility,
                lab=None,
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
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        else:
            # If facilities are provided, filter by the selected facility type
            query = (
                TBMaster.query.with_entities(*fields)
                .filter(
                    *filters,
                )
                .group_by(
                    *grouping,
                )
                .order_by(*ordering)
            )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        if month and year:

            response = [
                {
                    "Facility": row.Facility,
                    "Registered_Samples": row.TotalSamples,
                    "Month": month,
                    "Year": year,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Disaggregation": disaggregation,
                    "Type_Of_Result": gx_result_type if gx_result_type else "All",
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
                    "Registered_Samples": row.TotalSamples,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Disaggregation": disaggregation,
                    "Type_Of_Result": gx_result_type if gx_result_type else "All",
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


def tested_samples_by_facility_service(req_args):
    """
    Get the total number of samples tested by facility between two dates.
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.HL7ResultStatusCode == "F",
        ColumnNames.isnot(None),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=health_facility,
                lab=None,  # No lab is needed for this query
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
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        elif not facilities:
            # If no facilities are provided, query all facilities
            query = (
                TBMaster.query.with_entities(
                    ColumnNames.label("Facility"),
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
                                    FINAL_RESULT_NOT_DETECTED_VALUES
                                ),
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
                                or_(
                                    TBMaster.FinalResult.in_(
                                        FINAL_RESULT_ERROR_DETECTED_VALUES
                                    ),
                                    func.length(
                                        TBMaster.LIMSRejectionCode) > 0,
                                    TBMaster.FinalResult.is_(None),
                                ),
                                1,
                            )
                        )
                    ).label("errors"),
                    TOTAL_ALL.label("TotalSamples"),
                )
                .filter(
                    *filters,
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )
        else:
            # If facilities are provided, filter by the selected facility type
            query = (
                TBMaster.query.with_entities(
                    ColumnNames.label("Facility"),
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
                                    FINAL_RESULT_NOT_DETECTED_VALUES
                                ),
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
                                or_(
                                    TBMaster.FinalResult.in_(
                                        FINAL_RESULT_ERROR_DETECTED_VALUES
                                    ),
                                    func.length(
                                        TBMaster.LIMSRejectionCode) > 0,
                                ),
                                1,
                            )
                        )
                    ).label("errors"),
                    TOTAL_ALL.label("TotalSamples"),
                )
                .filter(
                    *filters,
                    GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                        facilities
                    ),
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Facility": row.Facility,
                "Tested_Samples": row.TotalSamples,
                "Detected": row.tb_detected,
                "Not_Detected": row.tb_not_detected,
                "Invalid": row.invalid_results,
                "Errors": row.errors,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type if facility_type else None,
                "Type_Of_Result": gx_result_type if gx_result_type else "All",
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


def tested_samples_by_month_by_facility_service(req_args):
    """
    Get the total number of samples tested by month by facility between two dates.
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

    user_role = patient_access_role(user)

    month = req_args.get("month") if req_args.get("month") != "" else None
    year = req_args.get("year") if req_args.get("year") != "" else None

    print(f"Month: {month}, Year: {year}")

    # print(dates[1], datetime.fromisoformat(dates[1]).year)
    if year and int(year) > int(datetime.fromisoformat(dates[1]).year):
        return {
            "Status": "error",
            "Data": [],
            "Message": "Year cannot be greater than the current year.",
        }

    fields = [
        func.count(
            case(
                (
                    TBMaster.FinalResult.in_(FINAL_RESULT_INVALID_VALUES),
                    1,
                )
            ),
        ).label("invalid_results"),
        func.count(
            case(
                (
                    TBMaster.FinalResult.in_(FINAL_RESULT_NOT_DETECTED_VALUES),
                    1,
                )
            ),
        ).label("tb_not_detected"),
        func.count(
            case(
                (
                    TBMaster.FinalResult.in_(FINAL_RESULT_DETECTED_VALUES),
                    1,
                )
            ),
        ).label("tb_detected"),
        func.count(
            case(
                (
                    or_(
                        TBMaster.FinalResult.in_(
                            FINAL_RESULT_ERROR_DETECTED_VALUES),
                        func.length(TBMaster.LIMSRejectionCode) > 0,
                        TBMaster.FinalResult.is_(None),
                    ),
                    1,
                )
            )
        ).label("errors"),
        TOTAL_ALL.label("TotalSamples"),
    ]

    grouping = []

    ordering = []

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    facilities = [f.strip() for f in facilities] if facilities else []

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.HL7ResultStatusCode == "F",
    ]

    if facilities and any(facility.strip() for facility in facilities):
        filters.append(
            GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                facilities
            )
        )

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if month is not None:
        fields.append(ColumnNames.label("Facility"))
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
                health_facility=health_facility,
                lab=None,
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
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        else:
            # If no facilities are provided, query all facilities
            query = (
                TBMaster.query.with_entities(*fields)
                .filter(
                    *filters,
                )
                .group_by(*grouping)
                .order_by(*ordering)
            )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        if month and year:
            response = [
                {
                    "Facility": row.Facility,
                    "Tested_Samples": row.TotalSamples,
                    "Month": month,
                    "Year": year,
                    "Detected": row.tb_detected,
                    "Not_Detected": row.tb_not_detected,
                    "Invalid": row.invalid_results,
                    "Errors": row.errors,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Disaggregation": disaggregation,
                    "Type_Of_Result": gx_result_type if gx_result_type else "All",
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
                    "Tested_Samples": row.TotalSamples,
                    "Detected": row.tb_detected,
                    "Not_Detected": row.tb_not_detected,
                    "Invalid": row.invalid_results,
                    "Errors": row.errors,
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Disaggregation": disaggregation,
                    "Facility_Type": facility_type if facility_type else None,
                    "Type_Of_Result": gx_result_type if gx_result_type else "All",
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


def tested_samples_by_facility_disaggregated_service(req_args):
    """
    Get the total number of samples tested by facility between two dates,
    disaggregated by mtb trace, detected, invalid, without result and errors.
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.HL7ResultStatusCode == "F",
        ColumnNames.isnot(None),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    try:

        common_entities = [
            ColumnNames.label("Facility"),
            TOTAL_ALL.label("TotalSamples"),
            func.count(
                case(
                    (
                        or_(
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_DETECTED_VALUES),
                            TBMaster.MtbTrace.in_(
                                FINAL_RESULT_DETECTED_VALUES),
                        ),
                        1,
                    )
                )
            ).label("Detected"),
            func.count(
                case(
                    (
                        or_(
                            TBMaster.FinalResult.in_(
                                FINAL_RESULT_NOT_DETECTED_VALUES),
                            TBMaster.MtbTrace.in_(
                                FINAL_RESULT_NOT_DETECTED_VALUES),
                        ),
                        1,
                    )
                )
            ).label("NotDetected"),
            func.count(
                case(
                    (
                        TBMaster.Rifampicin.in_(DETECTED_VALUES),
                        1,
                    )
                )
            ).label("RifampicinDetected"),
            func.count(
                case(
                    (
                        TBMaster.Rifampicin.in_(NOT_DETECTED_VALUES),
                        1,
                    )
                )
            ).label("RifampicinNotDetected"),
            func.count(
                case(
                    (
                        or_(
                            TBMaster.FinalResult.in_(
                                ["invalid", "invalido", "inv"]),
                            TBMaster.Rifampicin.in_(
                                ["invalid", "invalido", "inv"]),
                        ),
                        1,
                    )
                )
            ).label("Invalid"),
            func.count(
                case(
                    (
                        or_(
                            TBMaster.FinalResult.is_(None),
                            TBMaster.FinalResult.in_(["NORES", "No Result"]),
                            TBMaster.MtbTrace.in_(["NORES", "No Result"]),
                        ),
                        1,
                    )
                )
            ).label("WithoutResult"),
            func.count(
                case(
                    (
                        and_(
                            TBMaster.HL7ResultStatusCode == "X",
                            or_(
                                TBMaster.LIMSRejectionCode != "",
                                TBMaster.LIMSRejectionDesc != "",
                            ),
                        ),
                        1,
                    )
                )
            ).label("RejectedSamples"),
        ]

        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=health_facility,
                lab=lab,
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
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        elif not facilities:
            query = (
                TBMaster.query.with_entities(*common_entities)
                .filter(*filters)
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )
        else:
            # If facilities are provided, filter by the selected facility type
            query = (
                TBMaster.query.with_entities(*common_entities)
                .filter(
                    *filters,
                    GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                        facilities
                    ),
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Facility": row.Facility,
                "Tested_Samples": row.TotalSamples,
                "Detected": row.Detected,
                "Not_Detected": row.NotDetected,
                "Rifampicin_Detected": row.RifampicinDetected,
                "Rifampicin_Not_Detected": row.RifampicinNotDetected,
                "Invalid": row.Invalid,
                "Without_Result": row.WithoutResult,
                "Rejected_Samples": row.RejectedSamples,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type if facility_type else None,
                "Type_Of_Result": gx_result_type if gx_result_type else "All",
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


def tested_samples_by_facility_disaggregated_by_gender_service(req_args):
    """
    Get the total number of samples tested by facility between two dates,
    disaggregated by Gender.
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

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

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

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.AnalysisDateTime.is_not(None),
        ColumnNames.is_not(None),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    try:
        sex_codes = {"M": "Male", "F": "Female", "I": "Indet"}

        result_types = {
            "Det": DETECTED_VALUES,
            "NotDet": NOT_DETECTED_VALUES,
            "Null": None,
        }

        counts = [ColumnNames.label("Facility")]

        for result_prefix, values in result_types.items():
            for sex_code, sex_label in sex_codes.items():
                counts.append(
                    func.count(
                        case(
                            (
                                and_(
                                    TBMaster.Rifampicin.in_(values),
                                    TBMaster.HL7SexCode == sex_code,
                                ),
                                1,
                            )
                        )
                    ).label(f"Rif{result_prefix}{sex_label}")
                    if result_prefix in ("Det", "NotDet")
                    else (
                        func.count(
                            case(
                                (
                                    and_(
                                        TBMaster.Rifampicin.is_(None),
                                        TBMaster.HL7SexCode == sex_label,
                                    ),
                                    1,
                                )
                            )
                        )
                    ).label(f"RifNull{sex_label}")
                )

        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=health_facility,
                lab=None,
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
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        elif not facilities:
            # If no facilities are provided, query all facilities
            query = (
                TBMaster.query.with_entities(*counts)
                .filter(*filters)
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )
        else:
            # If facilities are provided, filter by the selected facility type
            query = (
                TBMaster.query.with_entities(*counts)
                .filter(
                    *filters,
                    GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                        facilities
                    ),
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Facility": row.Facility,
                "Rif_Det_Male": row.RifDetMale,
                "Rif_Det_Female": row.RifDetFemale,
                "Rif_Det_Indet": row.RifDetIndet,
                "Rif_NotDet_Male": row.RifNotDetMale,
                "Rif_NotDet_Female": row.RifNotDetFemale,
                "Rif_NotDet_Indet": row.RifNotDetIndet,
                "Rif_Null_Male": row.RifNullMale,
                "Rif_Null_Female": row.RifNullFemale,
                "Rif_Null_Indet": row.RifNullIndet,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type if facility_type else None,
                "Type_Of_Result": gx_result_type if gx_result_type else "All",
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


def tested_samples_by_facility_disaggregated_by_age_service(req_args):
    """
    Get the total number of samples tested by facility between two dates,
    disaggregated by Age.
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.AnalysisDateTime.is_not(None),
        TBMaster.AgeInYears.isnot(None),
        ColumnNames.is_not(None),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    try:
        RESULT_CATEGORIES = {
            "Detected": lambda: TBMaster.FinalResult.in_(FINAL_RESULT_DETECTED_VALUES),
            "Not_Detected": lambda: TBMaster.FinalResult.in_(
                FINAL_RESULT_NOT_DETECTED_VALUES
            ),
            "Invalid": lambda: or_(
                TBMaster.FinalResult.in_(["invalid", "invalido", "inv"]),
                TBMaster.Rifampicin.in_(["invalid", "invalido", "inv"]),
            ),
            "WithoutResult": lambda: or_(
                TBMaster.FinalResult.in_(["NORES", "No Result"]),
                TBMaster.MtbTrace.in_(["NORES", "No Result"]),
            ),
            "RejectedSamples": lambda: and_(
                TBMaster.HL7ResultStatusCode == "X",
                or_(
                    TBMaster.LIMSRejectionCode != "",
                    TBMaster.LIMSRejectionDesc != "",
                ),
            ),
        }

        # Generate columns dynamically
        count_columns = [ColumnNames.label("Facility")]

        for age_min, age_max in TB_AGE_RANGES:
            age_suffix = (
                f"{age_min}_to_{age_max}"
                if age_max
                else ("65_plus" if age_min == 65 else "Not_Specified")
            )

            age_condition = (
                TBMaster.AgeInYears.between(age_min, age_max)
                if age_max
                else (
                    TBMaster.AgeInYears >= age_min
                    if age_min == 65
                    else TBMaster.AgeInYears.is_(None)
                )
            )

            for category, condition_func in RESULT_CATEGORIES.items():

                conditions = [age_condition, condition_func()]

                count_columns.append(
                    func.count(case((and_(*conditions), 1))).label(
                        f"{category}_{age_suffix}"
                    )
                )

            # Apply filters based on facilities
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=health_facility,
                lab=None,
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
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        elif not facilities:
            # If no facilities are provided, query all facilities
            query = (
                TBMaster.query.with_entities(*count_columns)
                .filter(*filters)
                .group_by(ColumnNames)
            )
        else:
            # If facilities are provided, filter by the selected facility type
            query = (
                TBMaster.query.with_entities(*count_columns)
                .filter(
                    *filters,
                    GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                        facilities
                    ),
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )

        data = query.all()

        response = [
            {
                "Facility": row.Facility,
                "0_4": {
                    "detected": row.Detected_0_to_4,
                    "not_detected": row.Not_Detected_0_to_4,
                    "invalid": row.Invalid_0_to_4,
                    "without_result": row.WithoutResult_0_to_4,
                    "rejected_samples": row.RejectedSamples_0_to_4,
                },
                "5_9": {
                    "detected": row.Detected_5_to_9,
                    "not_detected": row.Not_Detected_5_to_9,
                    "invalid": row.Invalid_5_to_9,
                    "without_result": row.WithoutResult_5_to_9,
                    "rejected_samples": row.RejectedSamples_5_to_9,
                },
                "10_14": {
                    "detected": row.Detected_10_to_14,
                    "not_detected": row.Not_Detected_10_to_14,
                    "invalid": row.Invalid_10_to_14,
                    "without_result": row.WithoutResult_10_to_14,
                    "rejected_samples": row.RejectedSamples_10_to_14,
                },
                "15_19": {
                    "detected": row.Detected_15_to_19,
                    "not_detected": row.Not_Detected_15_to_19,
                    "invalid": row.Invalid_15_to_19,
                    "without_result": row.WithoutResult_15_to_19,
                    "rejected_samples": row.RejectedSamples_15_to_19,
                },
                "20_24": {
                    "detected": row.Detected_20_to_24,
                    "not_detected": row.Not_Detected_20_to_24,
                    "invalid": row.Invalid_20_to_24,
                    "without_result": row.WithoutResult_20_to_24,
                    "rejected_samples": row.RejectedSamples_20_to_24,
                },
                "25_29": {
                    "detected": row.Detected_25_to_29,
                    "not_detected": row.Not_Detected_25_to_29,
                    "invalid": row.Invalid_25_to_29,
                    "without_result": row.WithoutResult_25_to_29,
                    "rejected_samples": row.RejectedSamples_25_to_29,
                },
                "30_34": {
                    "detected": row.Detected_30_to_34,
                    "not_detected": row.Not_Detected_30_to_34,
                    "invalid": row.Invalid_30_to_34,
                    "without_result": row.WithoutResult_30_to_34,
                    "rejected_samples": row.RejectedSamples_30_to_34,
                },
                "35_39": {
                    "detected": row.Detected_35_to_39,
                    "not_detected": row.Not_Detected_35_to_39,
                    "invalid": row.Invalid_35_to_39,
                    "without_result": row.WithoutResult_35_to_39,
                    "rejected_samples": row.RejectedSamples_35_to_39,
                },
                "40_44": {
                    "detected": row.Detected_40_to_44,
                    "not_detected": row.Not_Detected_40_to_44,
                    "invalid": row.Invalid_40_to_44,
                    "without_result": row.WithoutResult_40_to_44,
                    "rejected_samples": row.RejectedSamples_40_to_44,
                },
                "45_49": {
                    "detected": row.Detected_45_to_49,
                    "not_detected": row.Not_Detected_45_to_49,
                    "invalid": row.Invalid_45_to_49,
                    "without_result": row.WithoutResult_45_to_49,
                    "rejected_samples": row.RejectedSamples_45_to_49,
                },
                "50_54": {
                    "detected": row.Detected_50_to_54,
                    "not_detected": row.Not_Detected_50_to_54,
                    "invalid": row.Invalid_50_to_54,
                    "without_result": row.WithoutResult_50_to_54,
                    "rejected_samples": row.RejectedSamples_50_to_54,
                },
                "55_59": {
                    "detected": row.Detected_55_to_59,
                    "not_detected": row.Not_Detected_55_to_59,
                    "invalid": row.Invalid_55_to_59,
                    "without_result": row.WithoutResult_55_to_59,
                    "rejected_samples": row.RejectedSamples_55_to_59,
                },
                "60_64": {
                    "detected": row.Detected_60_to_64,
                    "not_detected": row.Not_Detected_60_to_64,
                    "invalid": row.Invalid_60_to_64,
                    "without_result": row.WithoutResult_60_to_64,
                    "rejected_samples": row.RejectedSamples_60_to_64,
                },
                "65+": {
                    "detected": row.Detected_65_plus,
                    "not_detected": row.Not_Detected_65_plus,
                    "invalid": row.Invalid_65_plus,
                    "without_result": row.WithoutResult_65_plus,
                    "rejected_samples": row.RejectedSamples_65_plus,
                },
                "Age_Not_Specified": {
                    "detected": row.Detected_Not_Specified,
                    "not_detected": row.Not_Detected_Not_Specified,
                    "invalid": row.Invalid_Not_Specified,
                    "without_result": row.WithoutResult_Not_Specified,
                    "rejected_samples": row.RejectedSamples_Not_Specified,
                },
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type,
                "Type_Of_Result": gx_result_type if gx_result_type else "All",
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


def tested_samples_by_sample_types_by_facility_service(req_args):
    """
    Get the number of samples tested by facility between two dates, disaggregated by age.
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        ColumnNames.isnot(None),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

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
    count_columns = [ColumnNames.label("Facility")]

    # print(SPECIMEN_TYPES)

    for spec_name, spec_codes in SPECIMEN_TYPES.items():
        count_columns.append(
            TOTAL_IN(TBMaster.LIMSSpecimenSourceCode, spec_codes).label(spec_name),
        )

    other_conditions = [
        func.count(
        case(
            (
                (
                    and_(
                        TBMaster.LIMSSpecimenSourceCode.notin_(ALL_SPECIMEN_CODES),
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
                health_facility=health_facility,
                lab=None,
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

        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        elif not facilities:
            # If no facilities are provided, query all facilities
            query = (
                TBMaster.query.with_entities(*count_columns)
                .filter(*filters)
                .group_by(ColumnNames)
            )
        else:
            # If facilities are provided, filter by the selected facility type
            query = (
                TBMaster.query.with_entities(*count_columns)
                .filter(
                    *filters,
                    GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                        facilities
                    ),
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )

        print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Facility": row.Facility,
                "Sputum": row.Sputum,
                "Feces": row.Feces,
                "Urine": row.Urine,
                "Blood": row.Blood,
                "Other": row.Other,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type,
                "Type_Of_Result": gx_result_type if gx_result_type else "All",
                "Role": user_role,
            }
            for row in data
        ]

        return response

    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": "An Error Occurred",
            "error": str(e),
        }
    

def tested_samples_types_by_facility_disaggregated_by_age_service(req_args):
    """
    Get the number of samples tested by facility between two dates, disaggregated by age.
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        ColumnNames.isnot(None),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    try:

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
        count_columns = [ColumnNames.label("Facility")]

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
                    TBMaster.LIMSSpecimenSourceCode.in_(spec_codes),
                ]

                if age_min is not None and age_max is not None:
                    conditions.append(
                        TBMaster.AgeInYears.between(age_min, age_max))
                elif age_min == 65 and age_max is None:
                    conditions.append(TBMaster.AgeInYears >= age_min)
                else:
                    conditions = [
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

        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=health_facility,
                lab=None,
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
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        elif not facilities:
            query = (
                TBMaster.query.with_entities(*count_columns)
                .filter(and_(*filters))
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )
        else:
            # If facilities are provided, filter by the selected facility type
            query = (
                TBMaster.query.with_entities(*count_columns)
                .filter(
                    and_(*filters),
                    GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                        facilities
                    ),
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )

        data = query.all()

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        response = [
            {
                "Facility": row.Facility,
                "0_4": {
                    "sputum": row.Sputum_0_to_4,
                    "feces": row.Feces_0_to_4,
                    "urine": row.Urine_0_to_4,
                    "blood": row.Blood_0_to_4,
                    "other": row.Other_0_to_4,
                },
                "5_9": {
                    "sputum": row.Sputum_5_to_9,
                    "feces": row.Feces_5_to_9,
                    "urine": row.Urine_5_to_9,
                    "blood": row.Blood_5_to_9,
                    "other": row.Other_5_to_9,
                },
                "10_14": {
                    "sputum": row.Sputum_10_to_14,
                    "feces": row.Feces_10_to_14,
                    "urine": row.Urine_10_to_14,
                    "blood": row.Blood_10_to_14,
                    "other": row.Other_10_to_14,
                },
                "15_19": {
                    "sputum": row.Sputum_15_to_19,
                    "feces": row.Feces_15_to_19,
                    "urine": row.Urine_15_to_19,
                    "blood": row.Blood_15_to_19,
                    "other": row.Other_15_to_19,
                },
                "20_24": {
                    "sputum": row.Sputum_20_to_24,
                    "feces": row.Feces_20_to_24,
                    "urine": row.Urine_20_to_24,
                    "blood": row.Blood_20_to_24,
                    "other": row.Other_20_to_24,
                },
                "25_29": {
                    "sputum": row.Sputum_25_to_29,
                    "feces": row.Feces_25_to_29,
                    "urine": row.Urine_25_to_29,
                    "blood": row.Blood_25_to_29,
                    "other": row.Other_25_to_29,
                },
                "30_34": {
                    "sputum": row.Sputum_30_to_34,
                    "feces": row.Feces_30_to_34,
                    "urine": row.Urine_30_to_34,
                    "blood": row.Blood_30_to_34,
                    "other": row.Other_30_to_34,
                },
                "35_39": {
                    "sputum": row.Sputum_35_to_39,
                    "feces": row.Feces_35_to_39,
                    "urine": row.Urine_35_to_39,
                    "blood": row.Blood_35_to_39,
                    "other": row.Other_35_to_39,
                },
                "40_44": {
                    "sputum": row.Sputum_40_to_44,
                    "feces": row.Feces_40_to_44,
                    "urine": row.Urine_40_to_44,
                    "blood": row.Blood_40_to_44,
                    "other": row.Other_40_to_44,
                },
                "45_49": {
                    "sputum": row.Sputum_45_to_49,
                    "feces": row.Feces_45_to_49,
                    "urine": row.Urine_45_to_49,
                    "blood": row.Blood_45_to_49,
                    "other": row.Other_45_to_49,
                },
                "50_54": {
                    "sputum": row.Sputum_50_to_54,
                    "feces": row.Feces_50_to_54,
                    "urine": row.Urine_50_to_54,
                    "blood": row.Blood_50_to_54,
                    "other": row.Other_50_to_54,
                },
                "55_59": {
                    "sputum": row.Sputum_55_to_59,
                    "feces": row.Feces_55_to_59,
                    "urine": row.Urine_55_to_59,
                    "blood": row.Blood_55_to_59,
                    "other": row.Other_55_to_59,
                },
                "60_64": {
                    "sputum": row.Sputum_60_to_64,
                    "feces": row.Feces_60_to_64,
                    "urine": row.Urine_60_to_64,
                    "blood": row.Blood_60_to_64,
                    "other": row.Other_60_to_64,
                },
                "65+": {
                    "sputum": row.Sputum_65_plus,
                    "feces": row.Feces_65_plus,
                    "urine": row.Urine_65_plus,
                    "blood": row.Blood_65_plus,
                    "other": row.Other_65_plus,
                },
                "Age_Not_Specified": {
                    "sputum": row.Sputum_Age_Not_Specified,
                    "feces": row.Feces_Age_Not_Specified,
                    "urine": row.Urine_Age_Not_Specified,
                    "blood": row.Blood_Age_Not_Specified,
                    "other": row.Other_Age_Not_Specified,
                },
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type,
                "Type_Of_Result": gx_result_type if gx_result_type else "All",
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


def tested_samples_by_facility_disaggregated_by_drug_type_service(req_args):
    """
    This function returns the number of tested samples by facility, disaggregated by drug type.
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

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

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        TBMaster.FinalResult.isnot(None),
        ColumnNames.isnot(None),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    for drug in drugs:
        if gx_result_type == "Ultra 6 Cores":
            cases.extend(generate_drug_cases(TBMaster, "Rifampicin"))
            break
        else:
            cases.extend(generate_drug_cases(TBMaster, drug))

    try:
        # print(ColumnNames)
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=health_facility,
                lab=None,
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
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        elif not facilities:
            query = (
                TBMaster.query.with_entities(
                    ColumnNames.label("Facility"), *cases)
                .filter(*filters)
                .group_by(ColumnNames)
            )
        else:
            # If facilities are provided, filter by the selected facility type
            query = (
                TBMaster.query.with_entities(
                    ColumnNames.label("Facility"), *cases)
                .filter(
                    *filters,
                    GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                        facilities
                    ),
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )

        print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        if gx_result_type == "Ultra 6 Cores":
            response = [
                {
                    "Facility": row.Facility,
                    "Rifampicin_Null": row.Rifampicin_Null,
                    "Rifampicin": {
                        "Resistance_Detected": row.Rifampicin_Resistance_Detected,
                        "Resistance_Not_Detected": row.Rifampicin_Resistance_Not_Detected,
                        "Resistance_Indeterminate": row.Rifampicin_Resistance_Indeterminate,
                    },
                    "Start_Date": dates[0],
                    "End_Date": dates[1],
                    "Disaggregation": disaggregation,
                    "Facility_Type": facility_type,
                    "Type_Of_Result": gx_result_type if gx_result_type else "All",
                    "Role": user_role,
                }
                for row in data
            ]
        else:
            response = [
                {
                    "Facility": row.Facility,
                    "Rifampicin_Null": row.Rifampicin_Null,
                    "Rifampicin": {
                    "Resistance_Detected": row.Rifampicin_Resistance_Detected,
                    "Resistance_Not_Detected": row.Rifampicin_Resistance_Not_Detected,
                    "Resistance_Indeterminate": row.Rifampicin_Resistance_Indeterminate,
                },
                "Isoniazid": {
                    "Resistance_Detected": row.Isoniazid_Resistance_Detected,
                    "Resistance_Not_Detected": row.Isoniazid_Resistance_Not_Detected,
                    "Resistance_Indeterminate": row.Isoniazid_Resistance_Indeterminate,
                },
                "Fluoroquinolona": {
                    "Resistance_Detected": row.Fluoroquinolona_Resistance_Detected,
                    "Resistance_Not_Detected": row.Fluoroquinolona_Resistance_Not_Detected,
                    "Resistance_Indeterminate": row.Fluoroquinolona_Resistance_Indeterminate,
                },
                "Kanamicin": {
                    "Resistance_Detected": row.Kanamicin_Resistance_Detected,
                    "Resistance_Not_Detected": row.Kanamicin_Resistance_Not_Detected,
                    "Resistance_Indeterminate": row.Kanamicin_Resistance_Indeterminate,
                },
                "Amikacin": {
                    "Resistance_Detected": row.Amikacina_Resistance_Detected,
                    "Resistance_Not_Detected": row.Amikacina_Resistance_Not_Detected,
                    "Resistance_Indeterminate": row.Amikacina_Resistance_Indeterminate,
                },
                "Capreomicin": {
                    "Resistance_Detected": row.Capreomicin_Resistance_Detected,
                    "Resistance_Not_Detected": row.Capreomicin_Resistance_Not_Detected,
                    "Resistance_Indeterminate": row.Capreomicin_Resistance_Indeterminate,
                },
                "Ethionamide": {
                    "Resistance_Detected": row.Ethionamida_Resistance_Detected,
                    "Resistance_Not_Detected": row.Ethionamida_Resistance_Not_Detected,
                    "Resistance_Indeterminate": row.Ethionamida_Resistance_Indeterminate,
                },
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type,
                "Type_Of_Result": gx_result_type if gx_result_type else "All",
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


def tested_samples_by_facility_disaggregated_by_drug_type_by_age_service(req_args):
    """
    This function returns the number of tested samples by facility, disaggregated by drug type and age.
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

    user_role = patient_access_role(user)

    drug = req_args.get("drug")

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    filters = [
        TBMaster.AnalysisDateTime.between(dates[0], dates[1]),
        # TBMaster.FinalResult.isnot(None),
        ColumnNames.isnot(None),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    try:
        drug_column = getattr(TBMaster, drug)

        # Generate all count columns dynamically
        count_columns = [
            create_count_column(
                start, end, state, values, TBMaster, drug_column, gx_result_type
            )
            for (start, end) in TB_AGE_RANGES
            for state, values in TB_RESISTANCE_STATES.items()
        ]

        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            # print("Calling get_patients for health_facility")

            query = get_patients(
                health_facility=health_facility,
                lab=None,
                dates=dates,
                model=TBMaster,
                indicator=TBMaster.AnalysisDateTime,
                gx_result_type=gx_result_type,
                test_type="tb",
                month=None,
                year=None,
            )

            print(str(query.statement))

            data = query.all()

            response = process_patients(
                data, dates, facility_type, gx_result_type, "tb", None, None
            )

            return response
        elif facility_type == "health_facility" and user_role != "Admin":
            return {
                "status": "error",
                "code": 403,
                "message": f"Forbidden - User with id {user_id} and role {user_role} is not authorized to access this resource.",
            }
        elif not facilities:
            # If no facilities are provided, query all facilities
            query = (
                TBMaster.query.with_entities(
                    ColumnNames.label("Facility"), *count_columns
                )
                .filter(*filters)
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )
        else:
            # If facilities are provided, query only those facilities
            query = (
                TBMaster.query.with_entities(
                    ColumnNames.label("Facility"), *count_columns
                )
                .filter(
                    *filters,
                    GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                        facilities
                    ),
                )
                .group_by(ColumnNames)
                .order_by(ColumnNames)
            )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Facility": row.Facility,
                "0_4": {
                    "Resistance_Detected": row.Resistance_Detected_0_4,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_0_4,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_0_4,
                },
                "5_9": {
                    "Resistance_Detected": row.Resistance_Detected_5_9,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_5_9,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_5_9,
                },
                "10_14": {
                    "Resistance_Detected": row.Resistance_Detected_10_14,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_10_14,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_10_14,
                },
                "15_19": {
                    "Resistance_Detected": row.Resistance_Detected_15_19,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_15_19,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_15_19,
                },
                "20_24": {
                    "Resistance_Detected": row.Resistance_Detected_20_24,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_20_24,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_20_24,
                },
                "25_29": {
                    "Resistance_Detected": row.Resistance_Detected_25_29,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_25_29,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_25_29,
                },
                "30_34": {
                    "Resistance_Detected": row.Resistance_Detected_30_34,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_30_34,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_30_34,
                },
                "35_39": {
                    "Resistance_Detected": row.Resistance_Detected_35_39,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_35_39,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_35_39,
                },
                "40_44": {
                    "Resistance_Detected": row.Resistance_Detected_40_44,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_40_44,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_40_44,
                },
                "45_49": {
                    "Resistance_Detected": row.Resistance_Detected_45_49,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_45_49,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_45_49,
                },
                "50_54": {
                    "Resistance_Detected": row.Resistance_Detected_50_54,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_50_54,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_50_54,
                },
                "55_59": {
                    "Resistance_Detected": row.Resistance_Detected_55_59,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_55_59,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_55_59,
                },
                "60_64": {
                    "Resistance_Detected": row.Resistance_Detected_60_64,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_60_64,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_60_64,
                },
                "65+": {
                    "Resistance_Detected": row.Resistance_Detected_65_plus,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_65_plus,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_65_plus,
                },
                "Not_Specified": {
                    "Resistance_Detected": row.Resistance_Detected_Not_Specified,
                    "Resistance_Not_Detected": row.Resistance_Not_Detected_Not_Specified,
                    "Resistance_Indeterminate": row.Resistance_Indeterminate_Not_Specified,
                },
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Disaggregation": disaggregation,
                "Facility_Type": facility_type,
                "Type_Of_Result": gx_result_type if gx_result_type else "All",
                "Drug": drug,
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


def rejected_samples_by_facility_service(req_args):
    """
    Retrieve the number of rejected samples by facility
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
        disaggregation, facility_type, TBMaster, "facilities")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.RegisteredDateTime.is_not(None),
        or_(
            func.length(TBMaster.LIMSRejectionCode) > 0,
            func.length(TBMaster.LIMSRejectionDesc) > 0,
        ),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    if facilities:
        filters.append(
            GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                facilities
            )
        )

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=health_facility,  # No facility is required here
                lab=None,
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
                case(
                    (
                        or_(
                            ColumnNames.is_(None),
                            func.length(ColumnNames) == 0,
                        ),
                        literal("Not Specified"),
                    ),
                    else_=ColumnNames,
                ).label("Facility"),
                TOTAL_ALL.label("total"),
            )
            .filter(
                *filters,
            )
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        # Serialize de data to JSON
        response = [
            {
                "Facility": row.Facility,
                "Rejected_Samples": row.total,
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
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def rejected_samples_by_facility_by_month_service(req_args):
    """
    Retrieve the number of rejected samples by facility by month
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
        disaggregation, facility_type, TBMaster, "facilities")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        or_(
            func.length(TBMaster.LIMSRejectionCode) > 0,
            func.length(TBMaster.LIMSRejectionDesc) > 0,
        ),
    ]

    fields = [
        TOTAL_ALL.label("total"),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    if facilities:
        filters.append(
            GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                facilities
            )
        )

    if month is not None:
        fields.append(ColumnNames.label("Facility"))
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
                health_facility=health_facility,  # No facility is required here
                lab=None,
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
            .filter(
                *filters,
            )
            .group_by(*grouping)
            .order_by(*ordering)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        # Query the data
        data = query.all()

        if month and year:
            response = [
                {
                    "Facility": row.Facility,
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


def rejected_samples_by_facility_by_reason_service(req_args):
    """
    Retrieve the number of rejected samples by reason by facility
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
        disaggregation, facility_type, TBMaster, "facilities")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.RegisteredDateTime.between(dates[0], dates[1]),
        TBMaster.RegisteredDateTime.is_not(None),
        or_(
            func.length(TBMaster.LIMSRejectionCode) > 0,
            func.length(TBMaster.LIMSRejectionDesc) > 0,
        ),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if lab_type.lower() != "all":
        filters.append(LAB_TYPE(TBMaster, lab_type))

    if facilities:
        filters.append(
            GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                facilities
            )
        )

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
                health_facility=health_facility,  # No facility is required here
                lab=None,
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
                case(
                    (
                        or_(
                            ColumnNames.is_(None),
                            func.length(ColumnNames) == 0,
                        ),
                        literal("Not Specified"),
                    ),
                    else_=ColumnNames,
                ).label("Facility"),
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
                TOTAL_ALL.label("total"),
            )
            .filter(
                *filters,
            )
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        response = [
            {
                "Facility": row.Facility,
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
    except Exception as e:
        # Prepare the error response
        response = {
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

        return response


def rejected_samples_by_facility_by_reason_by_month_service(req_args):
    """
    Retrieve the number of rejected samples by facility by reason by month
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
    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

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
        TOTAL_ALL.label("total"),
    ]

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    if facilities:
        filters.append(
            GET_COLUMN_NAME(False, facility_type, TBMaster, "facilities").in_(
                facilities
            )
        )

    if month is not None:
        fields.append(ColumnNames.label("Facility"))
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
                health_facility=health_facility,  # No facility is required here
                lab=None,
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
                    "Facility": row.Facility,
                    "Month": month,
                    "Year": year,
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


def trl_samples_by_facility_by_days_service(req_args):
    """
    Retrieve the turnaround time samples tested in days
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip() for f in facilities if f.strip()]

    filters = [
        TBMaster.AuthorisedDateTime.between(dates[0], dates[1]),
        TBMaster.AuthorisedDateTime.is_not(None),
        TBMaster.RequestingProvinceName.is_not(None),
        TBMaster.RequestingDistrictName.is_not(None),
        TBMaster.RequestingFacilityName.is_not(None),
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

    trl_functions = trl_by_lab_by_days(TBMaster)

    days_groups = [
        (
            func.count(case(((value.between(min_days, max_days), 1)))).label(
                f"{key}_between_{min_days}_{max_days}"
            )
            if min_days is not None and max_days is not None
            else (
                func.count(case(((value < max_days), 1))).label(
                    f"{key}_less_than_{max_days}"
                )
                if min_days is None
                else (
                    func.count(case(((value > min_days), 1))).label(
                        f"{key}_greater_than_{min_days}"
                    )
                )
            )
        )
        for key, value in trl_functions.items()
        for min_days, max_days in TRL_DAYS
    ]

    # print(select(*age_groups))

    try:
        if facility_type == "health_facility" and user_role == "Admin":
            # Call get_patients if facility_type is equal to health_facility
            # And disaggregation is true
            query = get_patients(
                health_facility=health_facility,  # No facility is required here
                lab=None,
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
                ColumnNames.label("facility"),
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
                "Facility": row.facility,
                "Total": row.total,
                "Role": user_role,
                "Specimen_Datetime_Null": row.specimen_datetime_null,
                "Received_Datetime_Null": row.received_datetime_null,
                "Authorised_Datetime_Null": row.authorised_datetime_null,
                **{
                    key: {
                        # Replaces the key name from the key and maintains the ages structure
                        # in the subdictionary
                        day_group.name.replace(f"{key}_", ""): getattr(
                            row, day_group.name
                        )
                        for day_group in days_groups
                        if day_group.name.startswith(f"{key}_")
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


def trl_samples_by_facility_by_days_tb_service(req_args):
    """
    Retrieve the turnaround time tested samples in days for pnct specifique time range
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
            "Status": "error",
            "Data": [],
            "Message": f"An error occurred: {str(e)}",
        }

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    facilities = [f.strip() for f in facilities] if facilities else []

    filters = [
        TBMaster.AuthorisedDateTime.between(dates[0], dates[1]),
        TBMaster.AuthorisedDateTime.is_not(None),
        TBMaster.RequestingProvinceName.is_not(None),
        TBMaster.RequestingDistrictName.is_not(None),
        TBMaster.RequestingFacilityName.is_not(None),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.RequestingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.RequestingDistrictName.in_(facilities))
        elif facility_type == "facility":
            filters.append(TBMaster.RequestingFacilityName.in_(facilities))
    
    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    trl_by_lab_by_days = trl_by_lab_by_days_tb(TBMaster)

    days_groups_tb = []

    days_groups_tb = []

    for key, value in trl_by_lab_by_days.items():

        if key == "colheita_us__recepcao_lab":

            days_groups_tb.append(
                func.count(case(((value < 5), 1))).label(f"{key}_days_under_5")
            )

            days_groups_tb.append(
                func.count(case(((value > 5), 1))).label(f"{key}_days_over_5")
            )

        elif key == "recepcao_lab__validacao_no_lab":

            days_groups_tb.append(
                func.count(case(((value < 2), 1))).label(f"{key}_days_under_2")
            )

            days_groups_tb.append(
                func.count(case(((value >= 2), 1))).label(f"{key}_days_over_2")
            )

        else:

            days_groups_tb.append(
                func.count(case(((value < 7), 1))).label(f"{key}_days_under_7")
            )

            days_groups_tb.append(
                func.count(case(((value >= 7), 1))).label(f"{key}_days_over_7")
            )

    # for day_group in days_groups_tb:
    #     print(day_group)

    try:
        if facility_type == "health_facility" and user_role == "Admin":

            query = get_patients(
                health_facility=health_facility,  # No facility is required here
                lab=None,
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
                ColumnNames.label("facility"),
                *days_groups_tb,
                TOTAL_ALL.label("total"),
            )
            .filter(*filters)
            .group_by(ColumnNames)
            .order_by(ColumnNames)
        )

        # print(query)

        # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

        data = query.all()

        # print(type(data[0]))
        # print(query.column_descriptions)
        response = []

        for row in data:

            metrics = {}

            for expr in days_groups_tb:

                name = expr.name
                value = getattr(row, name)

                # exemplo:
                # colheita_us__recepcao_lab_days_under_5
                # colheita_us__recepcao_lab_days_over_5

                if "_days_under_" in name:
                    metric, limit = name.split("_days_under_")
                    key = f"<{limit}"

                elif "_days_over_" in name:
                    metric, limit = name.split("_days_over_")
                    key = f">{limit}"

                else:
                    continue

                if metric not in metrics:
                    metrics[metric] = {}

                metrics[metric][key] = value

            response.append({
                "Facility": row.facility,
                "Total": row.total,
                "Role": user_role,
                **metrics,
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Type_Of_Result": gx_result_type or "All",
            })

        # Return the response
        return response

    except Exception as e:

        response = {
            "status": "error",
            "code": 500,
            "message": "An Error Occurred",
            "error": str(e),
        }

        return response
    

def trl_samples_by_facility_by_days_by_month_service(req_args):
    """
    Retrieve the turnaround time tested samples in days by month
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
        disaggregation, facility_type, TBMaster, "facilities")

    # Remove any empty or whitespace-only entries from facilities
    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AuthorisedDateTime.between(dates[0], dates[1]),
        TBMaster.RequestingProvinceName.is_(None),
        TBMaster.RequestingDistrictName.is_(None),
        TBMaster.RequestingFacilityName.is_(None),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.RequestingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.RequestingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.RequestingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

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
        fields.append(ColumnNames.label("facility"))
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
                health_facility=health_facility,  # No facility is required here
                lab=None,
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
                    "Facility": row.facility,
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


def trl_samples_avg_by_facility_service(req_args):
    """
    Retrieve the average turnaround time tested samples in days by facility
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

    user_role = patient_access_role(user)

    ColumnNames = GET_COLUMN_NAME(
        disaggregation, facility_type, TBMaster, "facilities")

    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AuthorisedDateTime.between(dates[0], dates[1]),
        TBMaster.AuthorisedDateTime.is_not(None),
        TBMaster.RequestingProvinceName.is_not(None),
        TBMaster.RequestingDistrictName.is_not(None),
        TBMaster.RequestingFacilityName.is_not(None),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.RequestingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.RequestingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.RequestingFacilityName.in_(facilities))

    if gx_result_type not in ("All", None):
        filters.append(TBMaster.TypeOfResult == gx_result_type)

    trl_avg_days = trl_by_lab_avg_days(TBMaster)

    avg_days_group = [
        case(((value == 0, 1)), else_=value).label(key)
        for key, value in trl_avg_days.items()
    ]

    try:

        if facility_type == "health_facility" and user_role == "Admin":
            query = get_patients(
                health_facility=health_facility,  # No facility is required here
                lab=None,
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
                ColumnNames.label("Facility"),
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
                "Facility": row.Facility,
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


def trl_samples_avg_by_facility_month_service(req_args):
    """
    Retrieve the average turnaround time tested samples in days by facility
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
        disaggregation, facility_type, TBMaster, "facilities")

    facilities = [f.strip()
                  for f in facilities if f.strip()] if facilities else []

    filters = [
        TBMaster.AuthorisedDateTime.between(dates[0], dates[1]),
        TBMaster.AuthorisedDateTime.is_not(None),
        TBMaster.RequestingProvinceName.is_not(None),
        TBMaster.RequestingDistrictName.is_not(None),
        TBMaster.RequestingFacilityName.is_not(None),
    ]

    if facilities:
        if facility_type == "province":
            filters.append(TBMaster.RequestingProvinceName.in_(facilities))
        elif facility_type == "district":
            filters.append(TBMaster.RequestingDistrictName.in_(facilities))
        elif facility_type == "health_facility":
            filters.append(TBMaster.RequestingFacilityName.in_(facilities))

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
        fields.append(ColumnNames.label("facility"))
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
                health_facility=health_facility,  # No facility is required here
                lab=None,
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
                    "Facility": row.facility,
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
