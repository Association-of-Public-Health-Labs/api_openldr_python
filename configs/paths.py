import os
import platform
import configparser
from pathlib import Path
from sqlalchemy.engine import URL

IS_WINDOWS = platform.system() == "Windows"

# -----------------------------
# Load configuration
# -----------------------------
config = None

if IS_WINDOWS:
    config = configparser.ConfigParser()
    config.read(Path(__file__).parent / "configs.ini")


def get_config(section, key, env_key=None, default=None):
    """
    Unified configuration getter.

    Windows  -> configs.ini
    Linux    -> environment variables
    """

    if IS_WINDOWS:
        return config.get(section, key, fallback=default)
    else:
        return os.environ.get(env_key or key.upper(), default)


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

USERNAME = get_config("Databases", "database_user", "DB_USER")
PASSWORD = get_config("Databases", "database_password", "DB_PASSWORD")


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


# -----------------------------
# SQL Server / ODBC
# -----------------------------
SQL_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
SQL_ODBC_POOLING = os.getenv("SQL_ODBC_POOLING", "true").strip().lower()


def build_odbc_connection_string(user, pwd, host, db):
    options = [
        f"DRIVER={{{SQL_ODBC_DRIVER}}}",
        f"SERVER={host}",
        f"DATABASE={db}",
        f"UID={user}",
        f"PWD={pwd}",
        "Encrypt=yes",
        "TrustServerCertificate=yes",
        "Connection Timeout=30",
        "MARS_Connection=No",
        "APP=OpenLDR API",
    ]

    if SQL_ODBC_POOLING in {"0", "false", "no", "off"}:
        options.append("Pooling=No")

    return ";".join(options) + ";"


SQL_CONNECTION_OPTIONS = {
    "driver": SQL_ODBC_DRIVER,
    "Encrypt": "yes",
    "TrustServerCertificate": "yes",
    "Connection Timeout": "30",
    "MARS_Connection": "No",
    "APP": "OpenLDR API",
    "Pooling": "No" if SQL_ODBC_POOLING in {"0", "false", "no", "off"} else "Default",
}


# -----------------------------
# SQLAlchemy URL Builder
# -----------------------------
def make_url(user, pwd, host, db):
    connection_string = build_odbc_connection_string(user, pwd, host, db)

    print(f"Connection string for {db}: {connection_string}")  # Debugging line

    return URL.create(
        "mssql+pyodbc",
        query={"odbc_connect": connection_string},
    )


# -----------------------------
# SQLAlchemy Binds
# -----------------------------
SQLALCHEMY_BINDS_APHL_OPENLDR_ORG_MZ = {
    # "vlSMS": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, VIRALLOADSMS_DATABASE),
    "vl": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, VIRALLOADDATA_DATABASE),
    "dpi": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, DPI_DATABASE_DATABASE),
    "ad": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, HIVAD_DATABASE),
    "tb": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, TBDATA_DATABASE_DATABASE),
    "dict": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, DICT_DATABASE_DATABASE),
    "users": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, USER_DATABASE),
}

SQLALCHEMY_BINDS_CDR_OPENLDR_ORG_MZ = {
    # "vlSMS": make_url(USERNAME, PASSWORD, CDR_DOMAIN_NAME, VIRALLOADSMS_DATABASE or VIRALLOADDATA_DATABASE),
    "vl": make_url(USERNAME, PASSWORD, CDR_DOMAIN_NAME, VIRALLOADDATA_DATABASE),
    "dpi": make_url(USERNAME, PASSWORD, CDR_DOMAIN_NAME, DPI_DATABASE_DATABASE),
    "ad": make_url(USERNAME, PASSWORD, CDR_DOMAIN_NAME, HIVAD_DATABASE),
    "tb": make_url(USERNAME, PASSWORD, CDR_DOMAIN_NAME, TBDATA_DATABASE_DATABASE),
    "dict": make_url(USERNAME, PASSWORD, CDR_DOMAIN_NAME, DICT_DATABASE_DATABASE),
    "users": make_url(USERNAME, PASSWORD, CDR_DOMAIN_NAME, USER_DATABASE),
}

SQLALCHEMY_BINDS_CLOUD_QUEUE_OPENLDR_ORG_MZ = {
    "vl": make_url(USERNAME, PASSWORD, CLOUD_DOMAIN_NAME, VIRALLOADDATA_DATABASE),
    "dpi": make_url(USERNAME, PASSWORD, CLOUD_DOMAIN_NAME, DPI_DATABASE_DATABASE),
    "ad": make_url(USERNAME, PASSWORD, CLOUD_DOMAIN_NAME, HIVAD_DATABASE),
    "tb": make_url(USERNAME, PASSWORD, CLOUD_DOMAIN_NAME, TBDATA_DATABASE_DATABASE),
    "dict": make_url(USERNAME, PASSWORD, CLOUD_DOMAIN_NAME, DICT_DATABASE_DATABASE),
    "users": make_url(USERNAME, PASSWORD, CLOUD_DOMAIN_NAME, USER_DATABASE),
}
