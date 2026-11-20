"""SQL assets plus opt-in, real SQL Server migration/reapplication tests.

The default run performs static contract checks only; SQLite cannot execute or
validate T-SQL. To run the SQL Server tests, create an EMPTY disposable database
whose name starts with ``OpenLDR_API_test_deactivation_`` and set BOTH variables:

* OPENLDR_DEACTIVATION_SQLSERVER_TEST_DATABASE: that database's exact name.
* OPENLDR_DEACTIVATION_SQLSERVER_TEST_CONNECTION_STRING: ODBC connection string
  selecting that same database, supplied securely through the environment.

Tests refuse Utils, other database names, or pre-existing account/audit tables.
All fixtures and migration DDL are inside an outer transaction, rolled back on
cleanup. Only the target database name (USE and its guard) is substituted.
No configured application database/credential is discovered or used implicitly.
"""

import os
import re
from datetime import datetime
from pathlib import Path

import pytest


SQL_DIRECTORY = Path(__file__).resolve().parents[1] / "sql" / "auth"
MIGRATION = SQL_DIRECTORY / "001_add_user_is_active.sql"
VERIFICATION = SQL_DIRECTORY / "002_verify_user_is_active.sql"
CONNECTION_ENV = "OPENLDR_DEACTIVATION_SQLSERVER_TEST_CONNECTION_STRING"
DATABASE_ENV = "OPENLDR_DEACTIVATION_SQLSERVER_TEST_DATABASE"
DATABASE_PATTERN = re.compile(r"OpenLDR_API_test_deactivation_[A-Za-z0-9_]{1,64}\Z")


def _without_comments(sql):
    return re.sub(r"/\*.*?\*/|--[^\r\n]*", "", sql, flags=re.DOTALL)


def _batches(sql):
    return [batch for batch in re.split(r"(?im)^\s*GO\s*$", sql) if batch.strip()]


def _sandbox_script(path, database):
    if DATABASE_PATTERN.fullmatch(database) is None:
        raise ValueError("SQL migration tests require a disposable test database")
    script = path.read_text(encoding="utf-8")
    assert script.count("USE [Utils];") == 1
    assert script.count("DB_NAME() <> N'Utils'") == 1
    return script.replace("USE [Utils];", f"USE [{database}];", 1).replace(
        "DB_NAME() <> N'Utils'", f"DB_NAME() <> N'{database}'", 1
    )


def test_migration_targets_declared_sqlserver_schema_and_key():
    sql = _without_comments(MIGRATION.read_text(encoding="utf-8"))
    assert "USE [Utils];" in sql
    assert "IF DB_NAME() <> N'Utils'" in sql
    assert sql.index("IF DB_NAME() <> N'Utils'") < sql.index("ALTER TABLE")
    assert "OBJECT_ID(N'[dbo].[openldr_api_user_users]', N'U')" in sql
    assert "c.name = N'user_id'" in sql
    assert "TYPE_NAME(c.user_type_id) = N'nvarchar'" in sql
    assert "c.max_length = 100" in sql
    assert "i.is_primary_key = 1" in sql and "extra.key_ordinal > 1" in sql


def test_migration_uses_transactional_dynamic_ddl_for_initial_backfill():
    sql = _without_comments(MIGRATION.read_text(encoding="utf-8"))
    assert "SET XACT_ABORT ON" in sql
    assert "BEGIN TRANSACTION" in sql and "COMMIT TRANSACTION" in sql
    assert "BEGIN CATCH" in sql and "ROLLBACK TRANSACTION" in sql
    assert "COL_LENGTH(N'dbo.openldr_api_user_users', N'is_active') IS NULL" in sql
    assert re.search(r"EXEC sys\.sp_executesql N'\s*ALTER TABLE", sql)
    assert re.search(r"ADD \[is_active\] BIT NOT NULL\s+CONSTRAINT "
                     r"\[DF_openldr_api_user_users_is_active\] DEFAULT \(1\)\s+WITH VALUES", sql)


def test_reapplication_has_no_account_or_audit_data_mutations():
    sql = _without_comments(MIGRATION.read_text(encoding="utf-8"))
    assert re.search(r"\b(?:UPDATE|DELETE|INSERT|MERGE|TRUNCATE)\b", sql, re.IGNORECASE) is None
    assert "updated_at" not in sql.lower()
    assert "openldr_api_user_logs" not in sql.lower()
    assert "@default_name <> N'DF_openldr_api_user_users_is_active'" in sql
    assert "@default_definition <> N'1'" in sql


@pytest.mark.parametrize("path", [MIGRATION, VERIFICATION], ids=["migration", "verification"])
def test_sql_assets_avoid_syntax_unavailable_on_sqlserver_2014(path):
    sql = _without_comments(path.read_text(encoding="utf-8")).upper()
    for unsupported in (
        r"\bCREATE\s+OR\s+ALTER\b", r"\bDROP\s+\w+\s+IF\s+EXISTS\b",
        r"\bSTRING_AGG\s*\(", r"\bSTRING_SPLIT\s*\(", r"\bOPENJSON\s*\(",
        r"\bJSON_VALUE\s*\(", r"\bSESSION_CONTEXT\s*\(", r"\bFOR\s+JSON\b",
    ):
        assert re.search(unsupported, sql) is None


