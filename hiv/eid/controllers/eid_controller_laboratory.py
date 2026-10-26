from flask_restful import Resource

from hiv.eid.services.eid_services_laboratory import (
    tested_samples_by_month_service,
    registered_samples_by_month_service,
    tested_samples_service,
    tat_service,
    tat_samples_service,
    rejected_samples_service,
    rejected_samples_by_month_service,
    samples_by_equipment_service,
    samples_by_equipment_by_month_service,
    sample_routes_service,
    sample_routes_viewport_service,
)
from hiv.eid.controllers.eid_args import EID_FILTER_ARGS, eid_parser
from utilities.controller_helpers import STR_ARG, build_common_parser, run_reporting_endpoint

_parser = eid_parser
# The map viewport (south,west,north,east) only applies to the viewport route.
_viewport_parser = build_common_parser(extra_args=EID_FILTER_ARGS + [("viewport", STR_ARG)])


class EidTestedSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve EID tested samples by month
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID tested samples by month
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, tested_samples_by_month_service)


class EidRegisteredSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve EID registered samples by month
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID registered samples by month
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, registered_samples_by_month_service)


class EidTestedSamples(Resource):
    def get(self):
        """
        Retrieve EID tested samples by laboratory
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID tested samples by laboratory
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, tested_samples_service)


class EidTat(Resource):
    def get(self):
        """
        Retrieve EID turnaround time by laboratory
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID turnaround time by laboratory
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, tat_service)


class EidTatSamples(Resource):
    def get(self):
        """
        Retrieve EID TAT sample distribution by time brackets
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
            - $ref: '#/parameters/TATCategoryParameter'
        responses:
            200:
                description: EID TAT sample distribution
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, tat_samples_service)


class EidRejectedSamples(Resource):
    def get(self):
        """
        Retrieve EID rejected samples by laboratory
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID rejected samples by laboratory
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, rejected_samples_service)


class EidRejectedSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve EID rejected samples by month
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID rejected samples by month
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, rejected_samples_by_month_service)


class EidSamplesByEquipment(Resource):
    def get(self):
        """
        Retrieve EID samples by equipment type
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID samples by equipment type
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, samples_by_equipment_service)


class EidSamplesByEquipmentByMonth(Resource):
    def get(self):
        """
        Retrieve EID samples by equipment type by month
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID samples by equipment type by month
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, samples_by_equipment_by_month_service)


class EidSampleRoutes(Resource):
    def get(self):
        """
        Retrieve EID sample routes between facilities
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID sample routes
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, sample_routes_service)


class EidSampleRoutesViewport(Resource):
    def get(self):
        """
        Retrieve EID sample routes filtered by viewport
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
            - $ref: '#/parameters/ViewportParameter'
        responses:
            200:
                description: EID sample routes within viewport
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_viewport_parser.parse_args, sample_routes_viewport_service)
