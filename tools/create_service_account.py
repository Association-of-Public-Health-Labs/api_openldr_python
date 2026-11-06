"""
Create an API service account: the login a dashboard server uses to read report numbers.

    python -m tools.create_service_account NAME

NAME is lowercase letters, digits and hyphens, starting with a letter (e.g. ``tb-dashboard``). The
script stores a bcrypt hash of a new random secret in ``openldr_api_user_users`` (user_id
``svc-NAME``, role ``service``) and prints the secret once; it is not kept anywhere else. It writes
to the database the API is configured for, so run it where you mean to.

For the account to log in, add NAME to ``API_SERVICE_ACCOUNTS`` (comma separated) in the API's
environment. With PERMISSIONS_ENFORCED on, ``POST /auth/login`` accepts only those names, and their
tokens read the dashboards' report numbers, never patient rows or the admin endpoints.
"""
import re
import secrets
import sys
from datetime import datetime

import bcrypt

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


def validate_name(name):
    """The name, or ValueError when it is not lowercase letters, digits and hyphens starting with a letter."""
    if not NAME_PATTERN.fullmatch(name or ""):
        raise ValueError("NAME must match ^[a-z][a-z0-9-]*$ (lowercase letters, digits, hyphens; starts with a letter)")
    return name


def build_service_account(name):
    """``(secret, row)``: a new random secret and the unsaved User row holding only its bcrypt hash."""
    from auth.user_model import User

    validate_name(name)
    secret = secrets.token_urlsafe(48)
    now = datetime.now()
    row = User(
        user_id=f"svc-{name}",
        user_name=name,
        first_name="Service",
        last_name=name,
        password=bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        start_date=now,
        updated_at=now,
        role="service",
        email=None,
    )
    return secret, row


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m tools.create_service_account NAME", file=sys.stderr)
        return 2
    try:
        name = validate_name(argv[0])
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    from app import app
    from auth.user_model import User
    from db.database import db

    with app.app_context():
        if User.query.filter_by(user_id=f"svc-{name}").first() or User.query.filter_by(user_name=name).first():
            print(f"A user named {name} already exists; nothing was changed.", file=sys.stderr)
            return 1
        secret, row = build_service_account(name)
        db.session.add(row)
        db.session.commit()

    print(f"Service account {name} created. Secret (shown once):")
    print(secret)
    print(f"Add {name} to API_SERVICE_ACCOUNTS so it can log in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
