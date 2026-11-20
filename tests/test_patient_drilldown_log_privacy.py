"""Real drill-down/dictionary query construction must not print SQL or filters.

Only Query execution and the account lookup are replaced. The TB services run
their actual patient query builder and serializer with synthetic patient rows.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dict.services import facilities_services, laboratories_services
from tb.gxpert.services import (
    tb_gx_services_facilities,
    tb_gx_services_laboratories,
)
from tests.hiv.sql_capture import captured_queries, to_sql


SENSITIVE_FACILITY = "Unidade Sintetica Privacidade"
TB_DRILLDOWNS = [
    (tb_gx_services_facilities, "trl_samples_avg_by_facility_month_service", "RequestingFacilityName"),
    (tb_gx_services_laboratories, "trl_samples_avg_by_lab_month_service", "TestingFacilityName"),
]


def _patient_row():
    return SimpleNamespace(
        RequestID=" REQ-SYNTHETIC-PRIVACY ",
        RequestingProvinceName=" Provincia Sintetica ",
        RequestingDistrictName=" Distrito Sintetico ",
        RequestingFacilityName=f" {SENSITIVE_FACILITY} ",
        FacilityNationalCode="SYNTHETIC-CODE",
        TestingProvinceName=" Provincia Laboratorio ",
        TestingDistrictName=" Distrito Laboratorio ",
        TestingFacilityName=" Laboratorio Sintetico ",
        FIRSTNAME=" Paciente Sintetico ",
        SURNAME=" Privacidade ",
        AgeInYears=27,
        HL7SexCode=" F ",
        TELHOME=" 000-SYNTHETIC-TELEPHONE ",
        FinalResult="MTB Detected",
        MtbTrace=None,
        Rifampicin="Not Detected",
        Fluoroquinolona=None,
        Isoniazid=None,
        Kanamicin=None,
        Amikacina=None,
        Capreomicin=None,
        Ethionamida=None,
        RejectReason=None,
        RejectRemark=None,
        Remarks=" Observacao sintetica ",
        SpecimenDatetime=datetime(2025, 5, 1, 8),
        RegisteredDateTime=datetime(2025, 5, 2, 8),
        AnalysisDateTime=datetime(2025, 5, 3, 8),
        AuthorisedDateTime=datetime(2025, 5, 4, 8),
        LIMSSpecimenSourceCode=" SPT ",
        LIMSSpecimenSourceDesc=" Sputum ",
        LIMSAnalyzerCode=" SYNTHETIC-GX ",
        TypeOfResult="Ultra 6 Cores",
    )


def _drilldown_args():
    return {
        "user_id": "synthetic-admin",
        "interval_dates": ["2025-01-01,2025-12-31"],
        "health_facility": SENSITIVE_FACILITY,
        "month": 5,
        "year": 2025,
    }


@pytest.mark.parametrize("module,service_name,filter_column", TB_DRILLDOWNS)
def test_tb_admin_drilldown_preserves_patient_response_without_output(
    app, capsys, caplog, module, service_name, filter_column
):
    with app.app_context(), patch.object(
        module, "get_user_by_id_service", return_value=SimpleNamespace(role="Admin")
    ), captured_queries([[], [_patient_row()]]) as queries:
        result = getattr(module, service_name)(_drilldown_args())
        assert len(queries) == 2
        patient_sql = to_sql(queries[1])

    # The sensitive selection still goes to the database and to the authorised
    # response, while staying out of stdout, stderr and application logs.
    assert f"[{filter_column}] = '{SENSITIVE_FACILITY}'" in patient_sql
    assert len(result) == 1
    record = result[0]
    assert record == {
        "request_id": "REQ-SYNTHETIC-PRIVACY",
        "province": "Provincia Sintetica",
        "district": "Distrito Sintetico",
        "health_facility": SENSITIVE_FACILITY,
        "facility_national_code": "SYNTHETIC-CODE",
        "first_name": "Paciente Sintetico",
        "last_name": "Privacidade",
        "age_in_years": 27,
        "sex_code": "F",
        "telephone": "000-SYNTHETIC-TELEPHONE",
        "final_result": "MTB Detected",
        "mtb_trace": None,
        "rifampicin": "Not Detected",
        "fluoroquinolona": None,
        "isoniazid": None,
        "kanamicin": None,
        "amikacina": None,
        "capreomicin": None,
        "ethionamida": None,
        "reject_reason": None,
        "reject_remark": None,
        "remarks": "Observacao sintetica",
        "specimen_datetime": "2025-05-01T08:00:00",
        "registered_datetime": "2025-05-02T08:00:00",
        "analysis_datetime": "2025-05-03T08:00:00",
        "authorised_datetime": "2025-05-04T08:00:00",
        "specimen_source_code": "SPT",
        "specimen_source_desc": "Sputum",
        "analyzer_code": "SYNTHETIC-GX",
        "Start_Date": "2025-01-01",
        "End_Date": "2025-12-31",
        "Year": 2025,
        "Month": 5,
        "Facility_Type": "health_facility",
        "Type_Of_Result": "Ultra 6 Cores",
        "Requsting_Province_Name": "Provincia Sintetica",
        "Requesting_District_Name": "Distrito Sintetico",
        "Requesting_Facility_Name": SENSITIVE_FACILITY,
        "Testing_Province_Name": "Provincia Laboratorio",
        "Testing_District_Name": "Distrito Laboratorio",
        "Testing_Facility_Name": "Laboratorio Sintetico",
    }
    assert capsys.readouterr() == ("", "")
    assert not caplog.records


@pytest.mark.parametrize("module,service_name,filter_column", TB_DRILLDOWNS)
def test_tb_drilldown_keeps_non_admin_denial_without_patient_query(
    app, capsys, module, service_name, filter_column
):
    with app.app_context(), patch.object(
        module, "get_user_by_id_service", return_value=SimpleNamespace(role="tb_gx")
    ), captured_queries() as queries:
        result = getattr(module, service_name)(_drilldown_args())

    assert result["status"] == "error"
    assert result["code"] == 403
    assert len(queries) == 1  # No identifiable patient query was executed.
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("filter_name", ["province", "district"])
@pytest.mark.parametrize("kind", ["facilities", "laboratories"])
def test_filtered_dictionary_preserves_response_without_printing_query(
    app, capsys, caplog, kind, filter_name
):
    value = f"Filtro Sintetico {filter_name}"
    args = {filter_name: [value]}
    if kind == "facilities":
        module = facilities_services
        row = SimpleNamespace(
            FacilityCode="SYNTHETIC-FACILITY", FacilityNationalCode="SYNTHETIC-NATIONAL",
            FacilityType="H", Description=SENSITIVE_FACILITY,
            ProvinceName="Provincia Sintetica", DistrictName="Distrito Sintetico",
            Latitude=-25.0, Longitude=32.0, HFStatus=1,
        )
        expected = [{
            "FacilityCode": "SYNTHETIC-FACILITY", "FacilityNationalCode": "SYNTHETIC-NATIONAL",
            "FacilityType": "H", "FacilityName": SENSITIVE_FACILITY,
            "ProvinceName": "Provincia Sintetica", "DistrictName": "Distrito Sintetico",
            "Latitude": -25.0, "Longitude": 32.0, "HFStatus": 1,
        }]
    else:
        module = laboratories_services
        row = SimpleNamespace(
            LabCode="SYNTHETIC-LAB", LabName="Laboratorio Sintetico",
            ProvinceName="Provincia Sintetica", DistrictName="Distrito Sintetico",
        )
        expected = [{
            "LabCode": "SYNTHETIC-LAB", "LabName": "Laboratorio Sintetico",
            "ProvinceName": "Provincia Sintetica", "DistrictName": "Distrito Sintetico",
        }]

    with app.app_context(), captured_queries([[row]]) as queries:
        result = getattr(module, f"get_{kind}_by_{filter_name}")(args)
        assert len(queries) == 1
        assert value in to_sql(queries[0])

    assert result == expected
    assert capsys.readouterr() == ("", "")
    assert not caplog.records
