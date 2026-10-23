from flask_restful import Resource

from hiv.vl.services.vl_services_transport import (
    transport_tat_by_location_service,
    transport_tat_by_week_service,
)
from utilities.controller_helpers import STR_ARG, build_common_parser, run_reporting_endpoint

_parser = build_common_parser(extra_args=[("type_of_test", STR_ARG)])

_COUNTS = (
    "samples_with_collection_date, lt_7, between_7_15, between_16_21, gt_21 (days from collection at the "
    "health facility to reception at the lab), no_reception_date; total_tested and no_collection_date are null (the VL table has no total)"
)


def _endpoint(service):
    return run_reporting_endpoint(_parser.parse_args, service)


class VlTransportTatByLocation(Resource):
    def get(self):
        """
        VL sample transport TAT by province, district or health facility
        ---
        tags:
            - HIV Viral Load/Transport
        description: >
            From ReportData.VLTransportTATPerWeek, the source of the weekly VL spreadsheet's "Tempo de
            Transporte" sheet (Colheita à Recepção no Lab). Sums the Sunday-Saturday weeks inside
            interval_dates (week start >= start and week end <= end); rows without a requesting
            health facility are left out. Default window: the last complete week.
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/TransportFacilityType'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/TypeOfTestParameter'
        responses:
            200:
                description: "province, district, health_facility and facility_code (as the level asks), start_date, end_date, samples_with_collection_date, lt_7, between_7_15, between_16_21, gt_21, no_reception_date; total_tested and no_collection_date are null (the VL table has no total)"
            400:
                description: Invalid interval_dates, facility_type or type_of_test
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(transport_tat_by_location_service)


class VlTransportTatByWeek(Resource):
    def get(self):
        """
        VL sample transport TAT week by week
        ---
        tags:
            - HIV Viral Load/Transport
        description: >
            From ReportData.VLTransportTATPerWeek: one row per Sunday-Saturday week inside interval_dates, for
            the country or the province / district / health facility given. Default window: the
            last 28 complete weeks.
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/TypeOfTestParameter'
        responses:
            200:
                description: "start_date, end_date, samples_with_collection_date, lt_7, between_7_15, between_16_21, gt_21, no_reception_date; total_tested and no_collection_date are null (the VL table has no total)"
            400:
                description: Invalid interval_dates or type_of_test
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(transport_tat_by_week_service)
