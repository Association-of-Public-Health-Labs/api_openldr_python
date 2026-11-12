from flask import jsonify
from flask_restful import Resource, reqparse
from utilities.controller_helpers import authenticated_resource_method
from dict.services.laboratories_services import (
    get_all_laboratories,
    get_laboratories_by_province,
    get_laboratories_by_district,
)


class dict__laboratories(Resource):
    method_decorators = [authenticated_resource_method]

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
        """
        try:

            response = get_all_laboratories()

            return jsonify(response)

        except Exception as e:

            return jsonify(
                {
                    "status": "error",
                    "error": "Failed to retrieve laboratories",
                    "message": str(e),
                }
            )


class dict__laboratories__by_province(Resource):
    method_decorators = [authenticated_resource_method]

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
        """
        parser = reqparse.RequestParser()

        parser.add_argument(
            "province",
            type=lambda x: x,
            action="append",
            location="args",
            help="This field cannot be blank.",
        )

        req_args = parser.parse_args()

        try:

            response = get_laboratories_by_province(req_args)

            return jsonify(response)

        except Exception as e:

            return jsonify(
                {
                    "status": "error",
                    "error": "Failed to retrieve laboratories by province",
                    "message": str(e),
                }
            )


class dict__laboratories__by_district(Resource):
    method_decorators = [authenticated_resource_method]

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
        """
        parser = reqparse.RequestParser()

        parser.add_argument(
            "district",
            type=lambda x: x,
            action="append",
            location="args",
            help="This field cannot be blank.",
        )

        req_args = parser.parse_args()

        try:

            response = get_laboratories_by_district(req_args)

            return jsonify(response)

        except Exception as e:

            return jsonify(
                {
                    "status": "error",
                    "error": "Failed to retrieve laboratories by district",
                    "message": str(e),
                }
            )
