import os
import platform
import configparser
from pathlib import Path

import pyodbc
from sqlalchemy.engine import URL

IS_WINDOWS = platform.system() == "Windows"

# -----------------------------
# Load configuration
# -----------------------------
# Values are literal: credentials may contain '%' and are never interpolated.
config = configparser.ConfigParser(interpolation=None)
config.read(Path(__file__).parent / "configs.ini")


def get_config(section, key, env_key=None, default=None, *, raw=False):
    """
    Unified configuration getter.

    Environment variables take precedence on every platform, including an
    explicitly empty value. configs.ini supplies values that are not in env.
    """

    environment_key = env_key or key.upper()
    if environment_key in os.environ:
        return os.environ[environment_key]
    return config.get(section, key, fallback=default, raw=raw)


# -----------------------------
# Flask
# -----------------------------
SECRET_KEY = get_config("Flask", "secret_key", "FLASK_SECRET_KEY", "default-secret-key")


# -----------------------------
# Domains
# -----------------------------
LOCAL_DOMAIN_NAME = get_config("Domains", "local", "LOCAL_DOMAIN")
CDR_DOMAIN_NAME = get_config("Domains", "cdr", "CDR_DOMAIN")
CLOUD_DOMAIN_NAME = get_config("Domains", "cloud", "CLOUD_DOMAIN")
TB_DOMAIN_NAME = get_config("Domains", "tb", "TB_DASHBOARD_DOMAIN")


# -----------------------------
# Databases
# -----------------------------
VIRALLOADDATA_DATABASE = get_config("Databases", "ViralLoadData", "DB_VL_DATA")
# VIRALLOADSMS_DATABASE = get_config("Databases", "ViralLoadSMS", "DB_VL_SMS")
DPI_DATABASE_DATABASE = get_config("Databases", "Dpi", "DB_DPI")
HIVAD_DATABASE = get_config("Databases", "HivAdvancedDisease", "DB_HIV_AD")
TBDATA_DATABASE_DATABASE = get_config("Databases", "TBData", "DB_TB_DATA")
DICT_DATABASE_DATABASE = get_config("Databases", "Dictionary", "DB_DICT")
USER_DATABASE = get_config("Databases", "Users", "DB_USERS")
# Weekly VL lab reports (Resume table), produced by an external ETL.
REPORT_DATA_DATABASE = get_config("Databases", "ReportData", "DB_REPORT_DATA")

USERNAME = get_config("Databases", "database_user", "DB_USER")
PASSWORD = get_config("Databases", "database_password", "DB_PASSWORD")

# ReportData may live on another server, with its own login. Blank values fall
# back to the environment's server and DB_USER / DB_PASSWORD.
REPORT_DATA_HOST = get_config("Databases", "report_data_host", "REPORT_DATA_HOST")
REPORT_DATA_USER = (
    get_config("Databases", "report_data_user", "REPORT_DATA_USER") or USERNAME
)
REPORT_DATA_PASSWORD = (
    get_config("Databases", "report_data_password", "REPORT_DATA_PASSWORD") or PASSWORD
)


# -----------------------------
# Schemas
# -----------------------------
CDR_DOMAIN_NAME_SCHEMA = get_config("Schemas", "cdr_schema", "SCHEMA_CDR")


# -----------------------------
# Clerk
# -----------------------------
CLERK_WEBHOOK_SECRET_KEY = get_config(
    "Clerk", "clerk_webhook_secret", "CLERK_WEBHOOK_SECRET_KEY"
)

