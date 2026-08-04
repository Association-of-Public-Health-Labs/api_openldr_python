/*
    Read-only deployment verification for the materialized TBCultura dataset.

    The result sets contain metadata and aggregate counts only. They never
    return RequestID values, patient values, clinical text, or Agent command
    text.

    Compatibility:
      SQL Server 2014 / database compatibility level 120.
*/

USE [TBData];
GO

SET NOCOUNT ON;

/* 1. Server and database compatibility. */
SELECT
    CAST(SERVERPROPERTY('Edition') AS nvarchar(128)) AS [Edition],
    CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128)) AS [ProductVersion],
    DB_NAME() AS [DatabaseName],
    [compatibility_level] AS [CompatibilityLevel]
FROM [sys].[databases]
WHERE [name] = DB_NAME();

/* 2. Required objects and the deliberately absent custom routine. */
SELECT
    N'OpenLDRData.dbo.viewTB_Cultura' AS [ObjectName],
    CASE
        WHEN OBJECT_ID(N'[OpenLDRData].[dbo].[viewTB_Cultura]', N'V') IS NULL
            THEN 'MISSING'
        ELSE 'PRESENT'
    END AS [DeploymentStatus]
UNION ALL
SELECT
    N'TBData.dbo.TBCultura',
    CASE
        WHEN OBJECT_ID(N'[dbo].[TBCultura]', N'U') IS NULL
            THEN 'MISSING'
        ELSE 'PRESENT'
    END
UNION ALL
SELECT
    N'TBData.dbo.TBCulturaSyncRun',
    CASE
        WHEN OBJECT_ID(N'[dbo].[TBCulturaSyncRun]', N'U') IS NULL
            THEN 'MISSING'
        ELSE 'PRESENT'
    END
UNION ALL
SELECT
    N'TBData.dbo.usp_SyncTBCultura',
    CASE
        WHEN OBJECT_ID(N'[dbo].[usp_SyncTBCultura]', N'P') IS NULL
            THEN 'ABSENT_AS_REQUIRED'
        ELSE 'UNEXPECTEDLY_PRESENT'
    END;

/* 3. Source/target column contract. */
SELECT
    (
        SELECT COUNT(*)
        FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS]
        WHERE [TABLE_SCHEMA] = 'dbo'
          AND [TABLE_NAME] = 'viewTB_Cultura'
    ) AS [SourceViewColumnCount],
    (
        SELECT COUNT(*)
        FROM [TBData].[INFORMATION_SCHEMA].[COLUMNS]
        WHERE [TABLE_SCHEMA] = 'dbo'
          AND [TABLE_NAME] = 'TBCultura'
    ) AS [TargetTableColumnCount],
    CAST(130 AS int) AS [ExpectedSourceViewColumnCount],
    CAST(137 AS int) AS [ExpectedTargetTableColumnCount];

SELECT
    source_column.[ORDINAL_POSITION] AS [SourceOrdinal],
    source_column.[COLUMN_NAME] AS [ColumnName],
    source_column.[DATA_TYPE] AS [SourceDataType],
    target_column.[DATA_TYPE] AS [TargetDataType],
    source_column.[CHARACTER_MAXIMUM_LENGTH] AS [SourceMaxLength],
    target_column.[CHARACTER_MAXIMUM_LENGTH] AS [TargetMaxLength],
    CASE
        WHEN target_column.[COLUMN_NAME] IS NULL THEN 'MISSING_FROM_TARGET'
        WHEN source_column.[DATA_TYPE] COLLATE DATABASE_DEFAULT
             <> target_column.[DATA_TYPE] COLLATE DATABASE_DEFAULT
            THEN 'TYPE_MISMATCH'
        WHEN ISNULL(source_column.[CHARACTER_MAXIMUM_LENGTH], -2147483648)
             <> ISNULL(target_column.[CHARACTER_MAXIMUM_LENGTH], -2147483648)
            THEN 'LENGTH_MISMATCH'
        WHEN ISNULL(source_column.[NUMERIC_PRECISION], 0)
             <> ISNULL(target_column.[NUMERIC_PRECISION], 0)
            THEN 'PRECISION_MISMATCH'
        WHEN ISNULL(source_column.[NUMERIC_SCALE], 0)
             <> ISNULL(target_column.[NUMERIC_SCALE], 0)
            THEN 'SCALE_MISMATCH'
        ELSE 'ALIGNED'
    END AS [AlignmentStatus]
FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS] AS source_column
LEFT JOIN [TBData].[INFORMATION_SCHEMA].[COLUMNS] AS target_column
    ON target_column.[TABLE_SCHEMA] = 'dbo'
   AND target_column.[TABLE_NAME] = 'TBCultura'
   AND target_column.[COLUMN_NAME] COLLATE DATABASE_DEFAULT
       = source_column.[COLUMN_NAME] COLLATE DATABASE_DEFAULT
