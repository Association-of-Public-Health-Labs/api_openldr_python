from flask_restful import Resource

from tb.cultura.services.tb_cultura_services_resistance import (
    cultura_resistance_metrics_service,
)
from utilities.controller_helpers import STR_ARG, build_common_parser, run_reporting_endpoint


_parser = build_common_parser(
    extra_args=[
        ("type_of_laboratory", STR_ARG),
        ("drug", STR_ARG),
    ]
)


class TBCulturaResistanceMetrics(Resource):
    def get(self):
        """
        Retrieve TB culture resistance metrics by drug.
        ---
        tags:
            - Tuberculosis/Cultura/Resistance
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/TypeOfLaboratory'
            - $ref: '#/parameters/DrugTypeParameter'
            - $ref: '#/parameters/IntervalDates'
        responses:
            200:
                description: TB culture resistance metrics by drug.
        """
        return run_reporting_endpoint(_parser.parse_args, cultura_resistance_metrics_service)
