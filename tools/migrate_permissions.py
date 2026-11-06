"""
One-off: give existing Clerk users their first permissions, so nobody is locked out when
PERMISSIONS_ENFORCED is switched on.

    python -m tools.migrate_permissions --admins admins.txt            # dry run: prints a summary
    python -m tools.migrate_permissions --admins admins.txt --apply    # writes to Clerk

Every user gets all dashboards (vl, eid, tb). ``patientData`` is true when the user's role in
``openldr_api_user_users`` (matched on user_id = Clerk user id) is exactly ``Admin``. ``admin`` is true
only for the emails in the --admins file (one per line, case-insensitive). Other publicMetadata keys
are kept. Users who already have ``dashboards`` are skipped, so re-running never undoes changes made
in the admin dashboard.

Uses CLERK_API_URL and CLERK_SECRET_KEY and the API's configured users database. Prints counts and
emails only. Exit code 1 when any write failed.
"""
import argparse
import sys
from dataclasses import dataclass

DASHBOARDS = ["vl", "eid", "tb"]
PAGE_SIZE = 100


@dataclass(frozen=True)
class Change:
    user_id: str
    email: str
    public_metadata: dict


def primary_email(user):
    """The user's primary email address, else the first one, else None."""
    addresses = user.get("email_addresses") or []
    primary_id = user.get("primary_email_address_id")
    for address in addresses:
        if address.get("id") == primary_id:
            return address.get("email_address")
    return addresses[0].get("email_address") if addresses else None


def plan_changes(clerk_users, db_roles, admin_emails):
    """The metadata to write for each user who has no ``dashboards`` yet. Pure."""
    admins = {e.strip().lower() for e in admin_emails}
    changes = []
    for user in clerk_users:
        existing = user.get("public_metadata") or {}
        if "dashboards" in existing:
            continue
        email = primary_email(user)
        metadata = dict(existing)
        metadata["dashboards"] = list(DASHBOARDS)
        metadata["patientData"] = db_roles.get(user["id"]) == "Admin"
        metadata["admin"] = bool(email) and email.lower() in admins
        changes.append(Change(user["id"], email, metadata))
    return changes


def unmatched_admins(clerk_users, admin_emails):
    """Admin emails (as listed) that match no Clerk user, sorted."""
    known = {e.lower() for e in (primary_email(u) for u in clerk_users) if e}
    for user in clerk_users:
        known.update(a["email_address"].lower() for a in user.get("email_addresses") or [] if a.get("email_address"))
    return sorted(e for e in admin_emails if e.strip().lower() not in known)


def read_admins(path):
    """Lowercased emails from a file, one per line; blank lines and # comments are ignored."""
    with open(path, encoding="utf-8") as handle:
        lines = (line.strip() for line in handle)
        return {line.lower() for line in lines if line and not line.startswith("#")}


def fetch_all_users(http, api_url, secret_key, page_size=PAGE_SIZE):
    """Every Clerk user, paging with limit/offset until a page comes back short or empty."""
    headers = {"Authorization": f"Bearer {secret_key}"}
    users, offset = [], 0
    while True:
        response = http.get(f"{api_url}/users", headers=headers, params={"limit": page_size, "offset": offset, "order_by": "created_at"})
        if response.status_code != 200:
            raise RuntimeError(f"Clerk user list failed: HTTP {response.status_code}")
        page = response.json()
        users.extend(page)
        if len(page) < page_size:
            return users
        offset += page_size


def run(http, api_url, secret_key, db_roles, admin_emails, apply, page_size=PAGE_SIZE):
    """Plan (and with ``apply`` write) the changes; returns the process exit code."""
    users = fetch_all_users(http, api_url, secret_key, page_size=page_size)
    changes = plan_changes(users, db_roles, admin_emails)
    missing = unmatched_admins(users, admin_emails)

    print(f"Clerk users: {len(users)}; to migrate: {len(changes)}; already migrated (skipped): {len(users) - len(changes)}")
    print(f"  patientData: {sum(c.public_metadata['patientData'] for c in changes)}; admin: {sum(c.public_metadata['admin'] for c in changes)}")
    for email in missing:
        print(f"WARNING admin email matches no Clerk user: {email}")

    if not apply:
        print("Dry run: nothing was written. Re-run with --apply to write.")
        return 0

    headers = {"Authorization": f"Bearer {secret_key}"}
    written, failed = 0, []
    for change in changes:
        try:
            response = http.patch(f"{api_url}/users/{change.user_id}/metadata", headers=headers, json={"public_metadata": change.public_metadata})
            ok = response.status_code == 200
            reason = f"HTTP {response.status_code}"
        except Exception as exc:  # network error: report, keep going
            ok, reason = False, type(exc).__name__
        if ok:
            written += 1
        else:
            failed.append(change)
            print(f"FAILED {change.email or change.user_id}: {reason}", file=sys.stderr)
    print(f"Written: {written}; failed: {len(failed)}")
    return 1 if failed else 0


def load_db_roles():
    """``{user_id: role}`` from openldr_api_user_users, in the API's configured users database."""
    from app import app
    from auth.user_model import User

    with app.app_context():
        return {row.user_id: row.role for row in User.query.with_entities(User.user_id, User.role).all()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--admins", required=True, help="file with one admin email per line")
    parser.add_argument("--apply", action="store_true", help="write to Clerk (default: dry run)")
    args = parser.parse_args(argv)

    import requests

    from configs.paths import CLERK_API_URL, CLERK_SECRET_KEY

    if not CLERK_API_URL or not CLERK_SECRET_KEY:
        print("CLERK_API_URL and CLERK_SECRET_KEY must be set.", file=sys.stderr)
        return 2
    return run(requests, CLERK_API_URL.rstrip("/"), CLERK_SECRET_KEY, load_db_roles(), read_admins(args.admins), args.apply)


if __name__ == "__main__":
    sys.exit(main())