CLERK_SECRET_KEY = get_config("Clerk", "secret_key", "CLERK_SECRET_KEY")
CLERK_API_URL = get_config("Clerk", "api_endpoint", "CLERK_API_URL")
CLERK_JWTS_URL = get_config("Clerk", "clerk_jwts_url", "CLERK_JWTS_URL")
CLERK_ISSUER = get_config("Clerk", "clerk_issuer", "CLERK_ISSUER")
CLERK_PUBLIC_KEY = get_config("Clerk", "clerk_public_key", "CLERK_PUBLIC_KEY")
# Optional comma-separated list of origins allowed in a Clerk token's ``azp``
# claim (e.g. "https://tb.openldr.org.mz,https://vl.openldr.org.mz").
# Empty means the azp claim is not checked.
CLERK_AUTHORIZED_PARTIES = get_config(
    "Clerk", "clerk_authorized_parties", "CLERK_AUTHORIZED_PARTIES"
)


# -----------------------------
# API service accounts
# -----------------------------
# Comma-separated user_name values allowed to POST /auth/login when PERMISSIONS_ENFORCED is on.
API_SERVICE_ACCOUNTS = get_config("Auth", "api_service_accounts", "API_SERVICE_ACCOUNTS")


# -----------------------------
# Email / SMTP (shared doubts and suggestions)
# -----------------------------
SMTP_HOST = get_config("Email", "host", "SMTP_HOST", raw=True)
SMTP_PORT = get_config("Email", "port", "SMTP_PORT", raw=True)
SMTP_USERNAME = get_config("Email", "username", "SMTP_USERNAME", raw=True)
# Raw reads preserve literal '%' characters in SMTP credentials.
SMTP_PASSWORD = get_config("Email", "password", "SMTP_PASSWORD", raw=True)
SMTP_FROM_ADDRESS = get_config("Email", "from_address", "SMTP_FROM_ADDRESS", raw=True)
SMTP_USE_TLS = get_config("Email", "use_tls", "SMTP_USE_TLS", raw=True)
SMTP_USE_SSL = get_config("Email", "use_ssl", "SMTP_USE_SSL", "false", raw=True)
SMTP_TIMEOUT = get_config("Email", "timeout", "SMTP_TIMEOUT", "15", raw=True)


# -----------------------------
# SQL Server / ODBC
# -----------------------------
SQL_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
SQL_ODBC_POOLING = os.getenv("SQL_ODBC_POOLING", "true").strip().lower()
# pyodbc pooling is process-wide and must be configured before any connection.
pyodbc.pooling = SQL_ODBC_POOLING not in {"0", "false", "no", "off"}


def _missing(value):
    return value is None or not str(value).strip()


def _odbc_value(value):
    value = str(value)
    if any(character in value for character in ";{}") or value != value.strip():
        return "{" + value.replace("}", "}}") + "}"
    return value


def build_odbc_connection_string(user, pwd, host, db):
    missing = [
        name
        for name, value in {"user": user, "pwd": pwd, "host": host, "db": db}.items()
        if _missing(value)
    ]
    if missing:
        raise ValueError("Missing SQL connection settings: " + ", ".join(missing))

    options = [
        f"DRIVER={{{SQL_ODBC_DRIVER}}}",
        f"SERVER={_odbc_value(host)}",
        f"DATABASE={_odbc_value(db)}",
        f"UID={_odbc_value(user)}",
        f"PWD={_odbc_value(pwd)}",
        "Encrypt=yes",
        "TrustServerCertificate=yes",
        "MARS_Connection=No",
        "APP=OpenLDR API",
    ]

    return ";".join(options) + ";"


SQL_CONNECTION_OPTIONS = {
    "driver": SQL_ODBC_DRIVER,
    "Encrypt": "yes",
    "TrustServerCertificate": "yes",
    "MARS_Connection": "No",
    "APP": "OpenLDR API",
    # Diagnostic metadata only; pooling is set through pyodbc, not ODBC attrs.
    "Pooling": "Default" if pyodbc.pooling else "No",
}


# -----------------------------
# SQLAlchemy URL Builder
# -----------------------------
def make_url(user, pwd, host, db):
    connection_string = build_odbc_connection_string(user, pwd, host, db)

    return URL.create(
        "mssql+pyodbc",
        query={"odbc_connect": connection_string},
    )


