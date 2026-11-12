import json
import logging
import bcrypt
from flask_jwt_extended import create_access_token
from auth.user_model import User, UserLogs
from auth.roles import CANONICAL_ROLES, normalize_role
from uuid import uuid4
from datetime import datetime, timedelta
from db.database import db
from flask import session
from configs.paths import *

# from configs.paths_local import *

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def _error_response(status: int, error: str, message: str) -> dict:
    """Create a standardized error response."""
    return {"status": status, "error": error, "message": message}


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def _check_admin_permission(user_id: str) -> tuple:
    """
    Check if user has admin permission.
    Returns (user, error_response) - error_response is None if user is admin.
    """
    user = get_user_by_id_service(user_id)
    if not user:
        return None, _error_response(404, "Not Found", "User not found")
    if user.role != "Admin":
        return user, {
            "status": "error",
            "code": 403,
            "message": f"Forbidden - User with id {user.user_id} and role {user.role} is not authorized to access this resource.",
        }
    return user, None


def _build_user_data(user) -> dict:
    """Build user data dictionary from user object."""
    return {
        "user_id": user.user_id,
        "user_name": user.user_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
    }


def login_user_service(args):
    """Authenticate one unambiguous account using its bcrypt password hash."""
    raw_username = args.get("username")
    raw_email = args.get("email")
    login_password = args.get("password")
    if any(
        value is not None and not isinstance(value, str)
        for value in (raw_username, raw_email)
    ):
        return _error_response(400, "Bad Request", "Username/email must be strings")
    login_username = raw_username.strip() if raw_username else None
    login_email = raw_email.strip() if raw_email else None
    if (
        not (login_username or login_email)
        or not isinstance(login_password, str)
        or not login_password
    ):
        return _error_response(
            400, "Bad Request", "Username/email and password are required"
        )
    try:
        password_bytes = login_password.encode("utf-8")
    except UnicodeEncodeError:
        return _error_response(400, "Bad Request", "Invalid password format")
    # bcrypt only distinguishes the first 72 bytes. Do not accept longer input
    # as another password sharing the same prefix.
    if len(password_bytes) > 72:
        return _error_response(
            400, "Bad Request", "Password exceeds bcrypt's 72-byte limit"
        )

    invalid = _error_response(401, "Unauthorized", "Invalid credentials")
    try:
        identifiers = {}
        if login_username:
            identifiers["user_name"] = login_username
        if login_email:
            identifiers["email"] = login_email
        # When both identifiers are supplied they must identify the same row.
        # Duplicates must never select an arbitrary account through .first().
        matches = User.query.filter_by(**identifiers).limit(2).all()
        if len(matches) != 1:
            return invalid
        user = matches[0]
        if login_password == user.user_id:
            return invalid
        try:
            password_matches = bcrypt.checkpw(
                password_bytes, user.password.encode("utf-8")
            )
        except (ValueError, TypeError, AttributeError):
            return invalid
        if not password_matches:
            return invalid

        user_data = {
            "user_id": user.user_id,
            "user_name": user.user_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email_address": user.email,
            "role": get_user_role(user),
        }
        # Create the token before persisting a successful-login marker. The
        # login timestamp and audit entry are committed together.
        access_token = create_access_token(
            identity=user.user_id,
            additional_claims=user_data,
            expires_delta=timedelta(hours=1),
        )
        user.last_login = datetime.now()
        db.session.add(
            UserLogs(
                user_id=user.user_id,
                log_id=str(uuid4()),
                log_date=datetime.now(),
                log_type="login",
                log_details=json.dumps(
                    {
                        "event": "login",
                        "source": "auth_service.login_user_service",
                        "user": {
                            "user_id": user.user_id,
                            "user_name": user.user_name,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "role": user.role,
                            "email": user.email,
                        },
                        "message": "Login successful",
                        "context": {},
                    }
                ),
            )
        )
        db.session.commit()
        return {
            "message": "Login successful",
            "data": user_data,
            "token": access_token,
            "status": 200,
        }
    except Exception as exc:
        db.session.rollback()
        logger.error("Local login failed (%s)", type(exc).__name__)
        return _error_response(500, "Internal Server Error", "An error occurred")


def logout_user_service(args):
    """
    Logout the user by clearing the session.
    Note: Logging is handled by the controller (Clerk webhook).
    """
    try:
        session.clear()
    except Exception as e:
        return _error_response(500, "Internal Server Error", str(e))

    return {"status": 200, "message": "Logout successful"}


def get_user_role(user_query):
    if user_query:
        return user_query.role if hasattr(user_query, "role") else "guest"
    return "guest"


