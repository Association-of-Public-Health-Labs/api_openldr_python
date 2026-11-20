-- Usage and audit tables for the admin dashboard (SQL Server 2014 compatible).
-- Run against the "users" database. Safe to re-run: every object is created only when missing.

IF OBJECT_ID(N'dbo.openldr_usage_events', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.openldr_usage_events (
        id          BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_openldr_usage_events PRIMARY KEY,
        user_id     NVARCHAR(250) NOT NULL,
        dashboard   NVARCHAR(20)  NOT NULL,
        page        NVARCHAR(250) NOT NULL,
        occurred_at DATETIME      NOT NULL CONSTRAINT DF_openldr_usage_events_occurred_at DEFAULT (GETUTCDATE())
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_openldr_usage_events_occurred_dashboard' AND object_id = OBJECT_ID(N'dbo.openldr_usage_events'))
    CREATE INDEX IX_openldr_usage_events_occurred_dashboard ON dbo.openldr_usage_events (occurred_at, dashboard);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_openldr_usage_events_user_occurred' AND object_id = OBJECT_ID(N'dbo.openldr_usage_events'))
    CREATE INDEX IX_openldr_usage_events_user_occurred ON dbo.openldr_usage_events (user_id, occurred_at);
GO

IF OBJECT_ID(N'dbo.openldr_patient_access_log', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.openldr_patient_access_log (
        id          BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_openldr_patient_access_log PRIMARY KEY,
        user_id     NVARCHAR(250) NOT NULL,
        dashboard   NVARCHAR(20)  NOT NULL,
        endpoint    NVARCHAR(250) NOT NULL,
        row_count   INT           NOT NULL,
        occurred_at DATETIME      NOT NULL CONSTRAINT DF_openldr_patient_access_log_occurred_at DEFAULT (GETUTCDATE())
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_openldr_patient_access_log_occurred_dashboard' AND object_id = OBJECT_ID(N'dbo.openldr_patient_access_log'))
    CREATE INDEX IX_openldr_patient_access_log_occurred_dashboard ON dbo.openldr_patient_access_log (occurred_at, dashboard);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_openldr_patient_access_log_user_occurred' AND object_id = OBJECT_ID(N'dbo.openldr_patient_access_log'))
    CREATE INDEX IX_openldr_patient_access_log_user_occurred ON dbo.openldr_patient_access_log (user_id, occurred_at);
GO

IF OBJECT_ID(N'dbo.openldr_admin_audit_log', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.openldr_admin_audit_log (
        id             BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_openldr_admin_audit_log PRIMARY KEY,
        actor_user_id  NVARCHAR(250) NOT NULL,
        action         NVARCHAR(50)  NOT NULL,
        target_user_id NVARCHAR(250) NULL,
        changes        NVARCHAR(MAX) NULL, -- JSON text; SQL Server 2014 has no JSON type
        occurred_at    DATETIME      NOT NULL CONSTRAINT DF_openldr_admin_audit_log_occurred_at DEFAULT (GETUTCDATE())
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_openldr_admin_audit_log_actor_occurred' AND object_id = OBJECT_ID(N'dbo.openldr_admin_audit_log'))
    CREATE INDEX IX_openldr_admin_audit_log_actor_occurred ON dbo.openldr_admin_audit_log (actor_user_id, occurred_at);
GO
