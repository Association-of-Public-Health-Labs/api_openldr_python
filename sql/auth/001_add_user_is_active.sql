/*
    Logical account deactivation, SQL Server 2014 (compatibility level 120).
    Target: [Utils].[dbo].[openldr_api_user_users], PK [user_id] NVARCHAR(50).

    Apply manually in a TEST environment first, then deploy this migration BEFORE
    the new API version. Existing rows become active only when the column is
    first added. Reapplication preserves saved states and every updated_at value.
    No accounts or audit records are deleted. No existing constraint/PK is renamed.

    Existing incompatible columns/defaults intentionally fail without repairs.
    Investigate such schema drift before retrying; do not reset inactive accounts.
*/

USE [Utils];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    -- Some clients continue with later GO batches when USE fails. Never apply
    -- account DDL in the connection's previous database in that situation.
    IF DB_NAME() <> N'Utils'
        THROW 51006, 'Migration refused: the current database must be Utils.', 1;

    DECLARE @users_object_id INT = OBJECT_ID(N'[dbo].[openldr_api_user_users]', N'U');
    IF @users_object_id IS NULL
        THROW 51000, 'Expected table dbo.openldr_api_user_users was not found.', 1;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.columns AS c
        WHERE c.object_id = @users_object_id
          AND c.name = N'user_id'
          AND TYPE_NAME(c.user_type_id) = N'nvarchar'
          AND c.max_length = 100 -- NVARCHAR length is expressed in bytes.
          AND c.is_nullable = 0
          AND c.is_computed = 0
    )
        THROW 51001, 'Expected user_id NVARCHAR(50) NOT NULL; no schema changes were applied.', 1;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.indexes AS i
        INNER JOIN sys.index_columns AS ic
            ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        INNER JOIN sys.columns AS c
            ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE i.object_id = @users_object_id
          AND i.is_primary_key = 1
          AND ic.key_ordinal = 1
          AND c.name = N'user_id'
          AND NOT EXISTS
          (
              SELECT 1
              FROM sys.index_columns AS extra
              WHERE extra.object_id = i.object_id
                AND extra.index_id = i.index_id
                AND extra.key_ordinal > 1
          )
    )
        THROW 51002, 'Expected the single-column primary key user_id; no schema changes were applied.', 1;

    IF COL_LENGTH(N'dbo.openldr_api_user_users', N'is_active') IS NULL
    BEGIN
        IF OBJECT_ID(N'[dbo].[DF_openldr_api_user_users_is_active]') IS NOT NULL
            THROW 51003, 'The required is_active default constraint name is already in use.', 1;

        -- Dynamic DDL prevents compilation from binding the new column before
        -- it exists. WITH VALUES backfills existing accounts only on first add.
        EXEC sys.sp_executesql N'
            ALTER TABLE [dbo].[openldr_api_user_users]
            ADD [is_active] BIT NOT NULL
                CONSTRAINT [DF_openldr_api_user_users_is_active] DEFAULT (1)
                WITH VALUES;';
    END;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.columns AS c
        WHERE c.object_id = @users_object_id
          AND c.name = N'is_active'
          AND TYPE_NAME(c.user_type_id) = N'bit'
          AND c.is_nullable = 0
          AND c.is_computed = 0
    )
        THROW 51004, 'Existing is_active must be BIT NOT NULL and non-computed; review schema drift manually.', 1;

    DECLARE @default_object_id INT;
    SELECT @default_object_id = c.default_object_id
    FROM sys.columns AS c
    WHERE c.object_id = @users_object_id AND c.name = N'is_active';

    IF @default_object_id = 0
    BEGIN
        IF OBJECT_ID(N'[dbo].[DF_openldr_api_user_users_is_active]') IS NOT NULL
            THROW 51003, 'The required is_active default constraint name is already in use.', 1;

        -- Adding a missing default affects future INSERTs only, not saved states.
        EXEC sys.sp_executesql N'
            ALTER TABLE [dbo].[openldr_api_user_users]
            ADD CONSTRAINT [DF_openldr_api_user_users_is_active]
                DEFAULT (1) FOR [is_active];';

        SELECT @default_object_id = c.default_object_id
        FROM sys.columns AS c
        WHERE c.object_id = @users_object_id AND c.name = N'is_active';
    END;

    DECLARE @default_name SYSNAME;
    DECLARE @default_definition NVARCHAR(MAX);
    SELECT @default_name = dc.name, @default_definition = dc.definition
    FROM sys.default_constraints AS dc
    WHERE dc.object_id = @default_object_id AND dc.parent_object_id = @users_object_id;

    -- SQL Server normally stores DEFAULT (1) as ((1)). Ignore only whitespace
    -- and parentheses; a different expression/name requires manual review.
    SET @default_definition = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
        @default_definition, N'(', N''), N')', N''), N' ', N''),
        NCHAR(9), N''), NCHAR(10), N''), NCHAR(13), N'');

    IF @default_name IS NULL
       OR @default_name <> N'DF_openldr_api_user_users_is_active'
       OR @default_definition IS NULL
       OR @default_definition <> N'1'
        THROW 51005, 'Expected DF_openldr_api_user_users_is_active DEFAULT (1); review the existing default manually.', 1;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