def test_deployment_verification_is_read_only_and_exposes_no_account_identifiers():
    sql = _without_comments(VERIFICATION.read_text(encoding="utf-8"))
    assert "USE [Utils];" in sql
    assert "IF DB_NAME() <> N'Utils'" in sql
    assert re.search(r"\b(?:UPDATE|DELETE|INSERT|MERGE|TRUNCATE|ALTER|CREATE|DROP)\b",
                     sql, re.IGNORECASE) is None
    assert "COUNT_BIG" in sql
    assert "user_id" not in sql and "password" not in sql and "email" not in sql


@pytest.mark.parametrize("database", ["Utils", "master", "production", "OpenLDR_API_test_deactivation_x]; USE [Utils"])
def test_sqlserver_harness_rejects_live_or_injected_database_names(database):
    with pytest.raises(ValueError, match="disposable test database"):
        _sandbox_script(MIGRATION, database)


class _SqlServerSandbox:
    def __init__(self, connection, database):
        self.connection = connection
        self.database = database

    def execute(self, sql, parameters=()):
        cursor = self.connection.cursor()
        cursor.execute(sql, parameters)
        return cursor

    def scalar(self, sql, parameters=()):
        return self.execute(sql, parameters).fetchone()[0]

    def apply(self, path=MIGRATION):
        for batch in _batches(_sandbox_script(path, self.database)):
            cursor = self.execute(batch)
            while cursor.nextset():
                pass

    def create_accounts(self, extra_column="", user_id_type="NVARCHAR(50)", primary_key="[user_id]"):
        # Arguments below are constant DDL fragments owned exclusively by tests.
        self.execute(f"""
            CREATE TABLE [dbo].[openldr_api_user_users]
            (
                [user_id] {user_id_type} NOT NULL,
                [sequence] INT NOT NULL DEFAULT (1),
                [updated_at] DATETIME NOT NULL,
                CONSTRAINT [PK_test_deactivation_users] PRIMARY KEY ({primary_key})
                {extra_column}
            );
        """)


@pytest.fixture
def sqlserver_sandbox():
    connection_string = os.environ.get(CONNECTION_ENV)
    database = os.environ.get(DATABASE_ENV)
    if not connection_string or not database:
        pytest.skip("Real SQL Server test not configured; no T-SQL engine validation was performed")
    if DATABASE_PATTERN.fullmatch(database) is None:
        pytest.fail("SQL Server tests require an OpenLDR_API_test_deactivation_ disposable database")

    import pyodbc

    try:
        connection = pyodbc.connect(connection_string, autocommit=True, timeout=5)
        connection.timeout = 5
    except pyodbc.Error:
        pytest.fail("Could not connect to the explicitly configured SQL Server test database", pytrace=False)

    try:
        sandbox = _SqlServerSandbox(connection, database)
        actual_database = sandbox.scalar("SELECT DB_NAME();")
        if actual_database != database:
            pytest.fail("Connection selected a different database; SQL Server test refused to write")
        major_version = int(str(sandbox.scalar("SELECT SERVERPROPERTY('ProductVersion');")).split(".")[0])
        assert major_version >= 12, "SQL Server 2014 or newer is required"
        assert sandbox.scalar("SELECT compatibility_level FROM sys.databases WHERE name = DB_NAME();") >= 120
        existing_count = sandbox.scalar("""
            SELECT COUNT(*) FROM sys.tables
            WHERE name IN (N'openldr_api_user_users', N'openldr_api_user_logs');
        """)
        if existing_count:
            pytest.fail("Test account/audit tables already exist; SQL Server test refused to write")
        sandbox.execute("BEGIN TRANSACTION;")
        yield sandbox
    finally:
        cursor = connection.cursor()
        cursor.execute("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;")
        connection.close()


