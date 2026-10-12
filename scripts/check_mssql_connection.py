import os
import re
import sys
import time
import argparse
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configs.paths import (  # noqa: E402
    CDR_DOMAIN_NAME,
    DPI_DATABASE_DATABASE,
    SQL_CONNECTION_OPTIONS,
    SQLALCHEMY_BINDS_CDR_OPENLDR_ORG_MZ,
    TBDATA_DATABASE_DATABASE,
    VIRALLOADDATA_DATABASE,
)


BIND_DIAGNOSTICS = {
    "vl": {
        "database": VIRALLOADDATA_DATABASE,
        "table": "VlData",
    },
    "dpi": {
        "database": DPI_DATABASE_DATABASE,
        "table": "EIDMaster",
    },
    "tb": {
        "database": TBDATA_DATABASE_DATABASE,
        "table": "TBMaster",
    },
}


def _sanitize_error(value):
    message = str(value)
    message = re.sub(r"(PWD|Password)=([^;'\"]+)", r"\1=***", message, flags=re.IGNORECASE)
    message = re.sub(r"(UID|User ID)=([^;'\"]+)", r"\1=***", message, flags=re.IGNORECASE)
    return message


def _env_flag_enabled(name):
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    value = os.getenv(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        print(f"Invalid {name}={value!r}; using {default}", file=sys.stderr)
        return int(default)


def build_engine_options():
    options = {
        "connect_args": {
            "timeout": _env_int("SQL_QUERY_TIMEOUT", "180"),
        },
    }

    if _env_flag_enabled("SQLALCHEMY_DISABLE_POOLING"):
        options["poolclass"] = NullPool
        return options

    options.update(
        {
            "pool_pre_ping": True,
            "pool_recycle": 1800,
            "pool_timeout": 30,
            "pool_size": _env_int("SQLALCHEMY_POOL_SIZE", "5"),
            "max_overflow": _env_int("SQLALCHEMY_MAX_OVERFLOW", "10"),
        }
    )
    return options


def _check_bind(bind_key, url, engine_options):
    diagnostics = BIND_DIAGNOSTICS[bind_key]
    started = time.perf_counter()
    engine = create_engine(url, **engine_options)
    try:
        with engine.connect() as connection:
            select_one = connection.execute(text("SELECT 1")).scalar_one()
            server_name = connection.execute(text("SELECT @@SERVERNAME")).scalar_one()
            service_name = connection.execute(text("SELECT @@SERVICENAME")).scalar_one()
            db_name = connection.execute(text("SELECT DB_NAME()")).scalar_one()
            row_count = connection.execute(
                text(f"SELECT COUNT_BIG(*) FROM dbo.{diagnostics['table']}")
            ).scalar_one()
    finally:
        engine.dispose()

    elapsed = time.perf_counter() - started
    print(f"[{bind_key}] status=ok")
    print(f"[{bind_key}] select_1={select_one}")
    print(f"[{bind_key}] SERVERNAME={server_name}")
    print(f"[{bind_key}] SERVICENAME={service_name}")
    print(f"[{bind_key}] DATABASE={db_name}")
    print(f"[{bind_key}] TABLE=dbo.{diagnostics['table']}")
    print(f"[{bind_key}] row_count={row_count}")
    print(f"[{bind_key}] elapsed_seconds={elapsed:.3f}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Check OpenLDR SQL Server binds.")
    parser.add_argument(
        "--bind",
        choices=["all", *BIND_DIAGNOSTICS.keys()],
        default="all",
        help="Bind to test. Defaults to all.",
    )
    args = parser.parse_args()

    engine_options = build_engine_options()
    bind_keys = list(BIND_DIAGNOSTICS) if args.bind == "all" else [args.bind]

    print("OpenLDR MSSQL connectivity check")
    print(f"host={CDR_DOMAIN_NAME}")
    print(
        "databases="
        + str({bind_key: BIND_DIAGNOSTICS[bind_key]["database"] for bind_key in bind_keys})
    )
    print(f"driver={SQL_CONNECTION_OPTIONS.get('driver')}")
    print(f"encrypt={SQL_CONNECTION_OPTIONS.get('Encrypt')}")
    print(f"trustServerCertificate={SQL_CONNECTION_OPTIONS.get('TrustServerCertificate')}")
    print(f"mars={SQL_CONNECTION_OPTIONS.get('MARS_Connection')}")
    print(f"app={SQL_CONNECTION_OPTIONS.get('APP')}")
    print(f"odbc_pooling={SQL_CONNECTION_OPTIONS.get('Pooling')}")
    print(f"query_timeout={engine_options['connect_args']['timeout']}")
    print(f"pooling_disabled={_env_flag_enabled('SQLALCHEMY_DISABLE_POOLING')}")

    ok = True
    for bind_key in bind_keys:
        try:
            _check_bind(
                bind_key,
                SQLALCHEMY_BINDS_CDR_OPENLDR_ORG_MZ[bind_key],
                engine_options,
            )
        except SQLAlchemyError as exc:
            ok = False
            print(f"[{bind_key}] status=failed")
            print(f"[{bind_key}] error_type={exc.__class__.__name__}")
            print(f"[{bind_key}] error={_sanitize_error(exc)}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