# -----------------------------
# SQLAlchemy Binds
# -----------------------------
_DOMAIN_SETTINGS = {
    "local": (LOCAL_DOMAIN_NAME, "LOCAL_DOMAIN ([Domains] local)"),
    "cdr": (CDR_DOMAIN_NAME, "CDR_DOMAIN ([Domains] cdr)"),
    "cloud": (CLOUD_DOMAIN_NAME, "CLOUD_DOMAIN ([Domains] cloud)"),
}

_DATABASE_SETTINGS = {
    "vl": (VIRALLOADDATA_DATABASE, "DB_VL_DATA ([Databases] ViralLoadData)"),
    "dpi": (DPI_DATABASE_DATABASE, "DB_DPI ([Databases] Dpi)"),
    "ad": (HIVAD_DATABASE, "DB_HIV_AD ([Databases] HivAdvancedDisease)"),
    "tb": (TBDATA_DATABASE_DATABASE, "DB_TB_DATA ([Databases] TBData)"),
    "dict": (DICT_DATABASE_DATABASE, "DB_DICT ([Databases] Dictionary)"),
    "users": (USER_DATABASE, "DB_USERS ([Databases] Users)"),
    "reportData": (REPORT_DATA_DATABASE, "DB_REPORT_DATA ([Databases] ReportData)"),
}


def _bind_settings(domain, bind_key):
    host = _DOMAIN_SETTINGS[domain]
    user = (USERNAME, "DB_USER ([Databases] database_user)")
    password = (PASSWORD, "DB_PASSWORD ([Databases] database_password)")
    if bind_key == "reportData":
        if REPORT_DATA_HOST:
            host = (REPORT_DATA_HOST, "REPORT_DATA_HOST ([Databases] report_data_host)")
        user = (
            REPORT_DATA_USER,
            "REPORT_DATA_USER / DB_USER ([Databases] report_data_user / database_user)",
        )
        password = (
            REPORT_DATA_PASSWORD,
            "REPORT_DATA_PASSWORD / DB_PASSWORD ([Databases] report_data_password / database_password)",
        )
    return {
        "user": user,
        "pwd": password,
        "host": host,
        "db": _DATABASE_SETTINGS[bind_key],
    }


def get_sqlalchemy_binds(domain, bind_keys=None):
    """Validate and build only the requested environment and database binds.

    Errors identify configuration names, never their values. Merely importing
    this module does not require every environment/database to be configured.
    """
    if domain not in _DOMAIN_SETTINGS:
        raise ValueError("SQL environment must be one of: local, cdr, cloud")
    keys = list(_DATABASE_SETTINGS) if bind_keys is None else list(bind_keys)
    if any(key not in _DATABASE_SETTINGS for key in keys):
        raise ValueError("Unknown SQL bind; expected: " + ", ".join(_DATABASE_SETTINGS))

    settings = {key: _bind_settings(domain, key) for key in keys}
    missing = list(
        dict.fromkeys(
            name
            for fields in settings.values()
            for value, name in fields.values()
            if _missing(value)
        )
    )
    if missing:
        raise ValueError(
            "Missing SQL configuration. Set environment variables or configs.ini: "
            + "; ".join(missing)
        )
    return {
        key: make_url(**{field: value for field, (value, _) in fields.items()})
        for key, fields in settings.items()
    }


def _configured_binds(domain):
    # Compatibility for existing imports: keep valid binds without making
    # unrelated or incomplete environments prevent configuration/tool imports.
    keys = [
        key
        for key in _DATABASE_SETTINGS
        if all(not _missing(value) for value, _ in _bind_settings(domain, key).values())
    ]
    return get_sqlalchemy_binds(domain, keys)


SQLALCHEMY_BINDS_APHL_OPENLDR_ORG_MZ = _configured_binds("local")
SQLALCHEMY_BINDS_CDR_OPENLDR_ORG_MZ = _configured_binds("cdr")
SQLALCHEMY_BINDS_CLOUD_QUEUE_OPENLDR_ORG_MZ = _configured_binds("cloud")
