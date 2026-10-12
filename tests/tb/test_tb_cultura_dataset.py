"""Contract tests for the materialized TB culture dataset."""

import re
from pathlib import Path

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.mssql import TINYINT

from tb.cultura.models.tb_cultura_model import TBCultura


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql" / "tb" / "cultura"

SOURCE_COLUMNS = (
    "RequestID",
    "EncryptedPatientID",
    "PatientLocation",
    "PatientNationalID",
    "PatientSurname",
    "PatientFirstName",
    "PatientDOB",
    "PatientDOBType",
    "PatientHealthcareNo",
    "PatientHomePhone",
    "PatientRegisteredDate",
    "PatientUUID",
    "AgeInYears",
    "AgeInDays",
    "HL7SexCode",
    "HL7EthnicGroupCode",
    "Deceased",
    "Newborn",
    "HL7PatientClassCode",
    "SpecimenDateTime",
    "LIMSPreReg_RegistrationDateTime",
    "LIMSPreReg_ReceivedDateTime",
    "LIMSPreReg_RegistrationFacilityCode",
    "RegisteredDateTime",
    "ReceivedDateTime",
    "AnalysisDateTime",
    "AuthorisedDateTime",
    "AdmitAttendDateTime",
    "FirstPrinted",
    "LIMSRejectionCode",
    "LIMSRejectionDesc",
    "SolidCultureResult",
    "SolidCultureResultDate",
    "LiquidCultureResult",
    "LiquidCultureResultDate",
    "InterpretedLiquidCultureResult",
    "InterpretedSolidCultureResult",
    "InterpretedCultureResultDate",
    "TBIDResult",
    "TBIDResultDate",
    "LPAPanelCode",
    "LPAIsoniazidResult",
    "LPAComplexMTBResult",
    "LPARifampicinResult",
    "LPAResultDate",
    "LPA2PanelCode",
    "LPA2FluoroquinoloneResult",
    "LPA2KACResult",
    "LPA2KACVResult",
    "LPA2KCVResult",
    "LPA2ComplexMTBResult",
    "LPA2LowLevelKanamycinResult",
    "LPA2ResultDate",
    "LPACMResult",
    "LPACMResultDate",
    "TSAPanelCode",
    "TSAEthambutolResult",
    "TSAIsoniazidResult",
    "TSAPyrazinamideResult",
    "TSARifampicinResult",
    "TSAStreptomycinResult",
    "TSAResultDate",
    "TSA2PanelCode",
    "TSA2AmikacinResult",
    "TSA2BedaquilineResult",
    "TSA2ClofazimineResult",
    "TSA2CapreomycinResult",
    "TSA2EthionamideResult",
    "TSA2KanamycinResult",
    "TSA2LevofloxacinResult",
    "TSA2LinezolidResult",
    "TSA2MoxifloxacinResult",
    "TSA2OfloxacinResult",
    "TSA2ProthionamideResult",
    "TSA2ResultDate",
    "FinalLJCultureResult",
    "FinalLJResultDate",
    "FinalMGITCultureResult",
    "FinalMGITResultDate",
    "DateTimeStamp",
    "Versionstamp",
    "LIMSDateTimeStamp",
    "LIMSVersionstamp",
    "LOINCPanelCode",
    "HL7PriorityCode",
    "CollectionVolume",
    "LIMSPointOfCareDesc",
    "RequestTypeCode",
    "ICD10ClinicalInfoCodes",
    "ClinicalInfo",
    "HL7SpecimenSourceCode",
    "LIMSSpecimenSourceCode",
    "LIMSSpecimenSourceDesc",
    "HL7SpecimenSiteCode",
    "LIMSSpecimenSiteCode",
    "LIMSSpecimenSiteDesc",
    "WorkUnits",
    "CostUnits",
    "HL7SectionCode",
    "HL7ResultStatusCode",
    "RegisteredBy",
    "TestedBy",
    "AuthorisedBy",
    "OrderingNotes",
    "AttendingDoctor",
    "ReferringRequestID",
    "Therapy",
    "LIMSAnalyzerCode",
    "TargetTimeDays",
    "TargetTimeMins",
    "Repeated",
    "LIMSVendorCode",
    "TestingLabRequestID",
    "LIMSFacilityCode",
    "LIMSFacilityName",
    "LIMSProvinceName",
    "LIMSDistrictName",
    "RequestingFacilityCode",
    "RequestingFacilityNationalCode",
    "RequestingFacilityName",
    "RequestingProvinceName",
    "RequestingDistrictName",
    "ReceivingFacilityCode",
    "ReceivingFacilityName",
    "ReceivingProvinceName",
    "ReceivingDistrictName",
    "TestingFacilityCode",
    "TestingFacilityName",
    "TestingProvinceName",
    "TestingDistrictName",
)

