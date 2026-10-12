/*
    Creates or updates a SQL Server Agent job whose single T-SQL step contains
    the complete TBCultura reconciliation. No custom database routine is
    created or invoked.

    The step command is assembled as nvarchar(max) chunks smaller than the
    SQL Server 2014 Unicode literal limit. Each embedded quote is escaped.

    Schedule:
      Every four hours at 00:30, 04:30, 08:30, 12:30, 16:30 and 20:30.
*/

USE [msdb];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE
    @JobName sysname = N'TB - Sync TBCultura',
    @JobDescription nvarchar(512) =
        N'Inline full reconciliation from OpenLDRData.dbo.viewTB_Cultura to TBData.dbo.TBCultura.',
    @StepName sysname = N'Synchronize TBCultura',
    @ScheduleName sysname = N'TB - Sync TBCultura - Every 4 Hours at 00:30',
    @JobID uniqueidentifier,
    @ScheduleID int,
    @StepID int,
    @Command nvarchar(max);

SET @Command = CAST(N'' AS nvarchar(max));
SET @Command += N'SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DEADLOCK_PRIORITY LOW;
SET LOCK_TIMEOUT 60000;

DECLARE
    @MaximumDeletePercent decimal(5, 2) = 10.00,
    @AllowLargeDelete bit = 0,
    @DeleteMissing bit = 1,
    @RunID bigint = NULL,
    @StartedAt datetime2(3) = SYSUTCDATETIME(),
    @CompletedAt datetime2(3),
    @MutationTime datetime2(3),
    @SourceRows bigint = 0,
    @TargetRowsBefore bigint = 0,
    @TargetRowsAfter bigint = 0,
    @InsertCandidateRows bigint = 0,
    @UpdateCandidateRows bigint = 0,
    @DeleteCandidateRows bigint = 0,
    @InsertedRows int = 0,
    @UpdatedRows int = 0,
    @DeletedRows int = 0,
    @DeletePercent decimal(9, 4) = 0,
    @LockResult int,
    @ReleaseLockResult int,
    @LockAcquired bit = 0,
    @CaughtErrorNumber int,
    @CaughtErrorState int,
    @CaughtErrorLine int,
    @SourceColumnCount int,
    @TargetColumnCount int,
    @StageColumnList nvarchar(max),
    @StageCompareList nvarchar(max),
    @TargetCompareList nvarchar(max),
    @InsertColumnList nvarchar(max),
    @InsertSelectList nvarchar(max),
    @UpdateSetList nvarchar(max),
    @SQL nvarchar(max);

IF OBJECT_ID(N''[dbo].[TBCultura]'', N''U'') IS NULL
BEGIN
    RAISERROR(N''TBCultura synchronization cannot start because its target table is not deployed.'', 16, 1);
    RETURN;
END;

IF OBJECT_ID(N''[dbo].[TBCulturaSyncRun]'', N''U'') IS NULL
BEGIN
    RAISERROR(N''TBCultura synchronization cannot start because its audit table is not deployed.'', 16, 1);
    RETURN;
END;

IF OBJECT_ID(N''[OpenLDRData].[dbo].[viewTB_Cultura]'', N''V'') IS NULL
BEGIN
    RAISERROR(N''TBCultura synchronization cannot start because its source view is unavailable.'', 16, 1);
    RETURN;
END;

INSERT INTO [dbo].[TBCulturaSyncRun]
(
    [StartedAt],
    [Status],
    [SourceRows],
    [TargetRowsBefore],
    [InsertedRows],
    [UpdatedRows],
    [DeletedRows],
    [TargetRowsAfter]
)
VALUES
(
    @StartedAt,
    ''RUNNING'',
    0,
    0,
    0,
    0,
    0,
    0
);

SET @RunID = CONVERT(bigint, SCOPE_IDENTITY());