def update_user_service(args, id):
    """
    Update user information.
    Note: Logging is handled by the controller (Clerk webhook).
    """
    update_username = args.get("username")
    update_first_name = args.get("first_name")
    update_last_name = args.get("last_name")
    update_password = args.get("password")
    update_confirm_password = args.get("confirm_password")
    update_email = args.get("email")
    update_role = args.get("role")
    update_user_id = args.get("user_id")

    # Check admin permission
    _, error = _check_admin_permission(id)
    if error:
        return error

    # Validate required fields
    required_fields = [
        update_username,
        update_first_name,
        update_last_name,
        update_email,
        update_role,
        update_user_id,
    ]
    if not all(required_fields):
        return _error_response(400, "Bad Request", "Invalid input")

    update_role = normalize_role(update_role)
    if update_role is None:
        return _error_response(
            400, "Bad Request", "Role must be one of: " + ", ".join(CANONICAL_ROLES)
        )

    change_password = update_password is not None or update_confirm_password is not None
    if change_password and (
        not update_password
        or not update_confirm_password
        or update_password != update_confirm_password
    ):
        return _error_response(400, "Bad Request", "Passwords do not match")

    user_query = User.query.filter_by(user_id=update_user_id).first()
    if not user_query:
        return _error_response(404, "Not Found", "User not found")

    # Store old values for response
    old_values = {
        "user_name": user_query.user_name,
        "first_name": user_query.first_name,
        "last_name": user_query.last_name,
        "email": user_query.email,
        "role": user_query.role,
    }

    # Update user fields
    user_query.user_name = update_username
    user_query.first_name = update_first_name
    user_query.last_name = update_last_name
    if change_password:
        user_query.password = _hash_password(update_password)
    user_query.email = update_email
    user_query.role = update_role
    user_query.updated_at = datetime.now()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return _error_response(500, "Internal Server Error", str(e))

    return {
        "message": "User updated successfully",
        "data": {
            "user_id": {"old": update_user_id, "new": user_query.user_id},
            "username": {"old": old_values["user_name"], "new": update_username},
            "first_name": {"old": old_values["first_name"], "new": update_first_name},
            "last_name": {"old": old_values["last_name"], "new": update_last_name},
            "email": {"old": old_values["email"], "new": update_email},
            "role": {"old": old_values["role"], "new": update_role},
        },
    }


def delete_user_service(id, current_user=None):
    """
    Delete a user by ID.
    Note: Logging is handled by the controller (Clerk webhook).

    Args:
        id: User ID to delete
        current_user: Optional - authenticated user ID for permission check.
                      If None, skips permission check (used by Clerk webhook).
    """
    if not id:
        return _error_response(400, "Bad Request", "User ID is required")

    # Check admin permission only if current_user is provided
    if current_user is not None:
        _, error = _check_admin_permission(current_user)
        if error:
            return error

    user_query = User.query.filter_by(user_id=id).first()
    if not user_query:
        return _error_response(404, "Not Found", "User not found")

    # Store values before deletion for response
    deleted_data = _build_user_data(user_query)

    try:
        db.session.delete(user_query)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return _error_response(500, "Internal Server Error", str(e))

    return {
        "message": "User deleted successfully",
        "data": {
            "user_id": deleted_data["user_id"],
            "username": deleted_data["user_name"],
            "first_name": deleted_data["first_name"],
            "last_name": deleted_data["last_name"],
            "email": deleted_data["email"],
            "role": deleted_data["role"],
        },
    }


def create_user_service(args, id):
    """Create an account only on behalf of an existing, persisted Admin."""
    if not id:
        return _error_response(403, "Forbidden", "Admin permission required")
    _, error = _check_admin_permission(id)
    if error:
        return _error_response(403, "Forbidden", "Admin permission required")
    return _create_user_record(args)


def provision_clerk_user_service(args):
    """Provision a standard user after the caller verifies the Svix signature.

    This is an internal webhook path, never a bypass selected by public JSON.
    Clerk data or metadata cannot assign an administrative role here.
    """
    if not args.get("user_id"):
        return _error_response(400, "Bad Request", "User ID is required")
    return _create_user_record({**args, "role": "user"})


def sync_clerk_user_service(args):
    """Sync a verified Clerk profile without overwriting local permissions.

    Called only by the signed webhook. Role and password are administered
    separately and must survive Clerk profile updates unchanged.
    """
    if not args.get("user_id"):
        return _error_response(400, "Bad Request", "User ID is required")
    fields = {
        "user_name": args.get("username"),
        "first_name": args.get("first_name"),
        "last_name": args.get("last_name"),
        "email": args.get("email"),
    }
    if not all(fields.values()):
        return _error_response(400, "Bad Request", "Profile fields are required")
    user = get_user_by_id_service(args["user_id"])
    if user is None:
        return _error_response(404, "Not Found", "User not found")
    for name, value in fields.items():
        setattr(user, name, value)
    user.updated_at = datetime.now()
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("Clerk profile persistence failed (%s)", type(exc).__name__)
        return _error_response(500, "Internal Server Error", "An error occurred")
    return {"message": "User updated successfully", "data": _build_user_data(user)}


