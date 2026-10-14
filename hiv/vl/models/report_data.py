from db.database import db


class Resume(db.Model):
    """Weekly VL figures per lab, produced by the ReportData ETL.

    Column names are the raw ones the legacy Node queries use (labcode,
    start_date, registered, ...). The camelCase names in Node's model file
    are stale. Verify against the real table before deploying (Task 5).
    """

    __bind_key__ = "reportData"
    __tablename__ = "Resume"
    __table_args__ = {"extend_existing": True}

    labcode = db.Column(db.String(10), primary_key=True)
    labname = db.Column(db.String(100))
    week = db.Column(db.String(20), primary_key=True)
    start_date = db.Column(db.DateTime, primary_key=True)
    end_date = db.Column(db.DateTime)
    backlogs = db.Column(db.Integer)
    tests = db.Column(db.Integer)
    registered = db.Column(db.Integer)
    rejected = db.Column(db.Integer)
    capacity = db.Column(db.Integer)
    tat = db.Column(db.Float)
