from flask_restful import Resource

from tb.cultura.services.tb_cultura_services_facility import (
    cultura_facility_metrics_service,
)
from utilities.controller_helpers import STR_ARG, build_common_parser, run_reporting_endpoint


_parser = build_common_parser(
    extra_args=[
        ("type_of_laboratory", STR_ARG),
    ]
)


class TBCulturaFacilityMetrics(Resource):
    def get(self):
        """
        Retrieve TB culture metrics grouped by requesting facility geography.
        ---
        tags:
            - Tuberculosis/Cultura/Facilities
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
                description: TB culture metrics grouped by facility.
        """
        return run_reporting_endpoint(_parser.parse_args, cultura_facility_metrics_service)
