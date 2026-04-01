import os
import platform
import configparser
from pathlib import Path
from urllib.parse import quote_plus

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
VIRALLOADSMS_DATABASE = get_config("Databases", "ViralLoadSMS", "DB_VL_SMS")
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
# SQLAlchemy URL Builder
# -----------------------------
# def make_url(user, pwd, host, db):
#     return f"mssql+pyodbc://{user}:{pwd}@{host}/{db}?driver=ODBC+Driver+18+for+SQL+Server"

def make_url(user, pwd, host, db):
    params = quote_plus(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={host};"
        f"DATABASE={db};"
        f"UID={user};"
        f"PWD={pwd};"
        "TrustServerCertificate=yes;"
    )

    return f"mssql+pyodbc:///?odbc_connect={params}"


# -----------------------------
# SQLAlchemy Binds
# -----------------------------
SQLALCHEMY_BINDS_APHL_OPENLDR_ORG_MZ = {
    "vlSMS": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, VIRALLOADSMS_DATABASE),
    "vl": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, VIRALLOADDATA_DATABASE),
    "dpi": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, DPI_DATABASE_DATABASE),
    "ad": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, HIVAD_DATABASE),
    "tb": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, TBDATA_DATABASE_DATABASE),
    "dict": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, DICT_DATABASE_DATABASE),
    "users": make_url(USERNAME, PASSWORD, LOCAL_DOMAIN_NAME, USER_DATABASE),
}

SQLALCHEMY_BINDS_CDR_OPENLDR_ORG_MZ = {
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