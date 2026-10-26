"""Patient search controllers (Admin only) for the HIV EID dashboard."""
from flask_restful import Resource

from hiv.eid.controllers.eid_args import EID_FILTER_ARGS
from hiv.eid.services.eid_services_patients import (
    get_patients_by_facility_service,
    get_patients_by_name_service,
    get_patients_by_result_type_service,
)
from utilities.controller_helpers import LIST_ARG, STR_ARG, build_common_parser, run_reporting_endpoint

_parser = build_common_parser(
    extra_args=[
        ("name", STR_ARG),
        ("result_type", LIST_ARG),
        ("page", STR_ARG),
        ("per_page", STR_ARG),
        ("date_basis", STR_ARG),
        ("rejected", STR_ARG),
        *EID_FILTER_ARGS,
    ]
)


def _endpoint(service):
    return run_reporting_endpoint(_parser.parse_args, service)


class EidPatientsByFacility(Resource):
    def get(self):
        """
        EID patients registered in the window, optionally at one health facility

        Admin only (403 otherwise). health_facility is optional, so
        /hiv/eid/patients/by_facility/?per_page=1 is the dashboard's admin
        probe. Patient routes are never cached. The window is on
        RegisteredDateTime (date_basis=analysis: AnalysisDateTime), both days included. Rows carry the caregiver's
        phone (CaregiverMobileContact) and the mother's PTV id (PtvMother):
        third-party contact details, never logged. result is FinalResult
        (✱7); lab_type is conventional or poc (null when the row is in
        neither); rejection_reason is LIMSRejectionDesc, else
        LIMSRejectionCode. per_page is capped at 500.
        ---
        tags:
            - HIV EID/Patients
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/LabCodeParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - name: result_type
              in: query
              type: array
              items:
                  type: string
                  enum: [positive, negative, indeterminate, rejected, pending]
              required: false
              description: Result classes to keep (positive, negative, indeterminate by FinalResult; rejected; pending)
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
              description: Records per page (default 50, maximum 500)
            - name: date_basis
              in: query
              type: string
              enum: [registered, analysis]
              required: false
              default: registered
              description: Date the interval_dates window applies to. registered (default) = RegisteredDateTime; analysis = AnalysisDateTime (drill-downs from tested cards). Any other value is a 400.
            - name: rejected
              in: query
              type: string
              enum: ['true', 'false']
              required: false
              description: Only rejected samples, by the facility rejected routes' rule (R20) - IsPoc = 'No' and LIMSRejectionCode non-empty - with the window on AnalysisDateTime whatever date_basis is.
        responses:
            200:
                description: A page of EID patients.
            400:
                description: Invalid filter
            403:
                description: Admin only
            500:
                description: An Error Occurred
        """
        return _endpoint(get_patients_by_facility_service)


class EidPatientsByName(Resource):
    def get(self):
        """
        EID patients whose name contains the given text

        Admin only (403 otherwise). name matches the first name and surname
        together (partial, case-insensitive). Patient routes are never
        cached. The window is on RegisteredDateTime (date_basis=analysis: AnalysisDateTime), both days included.
        Rows carry the caregiver's phone (CaregiverMobileContact) and the
        mother's PTV id (PtvMother): third-party contact details, never
        logged. result is FinalResult (✱7); lab_type is conventional or poc
        (null when in neither); rejection_reason is LIMSRejectionDesc, else
        LIMSRejectionCode. per_page is capped at 500.
        ---
        tags:
            - HIV EID/Patients
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - name: name
              in: query
              type: string
              required: true
              description: Part of the patient's first name or surname
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/LabCodeParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - name: result_type
              in: query
              type: array
              items:
                  type: string
                  enum: [positive, negative, indeterminate, rejected, pending]
              required: false
              description: Result classes to keep
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
              description: Records per page (default 50, maximum 500)
            - name: date_basis
              in: query
              type: string
              enum: [registered, analysis]
              required: false
              default: registered
              description: Date the interval_dates window applies to. registered (default) = RegisteredDateTime; analysis = AnalysisDateTime (drill-downs from tested cards). Any other value is a 400.
            - name: rejected
              in: query
              type: string
              enum: ['true', 'false']
              required: false
              description: Only rejected samples, by the facility rejected routes' rule (R20) - IsPoc = 'No' and LIMSRejectionCode non-empty - with the window on AnalysisDateTime whatever date_basis is.
        responses:
            200:
                description: A page of EID patients.
            400:
                description: Invalid or missing filter
            403:
                description: Admin only
            500:
                description: An Error Occurred
        """
        return _endpoint(get_patients_by_name_service)


class EidPatientsByResultType(Resource):
    def get(self):
        """
        EID patients by result class

        Admin only (403 otherwise). result_type is required: positive,
        negative, indeterminate (FinalResult values, ✱7), rejected
        (LIMSRejectionCode or LIMSRejectionDesc non-empty) or pending (not
        rejected, no definitive result). Patient routes are never cached.
        The window is on RegisteredDateTime (date_basis=analysis: AnalysisDateTime), both days included. Rows carry
        the caregiver's phone (CaregiverMobileContact) and the mother's PTV
        id (PtvMother): third-party contact details, never logged.
        lab_type is conventional or poc (null when in neither);
        rejection_reason is LIMSRejectionDesc, else LIMSRejectionCode.
        per_page is capped at 500.
        ---
        tags:
            - HIV EID/Patients
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - name: result_type
              in: query
              type: array
              items:
                  type: string
                  enum: [positive, negative, indeterminate, rejected, pending]
              required: true
              description: Result classes to keep
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/LabCodeParameter'
            - $ref: '#/parameters/LabTypeParameter'
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
              description: Records per page (default 50, maximum 500)
            - name: date_basis
              in: query
              type: string
              enum: [registered, analysis]
              required: false
              default: registered
              description: Date the interval_dates window applies to. registered (default) = RegisteredDateTime; analysis = AnalysisDateTime (drill-downs from tested cards). Any other value is a 400.
            - name: rejected
              in: query
              type: string
              enum: ['true', 'false']
              required: false
              description: Only rejected samples, by the facility rejected routes' rule (R20) - IsPoc = 'No' and LIMSRejectionCode non-empty - with the window on AnalysisDateTime whatever date_basis is.
        responses:
            200:
                description: A page of EID patients.
            400:
                description: Invalid or missing filter
            403:
                description: Admin only
            500:
                description: An Error Occurred
        """
        return _endpoint(get_patients_by_result_type_service)
