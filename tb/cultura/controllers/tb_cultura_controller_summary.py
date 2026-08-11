from flask_restful import Resource

from tb.cultura.services.tb_cultura_services_summary import (
    cultura_diagnostic_cascade_service,
    cultura_results_by_month_service,
    cultura_summary_indicators_service,
    cultura_tat_and_backlog_service,
)
from utilities.controller_helpers import STR_ARG, build_common_parser, run_reporting_endpoint


_parser = build_common_parser(
    extra_args=[
        ("type_of_laboratory", STR_ARG),
    ]
)


class TBCulturaSummaryIndicators(Resource):
    def get(self):
        """
        Retrieve TB culture summary indicators.
        ---
        tags:
            - Tuberculosis/Cultura/Summary
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/TypeOfLaboratory'
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: A list of TB culture summary indicators.
        """
        return run_reporting_endpoint(_parser.parse_args, cultura_summary_indicators_service)


class TBCulturaResultsByMonth(Resource):
    def get(self):
        """
        Retrieve TB culture results by month.
        ---
        tags:
            - Tuberculosis/Cultura/Summary
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/TypeOfLaboratory'
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: A list of TB culture result metrics grouped by month.
        """
        return run_reporting_endpoint(_parser.parse_args, cultura_results_by_month_service)


class TBCulturaTatAndBacklog(Resource):
    def get(self):
        """
        Retrieve TB culture turnaround time and backlog indicators.
        ---
        tags:
            - Tuberculosis/Cultura/Summary
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/TypeOfLaboratory'
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: TB culture turnaround time and backlog indicators.
        """
        return run_reporting_endpoint(_parser.parse_args, cultura_tat_and_backlog_service)


class TBCulturaDiagnosticCascade(Resource):
    def get(self):
        """
        Retrieve TB culture diagnostic cascade indicators.
        ---
        tags:
            - Tuberculosis/Cultura/Summary
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/TypeOfLaboratory'
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: TB culture diagnostic cascade indicators.
        """
        return run_reporting_endpoint(_parser.parse_args, cultura_diagnostic_cascade_service)
