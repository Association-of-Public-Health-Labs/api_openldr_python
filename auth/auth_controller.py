import logging

import requests
from flask_restful import Resource, reqparse
from auth.auth_service import (
    login_user_service,
    get_all_users_service,
    update_user_service,
    delete_user_service,
    create_user_service,
    logout_user_service,
    get_user_by_id_service,
    save_user_log_service,
    update_last_login_service,
)
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask import jsonify, request
from configs.paths import *
from configs import paths as config_paths
from utilities.webhook_verification import (
    WebhookVerificationError,
    verify_svix_signature,
)

logger = logging.getLogger(__name__)

WEBHOOK_UNAUTHORIZED_BODY = {
    "status": 401,
    "error": "Unauthorized",
    "message": "Invalid webhook signature",
}
# from configs.paths_local import *


# =============================================================================
# Helper Functions
# =============================================================================

def _error_response(status: int, error: str, message: str):
    """Create a standardized error response."""
    return jsonify({"status": status, "error": error, "message": message})


def _success_response(message: str, data: dict = None):
    """Create a standardized success response (never carries a token)."""
    response = {"status": 200, "message": message}
    if data is not None:
        response["data"] = data
    return jsonify(response)


def _get_clerk_headers():
    """Get headers for Clerk API requests."""
    return {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _fetch_clerk_user(user_id: str):
    """Fetch user details from Clerk API."""
    headers = _get_clerk_headers()
    response = requests.get(f"{CLERK_API_URL}/users/{user_id}", headers=headers)
    if response.status_code != 200:
        return None
    return response.json()


def _build_user_args_from_clerk(user_id: str, clerk_data: dict, role: str = "user") -> dict:
    """Build user arguments dictionary from Clerk API response."""
    email = clerk_data.get("email_addresses", [{}])[0].get("email_address")
    first_name = clerk_data.get("first_name")
    last_name = clerk_data.get("last_name")
    
    return {
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": f"{first_name}_{last_name}",
        "email": email,
        "provider": "clerk",
        "password": user_id,
        "confirm_password": user_id,
        "role": role,
    }


def _build_log_args(user_id: str, log_type: str, event: str, source: str, user_data: dict, extra: dict = None) -> dict:
    """Build log arguments dictionary."""
    log_details = {
        "event": event,
        "source": source,
        "user": user_data,
    }
    if extra:
        log_details.update(extra)
    
    return {
        "user_id": user_id,
        "log_type": log_type,
        "log_details": log_details,
    }


def _save_log_silent(log_args: dict):
    """Save log without blocking on failure."""
    try:
        save_user_log_service(log_args)
    except Exception:
        pass


# =============================================================================
# Controllers
# =============================================================================

class user_controller(Resource):
    """
    Class to handle user login, update, and deletion.
    """

    @jwt_required()
    def get(self):
        """
        Handle GET request all users
        ---
        tags:
            - Authentication
        security:
            - Bearer: []
        responses:
            200:
                description: Returns a list of all users.
            401:
                description: Unauthorized
            500:
                description: An Error Occurred
        """
        current_user = get_jwt_identity()

        if not current_user:
            return _error_response(401, "Unauthorized", "User not authenticated")

        try:
            return jsonify(get_all_users_service(current_user))
        except Exception as e:
            return _error_response(500, "Internal Server Error", str(e))

    def post(self):
        """
        Handle POST request for user login.
        Expects 'username' and 'password' in the request body.
        ---
        tags:
            - Authentication
        parameters:
            - $ref: '#/parameters/UserLoginParameters'
        responses:
            200:
                description: Returns a JWT token if login is successful.
            400:
                description: Invalid Parameters
            500:
                description: An Error Occurred
        """
        parser = reqparse.RequestParser()
        parser.add_argument("username", required=True)
        parser.add_argument("password", required=True)
        args = parser.parse_args()

        if not args.get("username") or not args.get("password"):
            return _error_response(400, "Bad Request", "Username and password are required")

        try:
            return jsonify(login_user_service(args))
        except Exception as e:
            return _error_response(500, "Internal Server Error", str(e))

    @jwt_required()
    def put(self):
        """
        Handle PUT request for user update.
        Expects 'username', first_name', 'last_name', 'user_id', 'email', 'role', and optional 'password' and 'confirm_password' in the request body.
        ---
        tags:
            - Authentication
        security:
            - Bearer: []
        parameters:
            - $ref: '#/parameters/UserUpdateParameters'
        responses:
            200:
                description: Returns the updated user details.
            400:
                description: Invalid Parameters
            401:
                description: Unauthorized
            403:
                description: Forbidden
            500:
                description: An Error Occurred
        """
        current_user = get_jwt_identity()

        if not current_user:
            return _error_response(401, "Unauthorized", "User not authenticated")

        parser = reqparse.RequestParser()
        parser.add_argument("username", required=True)
        parser.add_argument("first_name", required=True)
        parser.add_argument("last_name", required=True)
        parser.add_argument("user_id", required=True)
        parser.add_argument("email", required=True)
        parser.add_argument("role", required=True)
        parser.add_argument("password", required=False, default=None)
        parser.add_argument("confirm_password", required=False, default=None)
        args = parser.parse_args()

        try:
            return jsonify(update_user_service(args, current_user))
        except Exception as e:
            return _error_response(500, "Internal Server Error", str(e))

    @jwt_required()
    def delete(self):
        """
        Handle DELETE request for user deletion.
        Expects 'user_id' in the request body.
        ---
        tags:
            - Authentication
        security:
            - Bearer: []
        parameters:
            - $ref: '#/parameters/UserDeletionParameters'
        responses:
            200:
                description: Returns a success message if deletion is successful.
            400:
                description: Invalid Parameters
            401:
                description: Unauthorized
            403:
                description: Forbidden
            500:
                description: An Error Occurred
        """
        current_user = get_jwt_identity()

        if not current_user:
            return _error_response(401, "Unauthorized", "User not authenticated")

        parser = reqparse.RequestParser()
        parser.add_argument("user_id", required=True)
        args = parser.parse_args()

        try:
            return jsonify(delete_user_service(args.user_id, current_user))
        except Exception as e:
            return _error_response(500, "Internal Server Error", str(e))


class user_create_controller(Resource):
    @jwt_required()
    def post(self):
        """
        Handle POST request for user creation.
        Expects 'username', 'password', 'confirm_password', 'email', and 'role' in the request body.
        ---
        tags:
            - Authentication
        parameters:
            - $ref: '#/parameters/UserCreateParameters'
        responses:
            200:
                description: Returns a success message if user is created successfully.
            400:
                description: Invalid Parameters
            403:
                description: Forbidden
            500:
                description: An Error Occurred
        """
        current_user = get_jwt_identity()

        if not current_user:
            return _error_response(401, "Unauthorized", "User not authenticated")

        parser = reqparse.RequestParser()
        parser.add_argument("username", required=True)
        parser.add_argument("first_name", required=True)
        parser.add_argument("last_name", required=True)
        parser.add_argument("password", required=True)
        parser.add_argument("confirm_password", required=True)
        parser.add_argument("email", required=True)
        parser.add_argument("role", required=True)
        args = parser.parse_args()

        try:
            return jsonify(create_user_service(args, current_user))
        except Exception as e:
            return _error_response(500, "Internal Server Error", str(e))


class clerk_user_controller(Resource):
    """
    Controller to handle Clerk webhook events for user authentication.

    Every request must carry a valid Svix signature made with
    ``CLERK_WEBHOOK_SECRET_KEY``; anything else gets a fixed 401 before the
    payload is parsed. Responses never include an access token: Clerk is the
    caller and ignores the body. API tokens come only from ``/auth/login``.
    """

    # Event handler mapping
    EVENT_HANDLERS = {
        "session.removed": "_handle_session_end",
        "session.ended": "_handle_session_end",
        "session.created": "_handle_session_created",
        "user.created": "_handle_user_created",
        "user.updated": "_handle_user_updated",
        "user.deleted": "_handle_user_deleted",
    }

    def post(self):
        """
        Handle POST request from clerk user authentication webhook.
        ---
        tags:
            - Clerk/Webhook
        responses:
            200:
                description: Returns a success message webhook is received.
            400:
                description: Invalid Parameters
            401:
                description: Missing or invalid Svix signature
            403:
                description: Forbidden
            500:
                description: An Error Occurred
        """
        try:
            verify_svix_signature(
                request.headers,
                request.get_data(),
                config_paths.CLERK_WEBHOOK_SECRET_KEY,
            )
        except WebhookVerificationError as exc:
            logger.warning("Rejected Clerk webhook: %r", exc)
            return WEBHOOK_UNAUTHORIZED_BODY, 401

        data = request.get_json(silent=True)

        if not data:
            return _error_response(400, "Bad Request", "Invalid payload")

        try:
            event_type = data.get("type")
            handler_name = self.EVENT_HANDLERS.get(event_type)

            if handler_name:
                handler = getattr(self, handler_name)
                return handler(data)

            return _error_response(400, "Bad Request", f"Unknown event type: {event_type}")

        except Exception as e:
            return _error_response(500, "Internal Server Error", str(e))

    def _handle_session_end(self, data: dict):
        """Handle session.removed and session.ended events."""
        user_id = data.get("data", {}).get("user_id")
        status = data.get("data", {}).get("status")

        clerk_data = _fetch_clerk_user(user_id)
        if not clerk_data:
            return _error_response(400, "Bad Request", "Failed to fetch user from Clerk API")

        args = _build_user_args_from_clerk(user_id, clerk_data)
        logout = logout_user_service(args)

        log_type = "logout" if status == "removed" else "session_ended"
        event = "user_logout"
        user_data = {
            "user_id": user_id,
            "first_name": clerk_data.get("first_name"),
            "last_name": clerk_data.get("last_name"),
            "email": clerk_data.get("email_addresses", [{}])[0].get("email_address"),
        }
        log_args = _build_log_args(user_id, log_type, event, "auth_controller.clerk_webhook", user_data)
        _save_log_silent(log_args)

        return _success_response(logout.get("message"), logout.get("data"))

    def _handle_session_created(self, data: dict):
        """Handle session.created event - login existing user or create new user."""
        user_id = data.get("data", {}).get("user_id")

        if not user_id:
            return _error_response(400, "Bad Request", "User ID not found in session data")

        clerk_data = _fetch_clerk_user(user_id)
        if not clerk_data:
            return _error_response(400, "Bad Request", "Failed to fetch user details from Clerk API")

        existing_user = get_user_by_id_service(user_id)

        if existing_user:
            return self._login_existing_user(existing_user, data)
        else:
            return self._create_new_user_from_clerk(user_id, clerk_data)

    def _login_existing_user(self, user, data: dict):
        """Record a Clerk login for an existing user (no token is issued)."""
        update_last_login_service(user.user_id)

        user_data = {
            "user_id": user.user_id,
            "user_name": user.user_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
        }
        extra = {
            "message": "User logged in via Clerk session.created",
            "context": {
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
                "clerk_session_id": data.get("data", {}).get("id"),
            },
        }
        log_args = _build_log_args(
            user.user_id, "login", "login",
            "auth_controller.clerk_user_controller.session_created",
            user_data, extra
        )
        _save_log_silent(log_args)

        return _success_response(
            "User session created successfully",
            {
                "user_id": user.user_id,
                "user_name": user.user_name,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email_address": user.email,
                "role": user.role,
            },
        )

    def _create_new_user_from_clerk(self, user_id: str, clerk_data: dict):
        """Create a new user from Clerk data."""
        args = _build_user_args_from_clerk(user_id, clerk_data)
        user_create = create_user_service(args, user_id)

        user_data = {
            "user_id": user_id,
            "first_name": clerk_data.get("first_name"),
            "last_name": clerk_data.get("last_name"),
            "email": clerk_data.get("email_addresses", [{}])[0].get("email_address"),
        }
        log_args = _build_log_args(
            user_id, "user_created", "user_created",    
            "auth_controller.clerk_webhook", user_data
        )
        _save_log_silent(log_args)

        return _success_response(user_create.get("message"), user_create.get("data"))

    def _handle_user_created(self, data: dict):
        """Handle user.created event."""
        user_id = data.get("data", {}).get("id")

        clerk_data = _fetch_clerk_user(user_id)
        if not clerk_data:
            return _error_response(400, "Bad Request", "Failed to fetch user from Clerk API")

        return self._create_new_user_from_clerk(user_id, clerk_data)

    def _handle_user_updated(self, data: dict):
        """Handle user.updated event."""
        user_id = data.get("data", {}).get("id")

        clerk_data = _fetch_clerk_user(user_id)
        if not clerk_data:
            return _error_response(400, "Bad Request", "Failed to fetch user from Clerk API")

        args = _build_user_args_from_clerk(user_id, clerk_data)
        user_update = update_user_service(args, user_id)

        user_data = {
            "user_id": user_id,
            "first_name": clerk_data.get("first_name"),
            "last_name": clerk_data.get("last_name"),
            "email": clerk_data.get("email_addresses", [{}])[0].get("email_address"),
        }
        log_args = _build_log_args(
            user_id, "user_updated", "user_updated",
            "auth_controller.clerk_webhook", user_data
        )
        _save_log_silent(log_args)

        return _success_response(user_update.get("message"), user_update.get("data"))

    def _handle_user_deleted(self, data: dict):
        """Handle user.deleted event."""
        user_id = data.get("data", {}).get("id")

        deleted = delete_user_service(user_id)

        user_data = {"user_id": user_id}
        log_args = _build_log_args(
            user_id, "user_deleted", "user_deleted",
            "auth_controller.clerk_webhook", user_data
        )
        _save_log_silent(log_args)

        return _success_response(deleted.get("message"), deleted.get("data"))
