from flask_restful import Resource

from hiv.vl.services.vl_services_summary import (
    header_indicators_service_by_month,
    number_of_samples_service_by_month,
    viral_suppression_service_by_month,
    tat_service_by_month,
    suppression_by_province_service_by_month,
    samples_history_service_by_month,
)
from utilities.controller_helpers import (
    VL_FILTER_ARGS,
    build_common_parser,
    run_reporting_endpoint,
)


# Shared parser for all VL summary endpoints.
_parser = build_common_parser(extra_args=VL_FILTER_ARGS)


class VlSummaryHeaderIndicatorsByMonth(Resource):
    def get(self):
        """
        Retrieve header indicator counts for the summary dashboard
        ---
        tags:
            - HIV Viral Load/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Header indicator counts (registered, tested, suppressed, not_suppressed, rejected)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args, header_indicators_service_by_month
        )


class VlSummaryNumberOfSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve monthly sample counts for the summary dashboard
        ---
        tags:
            - HIV Viral Load/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Monthly sample counts grouped by year/month
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args, number_of_samples_service_by_month
        )


class VlSummaryViralSuppressionByMonth(Resource):
    def get(self):
        """
        Retrieve monthly viral suppression trend for the summary dashboard
        ---
        tags:
            - HIV Viral Load/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Monthly suppression trend (suppressed, not_suppressed)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args, viral_suppression_service_by_month
        )


class VlSummaryTatByMonth(Resource):
    def get(self):
        """
        Retrieve monthly turnaround time summary for the dashboard
        ---
        tags:
            - HIV Viral Load/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Monthly TAT averages (collection_reception, reception_registration, registration_analysis, analysis_validation)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, tat_service_by_month)


class VlSummarySuppressionByProvinceByMonth(Resource):
    def get(self):
        """
        Retrieve viral suppression counts grouped by province (provincial map)
        ---
        tags:
            - HIV Viral Load/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Suppression counts grouped by RequestingProvinceName
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args, suppression_by_province_service_by_month
        )


class VlSummarySamplesHistoryByMonth(Resource):
    def get(self):
        """
        Retrieve historical sample counts by year/month
        ---
        tags:
            - HIV Viral Load/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Historical sample counts grouped by year/month
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args, samples_history_service_by_month
        )
