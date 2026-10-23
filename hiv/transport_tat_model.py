"""
Columns shared by ReportData's VLTransportTATPerWeek and EIDTransportTATPerWeek, the tables behind
the weekly CV/EID spreadsheets' "Tempo de Transporte" sheet (api-weekly-reports-python).

One row per requesting facility, testing lab, type of test and week. The dashboards read only
the "Colheita à Recepção no Lab" group (collection_to_lab_reception_*); the hub legs are kept
for completeness of the mapping, not used.
"""
from db.database import db


class TransportTatColumns:
    """Mixin: identical in both tables. Each model adds its own dates (and EID its total)."""

    FacilityNationalCode = db.Column(db.String(50))
    RequestingFacilityCode = db.Column(db.String(50))
    ProvinceName = db.Column(db.String(100))
    DistrictName = db.Column(db.String(100))
    RequestingFacilityName = db.Column(db.String(200))
    TestingFacilityName = db.Column(db.String(200))
    TypeOfTest = db.Column(db.String(50))
    TestedSamplesWithCollectionDate = db.Column(db.Integer)

    collection_to_lab_reception_lt_7 = db.Column(db.Integer)
    collection_to_lab_reception_7_15 = db.Column(db.Integer)
    collection_to_lab_reception_16_21 = db.Column(db.Integer)
    collection_to_lab_reception_gt_21 = db.Column(db.Integer)
    collection_to_lab_reception_no_data = db.Column(db.Integer)