OPERATIONAL_COLUMNS = (
    "EPTS",
    "EPTS_DATETIME",
    "SMS_NOTIFICATION",
    "SMS_NOTIFICATION_DATETIME",
    "CreatedAt",
    "UpdatedAt",
)


def _read_sql(name):
    return (SQL_DIR / name).read_text(encoding="utf-8")


def _all_sql():
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(SQL_DIR.glob("*.sql"))
    )


def _main_table_column_names():
    ddl = _read_sql("001_create_tbcultura_table.sql")
    start = ddl.index("CREATE TABLE [dbo].[TBCultura]")
    end = ddl.index("CONSTRAINT [PK_TBCultura]", start)
    table_definition = ddl[start:end]
    return tuple(
        re.findall(
            r"(?im)^\s*\[([A-Z0-9_]+)\]\s+\[[A-Z0-9]+\]",
            table_definition,
        )
    )


def _embedded_job_command_chunks():
    sql = _read_sql("002_create_tbcultura_sql_agent_job.sql")
    marker = "SET @Command += N'"
    chunks = []
    position = 0

    while True:
        start = sql.find(marker, position)
        if start == -1:
            break

        cursor = start + len(marker)
        decoded = []
        while cursor < len(sql):
            if sql[cursor] != "'":
                decoded.append(sql[cursor])
                cursor += 1
                continue

            if cursor + 1 < len(sql) and sql[cursor + 1] == "'":
                decoded.append("'")
                cursor += 2
                continue

            break
        else:
            raise AssertionError("Unterminated @Command Unicode literal")

        chunks.append("".join(decoded))
        position = cursor + 1

    return tuple(chunks)


def test_model_uses_tb_bind_and_target_table():
    assert TBCultura.__bind_key__ == "tb"
    assert TBCultura.__tablename__ == "TBCultura"


def test_model_matches_the_complete_source_contract():
    columns = TBCultura.__table__.columns

    assert len(SOURCE_COLUMNS) == 130
    assert tuple(column.name for column in columns)[1:131] == SOURCE_COLUMNS
    assert tuple(column.name for column in columns)[131:] == OPERATIONAL_COLUMNS
    assert len(columns) == 137


def test_model_key_contract():
    columns = TBCultura.__table__.columns

    assert isinstance(columns["ID"].type, BigInteger)
    assert columns["ID"].primary_key
    assert columns["ID"].autoincrement is True
    assert isinstance(columns["RequestID"].type, String)
    assert columns["RequestID"].type.length == 26
    assert columns["RequestID"].nullable is False
    assert columns["RequestID"].unique is True


def test_model_maps_representative_source_types():
    columns = TBCultura.__table__.columns

    assert isinstance(columns["PatientDOB"].type, DateTime)
    assert isinstance(columns["AgeInYears"].type, Integer)
    assert isinstance(columns["Deceased"].type, Boolean)
    assert isinstance(columns["CollectionVolume"].type, Float)
    assert isinstance(columns["Repeated"].type, TINYINT)
    assert columns["ClinicalInfo"].type.length == 250
    assert columns["TestingDistrictName"].type.length == 50


def test_model_includes_confirmed_sensitive_fields():
    columns = TBCultura.__table__.columns
    sensitive = {
        "PatientNationalID",
        "PatientSurname",
        "PatientFirstName",
        "PatientDOB",
        "PatientHealthcareNo",
        "PatientHomePhone",
        "PatientUUID",
        "ClinicalInfo",
        "OrderingNotes",
        "Therapy",
    }

    assert sensitive.issubset(columns.keys())


