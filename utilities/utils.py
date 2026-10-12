from sqlalchemy import and_, or_, func, case, text
from datetime import datetime
from dateutil.relativedelta import relativedelta
from configs.paths import *

# -----------------------------------------------------------------------------
# Dynamic date helpers
# -----------------------------------------------------------------------------
# These were previously calculated once at import time which meant that on
# long-running production servers the default date range drifted further into
# the past every day. They are now regenerated on every call.

def today():
    """Return the current date as a ``YYYY-MM-DD`` string."""
    return datetime.now().strftime("%Y-%m-%d")


def twelve_months_ago():
    """Return the date 12 months ago as a ``YYYY-MM-DD`` string."""
    return (datetime.now() - relativedelta(months=12)).strftime("%Y-%m-%d")


# Lambda function to extract the year from a date and label it as "year"
def YEAR(date_and_time):
    """
    Extract the year from a date and label it as "year"

    Parameters
    ----------
    date_and_time : datetime
        The date and time to extract the year from

    Returns
    -------
    year : int
        The extracted year
    """

    return func.year(date_and_time).label("year")


# Lambda function to extract the month from a date and label it as "month"
def MONTH(date_and_time):
    """
    Extract the month from a date and label it as "month"

    Parameters
    ----------
    date_and_time : datetime
        The date and time to extract the month from

    Returns
    -------
    month : int
        The extracted month
    """

    return func.month(date_and_time)


# Lambda function to extract a specific date part from a date and label it with the given name
def DATE_PART(date_name, date_and_time):
    """
    Extracts a specific date part from a date and labels it with the given name.

    Parameters
    ----------
    date_name : str
        The name of the date part to extract, e.g., "year", "month", "day", "dayofweek", "quarter", etc.
    date_and_time : datetime
        The date from which to extract the part.

    Returns
    -------
    sqlalchemy.sql.expression.Function
        A SQLAlchemy Function object that extracts the given date part from the given date and labels it with the given name.
    """
    return func.datename(text(date_name), date_and_time)


# Lambda function to extract the quarter from a date and label it as "quarter"


def QUARTER(date_and_time):
    """
    Extract the quarter from a date and label it as "quarter"

    Parameters
    ----------
    date_and_time : datetime
        The date and time to extract the quarter from

    Returns
    -------
    quarter : int
        The extracted quarter
    """
    return func.quarter(date_and_time)


# Lambda function to extract the day of the week from a date and label it as "week"


def WEEK(date_and_time):
    """
    Extract the day of the week from a date and label it as "week"

    Parameters
    ----------
    date_and_time : datetime
        The date and time to extract the day of the week from

    Returns
    -------
    week : int
        The extracted day of the week
    """
    return func.dayofweek(date_and_time)


# Lambda function to extract the day from a date and label it as "day"


def DAY(date_and_time):
    """
    Extract the day from a date and label it as "day"

    Parameters
    ----------
    date_and_time : datetime
        The date and time to extract the day from

    Returns
    -------
    day : int
        The extracted day
    """

    return func.day(date_and_time)


# Lambda function to return a statment for Conventional or POC type of laboratory


def LAB_TYPE(Model, lab_type):
    """
    A lambda function to return a statment for Conventional or POC type of laboratory
    based on the RequestID in Model table.

    Parameters
    ----------
    Model : sqlalchemy.ext.declarative.DeclarativeMeta
        The Model table
    lab_type : str
        The type of laboratory to return a statment for

    Returns
    -------
    sqlalchemy.sql.elements.BinaryExpression
        A statement for Conventional or POC type of laboratory
    """
    if lab_type == "Point_Of_Care":
        return func.isnumeric(func.substring(Model.RequestID, 7, 3)) == 1
    elif lab_type == "Conventional":
        return func.isnumeric(func.substring(Model.RequestID, 7, 3)) == 0


# Lambda function to count the total number of rows and label it as "total"
TOTAL_ALL = func.count().label("total")

# Lambda function to count the number of non-null values in a field and label it as "total_not_null"


def TOTAL_NOT_NULL(field):
    """
    A lambda function to count the number of non-null values in a field and label it as "total_not_null"

    Parameters
    ----------
    field : sqlalchemy.sql.elements.ColumnClause
        The field to count the number of non-null values

    Returns
    -------
    sqlalchemy.sql.elements.Label
        A statement with the label "total_not_null"
    """

    return func.count(
        case(
            (
                (
                    and_(
                        field.isnot(None),
                        func.length(field) > 0,
                    ),
                    1,
                )
            ),
            else_=None,
        )
    )


# Lambda function to count the number of null values in a field and label it as "total_null"


def TOTAL_NULL(field):
    """
    A lambda function to count the number of null values in a field and label it as "total_null"

    Parameters
    ----------
    field : sqlalchemy.sql.elements.ColumnClause
        The field to count the number of null values

    Returns
    -------
    sqlalchemy.sql.elements.Label
        A statement with the label "total_null"
    """

    return func.count(
        case(
            (
                (
                    or_(
                        field.is_(None),
                        func.length(field) == 0,
                    ),
                    1,
                )
            ),
            else_=None,
        )
    )


# Lambda function to count the number of values in a field that are in a given list of values and label it as "total_in"


