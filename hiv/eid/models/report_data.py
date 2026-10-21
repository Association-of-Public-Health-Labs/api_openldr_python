from db.database import db
from hiv.transport_tat_model import TransportTatColumns


class EidTransportTatPerWeek(TransportTatColumns, db.Model):
    """Weekly transport TAT of EID samples per requesting facility (ReportData ETL)."""

    __bind_key__ = "reportData"
    __tablename__ = "EIDTransportTATPerWeek"
    __table_args__ = {"extend_existing": True}

    # The table has no key; the endpoints only read aggregates, so the week start serves as the
    # mapper's identity (never used to load single rows).
    start = db.Column("start_date", db.Date, primary_key=True)
    end = db.Column("end_date", db.Date)
    updated = db.Column("updated_at", db.DateTime)
    TotalTestedSamples = db.Column(db.Integer)
