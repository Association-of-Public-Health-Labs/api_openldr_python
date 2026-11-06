from flask import request
from flask_restful import Resource

from usage.service import clean_page, record_page_view
from utilities.controller_helpers import authenticate_request
from utilities.permissions import (
    KNOWN_DASHBOARDS,
    current_permissions,
    forbidden_response,
    permissions_enforced,
)


def _bad_request(message):
    return {"status": "error", "code": 400, "message": message}, 400


class RecordPageView(Resource):
    def post(self):
        """Record a dashboard page view for the authenticated user.
        ---
        tags:
          - Usage
        security:
          - Bearer: []
        parameters:
          - name: body
            in: body
            required: true
            schema:
              type: object
              required: [dashboard, page]
              properties:
                dashboard:
                  type: string
                  enum: [vl, eid, tb]
                  example: vl
                page:
                  type: string
                  description: Path of the page. Query string and fragment are dropped; at most 250 characters are kept.
                  example: /lab
        responses:
          204:
            description: Accepted. Also returned when storing the event fails, because tracking never surfaces errors.
          400:
            description: Invalid JSON, unknown dashboard or missing page.
          401:
            description: Invalid or missing token.
          403:
            description: The user cannot open that dashboard.
        """
        user_id, error = authenticate_request()
        if error is not None:
            return error

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _bad_request("A JSON object is required")
        dashboard = payload.get("dashboard")
        if not isinstance(dashboard, str) or dashboard not in KNOWN_DASHBOARDS:
            return _bad_request("dashboard must be one of: " + ", ".join(sorted(KNOWN_DASHBOARDS)))
        page = payload.get("page")
        if not isinstance(page, str) or not clean_page(page):
            return _bad_request("page must be a non-empty string")

        # /usage/events belongs to no dashboard, so the gate lets it through; check the body's dashboard here.
        if permissions_enforced() and dashboard not in current_permissions().dashboards:
            return forbidden_response()

        record_page_view(user_id, dashboard, page)
        return "", 204