def TOTAL_IN(field, values):
    """
    A lambda function to count the number of values in a field that are in a given list of values and label it as "total_in"

    Parameters
    ----------
    field : sqlalchemy.sql.elements.ColumnClause
        The field to count the number of values
    values : list
        The list of values to count

    Returns
    -------
    sqlalchemy.sql.elements.Label
        A statement with the label "total_in"
    """
    return func.count(
        case(
            (
                (
                    and_(
                        field.isnot(None),
                        field.in_(values),
                    ),
                    1,
                )
            ),
            else_=None,
        )
    )


# Lambda function to calculate the average difference in days between two date fields and label it as "date_diff_avg_{field1}_to_{field2}"


def DATE_DIFF_AVG(fields):
    """
    A lambda function to calculate the average difference in days between two date fields and label it as "date_diff_avg_{field1}_to_{field2}"

    Parameters
    ----------
    field1 : sqlalchemy.sql.elements.ColumnClause
        The first date field
    field2 : sqlalchemy.sql.elements.ColumnClause
        The second date field

    Returns
    -------
    sqlalchemy.sql.elements.Label
        A statement with the label "date_diff_avg_{field1}_to_{field2}"
    """

    return func.avg(func.datediff(text("day"), fields[0], fields[1])).label(
        f"date_diff_avg_{fields[0]}_to_{fields[1]}"
    )


# Lambda function to calculate the minimum difference in days between two date fields and label it as "date_diff_min_{field1}_to_{field2}"


def DATE_DIFF_MIN(fields):
    """
    A lambda function to calculate the minimum difference in days between two date fields and label it as "date_diff_min_{field1}_to_{field2}"

    Parameters
    ----------
    field1 : sqlalchemy.sql.elements.ColumnClause
        The first date field
    field2 : sqlalchemy.sql.elements.ColumnClause
        The second date field

    Returns
    -------
    sqlalchemy.sql.elements.Label
        A statement with the label "date_diff_min_{field1}_to_{field2}"
    """
    return func.min(func.datediff(text("day"), fields[0], fields[1])).label(
        f"date_diff_min_{fields[0]}_to_{fields[1]}"
    )


# Lambda function to calculate the maximum difference in days between two date fields and label it as "date_diff_max_{field1}_to_{field2}"


def DATE_DIFF_MAX(fields):
    """
    A lambda function to calculate the maximum difference in days between two date fields and label it as "date_diff_max_{field1}_to_{field2}"

    Parameters
    ----------
    field1 : sqlalchemy.sql.elements.ColumnClause
        The first date field
    field2 : sqlalchemy.sql.elements.ColumnClause
        The second date field

    Returns
    -------
    sqlalchemy.sql.elements.Label
        A statement with the label "date_diff_max_{field1}_to_{field2}"
    """
    return func.max(func.datediff(text("day"), fields[0], fields[1])).label(
        f"date_diff_max_{fields[0]}_to_{fields[1]}"
    )


# Lambda function to count the number of rows where a field matches a given value and label it as "suppression"


def SUPPRESSION(field, value):
    """
    A lambda function to count the number of rows where a field matches a given value and label it as "suppression"

    Parameters
    ----------
    field : sqlalchemy.sql.elements.ColumnClause
        The field to count the number of values
    value : str
        The value to count

    Returns
    -------
    sqlalchemy.sql.elements.Label
        A statement with the label "suppression"
    """
    return func.count(case((field == f"{value}", 1), else_=None))


# Lambda function to count the number of rows where two fields match given values and label it as "gender_suppression"


def GENDER_SUPPRESSION(fields, values):
    """
    A lambda function to count the number of rows where two fields match given values and label it as "gender_suppression"

    Parameters
    ----------
    fields : list
        A list of two sqlalchemy.sql.elements.ColumnClause, the first for the patient's gender and the second for the patient's age
    values : list
        A list of two values to count, the first for the patient's gender and the second for the patient's age

    Returns
    -------
    sqlalchemy.sql.elements.Label
        A statement with the label "gender_suppression"
    """
    return func.count(
        case(
            ((and_(fields[0] == values[0], fields[1] == values[1]), 1)), else_=None)
    )


# List of possible values for the final result that indicate detection
FINAL_RESULT_DETECTED_VALUES = [
    "MTB DETECTADO ALTO",
    "MTB DETECTADO BAIXISSIMO",
    "MTB DETECTADO BAIXO",
    "MTB DETECTADO MEDIO",
    "MTB DETECTADO MUITO BAIXO",
    "MTB DETECTED",
    "MTB Detected HI",
    "MTB Detected Low",
    "MTB Detected Medium",
    "MTB Detected Muito Baixo",
    "MTB Detected Very Low",
    "TRAÇOS DE MTB DETECTADOS",
    "DETECTED",
]


def trl_by_lab_by_days(TBMaster):
    """
    Function to calculate the turnaround time (TAT) by laboratory in days

    Parameters
    ----------
    TBMaster : sqlalchemy.ext.declarative.DeclarativeMeta
        The TBMaster model

    Returns
    -------
    dict
        A dictionary with the following keys and values:
        - colheita_us__recepcao_lab: The turnaround time from specimen collection to reception in the laboratory
        - recepcao_lab__validacao_no_lab: The turnaround time from reception in the laboratory to validation
        - colheita_us__validacao_no_lab: The turnaround time from specimen collection to validation
    """
    return {
        "colheita_us__recepcao_lab": func.datediff(
            text("DAY"), TBMaster.SpecimenDatetime, TBMaster.ReceivedDateTime
        ),
        "recepcao_lab__validacao_no_lab": func.datediff(
            text("DAY"), TBMaster.ReceivedDateTime, TBMaster.AuthorisedDateTime
        ),
        "colheita_us__validacao_no_lab": func.datediff(
            text("DAY"), TBMaster.SpecimenDatetime, TBMaster.AuthorisedDateTime
        ),
    }


