from flask_restful import Resource
from hiv.eid.controllers.eid_args import eid_parser
from utilities.controller_helpers import run_reporting_endpoint
from hiv.eid.services.eid_services_summary import (
    summary_indicators_service,
    summary_tat_service,
    summary_tat_samples_service,
    summary_positivity_service,
    summary_number_of_samples_service,
    summary_indicators_by_province_service,
    summary_samples_positivity_service,
    summary_rejected_samples_by_month_service,
    summary_samples_by_equipment_service,
    summary_samples_by_equipment_by_month_service,
)


_parser = eid_parser


class EidSummaryIndicators(Resource):
    def get(self):
        """
        Retrieve EID summary indicators (registered, tested, rejected, pending, positive, negative)
        ---
        tags:
            - HIV EID/Summary
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
                description: EID summary indicators
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_indicators_service)


class EidSummaryTat(Resource):
    def get(self):
        """
        Retrieve EID summary TAT averages by month (6 hub segments)
        ---
        tags:
            - HIV EID/Summary
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
                description: EID summary TAT by month
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_tat_service)


class EidSummaryTatSamples(Resource):
    def get(self):
        """
        Retrieve EID summary TAT sample distribution by time brackets
        ---
        tags:
            - HIV EID/Summary
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
                description: EID summary TAT sample distribution
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_tat_samples_service)


class EidSummaryPositivity(Resource):
    def get(self):
        """
        Retrieve EID summary monthly positivity (total, positive, negative)
        ---
        tags:
            - HIV EID/Summary
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
                description: EID summary monthly positivity
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_positivity_service)


class EidSummaryNumberOfSamples(Resource):
    def get(self):
        """
        Retrieve EID summary monthly sample counts
        ---
        tags:
            - HIV EID/Summary
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
                description: EID summary monthly sample counts
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_number_of_samples_service)


class EidSummaryIndicatorsByProvince(Resource):
    def get(self):
        """
        Retrieve EID summary indicators per province
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: EID summary indicators by province
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_indicators_by_province_service)


class EidSummarySamplesPositivity(Resource):
    def get(self):
        """
        Retrieve EID summary samples positivity with gender splits
        ---
        tags:
            - HIV EID/Summary
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
                description: EID summary samples positivity breakdown
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_samples_positivity_service)


class EidSummaryRejectedSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve EID summary rejected samples grouped by month
        ---
        tags:
            - HIV EID/Summary
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
                description: EID summary rejected samples by month
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_rejected_samples_by_month_service)


class EidSummarySamplesByEquipment(Resource):
    def get(self):
        """
        Retrieve EID summary samples by equipment type
        ---
        tags:
            - HIV EID/Summary
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
                description: EID summary samples by equipment
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_samples_by_equipment_service)


class EidSummarySamplesByEquipmentByMonth(Resource):
    def get(self):
        """
        Retrieve EID summary samples by equipment type by month
        ---
        tags:
            - HIV EID/Summary
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
                description: EID summary samples by equipment by month
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_samples_by_equipment_by_month_service)
