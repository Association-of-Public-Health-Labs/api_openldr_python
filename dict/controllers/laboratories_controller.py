from flask_restful import Resource, reqparse
from utilities.controller_helpers import run_reporting_endpoint
from dict.services.laboratories_services import (
    get_all_laboratories,
    get_laboratories_by_province,
    get_laboratories_by_district,
)


class dict__laboratories(Resource):
    def get(self):
        """
        Get all laboratories.
        ---
        tags:
            - Dictionary/Laboratories
        responses:
            401:
                description: Invalid or missing token.
            403:
                description: A persisted dashboard role is required.
            200:
                description: A list of all laboratories.
            400:
                description: Invalid lab type provided.
            404:
                description: No laboratories found.
            500:
                description: An error occurred. Internal details are not returned.
        """
        return run_reporting_endpoint(lambda: {}, lambda _: get_all_laboratories())


class dict__laboratories__by_province(Resource):
    def get(self):
        """
        Get all laboratories by province.
        ---
        tags:
            - Dictionary/Laboratories
        parameters:
            - $ref: '#/parameters/ProvinceParameter'
        responses:
            401:
                description: Invalid or missing token.
            403:
                description: A persisted dashboard role is required.
            200:
                description: A list of all laboratories in the given province.
            404:
                description: No laboratories found for the specified province.
            500:
                description: An error occurred. Internal details are not returned.
        """
        parser = reqparse.RequestParser()

        parser.add_argument(
            "province",
            type=lambda x: x,
            action="append",
            location="args",
            help="This field cannot be blank.",
        )

        return run_reporting_endpoint(parser.parse_args, get_laboratories_by_province)


class dict__laboratories__by_district(Resource):
    def get(self):
        """
        Get all laboratories by district.
        ---
        tags:
            - Dictionary/Laboratories
        parameters:
            - $ref: '#/parameters/DistrictParameter'
        responses:
            401:
                description: Invalid or missing token.
            403:
                description: A persisted dashboard role is required.
            200:
                description: A list of all laboratories in the given district.
            404:
                description: No laboratories found for the specified district.
            500:
                description: An error occurred. Internal details are not returned.
        """
        parser = reqparse.RequestParser()

        parser.add_argument(
            "district",
            type=lambda x: x,
            action="append",
            location="args",
            help="This field cannot be blank.",
        )

        return run_reporting_endpoint(parser.parse_args, get_laboratories_by_district)