def trl_by_lab_by_days_tb(TBMaster):
    """
    Function to calculate the turnaround time (TAT) by laboratory in days using TBMaster model
    
    Parameters
    ----------
    TBMaster : sqlalchemy.ext.declarative.DeclarativeMeta
        The TBMaster model
    
    Returns
    -------
    dict
        A dictionary with the following keys and values:
        - colheita_us__recepcao_lab: The turnaround time from specimen collection to reception in the laboratory
        - recepcao_lab__validacao_no_lab: The turnaround time from reception in the laboratory to validation
        - colheita_us__validacao_no_lab: The turnaround time from specimen collection to validation
    """
    return {
        "colheita_us__recepcao_lab": func.datediff(
            text("DAY"), TBMaster.SpecimenDatetime, TBMaster.ReceivedDateTime
        ),
        "recepcao_lab__validacao_no_lab": func.datediff(
            text("DAY"), TBMaster.ReceivedDateTime, TBMaster.AuthorisedDateTime
        ),
        "colheita_us__validacao_no_lab": func.datediff(
            text("DAY"), TBMaster.SpecimenDatetime, TBMaster.AuthorisedDateTime
        ),
    }


def trl_by_lab_avg_days(TBMaster):
    """
    Function to calculate the average turnaround time (TAT) by laboratory in days

    Parameters
    ----------
    TBMaster : sqlalchemy.ext.declarative.DeclarativeMeta
        The TBMaster model

    Returns
    -------
    dict
        A dictionary with the following keys and values:
        - colheita_us__recepcao_lab: The average turnaround time from specimen collection to reception in the laboratory
        - recepcao_lab__registo_no_lab: The average turnaround time from reception in the laboratory to registration
        - registo_no_lab__analise_no_lab: The average turnaround time from registration to analysis in the laboratory
        - analise_no_lab__validacao_no_lab: The average turnaround time from analysis in the laboratory to validation
    """
    return {
        "colheita_us__recepcao_lab": func.avg(
            func.datediff(text("DAY"), TBMaster.SpecimenDatetime,
                          TBMaster.ReceivedDateTime)
        ),
        "recepcao_lab__registo_no_lab": func.avg(
            func.datediff(text("DAY"), TBMaster.ReceivedDateTime,
                          TBMaster.RegisteredDateTime)
        ),
        "registo_no_lab__analise_no_lab": func.avg(
            func.datediff(text("DAY"), TBMaster.RegisteredDateTime,
                          TBMaster.AnalysisDateTime)
        ),
        "analise_no_lab__validacao_no_lab": func.avg(
            func.datediff(text("DAY"), TBMaster.AnalysisDateTime,
                          TBMaster.AuthorisedDateTime)
        ),
    }


# List of possible values for the final result that indicate non-detection
FINAL_RESULT_NOT_DETECTED_VALUES = [
    "Micobacterias Não TB",
    "MTB not detected",
    "Not Detected",
    "NDET",
    "MICNO",
    "AMK Resistance NOT DETECTED",
    "CAP Resistance NOT DETECTED",
]


FINAL_RESULT_INDETERMINATE_VALUES = [
    "MTB Indeterminate",
    "Resistance Indeterminate",
    "RIF Resistance Indeterminate",
]

FINAL_RESULT_ERROR_DETECTED_VALUES = [
    "No Result",
    "Not Applicable",
    "Error",
    "Insufficient sample",
    "Instrument out of order",
    "INS",
]


FINAL_RESULT_INVALID_VALUES = [
    "INVALIDO",
    "Invalid",
    "Not viscous/Watery",
    "Very Viscous",
]

# List of possible values for rifampicin result that indicate non-detection
NOT_DETECTED_VALUES = [
    "MTB not detected",
    "NDET",
    "No Result",
    "NORES",
    "Resistance Not Detected",
    "RIF Resistance Not Detected",
]

# List of possible values for rifampicin result that indicate detection
DETECTED_VALUES = [
    "DET",
    "MTB Detected Medium",
    "Resistance Detected",
    "RIF Resistance Detected",
]

INDETERMINATED_VALUES = [
    "Indeterminate",
    "Resistance Indeterminate",
]

# List of possible values for the sputum specimen source code that indicate TB specimens
TB_SPUTUM_SPECIMEN_SOURCE_CODES = [
    "SPTX",
    "SPTX-L",
    "SPTX-M",
    "SPTX-S",
    "EXP",
    "ESCAR",
    "SAL",
]

# List of possible values for the feces specimen source code that indicate TB specimens
TB_FECES_SPECIMEN_SOURCE_CODES = ["FEC", "FEC-L", "FEC-M", "FEC-S", "FZ", "FF"]

# List of possible values for the urine specimen source code that indicate TB specimens
TB_URINE_SPECIMEN_SOURCE_CODES = [
    "UR", "UR-L", "UR-M", "UR-S", "U", "SUF", "US"]

