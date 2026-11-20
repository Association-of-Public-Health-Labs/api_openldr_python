from flask_restful import Resource, reqparse
from utilities.controller_helpers import run_reporting_endpoint
from dict.services.facilities_services import (
    get_all_facilities,
    get_facilities_by_province,
    get_facilities_by_district,
)


class dict__facilities(Resource):
    def get(self):
        """
        Get all facilities.
        ---
        tags:
            - Dictionary/Facilities
        responses:
            401:
                description: Invalid or missing token.
            403:
                description: A persisted dashboard role is required.
            200:
                description: A list of all facilities.
            400:
                description: Invalid facility type provided.
            404:
                description: No facilities found.
            500:
                description: An error occurred. Internal details are not returned.
        """
        return run_reporting_endpoint(lambda: {}, lambda _: get_all_facilities())


class dict__facilities__by_province(Resource):
    def get(self):
        """
        Get all facilities by province.
        ---
        tags:
            - Dictionary/Facilities
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
        responses:
            401:
                description: Invalid or missing token.
            403:
                description: A persisted dashboard role is required.
            200:
                description: A list of all facilities.
            400:
                description: Invalid facility type provided.
            404:
                description: No facilities found.
            500:
                description: An error occurred. Internal details are not returned.
        """
        parser = reqparse.RequestParser()

        parser.add_argument(
            "province",
            type=lambda x: x,
            location="args",
            action="append",
            help="This field cannot be blank.",
        )
        return run_reporting_endpoint(parser.parse_args, get_facilities_by_province)


class dict__facilities__by_district(Resource):
    def get(self):
        """
        Get all facilities by district.
        ---
        tags:
            - Dictionary/Facilities
        parameters:
            - $ref: '#/parameters/DistrictParameter'
        responses:
            401:
                description: Invalid or missing token.
            403:
                description: A persisted dashboard role is required.
            200:
                description: A list of all facilities.
            400:
                description: Invalid facility type provided.
            404:
                description: No facilities found.
            500:
                description: An error occurred. Internal details are not returned.
        """

        parser = reqparse.RequestParser()

        parser.add_argument(
            "district",
            type=lambda x: x,
            location="args",
            action="append",
            help="This field cannot be blank.",
        )

        return run_reporting_endpoint(parser.parse_args, get_facilities_by_district)