WHERE source_column.[TABLE_SCHEMA] = 'dbo'
  AND source_column.[TABLE_NAME] = 'viewTB_Cultura'
  AND
  (
      target_column.[COLUMN_NAME] IS NULL
      OR source_column.[DATA_TYPE] COLLATE DATABASE_DEFAULT
         <> target_column.[DATA_TYPE] COLLATE DATABASE_DEFAULT
      OR ISNULL(source_column.[CHARACTER_MAXIMUM_LENGTH], -2147483648)
         <> ISNULL(target_column.[CHARACTER_MAXIMUM_LENGTH], -2147483648)
      OR ISNULL(source_column.[NUMERIC_PRECISION], 0)
         <> ISNULL(target_column.[NUMERIC_PRECISION], 0)
      OR ISNULL(source_column.[NUMERIC_SCALE], 0)
         <> ISNULL(target_column.[NUMERIC_SCALE], 0)
  )
ORDER BY source_column.[ORDINAL_POSITION];

/* 4. Target index metadata. */
IF OBJECT_ID(N'[dbo].[TBCultura]', N'U') IS NOT NULL
BEGIN
    SELECT
        index_definition.[name] AS [IndexName],
        index_definition.[type_desc] AS [IndexType],
        index_definition.[is_unique] AS [IsUnique],
        index_definition.[is_primary_key] AS [IsPrimaryKey],
        index_definition.[has_filter] AS [HasFilter],
        STUFF
        (
            (
                SELECT
                    N',' + QUOTENAME
                    (
                        COL_NAME
                        (
                            index_column.[object_id],
                            index_column.[column_id]
                        )
                    )
                FROM [sys].[index_columns] AS index_column
                WHERE index_column.[object_id] = index_definition.[object_id]
                  AND index_column.[index_id] = index_definition.[index_id]
                  AND index_column.[key_ordinal] > 0
                ORDER BY index_column.[key_ordinal]
                FOR XML PATH(''), TYPE
            ).value('.', 'nvarchar(max)'),
            1,
            1,
            N''
        ) AS [KeyColumns]
    FROM [sys].[indexes] AS index_definition
    WHERE index_definition.[object_id] = OBJECT_ID(N'[dbo].[TBCultura]')
      AND index_definition.[index_id] > 0
      AND index_definition.[is_hypothetical] = 0
    ORDER BY
        index_definition.[is_primary_key] DESC,
        index_definition.[is_unique] DESC,
        index_definition.[name];
END;

/* 5. Aggregate target key quality; no key value is returned. */
IF OBJECT_ID(N'[dbo].[TBCultura]', N'U') IS NOT NULL
BEGIN
    EXEC [sys].[sp_executesql] N'
        SELECT
            COUNT_BIG(*) AS [TargetRows],
            SUM
            (
                CASE
                    WHEN [RequestID] IS NULL THEN CONVERT(bigint, 1)
                    ELSE CONVERT(bigint, 0)
                END
            ) AS [NullRequestIDRows],
            (
                SELECT COUNT_BIG(*)
                FROM
                (
                    SELECT [RequestID]
                    FROM [dbo].[TBCultura]
                    GROUP BY [RequestID]
                    HAVING COUNT_BIG(*) > 1
                ) AS duplicate_group
            ) AS [DuplicateRequestIDGroups]
        FROM [dbo].[TBCultura];';
END;

/* 6. Aggregate key reconciliation; view and target keys remain undisclosed. */
IF OBJECT_ID(N'[dbo].[TBCultura]', N'U') IS NOT NULL
   AND OBJECT_ID(N'[OpenLDRData].[dbo].[viewTB_Cultura]', N'V') IS NOT NULL
BEGIN
    EXEC [sys].[sp_executesql] N'
        SELECT
            SUM
            (
                CASE
                    WHEN source_key.[RequestID] IS NOT NULL
                        THEN CONVERT(bigint, 1)
                    ELSE CONVERT(bigint, 0)
                END
            ) AS [SourceRows],
            SUM
            (
                CASE
                    WHEN target_key.[RequestID] IS NOT NULL
                        THEN CONVERT(bigint, 1)
                    ELSE CONVERT(bigint, 0)
                END
            ) AS [TargetRows],
            SUM
            (
                CASE
                    WHEN source_key.[RequestID] IS NOT NULL
                     AND target_key.[RequestID] IS NULL
                        THEN CONVERT(bigint, 1)
                    ELSE CONVERT(bigint, 0)
                END
            ) AS [MissingFromTarget],
            SUM
            (
                CASE
                    WHEN source_key.[RequestID] IS NULL
                     AND target_key.[RequestID] IS NOT NULL
                        THEN CONVERT(bigint, 1)
                    ELSE CONVERT(bigint, 0)
                END
            ) AS [MissingFromSource]
        FROM
        (
            SELECT [RequestID]
            FROM [OpenLDRData].[dbo].[viewTB_Cultura]
        ) AS source_key
        FULL OUTER JOIN [dbo].[TBCultura] AS target_key
            ON target_key.[RequestID] COLLATE DATABASE_DEFAULT
               = source_key.[RequestID] COLLATE DATABASE_DEFAULT;';