# List of possible values for the blood specimen source code that indicate TB specimens
TB_BLOOD_SPECIMEN_SOURCE_CODES = [
    "BLO", "BLO-L", "BLO-M", "BLO-S", "SA", "SAT"]

# List of possible values for the Pleural Liquid specimen source code that indicate TB specimens
TB_PL_SPECIMEN_SOURCE_CODES = ["LP"]


# Define age ranges
TB_AGE_RANGES = [
    (0, 4),
    (5, 9),
    (10, 14),
    (15, 19),
    (20, 24),
    (25, 29),
    (30, 34),
    (35, 39),
    (40, 44),
    (45, 49),
    (50, 54),
    (55, 59),
    (60, 64),
    (65, None),
    (None, None),
]

TRL_DAYS = [
    (None, 7),
    (7, 15),
    (16, 21),
    (21, None),
]

# Define resistance states
TB_RESISTANCE_STATES = {
    "Detected": DETECTED_VALUES,
    "Not_Detected": NOT_DETECTED_VALUES,
    "Indeterminate": INDETERMINATED_VALUES,
}

# Define rejection reasons
SPECIMEN_REJECTION_CODES = {
    "INSUFICIENT_SPECIMEN": ["INS"],
    "SPECIMEN_NOT_RECEIVED": ["NSRP", "RSA", "SDBSA", "EMPT"],
    "SPECIMEN_UNSUITABLE_FOR_TESTING": [
        "UNS",
        "DRY",
        "AMCON",
        "SOIL",
        "RECDE",
        "SPUN",
        "INLS",
        "AMONR",
    ],
    "EQUIPMENT_FAILURE": ["MACH"],
    "REPEAT_SPECIMEN_COLLECTION": ["REPIT", "REJOL", "SPUN2"],
    "LABORATORY_ACIDENT": ["ACC"],
    "MISSING_REAGENT": ["FDR"],
    "DOUBLE_REGISTRATION": ["DUPRG"],
    "TECHNICAL_ERROR": ["ERRTC", "PROBT"],
    "OTHER": ["OUTR", "COM"],
}

SPECIMEN_REJECTION_CODES_VALUES = {
    "INSUFICIENT_SPECIMEN": ["Insufficient Sample"],
    "SPECIMEN_NOT_RECEIVED": [
        "Unsuitable for testing",
        "Dry Specimen",
        "DBS sem amostra",
        "Empty container received",
    ],
    "SPECIMEN_UNSUITABLE_FOR_TESTING": [
        "Unsuitable Specimen",
        "Dry Specimen",
        "Amostra contaminada com Produt",
        "Soiled Containers",
        "Overfilled container",
    ],
    "EQUIPMENT_FAILURE": ["Machine Breakdown"],
    "REPEAT_SPECIMEN_COLLECTION": [
        "Repeat Collection",
        "Repeat sample collection",
        "please repeat",
    ],
    "SPECIMEN_NOT_LABELED": ["Specimen Not Labelled", "Inadequately labeled samples"],
    "LABORATORY_ACIDENT": ["Laboratory Accident", "Problemas tecnicos no laborato"],
    "MISSING_REAGENT": ["Falts de reagente"],
    "DOUBLE_REGISTRATION": ["Double registration"],
    "TECHNICAL_ERROR": ["Error tecnico"],
    "OTHER": ["Outros", "Outros"],
}


def get_token(request):
    """
    Extract the token from the Authorization header of a request.

    This function retrieves the token from the 'Authorization' header
    in the request object. If the header is not present or does not
    contain a Bearer token, it returns None.

    Args:
        request: The HTTP request object containing headers.

    Returns:
        str or None: The extracted token if present, otherwise None.
    """

    auth_header = (request.headers.get("Authorization") or "").strip()
    scheme, _, token = auth_header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def get_user_token_info(token_payload):

    user_info = {
        "user_id": token_payload.get("user_id") or token_payload.get("sub"),
        "user_name": token_payload.get("user_name"),
        "first_name": token_payload.get("first_name"),
        "last_name": token_payload.get("last_name"),
        "email_address": token_payload.get("email_address"),
        "full_name": token_payload.get("full_name")
    }

    return user_info


def generate_drug_cases(TBMaster, drug):
    """
    Generate SQLAlchemy count expressions for drug resistance cases.

    This function creates three count expressions for a given drug and result type:
    1. Resistance Detected
    2. Resistance Not Detected
    3. Resistance Indeterminate

    Each expression counts the number of records in the TBMaster table where:
    - The TypeOfResult matches the given `gx_result_type`.
    - The specified drug attribute is not None and matches one of the detection values
    (DETECTED_VALUES, NOT_DETECTED_VALUES, or INDETERMINATED_VALUES).

    Args:
        TBMaster: The SQLAlchemy model representing the master table of TB data.
        drug (str): The name of the drug column in the TBMaster table.
        gx_result_type (str): The type of GeneXpert result to filter by.

    Returns:
        list: A list of SQLAlchemy count expressions labeled for each resistance state.
    """
    return [
        func.count(
            case(
                (
                    and_(
                        getattr(TBMaster, drug).isnot(None),
                        getattr(TBMaster, drug).in_(DETECTED_VALUES),
                    ),
                    1,
                )
            )
        ).label(f"{drug}_Resistance_Detected"),
        func.count(
            case(
                (
                    and_(
                        getattr(TBMaster, drug).isnot(None),
                        getattr(TBMaster, drug).in_(NOT_DETECTED_VALUES),
                    ),
                    1,
                )
            )
        ).label(f"{drug}_Resistance_Not_Detected"),
        func.count(
            case(
                (
                    and_(
                        getattr(TBMaster, drug).isnot(None),
                        getattr(TBMaster, drug).in_(INDETERMINATED_VALUES),
                    ),
                    1,
                )
            )
        ).label(f"{drug}_Resistance_Indeterminate"),
    ]