def test_sql_assets_exist_and_target_expected_objects():
    expected = {
        "001_create_tbcultura_table.sql",
        "002_create_tbcultura_sql_agent_job.sql",
        "003_verify_tbcultura_deployment.sql",
    }

    assert {path.name for path in SQL_DIR.glob("*.sql")} == expected
    assert "[dbo].[TBCultura]" in _read_sql("001_create_tbcultura_table.sql")
    assert "TB - Sync TBCultura" in _read_sql(
        "002_create_tbcultura_sql_agent_job.sql"
    )


def test_ddl_contains_every_source_and_operational_column():
    ddl = _read_sql("001_create_tbcultura_table.sql")

    for column_name in SOURCE_COLUMNS + OPERATIONAL_COLUMNS:
        assert f"[{column_name}]" in ddl


def test_ddl_preserves_exact_source_and_operational_column_order():
    columns = _main_table_column_names()

    assert columns[0] == "ID"
    assert columns[1:131] == SOURCE_COLUMNS
    assert columns[131:] == OPERATIONAL_COLUMNS
    assert len(columns) == 137


def test_no_custom_sync_stored_procedure_is_created_altered_or_called():
    sql = _all_sql().upper()

    procedure_definition = re.compile(
        r"\b(?:CREATE(?:\s+OR\s+ALTER)?|ALTER)\s+PROCEDURE\s+"
        r"(?:\[?[A-Z0-9_]+\]?\.){0,2}\[?USP_SYNCTBCULTURA\]?"
    )
    procedure_call = re.compile(
        r"\bEXEC(?:UTE)?\s+"
        r"(?:\[?[A-Z0-9_]+\]?\.){0,2}\[?USP_SYNCTBCULTURA\]?"
    )

    assert procedure_definition.search(sql) is None
    assert procedure_call.search(sql) is None
    assert not any("procedure" in path.name.lower() for path in SQL_DIR.glob("*.sql"))


def test_agent_job_embeds_full_guarded_sync_command():
    job_sql = _read_sql("002_create_tbcultura_sql_agent_job.sql").upper()

    required = (
        "SP_ADD_JOBSTEP",
        "@COMMAND",
        "SP_GETAPPLOCK",
        "SET XACT_ABORT ON",
        "#TBCULTURASTAGE",
        "EXCEPT",
        "@MAXIMUMDELETEPERCENT",
        "@ALLOWLARGEDELETE",
        "@DELETEMISSING",
        "@SOURCEROWS = 0",
        "WHERE [REQUESTID] IS NULL",
        "HAVING COUNT_BIG(*) > 1",
        "@DELETEPERCENT > @MAXIMUMDELETEPERCENT",
        "DATALENGTH(REPLACE(@COMMAND, NCHAR(13), N'')) <> 32536",
        "[OPENLDRDATA].[DBO].[VIEWTB_CULTURA]",
        "[DBO].[TBCULTURA]",
        "[DBO].[TBCULTURASYNCRUN]",
    )
    assert all(token in job_sql for token in required)
    assert re.search(r"(?m)^\s*MERGE\b", job_sql) is None

    forbidden = (
        "CREATE OR ALTER",
        "DROP TABLE IF EXISTS",
        "FOR JSON",
        "STRING_AGG",
        "CONCAT_WS",
    )
    assert not any(token in job_sql for token in forbidden)


def test_embedded_job_command_round_trips_without_truncation():
    chunks = _embedded_job_command_chunks()
    command = "".join(chunks)
    normalized_command = command.replace("\r", "")

    assert len(chunks) == 7
    assert max(map(len, chunks)) <= 3000
    assert len(command) == 16268
    assert len(normalized_command.encode("utf-16le")) == 32536
    assert command == command.strip()
    assert not any(line.strip().upper() == "GO" for line in command.splitlines())
    assert "PROCEDURE" not in command.upper()
    assert "USP_SYNCTBCULTURA" not in command.upper()
    assert "@SOURCECOLUMNCOUNT <> 130 OR @TARGETCOLUMNCOUNT <> 137" in command.upper()