def test_sqlserver_migration_backfills_defaults_preserves_history_and_inactive_reapplication(sqlserver_sandbox):
    sql = sqlserver_sandbox
    sql.create_accounts()
    timestamp = datetime(2020, 1, 2, 3, 4, 5)
    sql.execute("INSERT INTO dbo.openldr_api_user_users (user_id, updated_at) VALUES (?, ?);", ("existing", timestamp))
    sql.execute("""
        CREATE TABLE dbo.openldr_api_user_logs
        (
            log_id NVARCHAR(50) NOT NULL PRIMARY KEY,
            user_id NVARCHAR(50) NOT NULL,
            log_date DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES dbo.openldr_api_user_users (user_id)
        );
    """)
    sql.execute("INSERT INTO dbo.openldr_api_user_logs VALUES (?, ?, ?);", ("historic", "existing", timestamp))

    sql.apply()
    assert sql.scalar("SELECT is_active FROM dbo.openldr_api_user_users WHERE user_id = N'existing';") is True
    sql.execute("INSERT INTO dbo.openldr_api_user_users (user_id, updated_at) VALUES (?, ?);", ("new-default", timestamp))
    assert sql.scalar("SELECT is_active FROM dbo.openldr_api_user_users WHERE user_id = N'new-default';") is True

    deactivation_time = datetime(2021, 2, 3, 4, 5, 6)
    sql.execute("UPDATE dbo.openldr_api_user_users SET is_active = 0, updated_at = ? WHERE user_id = N'existing';",
                (deactivation_time,))
    sql.apply()
    sql.apply(VERIFICATION)
    row = sql.execute("SELECT is_active, updated_at FROM dbo.openldr_api_user_users WHERE user_id = N'existing';").fetchone()
    assert tuple(row) == (False, deactivation_time)
    assert sql.scalar("SELECT COUNT(*) FROM dbo.openldr_api_user_users;") == 2
    assert sql.scalar("SELECT COUNT(*) FROM dbo.openldr_api_user_logs WHERE user_id = N'existing';") == 1
    assert sql.scalar("SELECT log_date FROM dbo.openldr_api_user_logs WHERE log_id = N'historic';") == timestamp


def test_sqlserver_migration_adds_missing_default_without_changing_existing_inactive_accounts(sqlserver_sandbox):
    sql = sqlserver_sandbox
    sql.create_accounts(extra_column=", [is_active] BIT NOT NULL")
    timestamp = datetime(2020, 1, 2, 3, 4, 5)
    sql.execute("INSERT INTO dbo.openldr_api_user_users (user_id, updated_at, is_active) VALUES (?, ?, 0);", ("inactive", timestamp))
    sql.apply()
    row = sql.execute("SELECT is_active, updated_at FROM dbo.openldr_api_user_users;").fetchone()
    assert tuple(row) == (False, timestamp)
    sql.execute("INSERT INTO dbo.openldr_api_user_users (user_id, updated_at) VALUES (?, ?);", ("new-default", timestamp))
    assert sql.scalar("SELECT is_active FROM dbo.openldr_api_user_users WHERE user_id = N'new-default';") is True


@pytest.mark.parametrize("extra_column", [
    ", [is_active] BIT NULL",
    ", [is_active] INT NOT NULL",
    ", [is_active] AS CONVERT(BIT, 1)",
    ", [is_active] BIT NOT NULL CONSTRAINT DF_openldr_api_user_users_is_active DEFAULT (0)",
    ", [is_active] BIT NOT NULL CONSTRAINT WrongDefaultName DEFAULT (1)",
], ids=["nullable", "wrong-type", "computed", "inactive-default", "wrong-default-name"])
def test_sqlserver_migration_rejects_schema_drift_transactionally(sqlserver_sandbox, extra_column):
    import pyodbc

    sql = sqlserver_sandbox
    sql.create_accounts(extra_column=extra_column)
    with pytest.raises(pyodbc.Error):
        sql.apply()
    assert sql.scalar("SELECT @@TRANCOUNT;") == 0
    # The migration CATCH rolls back the entire outer test transaction as well.
    assert sql.scalar("SELECT OBJECT_ID(N'dbo.openldr_api_user_users', N'U');") is None


@pytest.mark.parametrize("user_id_type, primary_key", [
    ("NVARCHAR(250)", "[user_id]"),
    ("VARCHAR(50)", "[user_id]"),
    ("NVARCHAR(50)", "[sequence]"),
    ("NVARCHAR(50)", "[user_id], [sequence]"),
], ids=["wrong-length", "non-unicode", "wrong-primary-key", "composite-primary-key"])
def test_sqlserver_migration_rejects_an_unexpected_user_key(sqlserver_sandbox, user_id_type, primary_key):
    import pyodbc

    sql = sqlserver_sandbox
    sql.create_accounts(user_id_type=user_id_type, primary_key=primary_key)
    with pytest.raises(pyodbc.Error):
        sql.apply()
    assert sql.scalar("SELECT @@TRANCOUNT;") == 0


def test_sqlserver_migration_rejects_missing_table(sqlserver_sandbox):
    import pyodbc

    with pytest.raises(pyodbc.Error):
        sqlserver_sandbox.apply()
    assert sqlserver_sandbox.scalar("SELECT @@TRANCOUNT;") == 0


@pytest.mark.parametrize("path", [MIGRATION, VERIFICATION], ids=["migration", "verification"])
def test_sqlserver_scripts_refuse_a_database_different_from_their_target(sqlserver_sandbox, path):
    import pyodbc

    sql = sqlserver_sandbox
    # The USE still selects the safe test DB; deliberately leave the production
    # guard unchanged to exercise refusal without ever selecting/writing Utils.
    script = _sandbox_script(path, sql.database).replace(
        f"DB_NAME() <> N'{sql.database}'", "DB_NAME() <> N'Utils'", 1
    )
    with pytest.raises(pyodbc.Error):
        for batch in _batches(script):
            cursor = sql.execute(batch)
            while cursor.nextset():
                pass
    assert sql.scalar("SELECT OBJECT_ID(N'dbo.openldr_api_user_users', N'U');") is None