def create_count_column(
    age_start, age_end, state, values, TBMaster, drug_column, gx_result_type
):
    """
    Create a SQLAlchemy column that counts the number of records in a TBMaster query
    that match a given condition.

    Parameters
    ----------
    age_start : int
        The start of the age range to filter by.
    age_end : int or None
        The end of the age range to filter by. If None, the filter is for 65+.
    state : str
        The state of the TB test result (e.g. 'Detected', 'Not_Detected', 'Indeterminate').
    values : list of str
        The values that the drug column should be in.
    TBMaster : sqlalchemy declarative base
        The TBMaster table.
    drug_column : sqlalchemy column
        The column of the drug to filter by.
    gx_result_type : str
        The type of result to filter by (e.g. 'Xpert', 'Ultra').

    Returns
    -------
    sqlalchemy.sql.expression.Function
        A column that can be added to a query that counts the number of records that
        match the condition.
    """

    if age_start is None and age_end is None:
        age_condition = TBMaster.AgeInYears.is_(None)
        label_suffix = "Not_Specified"
    else:
        age_condition = (
            TBMaster.AgeInYears >= age_start
            if age_end is None
            else TBMaster.AgeInYears.between(age_start, age_end)
        )

        label_suffix = (
            f"{age_start}_{age_end}" if age_end is not None else f"{age_start}_plus"
        )

    condition = (
        and_(
            drug_column.in_(values),
            age_condition,
        )
        if drug_column is not None
        else (and_(age_condition))
    )

    return func.count(case({condition: 1}, else_=None)).label(
        f"Resistance_{state}_{label_suffix}"
    )


def GET_COLUMN_NAME(disaggregation, facility_type, Model, flag):
    """
    Get the appropriate column name based on the disaggregation and facility type.

    Parameters
    ----------
    disaggregation : bool
        Whether to disaggregate the data or not.
    facility_type : str
        The type of facility (province, district, or health facility).
    TbMaster : object
        The TbMaster object containing the column names.

    Returns
    -------
    str
        The appropriate column name based on the given parameters.
    """
    if disaggregation is True:
        if facility_type == "province":
            if flag == "facilities":
                return Model.RequestingDistrictName
            if flag == "laboratories":
                return Model.TestingDistrictName
        elif facility_type == "district":
            if flag == "facilities":
                return Model.RequestingFacilityName
            if flag == "laboratories":
                return Model.TestingFacilityName
        elif facility_type == "health_facility":
            if flag == "facilities":
                return Model.RequestingDistrictName
            if flag == "laboratories":
                return Model.TestingDistrictName
        else:
            if flag == "facilities":
                return Model.RequestingProvinceName
            if flag == "laboratories":
                return Model.TestingProvinceName
    else:
        if facility_type == "province":
            if flag == "facilities":
                return Model.RequestingProvinceName
            if flag == "laboratories":
                return Model.TestingProvinceName
        elif facility_type == "district":
            if flag == "facilities":
                return Model.RequestingDistrictName
            if flag == "laboratories":
                return Model.TestingDistrictName
        elif facility_type == "health_facility":
            if flag == "facilities":
                return Model.RequestingFacilityName
            if flag == "laboratories":
                return Model.TestingFacilityName
        else:
            if flag == "facilities":
                return Model.RequestingProvinceName
            if flag == "laboratories":
                return Model.TestingProvinceName


def PROCESS_COMMON_PARAMS_FACILITY(args):
    """
    Process common parameters used across multiple functions.

    Parameters
    ----------
    args : dict
        The input arguments.

    Returns
    -------
    tuple
        A tuple containing the processed parameters:
        (dates, disaggregation, facility_type, gx_result_type, facilities)
    """
    # Get the interval dates from the input arguments, defaulting to the last 12 months if not provided
    dates = (
        args.get("interval_dates")[0].split(",")
        if args.get("interval_dates") is not None
        else [twelve_months_ago(), today()]
    )

    # Get the disaggregation value from the input arguments, defaulting to False if not provided
    disaggregation = True if args.get("disaggregation") == "True" else False

    # Get the facility type from the input arguments, defaulting to "province" if not provided
    facility_type = (
        "province"
        if args.get("province")
        and not (args.get("district") or args.get("health_facility"))
        # and not disaggregation
        else (
            "district"
            if args.get("district") and not args.get("health_facility")
            # and not disaggregation
            else (
                "health_facility"
                if args.get("health_facility")
                else args.get("facility_type")
            )
        )
    )

    # Get the health facility from the input arguments, defaulting to None if not provided
    health_facility = (
        args.get("health_facility") if args.get(
            "health_facility") is not None else None
    )
    # Get the GeneXpert result type from the input arguments, defaulting to "Ultra 6 Cores" if not provided
    gx_result_type = (
        args.get("genexpert_result_type") if args.get(
            "genexpert_result_type") else None
    )

    # Get the type of laboratory from the input arguments, defaulting to "Conventional" if not provided
    type_of_laboratory = (
        args.get("type_of_laboratory") if args.get(
            "type_of_laboratory") else "all"
    )

    if args.get("conventional_laboratories") is not None:
        facilities = args["conventional_laboratories"]
    elif args.get("point_of_care_laboratories") is not None:
        facilities = args["point_of_care_laboratories"]
    # Get the facilities based on the input arguments
    elif args.get("province") is not None:
        if args.get("district") is not None:
            # if args.get("health_facility") is not None:
            #     facilities = args["health_facility"]
            # else:
            facilities = args["district"]
        else:
            facilities = args["province"]
    else:
        facilities = []

    return (
        dates,
        disaggregation,
        facility_type,
        gx_result_type,
        facilities,
        type_of_laboratory,
        health_facility,
    )


