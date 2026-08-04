/*
    Materialized TB culture dataset.

    Source: [OpenLDRData].[dbo].[viewTB_Cultura]
    Target: [TBData].[dbo].[TBCultura]
    Target platform: SQL Server 2014, database compatibility level 120.

    WARNING: This table contains patient-identifying and clinical data (PII/PHI).
    Restrict SELECT permissions to the same or a narrower audience than the source
    view. This script creates schema objects only; it does not load any data.
*/

USE [TBData];
GO

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO
SET ANSI_PADDING ON;
GO
SET ANSI_WARNINGS ON;
GO
SET ARITHABORT ON;
GO
SET CONCAT_NULL_YIELDS_NULL ON;
GO
SET NUMERIC_ROUNDABORT OFF;
GO

IF OBJECT_ID(N'[dbo].[TBCultura]', N'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[TBCultura]
    (
        [ID] [bigint] IDENTITY(1,1) NOT NULL,

        -- Source columns, in the exact ordinal order of viewTB_Cultura.
        [RequestID] [varchar](26) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
        [EncryptedPatientID] [varchar](64) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [PatientLocation] [varchar](5) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [PatientNationalID] [varchar](26) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [PatientSurname] [varchar](31) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [PatientFirstName] [varchar](31) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [PatientDOB] [datetime] NULL,
        [PatientDOBType] [varchar](25) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [PatientHealthcareNo] [varchar](25) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [PatientHomePhone] [varchar](20) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [PatientRegisteredDate] [datetime] NULL,
        [PatientUUID] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [AgeInYears] [int] NULL,
        [AgeInDays] [int] NULL,
        [HL7SexCode] [char](1) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [HL7EthnicGroupCode] [char](3) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [Deceased] [bit] NULL,
        [Newborn] [bit] NULL,
        [HL7PatientClassCode] [char](1) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [SpecimenDateTime] [datetime] NULL,
        [LIMSPreReg_RegistrationDateTime] [datetime] NULL,
        [LIMSPreReg_ReceivedDateTime] [datetime] NULL,
        [LIMSPreReg_RegistrationFacilityCode] [varchar](15) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [RegisteredDateTime] [datetime] NULL,
        [ReceivedDateTime] [datetime] NULL,
        [AnalysisDateTime] [datetime] NULL,
        [AuthorisedDateTime] [datetime] NULL,
        [AdmitAttendDateTime] [datetime] NULL,
        [FirstPrinted] [datetime] NULL,
        [LIMSRejectionCode] [varchar](10) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSRejectionDesc] [varchar](250) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [SolidCultureResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [SolidCultureResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LiquidCultureResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LiquidCultureResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [InterpretedLiquidCultureResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [InterpretedSolidCultureResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [InterpretedCultureResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TBIDResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TBIDResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPAPanelCode] [varchar](3) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPAIsoniazidResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPAComplexMTBResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPARifampicinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPAResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPA2PanelCode] [varchar](4) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPA2FluoroquinoloneResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPA2KACResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPA2KACVResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPA2KCVResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPA2ComplexMTBResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPA2LowLevelKanamycinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPA2ResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPACMResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LPACMResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSAPanelCode] [varchar](3) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSAEthambutolResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSAIsoniazidResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSAPyrazinamideResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSARifampicinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSAStreptomycinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSAResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2PanelCode] [varchar](4) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2AmikacinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2BedaquilineResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2ClofazimineResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2CapreomycinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2EthionamideResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2KanamycinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2LevofloxacinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2LinezolidResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2MoxifloxacinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2OfloxacinResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2ProthionamideResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TSA2ResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [FinalLJCultureResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [FinalLJResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [FinalMGITCultureResult] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [FinalMGITResultDate] [varchar](80) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [DateTimeStamp] [datetime] NULL,
        [Versionstamp] [varchar](30) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSDateTimeStamp] [datetime] NULL,
        [LIMSVersionstamp] [varchar](30) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LOINCPanelCode] [varchar](10) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [HL7PriorityCode] [char](1) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [CollectionVolume] [float](53) NULL,
        [LIMSPointOfCareDesc] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [RequestTypeCode] [varchar](3) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [ICD10ClinicalInfoCodes] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [ClinicalInfo] [varchar](250) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [HL7SpecimenSourceCode] [varchar](10) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSSpecimenSourceCode] [varchar](10) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSSpecimenSourceDesc] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [HL7SpecimenSiteCode] [varchar](10) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSSpecimenSiteCode] [varchar](10) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSSpecimenSiteDesc] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [WorkUnits] [float](53) NULL,
        [CostUnits] [float](53) NULL,
        [HL7SectionCode] [varchar](3) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [HL7ResultStatusCode] [char](1) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [RegisteredBy] [varchar](250) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TestedBy] [varchar](250) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [AuthorisedBy] [varchar](250) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [OrderingNotes] [varchar](250) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [AttendingDoctor] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [ReferringRequestID] [varchar](25) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [Therapy] [varchar](250) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSAnalyzerCode] [varchar](10) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TargetTimeDays] [int] NULL,
        [TargetTimeMins] [int] NULL,
        [Repeated] [tinyint] NULL,
        [LIMSVendorCode] [varchar](4) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TestingLabRequestID] [varchar](20) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSFacilityCode] [varchar](15) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSFacilityName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSProvinceName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [LIMSDistrictName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [RequestingFacilityCode] [varchar](15) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [RequestingFacilityNationalCode] [varchar](15) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [RequestingFacilityName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [RequestingProvinceName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [RequestingDistrictName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [ReceivingFacilityCode] [varchar](10) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [ReceivingFacilityName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [ReceivingProvinceName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [ReceivingDistrictName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TestingFacilityCode] [varchar](10) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TestingFacilityName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TestingProvinceName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [TestingDistrictName] [varchar](50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,

        -- Target-owned operational columns; the source synchronization must
        -- preserve notification state when source rows change.
        [EPTS] [varchar](255) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [EPTS_DATETIME] [datetime] NULL,
        [SMS_NOTIFICATION] [varchar](100) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
        [SMS_NOTIFICATION_DATETIME] [datetime] NULL,
        [CreatedAt] [datetime2](3) NOT NULL
            CONSTRAINT [DF_TBCultura_CreatedAt] DEFAULT (SYSUTCDATETIME()),
        [UpdatedAt] [datetime2](3) NOT NULL
            CONSTRAINT [DF_TBCultura_UpdatedAt] DEFAULT (SYSUTCDATETIME()),

        CONSTRAINT [PK_TBCultura]
            PRIMARY KEY CLUSTERED ([ID] ASC)
    );
END;
GO

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE [object_id] = OBJECT_ID(N'[dbo].[TBCultura]', N'U')
      AND [name] = N'UX_TBCultura_RequestID'
)
BEGIN
    CREATE UNIQUE NONCLUSTERED INDEX [UX_TBCultura_RequestID]
        ON [dbo].[TBCultura] ([RequestID] ASC);
END;
GO

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE [object_id] = OBJECT_ID(N'[dbo].[TBCultura]', N'U')
      AND [name] = N'IX_TBCultura_RegisteredDateTime'
)
BEGIN
    CREATE NONCLUSTERED INDEX [IX_TBCultura_RegisteredDateTime]
        ON [dbo].[TBCultura] ([RegisteredDateTime] ASC)
        WHERE [RegisteredDateTime] IS NOT NULL;
END;
GO

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE [object_id] = OBJECT_ID(N'[dbo].[TBCultura]', N'U')
      AND [name] = N'IX_TBCultura_RequestingGeo_RegisteredDateTime'
)
BEGIN
    CREATE NONCLUSTERED INDEX [IX_TBCultura_RequestingGeo_RegisteredDateTime]
        ON [dbo].[TBCultura]
        (
            [RequestingProvinceName] ASC,
            [RequestingDistrictName] ASC,
            [RequestingFacilityCode] ASC,
            [RegisteredDateTime] ASC
        )
        WHERE [RequestingProvinceName] IS NOT NULL
          AND [RequestingDistrictName] IS NOT NULL
          AND [RequestingFacilityCode] IS NOT NULL
          AND [RegisteredDateTime] IS NOT NULL;
END;
GO

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE [object_id] = OBJECT_ID(N'[dbo].[TBCultura]', N'U')
      AND [name] = N'IX_TBCultura_TestingFacility_RegisteredDateTime'
)
BEGIN
    CREATE NONCLUSTERED INDEX [IX_TBCultura_TestingFacility_RegisteredDateTime]
        ON [dbo].[TBCultura]
        (
            [TestingFacilityCode] ASC,
            [RegisteredDateTime] ASC
        )
        WHERE [TestingFacilityCode] IS NOT NULL
          AND [RegisteredDateTime] IS NOT NULL;
END;
GO

IF OBJECT_ID(N'[dbo].[TBCulturaSyncRun]', N'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[TBCulturaSyncRun]
    (
        [RunID] [bigint] IDENTITY(1,1) NOT NULL,
        [StartedAt] [datetime2](3) NOT NULL,
        [CompletedAt] [datetime2](3) NULL,
        [Status] [varchar](20) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
        [SourceRows] [int] NULL,
        [TargetRowsBefore] [int] NULL,
        [InsertedRows] [int] NULL,
        [UpdatedRows] [int] NULL,
        [DeletedRows] [int] NULL,
        [TargetRowsAfter] [int] NULL,
        [DurationMs] [bigint] NULL,
        [ErrorNumber] [int] NULL,
        -- The synchronization procedure must store a sanitized message only:
        -- no SQL text, connection details, credentials, or row values.
        [ErrorMessage] [nvarchar](2048) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,

        CONSTRAINT [PK_TBCulturaSyncRun]
            PRIMARY KEY CLUSTERED ([RunID] ASC),
        CONSTRAINT [CK_TBCulturaSyncRun_Status]
            CHECK ([Status] IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'SKIPPED'))
    );
END;
GO
