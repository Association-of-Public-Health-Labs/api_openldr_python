/*
    Read-only post-migration checks, SQL Server 2014.
    Run after 001_add_user_is_active.sql and before the new API starts.
    Results expose schema and aggregate counts only, not account identifiers.
    Reapplication/INSERT/backfill tests run separately in the disposable test DB;
    this verification never modifies live accounts or their audit history.
*/

USE [Utils];
GO

SET NOCOUNT ON;

IF DB_NAME() <> N'Utils'
    THROW 51102, 'Verification refused: the current database must be Utils.', 1;

DECLARE @users_object_id INT = OBJECT_ID(N'[dbo].[openldr_api_user_users]', N'U');
IF @users_object_id IS NULL
    THROW 51100, 'Expected table dbo.openldr_api_user_users was not found.', 1;

IF NOT EXISTS
(
    SELECT 1
    FROM sys.columns AS c
    INNER JOIN sys.default_constraints AS dc ON dc.object_id = c.default_object_id
    WHERE c.object_id = @users_object_id
      AND c.name = N'is_active'
      AND TYPE_NAME(c.user_type_id) = N'bit'
      AND c.is_nullable = 0
      AND c.is_computed = 0
      AND dc.name = N'DF_openldr_api_user_users_is_active'
      AND REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
          dc.definition, N'(', N''), N')', N''), N' ', N''),
          NCHAR(9), N''), NCHAR(10), N''), NCHAR(13), N'') = N'1'
)
    THROW 51101, 'The required is_active BIT NOT NULL DEFAULT (1) contract is missing.', 1;

SELECT
    TYPE_NAME(c.user_type_id) AS ColumnType,
    c.is_nullable AS IsNullable,
    dc.name AS DefaultConstraint,
    dc.definition AS DefaultDefinition
FROM sys.columns AS c
INNER JOIN sys.default_constraints AS dc ON dc.object_id = c.default_object_id
WHERE c.object_id = @users_object_id AND c.name = N'is_active';

-- Compile the read only after the column existence/schema guard has passed.
EXEC sys.sp_executesql N'
    SELECT COUNT_BIG(*) AS TotalAccounts,
           COUNT_BIG(CASE WHEN [is_active] = 1 THEN 1 END) AS ActiveAccounts,
           COUNT_BIG(CASE WHEN [is_active] = 0 THEN 1 END) AS InactiveAccounts
    FROM [dbo].[openldr_api_user_users];';
GO