def get_patients(
    health_facility,
    lab,
    dates,
    model,
    indicator,
    gx_result_type,
    test_type,
    month,
    year,
):
    """
    Get patients based on the health_facility, lab, and dates.

    Parameters
    ----------
    health_facility : str
        The health_facility to filter by.
    lab : str
        The type of laboratory.
    dates : list
        The list of dates to filter by.
    Model : sqlalchemy.ext.declarative.DeclarativeMeta
        The TBMaster model.

    Returns
    -------
    sqlalchemy.sql.elements.BinaryExpression
        A SQLAlchemy expression to filter patients based on the given parameters.
    """
    filters = [
        (
            model.RequestingFacilityName == health_facility
            if health_facility
            else model.TestingFacilityName == lab
        ),
        indicator.between(dates[0], dates[1]),
    ]

    if year is not None:
        filters.append(YEAR(indicator) == year)
    if month is not None:
        filters.append(DATE_PART("MONTH", indicator) == month)

    if test_type == "tb":

        if gx_result_type != "All" and gx_result_type is not None:
            filters.append(model.TypeOfResult == gx_result_type)

        patiens = model.query.with_entities(
            model.RequestID,
            model.RequestingProvinceName,
            model.RequestingDistrictName,
            model.RequestingFacilityName,
            model.FacilityNationalCode,
            model.TestingProvinceName,
            model.TestingDistrictName,
            model.TestingFacilityName,
            model.FIRSTNAME,
            model.SURNAME,
            model.AgeInYears,
            model.HL7SexCode,
            model.TELHOME,
            model.FinalResult,
            model.MtbTrace,
            model.Rifampicin,
            model.Fluoroquinolona,
            model.Isoniazid,
            model.Kanamicin,
            model.Amikacina,
            model.Capreomicin,
            model.Ethionamida,
            model.RejectReason,
            model.RejectRemark,
            model.Remarks,
            model.SpecimenDatetime,
            model.RegisteredDateTime,
            model.AnalysisDateTime,
            model.AuthorisedDateTime,
            model.LIMSSpecimenSourceCode,
            model.LIMSSpecimenSourceDesc,
            model.LIMSAnalyzerCode,
            model.TypeOfResult,
        ).filter(*filters)

    elif test_type == "vl":

        patiens = model.query.with_entities(
            model.RequestID,
            model.RequestingProvinceName,
            model.RequestingDistrictName,
            model.RequestingFacilityName,
            model.RequestingFacilityNationalCode,
            model.TestingProvinceName,
            model.TestingDistrictName,
            model.TestingFacilityName,
            model.FIRSTNAME,
            model.SURNAME,
            model.AgeInYears,
            model.HL7SexCode,
            model.TELHOME,
            model.ViralLoadResultCategory,
            model.FinalViralLoadResult,
            model.HL7ResultStatusCode,
            model.HIVVL_ViralLoadResult,
            model.HIVVL_VRLogValue,
            model.ReasonForTest,
            model.Pregnant,
            model.BreastFeeding,
            model.ARTRegimen,
            model.LIMSRejectionCode,
            model.LIMSRejectionDesc,
            model.LIMSSpecimenSourceCode,
            model.LIMSSpecimenSourceDesc,
            model.SpecimenDatetime,
            model.RegisteredDateTime,
            model.AnalysisDateTime,
            model.AuthorisedDateTime,
        ).filter(*filters)

    return patiens