END;

/* 7. Latest sanitized synchronization metrics. */
IF OBJECT_ID(N'[dbo].[TBCulturaSyncRun]', N'U') IS NOT NULL
BEGIN
    EXEC [sys].[sp_executesql] N'
        SELECT TOP (20)
            [RunID],
            [StartedAt],
            [CompletedAt],
            [Status],
            [SourceRows],
            [TargetRowsBefore],
            [InsertedRows],
            [UpdatedRows],
            [DeletedRows],
            [TargetRowsAfter],
            [DurationMs],
            [ErrorNumber],
            [ErrorMessage]
        FROM [dbo].[TBCulturaSyncRun]
        ORDER BY [RunID] DESC;';
END;

/*
    8. Agent metadata and inline-command contract. Command text is inspected
       inside SQL Server but is never returned.
*/
SELECT
    job.[name] AS [JobName],
    job.[enabled] AS [JobEnabled],
    job_step.[step_name] AS [StepName],
    job_step.[database_name] AS [StepDatabase],
    job_step.[retry_attempts] AS [RetryAttempts],
    job_step.[retry_interval] AS [RetryIntervalMinutes],
    LEN(job_step.[command]) AS [StepCommandCharacters],
    DATALENGTH(REPLACE(job_step.[command], NCHAR(13), N''))
        AS [StepCommandNormalizedBytes],
    CASE
        WHEN job_step.[command] IS NULL THEN 'MISSING_STEP'
        WHEN DATALENGTH(REPLACE(job_step.[command], NCHAR(13), N'')) <> 32536
            THEN 'INLINE_COMMAND_LENGTH_MISMATCH'
        WHEN job_step.[command] LIKE N'%usp[_]SyncTBCultura%'
            THEN 'CUSTOM_ROUTINE_REFERENCE_FOUND'
        WHEN job_step.[command] NOT LIKE N'%sp[_]getapplock%'
          OR job_step.[command] NOT LIKE N'%#TBCulturaStage%'
          OR job_step.[command] NOT LIKE N'%EXCEPT%'
          OR job_step.[command] NOT LIKE N'%SET XACT_ABORT ON%'
          OR job_step.[command] NOT LIKE N'%@MaximumDeletePercent%'
          OR job_step.[command] NOT LIKE N'%@AllowLargeDelete%'
          OR job_step.[command] NOT LIKE N'%@DeleteMissing%'
            THEN 'INLINE_CONTRACT_INCOMPLETE'
        ELSE 'INLINE_CONTRACT_PRESENT'
    END AS [InlineCommandStatus],
    schedule.[name] AS [ScheduleName],
    schedule.[enabled] AS [ScheduleEnabled],
    schedule.[freq_type] AS [FrequencyType],
    schedule.[freq_subday_type] AS [SubdayFrequencyType],
    schedule.[freq_subday_interval] AS [SubdayInterval],
    schedule.[active_start_time] AS [ActiveStartTime]
FROM [msdb].[dbo].[sysjobs] AS job
LEFT JOIN [msdb].[dbo].[sysjobsteps] AS job_step
    ON job_step.[job_id] = job.[job_id]
   AND job_step.[step_name] = N'Synchronize TBCultura'
LEFT JOIN [msdb].[dbo].[sysjobschedules] AS job_schedule
    ON job_schedule.[job_id] = job.[job_id]
LEFT JOIN [msdb].[dbo].[sysschedules] AS schedule
    ON schedule.[schedule_id] = job_schedule.[schedule_id]
WHERE job.[name] = N'TB - Sync TBCultura';

/* 9. Stale RUNNING audits can indicate a killed Agent session. */
IF OBJECT_ID(N'[dbo].[TBCulturaSyncRun]', N'U') IS NOT NULL
BEGIN
    EXEC [sys].[sp_executesql] N'
        SELECT COUNT_BIG(*) AS [StaleRunningRuns]
        FROM [dbo].[TBCulturaSyncRun]
        WHERE [Status] = ''RUNNING''
          AND [StartedAt] < DATEADD(hour, -8, SYSUTCDATETIME());';
END;

/* 10. Latest Agent outcomes; history messages are intentionally excluded. */
SELECT TOP (10)
    history.[run_status] AS [RunStatus],
    history.[run_date] AS [RunDate],
    history.[run_time] AS [RunTime],
    history.[run_duration] AS [RunDuration]
FROM [msdb].[dbo].[sysjobs] AS job
INNER JOIN [msdb].[dbo].[sysjobhistory] AS history
    ON history.[job_id] = job.[job_id]
   AND history.[step_id] = 0
WHERE job.[name] = N'TB - Sync TBCultura'
ORDER BY history.[instance_id] DESC;
GO