def test_embedded_job_normalizes_cross_database_metadata_collations():
    command = "".join(_embedded_job_command_chunks()).upper()

    column_name_join = re.compile(
        r"TARGET_COLUMN\.\[COLUMN_NAME\]\s+COLLATE\s+DATABASE_DEFAULT\s*"
        r"=\s*SOURCE_COLUMN\.\[COLUMN_NAME\]\s+COLLATE\s+DATABASE_DEFAULT"
    )
    data_type_comparison = re.compile(
        r"SOURCE_COLUMN\.\[DATA_TYPE\]\s+COLLATE\s+DATABASE_DEFAULT\s*"
        r"<>\s*TARGET_COLUMN\.\[DATA_TYPE\]\s+COLLATE\s+DATABASE_DEFAULT"
    )

    assert column_name_join.search(command)
    assert data_type_comparison.search(command)
    assert (
        "[REQUESTID] VARCHAR(26) COLLATE SQL_LATIN1_GENERAL_CP1_CI_AS NOT NULL"
        in command
    )


def test_embedded_job_cleans_stale_temp_tables_before_recreating_them():
    command = "".join(_embedded_job_command_chunks()).upper()

    stage_object_check = "OBJECT_ID(N'TEMPDB..#TBCULTURASTAGE', N'U')"
    changed_object_check = "OBJECT_ID(N'TEMPDB..#CHANGEDREQUESTID', N'U')"

    assert stage_object_check in command
    assert changed_object_check in command
    assert "DROP TABLE #TBCULTURASTAGE" in command
    assert "DROP TABLE #CHANGEDREQUESTID" in command
    assert command.index(stage_object_check) < command.index("INTO #TBCULTURASTAGE")
    assert command.index(changed_object_check) < command.index(
        "CREATE TABLE #CHANGEDREQUESTID"
    )


def test_agent_job_is_staggered_every_four_hours():
    job_sql = _read_sql("002_create_tbcultura_sql_agent_job.sql").upper()

    assert "TB - SYNC TBCULTURA" in job_sql
    assert "@FREQ_SUBDAY_TYPE = 8" in job_sql
    assert "@FREQ_SUBDAY_INTERVAL = 4" in job_sql
    assert "@ACTIVE_START_TIME = 003000" in job_sql
    assert "@RETRY_ATTEMPTS = 2" in job_sql
    assert "@RETRY_INTERVAL = 10" in job_sql


def test_verification_script_is_read_only_and_does_not_select_patient_values():
    verification_sql = _read_sql("003_verify_tbcultura_deployment.sql").upper()

    persistent_write = re.compile(
        r"(?m)^\s*(?:"
        r"INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE|"
        r"CREATE\s+(?:TABLE|INDEX|PROCEDURE)|"
        r"ALTER\s+(?:TABLE|INDEX|PROCEDURE)|"
        r"DROP\s+(?:TABLE|INDEX|PROCEDURE)|TRUNCATE\s+TABLE"
        r")\b"
    )

    assert persistent_write.search(verification_sql) is None
    assert "SP_START_JOB" not in verification_sql
    assert "PATIENTSURNAME" not in verification_sql
    assert "PATIENTFIRSTNAME" not in verification_sql
    assert "PATIENTNATIONALID" not in verification_sql
    assert "PATIENTHOMEPHONE" not in verification_sql
    assert "INLINE_COMMAND_LENGTH_MISMATCH" in verification_sql
    assert "STALERUNNINGRUNS" in verification_sql


def test_verification_normalizes_cross_database_text_collations():
    verification_sql = _read_sql("003_verify_tbcultura_deployment.sql").upper()

    column_name_join = re.compile(
        r"TARGET_COLUMN\.\[COLUMN_NAME\]\s+COLLATE\s+DATABASE_DEFAULT\s*"
        r"=\s*SOURCE_COLUMN\.\[COLUMN_NAME\]\s+COLLATE\s+DATABASE_DEFAULT"
    )
    data_type_comparison = re.compile(
        r"SOURCE_COLUMN\.\[DATA_TYPE\]\s+COLLATE\s+DATABASE_DEFAULT\s*"
        r"<>\s*TARGET_COLUMN\.\[DATA_TYPE\]\s+COLLATE\s+DATABASE_DEFAULT"
    )
    request_id_join = re.compile(
        r"TARGET_KEY\.\[REQUESTID\]\s+COLLATE\s+DATABASE_DEFAULT\s*"
        r"=\s*SOURCE_KEY\.\[REQUESTID\]\s+COLLATE\s+DATABASE_DEFAULT"
    )

    assert column_name_join.search(verification_sql)
    assert len(data_type_comparison.findall(verification_sql)) == 2
    assert request_id_join.search(verification_sql)