def process_patients(
    patiens, dates, facility_type, gx_result_type, test_type, month, year
):
    """Process the list of patients and return a structured response."""

    if test_type == "tb":
        response = [
            {
                "request_id": patient.RequestID.strip() if patient.RequestID else None,
                "province": (
                    patient.RequestingProvinceName.strip()
                    if patient.RequestingProvinceName
                    else None
                ),
                "district": (
                    patient.RequestingDistrictName.strip()
                    if patient.RequestingDistrictName
                    else None
                ),
                "health_facility": (
                    patient.RequestingFacilityName.strip()
                    if patient.RequestingFacilityName
                    else None
                ),
                "facility_national_code": patient.FacilityNationalCode,
                "first_name": patient.FIRSTNAME.strip() if patient.FIRSTNAME else None,
                "last_name": patient.SURNAME.strip() if patient.SURNAME else None,
                "age_in_years": patient.AgeInYears,
                "sex_code": patient.HL7SexCode.strip() if patient.HL7SexCode else None,
                "telephone": patient.TELHOME.strip() if patient.TELHOME else None,
                "final_result": patient.FinalResult,
                "mtb_trace": patient.MtbTrace,
                "rifampicin": patient.Rifampicin,
                "fluoroquinolona": patient.Fluoroquinolona,
                "isoniazid": patient.Isoniazid,
                "kanamicin": patient.Kanamicin,
                "amikacina": patient.Amikacina,
                "capreomicin": patient.Capreomicin,
                "ethionamida": patient.Ethionamida,
                "reject_reason": (
                    patient.RejectReason.strip() if patient.RejectReason else None
                ),
                "reject_remark": (
                    patient.RejectRemark.strip() if patient.RejectRemark else None
                ),
                "remarks": patient.Remarks.strip() if patient.Remarks else None,
                "specimen_datetime": (
                    patient.SpecimenDatetime.isoformat()
                    if patient.SpecimenDatetime
                    else None
                ),
                "registered_datetime": (
                    patient.RegisteredDateTime.isoformat()
                    if patient.RegisteredDateTime
                    else None
                ),
                "analysis_datetime": (
                    patient.AnalysisDateTime.isoformat()
                    if patient.AnalysisDateTime
                    else None
                ),
                "authorised_datetime": (
                    patient.AuthorisedDateTime.isoformat()
                    if patient.AuthorisedDateTime
                    else None
                ),
                "specimen_source_code": (
                    patient.LIMSSpecimenSourceCode.strip()
                    if patient.LIMSSpecimenSourceCode
                    else None
                ),
                "specimen_source_desc": (
                    patient.LIMSSpecimenSourceDesc.strip()
                    if patient.LIMSSpecimenSourceDesc
                    else None
                ),
                "analyzer_code": (
                    patient.LIMSAnalyzerCode.strip()
                    if patient.LIMSAnalyzerCode
                    else None
                ),
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Year": year,
                "Month": month,
                "Facility_Type": facility_type,
                "Type_Of_Result": (
                    gx_result_type
                    if gx_result_type is not None
                    else patient.TypeOfResult
                ),
                "Requsting_Province_Name": (
                    patient.RequestingProvinceName.strip()
                    if patient.RequestingProvinceName
                    else None
                ),
                "Requesting_District_Name": (
                    patient.RequestingDistrictName.strip()
                    if patient.RequestingDistrictName
                    else None
                ),
                "Requesting_Facility_Name": (
                    patient.RequestingFacilityName.strip()
                    if patient.RequestingFacilityName
                    else None
                ),
                "Testing_Province_Name": (
                    patient.TestingProvinceName.strip()
                    if patient.TestingProvinceName
                    else None
                ),
                "Testing_District_Name": (
                    patient.TestingDistrictName.strip()
                    if patient.TestingDistrictName
                    else None
                ),
                "Testing_Facility_Name": (
                    patient.TestingFacilityName.strip()
                    if patient.TestingFacilityName
                    else None
                ),
            }
            for patient in patiens
        ]

        return response

    elif test_type == "vl":
        response = [
            {
                "request_id": patient.RequestID.strip() if patient.RequestID else None,
                "province": (
                    patient.RequestingProvinceName.strip()
                    if patient.RequestingProvinceName
                    else None
                ),
                "district": (
                    patient.RequestingDistrictName.strip()
                    if patient.RequestingDistrictName
                    else None
                ),
                "health_facility": (
                    patient.RequestingFacilityName.strip()
                    if patient.RequestingFacilityName
                    else None
                ),
                "facility_national_code": patient.RequestingFacilityNationalCode,
                "first_name": patient.FIRSTNAME.strip() if patient.FIRSTNAME else None,
                "last_name": patient.SURNAME.strip() if patient.SURNAME else None,
                "age_in_years": patient.AgeInYears,
                "sex_code": patient.HL7SexCode.strip() if patient.HL7SexCode else None,
                "telephone": patient.TELHOME.strip() if patient.TELHOME else None,
                "viral_load_result_category": (
                    patient.ViralLoadResultCategory.strip()
                    if patient.ViralLoadResultCategory
                    else None
                ),
                "viral_load_result": (
                    patient.HIVVL_ViralLoadResult.strip()
                    if patient.HIVVL_ViralLoadResult
                    else None
                ),
                "viral_load_log_value": (
                    patient.HIVVL_VRLogValue.strip()
                    if patient.HIVVL_VRLogValue
                    else None
                ),
                "reason_for_test": (
                   "Reason Not Specified"
                    if patient.ReasonForTest.strip() in ["Não preenchido", "No", "Reason Not Specified", "Yes", ""] 
                    else "Routine" if patient.ReasonForTest.strip() == "Routine" 
                    else "Repeat" if patient.ReasonForTest.strip() in ["Repeat after breastfeeding", "Repeat"] 
                    else "Suspected treatment failure" if patient.ReasonForTest.strip() == "Suspected treatment failure" 
                    else None
                ),
                "pregnant": patient.Pregnant.strip() if patient.Pregnant else None,
                "breastfeeding": (
                    patient.BreastFeeding.strip() if patient.BreastFeeding else None
                ),
                "art_regimen": (
                    patient.ARTRegimen.strip() if patient.ARTRegimen else None
                ),
                "rejection_code": (
                    patient.LIMSRejectionCode.strip()
                    if patient.LIMSRejectionCode
                    else None
                ),
                "rejection_desc": (
                    patient.LIMSRejectionDesc.strip()
                    if patient.LIMSRejectionDesc
                    else None
                ),
                "specimen_source_code": (
                    patient.LIMSSpecimenSourceCode.strip()
                    if patient.LIMSSpecimenSourceCode
                    else None
                ),
                "specimen_source_desc": (
                    patient.LIMSSpecimenSourceDesc.strip()
                    if patient.LIMSSpecimenSourceDesc
                    else None
                ),
                "specimen_datetime": (
                    patient.SpecimenDatetime.isoformat()
                    if patient.SpecimenDatetime
                    else None
                ),
                "registered_datetime": (
                    patient.RegisteredDateTime.isoformat()
                    if patient.RegisteredDateTime
                    else None
                ),
                "analysis_datetime": (
                    patient.AnalysisDateTime.isoformat()
                    if patient.AnalysisDateTime
                    else None
                ),
                "authorised_datetime": (
                    patient.AuthorisedDateTime.isoformat()
                    if patient.AuthorisedDateTime
                    else None
                ),
                "final_viral_load_result": (
                    patient.FinalViralLoadResult.strip()
                    if patient.FinalViralLoadResult
                    else None
                ),
                "hl7_result_status_code": (
                    patient.HL7ResultStatusCode.strip()
                    if patient.HL7ResultStatusCode
                    else None
                ),
                "Start_Date": dates[0],
                "End_Date": dates[1],
                "Year": year,
                "Month": month,
                "Facility_Type": facility_type,
                "Requesting_Province_Name": (
                    patient.RequestingProvinceName.strip()
                    if patient.RequestingProvinceName
                    else None
                ),
                "Requesting_District_Name": (
                    patient.RequestingDistrictName.strip()
                    if patient.RequestingDistrictName
                    else None
                ),
                "Requesting_Facility_Name": (
                    patient.RequestingFacilityName.strip()
                    if patient.RequestingFacilityName
                    else None
                ),
                "Testing_Province_Name": (
                    patient.TestingProvinceName.strip()
                    if patient.TestingProvinceName
                    else None
                ),
                "Testing_District_Name": (
                    patient.TestingDistrictName.strip()
                    if patient.TestingDistrictName
                    else None
                ),
                "Testing_Facility_Name": (
                    patient.TestingFacilityName.strip()
                    if patient.TestingFacilityName
                    else None
                ),
            }
            for patient in patiens
        ]

        return response


