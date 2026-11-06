import logging

from flask import request
from flask_restful import Resource

from usage import reports
from usage.service import clean_page, record_admin_action, record_page_view
from utilities.controller_helpers import GENERIC_SERVER_ERROR, authenticate_request
from utilities.permissions import (
    KNOWN_DASHBOARDS,
    current_permissions,
    forbidden_response,
    permissions_enforced,
    require_admin_claim,
)
from utilities.service_helpers import InvalidParameter

logger = logging.getLogger(__name__)


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


def _admin_report(report, *, dashboard_filter=True, limit_default=None):
    """Authenticate, require the admin claim, parse the period (and dashboard, limit), run the report."""
    user_id, error = authenticate_request()
    if error is not None:
        return error
    forbidden = require_admin_claim()
    if forbidden is not None:
        return forbidden
    try:
        args = [reports.parse_period(request.args.getlist("interval_dates"))]
        if limit_default is not None:
            args.append(reports.parse_limit(request.args.get("limit"), limit_default))
        if dashboard_filter:
            args.append(request.args.get("dashboard") or None)
        return report(*args)
    except InvalidParameter as exc:
        return _bad_request(str(exc))
    except Exception:
        logger.exception("Unhandled error on %s", request.path)
        return {"status": "error", "code": 500, "message": GENERIC_SERVER_ERROR}, 500


class UsageSummary(Resource):
    def get(self):
        """Active users and sessions for a period, with the period just before it.
        ---
        tags:
          - Usage
        security:
          - Bearer: []
        parameters:
          - name: interval_dates
            in: query
            required: true
            type: string
            description: Start and end date, YYYY-MM-DD,YYYY-MM-DD. The end date is included.
          - name: dashboard
            in: query
            required: false
            type: string
            enum: [vl, eid, tb]
        responses:
          200:
            description: Totals. previous covers the same number of days immediately before the start.
            schema:
              type: object
              properties:
                active_users:
                  type: integer
                sessions:
                  type: integer
                sessions_per_user:
                  type: number
                previous:
                  type: object
                  properties:
                    active_users:
                      type: integer
                    sessions:
                      type: integer
          400:
            description: Missing or malformed interval_dates.
          401:
            description: Invalid or missing token.
          403:
            description: The token does not carry the admin claim, or is a service token.
        """
        return _admin_report(reports.summary)


class UsageActiveUsersByMonth(Resource):
    def get(self):
        """Distinct active users per month and dashboard.
        ---
        tags:
          - Usage
        security:
          - Bearer: []
        parameters:
          - name: interval_dates
            in: query
            required: true
            type: string
            description: Start and end date, YYYY-MM-DD,YYYY-MM-DD. The end date is included.
        responses:
          200:
            description: One row per year, month and dashboard.
            schema:
              type: array
              items:
                type: object
                properties:
                  year:
                    type: integer
                  month:
                    type: integer
                  dashboard:
                    type: string
                  active_users:
                    type: integer
          400:
            description: Missing or malformed interval_dates.
          401:
            description: Invalid or missing token.
          403:
            description: The token does not carry the admin claim, or is a service token.
        """
        return _admin_report(reports.active_users_by_month, dashboard_filter=False)


class UsageByDashboard(Resource):
    def get(self):
        """Active users and sessions per dashboard.
        ---
        tags:
          - Usage
        security:
          - Bearer: []
        parameters:
          - name: interval_dates
            in: query
            required: true
            type: string
            description: Start and end date, YYYY-MM-DD,YYYY-MM-DD. The end date is included.
        responses:
          200:
            description: One row per dashboard with activity.
            schema:
              type: array
              items:
                type: object
                properties:
                  dashboard:
                    type: string
                  active_users:
                    type: integer
                  sessions:
                    type: integer
                  sessions_per_user:
                    type: number
          400:
            description: Missing or malformed interval_dates.
          401:
            description: Invalid or missing token.
          403:
            description: The token does not carry the admin claim, or is a service token.
        """
        return _admin_report(reports.by_dashboard, dashboard_filter=False)