BEGIN TRY
    IF @MaximumDeletePercent IS NULL
       OR @MaximumDeletePercent < 0
       OR @MaximumDeletePercent > 100
    BEGIN
        RAISERROR(N''MaximumDeletePercent must be between 0 and 100.'', 16, 1);
    END;

    IF @AllowLargeDelete IS NULL OR @DeleteMissing IS NULL
    BEGIN
        RAISERROR(N''AllowLargeDelete and DeleteMissing must be either 0 or 1.'', 16, 1);
    END;

    EXEC @LockResult = [sys].[sp_getapplock]
        @Resource = N''TBData.dbo.TBCultura.Sync'',
        @LockMode = N''Exclusive'',
        @LockOwner = N''Session'',
        @LockTimeout = 0,
        @DbPrincipal = N''public'';

    IF @LockResult = -1
    BEGIN
        SET @CompletedAt = SYSUTCDATETIME();

        UPDATE [dbo].[TBCulturaSyncRun]
        SET
            [CompletedAt] = @CompletedAt,
            [Status] = ''SKIPPED'',
            [DurationMs] = DATEDIFF(millisecond, @StartedAt, @CompletedAt),
            [ErrorMessage] = N''Another TBCultura synchronizat';
SET @Command += N'ion execution already holds the application lock.''
        WHERE [RunID] = @RunID;

        RETURN;
    END;

    IF @LockResult < 0
    BEGIN
        RAISERROR(N''TBCultura synchronization could not acquire its application lock.'', 16, 1);
    END;

    SET @LockAcquired = 1;

    SELECT @SourceColumnCount = COUNT(*)
    FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS]
    WHERE [TABLE_SCHEMA] = ''dbo''
      AND [TABLE_NAME] = ''viewTB_Cultura'';

    SELECT @TargetColumnCount = COUNT(*)
    FROM [TBData].[INFORMATION_SCHEMA].[COLUMNS]
    WHERE [TABLE_SCHEMA] = ''dbo''
      AND [TABLE_NAME] = ''TBCultura'';

    IF @SourceColumnCount <> 130 OR @TargetColumnCount <> 137
    BEGIN
        RAISERROR(N''TBCultura synchronization stopped because the deployed column counts do not match the data contract.'', 16, 1);
    END;

    IF EXISTS
    (
        SELECT 1
        FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS] AS source_column
        LEFT JOIN [TBData].[INFORMATION_SCHEMA].[COLUMNS] AS target_column
            ON target_column.[TABLE_SCHEMA] = ''dbo''
           AND target_column.[TABLE_NAME] = ''TBCultura''
           AND target_column.[COLUMN_NAME] COLLATE DATABASE_DEFAULT
               = source_column.[COLUMN_NAME] COLLATE DATABASE_DEFAULT
        WHERE source_column.[TABLE_SCHEMA] = ''dbo''
          AND source_column.[TABLE_NAME] = ''viewTB_Cultura''
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
    )
    BEGIN
        RAISERROR(N''TBCultura synchronization stopped because source and target column metadata are not aligned.'', 16, 1);
    END;

    SELECT @StageColumnList =
        STUFF
        (
            (
                SELECT N'',v.'' + QUOTENAME(source_column.[COLUMN_NAME])
                FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS] AS source_column
                WHERE source_column.[TABLE_SCHEMA] = ''dbo''
                  AND source_column.[TABLE_NAME] = ''viewTB_Cultura''
                ORDER BY source_column.[ORDINAL_POSITION]
                FOR XML PATH(''''), TYPE
            ).value(''.'', ''nvarchar(max)''),
            1,
            1,
            N''''
        );

    SELECT @StageCompareList =
        STUFF
        (
            (
                SELECT N'',s.'' + QUOTENAME(source_column.[COLUMN_NAME])
                FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS] AS source_column
                WHERE source_column.[TABLE_SCHEMA] = ''dbo''
                  ';
SET @Command += N'AND source_column.[TABLE_NAME] = ''viewTB_Cultura''
                ORDER BY source_column.[ORDINAL_POSITION]
                FOR XML PATH(''''), TYPE
            ).value(''.'', ''nvarchar(max)''),
            1,
            1,
            N''''
        );

    SELECT @TargetCompareList =
        STUFF
        (
            (
                SELECT N'',t.'' + QUOTENAME(source_column.[COLUMN_NAME])
                FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS] AS source_column
                WHERE source_column.[TABLE_SCHEMA] = ''dbo''
                  AND source_column.[TABLE_NAME] = ''viewTB_Cultura''
                ORDER BY source_column.[ORDINAL_POSITION]
                FOR XML PATH(''''), TYPE
            ).value(''.'', ''nvarchar(max)''),
            1,
            1,
            N''''
        );

    SELECT @InsertColumnList =
        STUFF
        (
            (
                SELECT N'','' + QUOTENAME(source_column.[COLUMN_NAME])
                FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS] AS source_column
                WHERE source_column.[TABLE_SCHEMA] = ''dbo''
                  AND source_column.[TABLE_NAME] = ''viewTB_Cultura''
                ORDER BY source_column.[ORDINAL_POSITION]
                FOR XML PATH(''''), TYPE
            ).value(''.'', ''nvarchar(max)''),
            1,
            1,
            N''''
        );

    SELECT @InsertSelectList =
        STUFF
        (
            (
                SELECT N'',s.'' + QUOTENAME(source_column.[COLUMN_NAME])
                FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS] AS source_column
                WHERE source_column.[TABLE_SCHEMA] = ''dbo''
                  AND source_column.[TABLE_NAME] = ''viewTB_Cultura''
                ORDER BY source_column.[ORDINAL_POSITION]
                FOR XML PATH(''''), TYPE
            ).value(''.'', ''nvarchar(max)''),
            1,
            1,
            N''''
        );

    SELECT @UpdateSetList =
        STUFF
        (
            (
                SELECT
                    N'',t.'' + QUOTENAME(source_column.[COLUMN_NAME])
                    + N''=s.'' + QUOTENAME(source_column.[COLUMN_NAME])
                FROM [OpenLDRData].[INFORMATION_SCHEMA].[COLUMNS] AS source_column
                WHERE source_column.[TABLE_SCHEMA] = ''dbo''
                  AND source_column.[TABLE_NAME] = ''viewTB_Cultura''
                  AND source_column.[COLUMN_NAME] <> ''RequestID''
                ORDER BY source_column.[ORDINAL_POSITION]
                FOR XML PATH(''''), TYPE
            ).value(''.'', ''nvarchar(max)''),
            1,
            1,
            N''''
        );';
SET @Command += N'

    IF OBJECT_ID(N''tempdb..#TBCulturaStage'', N''U'') IS NOT NULL
    BEGIN
        DROP TABLE #TBCulturaStage;
    END;

    IF OBJECT_ID(N''tempdb..#ChangedRequestID'', N''U'') IS NOT NULL
    BEGIN
        DROP TABLE #ChangedRequestID;
    END;

    SELECT TOP (0) *
    INTO #TBCulturaStage
    FROM [OpenLDRData].[dbo].[viewTB_Cultura];

    SET @SQL =
        N''INSERT INTO #TBCulturaStage ('' + @InsertColumnList + N'')
          SELECT '' + @StageColumnList + N''
          FROM [OpenLDRData].[dbo].[viewTB_Cultura] AS v;'';

    EXEC [sys].[sp_executesql] @SQL;

    SELECT @SourceRows = COUNT_BIG(*)
    FROM #TBCulturaStage;

    IF @SourceRows = 0';
SET @Command += N'
    BEGIN
        RAISERROR(N''TBCultura source validation failed because the source returned no rows.'', 16, 1);
    END;

    IF EXISTS
    (
        SELECT 1
        FROM #TBCulturaStage
        WHERE [RequestID] IS NULL
    )
    BEGIN
        RAISERROR(N''TBCultura source validation failed because one or more RequestID values are NULL.'', 16, 1);
    END;

    IF EXISTS
    (
        SELECT 1
        FROM #TBCulturaStage
        GROUP BY [RequestID]
        HAVING COUNT_BIG(*) > 1
    )
    BEGIN
        RAISERROR(N''TBCultura source validation failed because duplicate RequestID values exist.'', 16, 1);
    END;

    CREATE UNIQUE CLUSTERED INDEX [CUX_TBCulturaStage_RequestID]
        ON #TBCulturaStage ([RequestID]);

    SELECT @TargetRowsBefore = COUNT_BIG(*)
    FROM [dbo].[TBCultura];

    CREATE TABLE #ChangedRequestID
    (
        [RequestID] varchar(26) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
        PRIMARY KEY CLUSTERED ([RequestID])
    );

    SET @SQL =
        N''INSERT INTO #ChangedRequestID ([RequestID])
          SELECT s.[RequestID]
          FROM #TBCulturaStage AS s
          INNER JOIN [dbo].[TBCultura] AS t
              ON t.[RequestID] = s.[RequestID]
          WHERE EXISTS
          (
              SELECT '' + @StageCompareList + N''
              EXCEPT
              SELECT '' + @TargetCompareList + N''
          );'';

    EXEC [sys].[sp_executesql] @SQL;

    SELECT @UpdateCandidateRows = COUNT_BIG(*)
    FROM #ChangedRequestID;

    SELECT @InsertCandidateRows = COUNT_BIG(*)
    FROM #TBCulturaStage AS s
    WHERE NOT EXISTS
    (
        SELECT 1
        FROM [dbo].[TBCultura] AS t
        WHERE t.[RequestID] = s.[RequestID]
    );

    IF @DeleteMissing = 1
    BEGIN
        SELECT @DeleteCandidateRows = COUNT_BIG(*)
        FROM [dbo].[TBCultura] AS t
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM #TBCulturaStage AS s
            WHERE s.[RequestID] = t.[RequestID]
        );
    END;

    SET @DeletePercent =
        CASE
            WHEN @TargetRowsBefore = 0 THEN 0
            ELSE
                CONVERT(decimal(19, 4), @DeleteCandidateRows)
                * CONVERT(decimal(19, 4), 100)
                / CONVERT(decimal(19, 4), @TargetRowsBefore)
        END;

    IF @DeleteMissing = 1
       AND @AllowLargeDelete = 0
       AND @DeletePercent > @MaximumDeletePercent
    BEGIN
        RAISERROR(N''TBCultura delete guard blocked a deletion larger than the configured percentage.'', 16, 1);
    END;

    SET @MutationTime = SYSUTCDATETIME();

    BEGIN TRANSACTION;

    SET @SQL =
        N''UPDATE t
          SET '' + @UpdateSetList + N'',
              t.[UpdatedAt]=@MutationTime
          FROM [dbo].[TBCultura] AS t
          INNER JOIN #TBCulturaStage AS s
              ON s.[RequestID] = t.[RequestID]
          INNER JOIN #ChangedRequestID AS changed
              ON changed.[RequestID] = t.[RequestID];
          SET @AffectedRows = @@ROWCOUNT;'';

    EXEC [sys].[sp_executesql]';
SET @Command += N'
        @SQL,
        N''@MutationTime datetime2(3), @AffectedRows int OUTPUT'',
        @MutationTime = @MutationTime,
        @AffectedRows = @UpdatedRows OUTPUT;

    SET @SQL =
        N''INSERT INTO [dbo].[TBCultura]
          ('' + @InsertColumnList + N'', [CreatedAt], [UpdatedAt])
          SELECT '' + @InsertSelectList + N'', @MutationTime, @MutationTime
          FROM #TBCulturaStage AS s
          WHERE NOT EXISTS
          (
              SELECT 1
              FROM [dbo].[TBCultura] AS t WITH (UPDLOCK, HOLDLOCK)
              WHERE t.[RequestID] = s.[RequestID]
          );
          SET @AffectedRows = @@ROWCOUNT;'';

    EXEC [sys].[sp_executesql]
        @SQL,
        N''@MutationTime datetime2(3), @AffectedRows int OUTPUT'',
        @MutationTime = @MutationTime,
        @AffectedRows = @InsertedRows OUTPUT;

    IF @DeleteMissing = 1
    BEGIN
        DELETE t
        FROM [dbo].[TBCultura] AS t
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM #TBCulturaStage AS s
            WHERE s.[RequestID] = t.[RequestID]
        );

        SET @DeletedRows = @@ROWCOUNT;
    END;

    SELECT @TargetRowsAfter = COUNT_BIG(*)
    FROM [dbo].[TBCultura];

    IF @DeleteMissing = 1
       AND @TargetRowsAfter <> @SourceRows
    BEGIN
        RAISERROR(N''TBCultura post-synchronization row-count validation failed.'', 16, 1);
    END;

    IF @DeleteMissing = 0
       AND @TargetRowsAfter <> @TargetRowsBefore + CONVERT(bigint, @InsertedRows)
    BEGIN
        RAISERROR(N''TBCultura append-only row-count validation failed.'', 16, 1);
    END;

    IF CONVERT(bigint, @InsertedRows) <> @InsertCandidateRows
       OR CONVERT(bigint, @UpdatedRows) <> @UpdateCandidateRows
       OR CONVERT(bigint, @DeletedRows) <> @DeleteCandidateRows
    BEGIN
        RAISERROR(N''TBCultura post-synchronization mutation-count validation failed.'', 16, 1);
    END;

    SET @CompletedAt = SYSUTCDATETIME();

    UPDATE [dbo].[TBCulturaSyncRun]
    SET
        [CompletedAt] = @CompletedAt,
        [Status] = ''SUCCEEDED'',
        [SourceRows] = @SourceRows,
        [TargetRowsBefore] = @TargetRowsBefore,
        [InsertedRows] = @InsertedRows,
        [UpdatedRows] = @UpdatedRows,
        [DeletedRows] = @DeletedRows,
        [TargetRowsAfter] = @TargetRowsAfter,
        [DurationMs] = DATEDIFF(millisecond, @StartedAt, @CompletedAt),
        [ErrorNumber] = NULL,
        [ErrorMessage] = NULL
    WHERE [RunID] = @RunID;

    COMMIT TRANSACTION;

    EXEC @ReleaseLockResult = [sys].[sp_releaseapplock]
        @Resource = N''TBData.dbo.TBCultura.Sync'',
        @LockOwner = N''Session'',
        @DbPrincipal = N''public'';

    SET @LockAcquired = 0;
END TRY
BEGIN CATCH
    SET @CaughtErrorNumber = ERROR_NUMBER();
    SET @CaughtErrorState = ERROR_STATE();
    SET @CaughtErrorLine = ERROR_LINE();

    IF XACT_STATE() <> 0
    BEGIN
        ROLLBACK TRANSACTION;
    END;

    SET @CompletedAt = SYSUTCDATETIME();

    IF @RunID IS NOT NULL
    BEGIN';
SET @Command += N'
        UPDATE [dbo].[TBCulturaSyncRun]
        SET
            [CompletedAt] = @CompletedAt,
            [Status] = ''FAILED'',
            [SourceRows] = @SourceRows,
            [TargetRowsBefore] = @TargetRowsBefore,
            [InsertedRows] = 0,
            [UpdatedRows] = 0,
            [DeletedRows] = 0,
            [TargetRowsAfter] = @TargetRowsBefore,
            [DurationMs] = DATEDIFF(millisecond, @StartedAt, @CompletedAt),
            [ErrorNumber] = @CaughtErrorNumber,
            [ErrorMessage] = N''TBCultura synchronization failed. Numeric diagnostics were retained without row data.''
        WHERE [RunID] = @RunID;
    END;

    IF @LockAcquired = 1
    BEGIN
        EXEC @ReleaseLockResult = [sys].[sp_releaseapplock]
            @Resource = N''TBData.dbo.TBCultura.Sync'',
            @LockOwner = N''Session'',
            @DbPrincipal = N''public'';
    END;

    RAISERROR
    (
        N''TBCultura synchronization failed (error %d, state %d, line %d).'',
        16,
        1,
        @CaughtErrorNumber,
        @CaughtErrorState,
        @CaughtErrorLine
    );
END CATCH;';

IF DATALENGTH(REPLACE(@Command, NCHAR(13), N'')) <> 32536
BEGIN
    RAISERROR
    (
        N'TBCultura Agent command assembly failed its byte-length check.',
        16,
        1
    );
END;

SELECT @JobID = [job_id]
FROM [msdb].[dbo].[sysjobs]
WHERE [name] = @JobName;

IF @JobID IS NULL
BEGIN
    EXEC [msdb].[dbo].[sp_add_job]
        @job_name = @JobName,
        @enabled = 1,
        @description = @JobDescription,
        @notify_level_eventlog = 2,
        @delete_level = 0,
        @job_id = @JobID OUTPUT;
END;
ELSE
BEGIN
    EXEC [msdb].[dbo].[sp_update_job]
        @job_id = @JobID,
        @enabled = 1,
        @description = @JobDescription,
        @notify_level_eventlog = 2,
        @delete_level = 0;
END;

SELECT @StepID = [step_id]
FROM [msdb].[dbo].[sysjobsteps]
WHERE [job_id] = @JobID
  AND [step_name] = @StepName;

IF @StepID IS NULL
BEGIN
    EXEC [msdb].[dbo].[sp_add_jobstep]
        @job_id = @JobID,
        @step_name = @StepName,
        @subsystem = N'TSQL',
        @database_name = N'TBData',
        @command = @Command,
        @retry_attempts = 2,
        @retry_interval = 10,
        @on_success_action = 1,
        @on_fail_action = 2;

    SELECT @StepID = [step_id]
    FROM [msdb].[dbo].[sysjobsteps]
    WHERE [job_id] = @JobID
      AND [step_name] = @StepName;
END;
ELSE
BEGIN
    EXEC [msdb].[dbo].[sp_update_jobstep]
        @job_id = @JobID,
        @step_id = @StepID,
        @step_name = @StepName,
        @subsystem = N'TSQL',
        @database_name = N'TBData',
        @command = @Command,
        @retry_attempts = 2,
        @retry_interval = 10,
        @on_success_action = 1,
        @on_fail_action = 2;
END;

EXEC [msdb].[dbo].[sp_update_job]
    @job_id = @JobID,
    @enabled = 1,
    @start_step_id = @StepID;

SELECT @ScheduleID = [schedule_id]
FROM [msdb].[dbo].[sysschedules]
WHERE [name] = @ScheduleName;

IF @ScheduleID IS NULL
BEGIN
    EXEC [msdb].[dbo].[sp_add_schedule]
        @schedule_name = @ScheduleName,
        @enabled = 1,
        @freq_type = 4,
        @freq_interval = 1,
        @freq_subday_type = 8,
        @freq_subday_interval = 4,
        @freq_recurrence_factor = 1,
        @active_start_date = 20000101,
        @active_end_date = 99991231,
        @active_start_time = 003000,
        @active_end_time = 235959,
        @schedule_id = @ScheduleID OUTPUT;
END;
ELSE
BEGIN
    EXEC [msdb].[dbo].[sp_update_schedule]
        @schedule_id = @ScheduleID,
        @enabled = 1,
        @freq_type = 4,
        @freq_interval = 1,
        @freq_subday_type = 8,
        @freq_subday_interval = 4,
        @freq_recurrence_factor = 1,
        @active_start_date = 20000101,
        @active_end_date = 99991231,
        @active_start_time = 003000,
        @active_end_time = 235959;
END;

IF NOT EXISTS
(
    SELECT 1
    FROM [msdb].[dbo].[sysjobschedules]
    WHERE [job_id] = @JobID
      AND [schedule_id] = @ScheduleID
)
BEGIN
    EXEC [msdb].[dbo].[sp_attach_schedule]
        @job_id = @JobID,
        @schedule_id = @ScheduleID;
END;

IF NOT EXISTS
(
    SELECT 1
    FROM [msdb].[dbo].[sysjobservers]
    WHERE [job_id] = @JobID
      AND [server_id] = 0
)
BEGIN
    EXEC [msdb].[dbo].[sp_add_jobserver]
        @job_id = @JobID,
        @server_name = N'(LOCAL)';
END;
GO