def POSITIVITY(field, value):
    """
    Count records where field matches value (for EID positive/negative counting).
    Analogous to SUPPRESSION() but with generic naming.

    Parameters
    ----------
    field : sqlalchemy.Column
        The column to check (e.g., PCR_Result, POC_Result)
    value : str
        The value to match (e.g., "Positive", "Negative")

    Returns
    -------
    sqlalchemy.sql.expression
        A CASE expression that counts matching records
    """
    return func.count(case((field.like(f"%{value}%"), 1)))


def LAB_TYPE_EID(Model, lab_type):
    """
    Filter EID records by test type (conventional PCR vs Point of Care).

    Parameters
    ----------
    Model : sqlalchemy.Model
        The EIDMaster model class
    lab_type : str
        "conventional", "poc", or "all"

    Returns
    -------
    sqlalchemy.sql.expression or None
        A filter condition, or None if lab_type is "all"
    """
    if lab_type.lower() == "poc":
        return Model.IsPoc == "Yes"
    elif lab_type.lower() == "conventional":
        return Model.IsPoc != "Yes"
    return None


def EQUIPMENT_COUNT(Model, equipment_name):
    """
    Count records by equipment/analyzer type.

    Parameters
    ----------
    Model : sqlalchemy.Model
        The model class with ResultLIMSAnalyzerCode column
    equipment_name : str
        Equipment code (e.g., "CAPCTM", "ALINITY", "M2000")

    Returns
    -------
    sqlalchemy.sql.expression
        A CASE expression counting matching records
    """
    return func.count(case((Model.ResultLIMSAnalyzerCode == equipment_name, 1)))


def PROCESS_COMMON_PARAMS_VL(req_args):
    """
    Extract and normalize common query parameters used across all modules.
    Standardizes parameter handling for VL, EID, and TB endpoints.

    Parameters
    ----------
    req_args : dict
        Parsed request arguments from reqparse

    Returns
    -------
    tuple
        (dates, facilities, facility_type, disaggregation, health_facility)
    """
    # Date range - default to last 12 months
    dates = (
        req_args.get("interval_dates")[0].split(",")
        if req_args.get("interval_dates") is not None
        else [twelve_months_ago(), today()]
    )

    # Facility type - default to province
    facility_type = req_args.get("facility_type") or "province"

    # Disaggregation - default to False
    disaggregation_raw = req_args.get("disaggregation")
    disaggregation = disaggregation_raw == "True" if disaggregation_raw else False

    # Health facility
    health_facility = req_args.get("health_facility")

    # Facilities list - from province, district, or health_facility depending on type
    facilities = []
    if facility_type == "province":
        facilities = req_args.get("province") or []
    elif facility_type == "district":
        facilities = req_args.get("district") or []
    elif facility_type == "health_facility" and health_facility:
        facilities = [health_facility]

    # Clean up facilities list
    facilities = [f.strip() for f in facilities if f and f.strip()]

    return dates, facilities, facility_type, disaggregation, health_facility