class UsageTopUsers(Resource):
    def get(self):
        """Users with the most sessions. Names are not returned; resolve user_id through Clerk.
        ---
        tags:
          - Usage
        security:
          - Bearer: []
        parameters:
          - name: interval_dates
            in: query
            required: true
            type: string
            description: Start and end date, YYYY-MM-DD,YYYY-MM-DD. The end date is included.
          - name: dashboard
            in: query
            required: false
            type: string
            enum: [vl, eid, tb]
          - name: limit
            in: query
            required: false
            type: integer
            default: 10
            description: From 1 to 100.
        responses:
          200:
            description: Users by sessions, highest first.
            schema:
              type: array
              items:
                type: object
                properties:
                  user_id:
                    type: string
                  dashboards:
                    type: array
                    items:
                      type: string
                  sessions:
                    type: integer
                  last_visit:
                    type: string
                    format: date-time
          400:
            description: Missing or malformed interval_dates, or invalid limit.
          401:
            description: Invalid or missing token.
          403:
            description: The token does not carry the admin claim, or is a service token.
        """
        return _admin_report(reports.top_users, limit_default=10)


class UsageTopPages(Resource):
    def get(self):
        """Most viewed pages.
        ---
        tags:
          - Usage
        security:
          - Bearer: []
        parameters:
          - name: interval_dates
            in: query
            required: true
            type: string
            description: Start and end date, YYYY-MM-DD,YYYY-MM-DD. The end date is included.
          - name: dashboard
            in: query
            required: false
            type: string
            enum: [vl, eid, tb]
          - name: limit
            in: query
            required: false
            type: integer
            default: 5
            description: From 1 to 100.
        responses:
          200:
            description: Pages by views, highest first.
            schema:
              type: array
              items:
                type: object
                properties:
                  dashboard:
                    type: string
                  page:
                    type: string
                  views:
                    type: integer
          400:
            description: Missing or malformed interval_dates, or invalid limit.
          401:
            description: Invalid or missing token.
          403:
            description: The token does not carry the admin claim, or is a service token.
        """
        return _admin_report(reports.top_pages, limit_default=5)


class UsagePatientAccess(Resource):
    def get(self):
        """How often each user opened patient-level rows.
        ---
        tags:
          - Usage
        security:
          - Bearer: []
        parameters:
          - name: interval_dates
            in: query
            required: true
            type: string
            description: Start and end date, YYYY-MM-DD,YYYY-MM-DD. The end date is included.
          - name: dashboard
            in: query
            required: false
            type: string
            enum: [vl, eid, tb]
        responses:
          200:
            description: One row per user and dashboard.
            schema:
              type: array
              items:
                type: object
                properties:
                  user_id:
                    type: string
                  dashboard:
                    type: string
                  accesses:
                    type: integer
                  last_access:
                    type: string
                    format: date-time
          400:
            description: Missing or malformed interval_dates.
          401:
            description: Invalid or missing token.
          403:
            description: The token does not carry the admin claim, or is a service token.
        """
        return _admin_report(reports.patient_access)


class RecordAdminAudit(Resource):
    def post(self):
        """Record an administrative change to a user. The actor is the token's user.
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
              required: [action, target_user_id]
              properties:
                action:
                  type: string
                  description: At most 50 characters.
                  example: update_permissions
                target_user_id:
                  type: string
                  example: user_2abc
                changes:
                  type: object
                  description: Any JSON, stored as text.
        responses:
          201:
            description: Stored.
          400:
            description: Invalid JSON, or a missing action or target_user_id.
          401:
            description: Invalid or missing token.
          403:
            description: The token does not carry the admin claim, or is a service token.
        """
        actor, error = authenticate_request()
        if error is not None:
            return error
        forbidden = require_admin_claim()
        if forbidden is not None:
            return forbidden

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _bad_request("A JSON object is required")
        action = payload.get("action")
        if not isinstance(action, str) or not action.strip() or len(action.strip()) > 50:
            return _bad_request("action must be a non-empty string of at most 50 characters")
        target = payload.get("target_user_id")
        if not isinstance(target, str) or not target.strip() or len(target.strip()) > 250:
            return _bad_request("target_user_id must be a non-empty string")

        try:
            audit_id = record_admin_action(actor, action.strip(), target.strip(), payload.get("changes"))
        except Exception:
            logger.exception("Could not store admin audit entry")
            return {"status": "error", "code": 500, "message": GENERIC_SERVER_ERROR}, 500
        return {"status": "ok", "id": audit_id}, 201
