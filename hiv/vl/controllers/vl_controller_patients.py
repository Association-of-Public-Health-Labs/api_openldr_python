from flask_restful import Resource

from hiv.vl.services.vl_services_patients import (
    get_patients_by_name_service,
    get_patients_by_facility_service,
    get_patients_by_result_type_service,
    get_patients_by_test_reason_service,
)
from utilities.controller_helpers import (
    LIST_ARG,
    STR_ARG,
    VL_PATIENT_FILTER_ARGS,
    build_common_parser,
    run_reporting_endpoint,
)


# Shared parser for all VL patient endpoints.
#
# NOTE: the legacy parser declared ``test_reason`` twice (once as a list
# argument, once as a plain string). In reqparse the second declaration wins,
# which meant the list form was silently ignored. We keep a single, explicit
# list declaration to match the actual query-string behaviour expected by the
# service layer (multi-valued test_reason).
_parser = build_common_parser(
    extra_args=[
        ("first_name", STR_ARG),
        ("surname", STR_ARG),
        ("result_type", LIST_ARG),
        ("test_reason", LIST_ARG),
        ("page", {"type": int, "location": "args", "default": 1}),
        ("per_page", {"type": int, "location": "args", "default": 50}),
        *VL_PATIENT_FILTER_ARGS,
    ]
)


def _endpoint(service):
    return run_reporting_endpoint(_parser.parse_args, service)


class VlPatientsByName(Resource):
    def get(self):
        """
        Retrieve VL patients by first name or surname between two dates
        ---
        tags:
            - HIV Viral Load/Patients
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - name: first_name
              in: query
              type: string
              required: false
              description: The patient's first name (partial match)
            - name: surname
              in: query
              type: string
              required: false
              description: The patient's surname (partial match)
            - $ref: '#/parameters/HealthFacilityParameter'
            - name: page
              in: query
              type: integer
              required: false
              default: 1
              description: Page number (1-indexed)
            - name: per_page
              in: query
              type: integer
              required: false
              default: 50
              description: Number of records per page
        responses:
            200:
                description: A List of VL Patients matching the name criteria.
            400:
                description: Invalid Parameters
            403:
                description: Forbidden
            500:
                description: An Error Occurred
        """
        return _endpoint(get_patients_by_name_service)


class VlPatientsByFacility(Resource):
    def get(self):
        """
        Retrieve VL patients registered at a specific health facility between two dates
        ---
        tags:
            - HIV Viral Load/Patients
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/HealthFacilityParameter'
            - name: page
              in: query
              type: integer
              required: false
              default: 1
              description: Page number (1-indexed)
            - name: per_page
              in: query
              type: integer
              required: false
              default: 50
              description: Number of records per page
        responses:
            200:
                description: A List of VL Patients registered at the facility.
            400:
                description: Invalid Parameters
            403:
                description: Forbidden
            500:
                description: An Error Occurred
        """
        return _endpoint(get_patients_by_facility_service)


class VlPatientsByResultType(Resource):
    def get(self):
        """
        Retrieve VL patients by viral load result category (suppressed / not_suppressed) between two dates
        ---
        tags:
            - HIV Viral Load/Patients
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - name: result_type
              in: query
              type: array
              required: true
              items:
                type: string
                enum: ["suppressed", "not_suppressed"]
              description: The viral load result category to filter by
            - $ref: '#/parameters/HealthFacilityParameter'
            - name: page
              in: query
              type: integer
              required: false
              default: 1
              description: Page number (1-indexed)
            - name: per_page
              in: query
              type: integer
              required: false
              default: 50
              description: Number of records per page
        responses:
            200:
                description: A List of VL Patients filtered by result type.
            400:
                description: Invalid Parameters
            403:
                description: Forbidden
            500:
                description: An Error Occurred
        """
        return _endpoint(get_patients_by_result_type_service)


class VlPatientsByTestReason(Resource):
    def get(self):
        """
        Retrieve VL patients by reason for test between two dates
        ---
        tags:
            - HIV Viral Load/Patients
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/TestReasonParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - name: page
              in: query
              type: integer
              required: false
              default: 1
              description: Page number (1-indexed)
            - name: per_page
              in: query
              type: integer
              required: false
              default: 50
              description: Number of records per page
        responses:
            200:
                description: A List of VL Patients filtered by test reason.
            400:
                description: Invalid Parameters
            403:
                description: Forbidden
            500:
                description: An Error Occurred
        """
        return _endpoint(get_patients_by_test_reason_service)
