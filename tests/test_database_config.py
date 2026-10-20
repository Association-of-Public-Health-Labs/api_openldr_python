"""Configuration regressions without contacting SQL Server."""

import configparser
import runpy
from pathlib import Path

import pyodbc
import pytest


@pytest.fixture
def load_config(monkeypatch, tmp_path):
    ini = tmp_path / "configs.ini"
    original_read = configparser.ConfigParser.read
    monkeypatch.setattr(
        configparser.ConfigParser,
        "read",
        lambda self, *args, **kwargs: original_read(self, ini, **kwargs),
    )
    monkeypatch.setattr(pyodbc, "pooling", pyodbc.pooling)
    for name in (
        "CDR_DOMAIN", "LOCAL_DOMAIN", "CLOUD_DOMAIN", "DB_USER", "DB_PASSWORD",
        "DB_VL_DATA", "DB_DPI", "DB_HIV_AD", "DB_TB_DATA", "DB_DICT",
        "DB_USERS", "DB_REPORT_DATA", "SQL_ODBC_POOLING",
    ):
        monkeypatch.delenv(name, raising=False)

    def load(system="Windows", content=""):
        ini.write_text(content, encoding="utf-8")
        monkeypatch.setattr("platform.system", lambda: system)
        return runpy.run_path(str(Path(__file__).parents[1] / "configs" / "paths.py"))

    return load


@pytest.mark.parametrize("system", ["Windows", "Linux"])
def test_environment_overrides_ini_on_every_platform(load_config, monkeypatch, system):
    monkeypatch.setenv("CDR_DOMAIN", "sql.example.test,1433")
    settings = load_config(system, "[Domains]\ncdr=ini.example.test\n")
    assert settings["CDR_DOMAIN_NAME"] == "sql.example.test,1433"


@pytest.mark.parametrize("system", ["Windows", "Linux"])
def test_ini_fallback_preserves_literal_percent_in_password(load_config, system):
    settings = load_config(system, "[Databases]\ndatabase_password=pass%word\n")
    assert settings["PASSWORD"] == "pass%word"


def test_empty_environment_does_not_fall_back_to_another_server(load_config, monkeypatch):
    monkeypatch.setenv("CDR_DOMAIN", "")
    settings = load_config(content="[Domains]\ncdr=other.example.test\n")
    assert settings["CDR_DOMAIN_NAME"] == ""
    with pytest.raises(ValueError, match="CDR_DOMAIN"):
        settings["get_sqlalchemy_binds"]("cdr", ["vl"])


def test_missing_active_settings_report_names_without_credentials(load_config, monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "do-not-log-this")
    settings = load_config()
    with pytest.raises(ValueError) as error:
        settings["get_sqlalchemy_binds"]("cdr")
    message = str(error.value)
    assert "CDR_DOMAIN" in message
    assert "[Domains] cdr" in message
    assert "DB_USER" in message
    assert "DB_VL_DATA" in message
    assert "configs.ini" in message
    assert "do-not-log-this" not in message


def test_only_active_host_and_selected_databases_are_required(load_config, monkeypatch):
    for name, value in {
        "CDR_DOMAIN": "tcp:sql.example.test,1433",
        "DB_USER": "api-user",
        "DB_PASSWORD": "api-password",
        "DB_VL_DATA": "ViralLoadData",
    }.items():
        monkeypatch.setenv(name, value)
    settings = load_config()
    binds = settings["get_sqlalchemy_binds"]("cdr", bind_keys=["vl"])
    assert list(binds) == ["vl"]
    connection = binds["vl"].query["odbc_connect"]
    assert "SERVER=tcp:sql.example.test,1433;" in connection
    assert "DATABASE=ViralLoadData;" in connection
    assert "None" not in connection


@pytest.mark.parametrize("field", ["user", "pwd", "host", "db"])
@pytest.mark.parametrize("missing", [None, "", "   "])
def test_connection_builder_rejects_missing_values(load_config, field, missing):
    settings = load_config()
    arguments = dict(user="api-user", pwd="api-password", host="sql.test", db="vl")
    arguments[field] = missing
    with pytest.raises(ValueError):
        settings["build_odbc_connection_string"](**arguments)


def test_special_characters_are_escaped_in_odbc_values(load_config):
    settings = load_config()
    connection = settings["build_odbc_connection_string"](
        "api;user", " p%a;ss}word ", r"sql.test\SQLEXPRESS", "vl;data"
    )
    assert "UID={api;user};" in connection
    assert "PWD={ p%a;ss}}word };" in connection
    assert "DATABASE={vl;data};" in connection
    assert r"SERVER=sql.test\SQLEXPRESS;" in connection
    assert "Encrypt=yes;" in connection
    assert "TrustServerCertificate=yes;" in connection


def test_pooling_uses_pyodbc_without_unsupported_string_attributes(load_config, monkeypatch):
    monkeypatch.setenv("SQL_ODBC_POOLING", "false")
    settings = load_config()
    connection = settings["build_odbc_connection_string"]("user", "pwd", "sql.test", "vl")
    assert pyodbc.pooling is False
    assert "Pooling=" not in connection
    assert "Connection Timeout=" not in connection


def test_connection_check_stops_before_engine_creation_on_missing_config(
    load_config, monkeypatch, capsys
):
    from scripts import check_mssql_connection
    from unittest.mock import Mock

    settings = load_config()
    create_engine = Mock()
    monkeypatch.setattr(check_mssql_connection, "get_sqlalchemy_binds", settings["get_sqlalchemy_binds"])
    monkeypatch.setattr(check_mssql_connection, "create_engine", create_engine)
    monkeypatch.setattr("sys.argv", ["check_mssql_connection.py", "--bind", "vl"])
    assert check_mssql_connection.main() == 1
    assert "CDR_DOMAIN" in capsys.readouterr().err
    create_engine.assert_not_called()
