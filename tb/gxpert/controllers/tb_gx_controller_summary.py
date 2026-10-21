from flask_restful import Resource

from tb.gxpert.services.tb_gx_services_summary import (
    dashboard_header_component_summary_service,
    dashboard_summary_positivity_by_month_service,
    dashboard_summary_positivity_by_lab_service,
    dashboard_summary_positivity_by_lab_by_age_service,
    dashboard_summary_sample_types_by_month_by_age_service,
    dashboard_summary_sample_types_by_facility_by_age_service,
)
from utilities.controller_helpers import (
    STR_ARG,
    build_common_parser,
    run_reporting_endpoint,
)

# Shared parser for all TB GeneXpert summary endpoints.
_parser = build_common_parser(
    extra_args=[
        ("genexpert_result_type", STR_ARG),
        ("type_of_laboratory", STR_ARG),
    ]
)


class dashboard_header_component_summary_controller(Resource):
    def get(self):
        """
        Retrieve the summary of the number of samples from  registration to analysis on the dashboard header
        ---
        tags:
        - Tuberculosis/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: A List of Dashboard Header Component Summary.
            400:
                description: Invalid Parameters
            404:
                description: Laboratory Not Found
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args, dashboard_header_component_summary_service
        )


class dashboard_summary_positivity_by_month_controller(Resource):

    def get(self):
        """
        Retrieve the number of tested samples by month
        ---
        tags:
        - Tuberculosis/Summary
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/GeneXpertResultType'
            - $ref: '#/parameters/TypeOfLaboratory'
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: A List of Dashboard Summary Positivity by Month.
            400:
                description: Invalid Parameters
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args, dashboard_summary_positivity_by_month_service
        )


class dashboard_summary_positivity_by_lab_controller(Resource):
    def get(self):
        """
        Retrieve the posotivity rate by laboratory
        ---
        tags:
        - Tuberculosis/Summary
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/GeneXpertResultType'
            - $ref: '#/parameters/TypeOfLaboratory'
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: A List of Dashboard Summary Positivity by Lab.
            400:
                description: Invalid Parameters
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args, dashboard_summary_positivity_by_lab_service
        )


class dashboard_summary_positivity_by_lab_by_age_controller(Resource):
    def get(self):
        """
        Retrieve the positivity rate by laboratory by age
        ---
        tags:
        - Tuberculosis/Summary
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/GeneXpertResultType'
            - $ref: '#/parameters/TypeOfLaboratory'
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: A List of Dashboard Summary Positivity by Lab by Age.
            400:
                description: Invalid Parameters
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args, dashboard_summary_positivity_by_lab_by_age_service
        )


class dashboard_summary_sample_types_by_month_by_age_controller(Resource):
    def get(self):
        """
        Retrieve the number of registered samples by month and by specimen type
        ---
        tags:
        - Tuberculosis/Summary
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/GeneXpertResultType'
            - $ref: '#/parameters/TypeOfLaboratory'
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: A List of Dashboard Summary Sample Types by Month.
            400:
                description: Invalid Parameters
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args,
            dashboard_summary_sample_types_by_month_by_age_service,
        )


class dashboard_summary_sample_types_by_facility_by_age_controller(Resource):
    def get(self):
        """
        Retrieve the number of registered samples by facility by specimen type by age
        ---
        tags:
        - Tuberculosis/Summary
        parameters:
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/GeneXpertResultType'
        responses:
            200:
                description: A List of Dashboard Summary Sample Types by Facility by Age.
            400:
                description: Invalid Parameters
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(
            _parser.parse_args,
            dashboard_summary_sample_types_by_facility_by_age_service,
        )
