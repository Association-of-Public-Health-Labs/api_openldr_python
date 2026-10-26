from hiv.eid.models.eid_master_model import EIDMaster


def test_model_has_no_result_prefixed_columns():
    assert not [c.name for c in EIDMaster.__table__.columns if c.name.startswith("Result")]


def test_model_has_final_result_and_contact_columns():
    names = {c.name for c in EIDMaster.__table__.columns}
    assert {"FinalResult", "CaregiverMobileContact", "AnalysisDateTime", "RegisteredDateTime"} <= names
