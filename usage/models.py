from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text

from db.database import db

def _now():
    # Naive UTC, matching the DATETIME columns and the GETUTCDATE() default in the SQL script.
    return datetime.now(timezone.utc).replace(tzinfo=None)


# SQLite (tests) only autoincrements INTEGER primary keys; SQL Server wants BIGINT.
_ID = BigInteger().with_variant(Integer, "sqlite")


class UsageEvent(db.Model):
    """One dashboard page view. Written by POST /usage/events."""

    __tablename__ = "openldr_usage_events"
    __bind_key__ = "users"
    id = Column(_ID, primary_key=True, autoincrement=True)
    user_id = Column(String(250), nullable=False)
    dashboard = Column(String(20), nullable=False)
    page = Column(String(250), nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=_now)


class PatientAccessLog(db.Model):
    """One access to patient-level rows."""

    __tablename__ = "openldr_patient_access_log"
    __bind_key__ = "users"
    id = Column(_ID, primary_key=True, autoincrement=True)
    user_id = Column(String(250), nullable=False)
    dashboard = Column(String(20), nullable=False)
    endpoint = Column(String(250), nullable=False)
    row_count = Column(Integer, nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=_now)


class AdminAuditLog(db.Model):
    """One administrative change to a user. ``changes`` holds JSON text."""

    __tablename__ = "openldr_admin_audit_log"
    __bind_key__ = "users"
    id = Column(_ID, primary_key=True, autoincrement=True)
    actor_user_id = Column(String(250), nullable=False)
    action = Column(String(50), nullable=False)
    target_user_id = Column(String(250), nullable=True)
    changes = Column(Text, nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=_now)