def _create_user_record(args):
    """
    Persist a user after public authorisation or verified webhook provisioning.
    Logging of successful Clerk creation is handled by the webhook controller.
    """
    create_username = args.get("username")
    create_first_name = args.get("first_name")
    create_last_name = args.get("last_name")
    create_password = args.get("password")
    create_confirm_password = args.get("confirm_password")
    create_email = args.get("email")
    create_role = args.get("role")

    # Validate required fields
    required_fields = [
        create_username,
        create_first_name,
        create_last_name,
        create_password,
        create_confirm_password,
        create_email,
        create_role,
    ]
    if not all(required_fields):
        return _error_response(400, "Bad Request", "All fields are required")

    create_role = normalize_role(create_role)
    if create_role is None:
        return _error_response(
            400, "Bad Request", "Role must be one of: " + ", ".join(CANONICAL_ROLES)
        )

    if create_password != create_confirm_password:
        return _error_response(400, "Bad Request", "Passwords do not match")

    # Check for existing user with same username/email
    existing_users = User.query.filter_by(user_name=create_username).all()
    for user in existing_users:
        if user.user_name == create_username or user.email == create_email:
            if _verify_password(create_password, user.password):
                return _error_response(
                    400, "Bad Request", "Username or email already exists"
                )

    new_user_id = args.get("user_id") or str(uuid4())

    user = User(
        user_name=create_username,
        first_name=create_first_name,
        last_name=create_last_name,
        password=_hash_password(create_password),
        email=create_email,
        role=create_role,
        user_id=new_user_id,
        start_date=datetime.now(),
        updated_at=datetime.now(),
    )

    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("User creation persistence failed (%s)", type(e).__name__)
        return _error_response(500, "Internal Server Error", "An error occurred")

    return {
        "message": "User created successfully",
        "data": {
            "user_id": new_user_id,
            "username": create_username,
            "first_name": create_first_name,
            "last_name": create_last_name,
            "email": create_email,
            "role": create_role,
        },
    }


def get_all_users_service(id):

    try:
        user = get_user_by_id_service(id)
    except Exception as e:
        return {"status": 500, "message": str(e)}

    if not user:
        return {"status": 404, "message": "User not found"}

    if user.role != "Admin":
        return {
            "status": "error",
            "code": 403,
            "message": f"Forbidden - User with id {user.user_id} and role {user.role} is not authorized to access this resource.",
        }

    users = User.query.all()

    try:
        save_user_log_service(
            {
                "user_id": id,
                "log_type": "get_all_users",
                "log_details": {
                    "event": "get_all_users",
                    "source": "auth_service.get_all_users_service",
                    "user": {
                        "user_id": id,
                        "role": user.role,
                    },
                    "message": "Fetched all users",
                    "context": {
                        "count": len(users),
                        "user_ids": [u.user_id for u in users],
                    },
                },
            }
        )
    except Exception as e:
        return {"status": 500, "message": str(e)}

    return [
        {
            "username": user.user_name,
            "email": user.email,
            "role": user.role,
            "user_id": user.user_id,
        }
        for user in users
    ]


def get_user_by_id_service(id):
    """
    Get a user by their id.

    Args:
        id (int): The id of the user.

    Returns:
        User: The user object if found, None otherwise.
    """
    user = (
        User.query.filter(User.user_id == id).order_by(User.start_date.desc()).first()
    )

    return user


def save_user_log_service(args):

    user_log = UserLogs(
        user_id=args.get("user_id"),
        log_id=str(uuid4()),
        log_date=datetime.now(),
        log_type=args.get("log_type"),
        log_details=json.dumps(args.get("log_details")),
    )
    try:
        db.session.add(user_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {"status": 500, "message": str(e)}


def update_last_login_service(user_id: str):
    """
    Update the last_login field for the given user_id.
    Note: Logging is handled by the controller (Clerk webhook).
    """
    try:
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            return _error_response(404, "Not Found", "User not found")

        user.last_login = datetime.now()
        db.session.commit()
        return {"status": 200, "message": "last_login updated"}
    except Exception as e:
        db.session.rollback()
        return _error_response(500, "Internal Server Error", str(e))
