"""
SQL Server rejects bound parameters inside GROUP BY (error 8120): the select
list and GROUP BY expressions must match, and pyodbc sends each bound value
as a separate ``?``. ``to_sql`` compiles with literal binds, so it cannot see
this. Compile with the real pyodbc dialect instead.
"""
import inspect
from unittest.mock import patch

import pytest
from sqlalchemy.dialects.mssql import pyodbc

from hiv.vl.services import (
    vl_services_facilities,
    vl_services_laboratory,
    vl_services_summary,
    vl_services_weekly,
)
from tests.hiv.sql_capture import captured_queries

MODULES = [
    vl_services_summary,
    vl_services_laboratory,
    vl_services_facilities,
    vl_services_weekly,
]
EXCLUDED = {"tat_vs_disalinks_service"}

SERVICES = {}
for _module in MODULES:
    for _name, _fn in inspect.getmembers(_module, inspect.isfunction):
        if (
            _name.endswith("_service")
            and _name not in EXCLUDED
            and _fn.__module__ == _module.__name__
        ):
            SERVICES[_name] = (_module, _fn)

CASES = {
    "laboratory": {
        "interval_dates": ["2025-01-01,2025-12-31"],
        "lab_code": ["PCD"],
        "age_range": "15,49",
    },
    "facility": {
        "interval_dates": ["2025-01-01,2025-12-31"],
        "facility_type": "district",
        "district": ["Chibuto"],
        "disaggregation": "true",
    },
}


def _group_by_text(sql):
    if " GROUP BY " not in sql:
        return ""
    tail = sql.rsplit(" GROUP BY ", 1)[1]
    return tail.split(" ORDER BY ", 1)[0]


@pytest.mark.parametrize("case", sorted(CASES))
@pytest.mark.parametrize("name", sorted(SERVICES))
def test_group_by_has_no_bound_parameters(app, name, case):
    module, service = SERVICES[name]
    with app.app_context(), captured_queries() as queries:
        with patch.object(
            module, "_get_user_role", create=True, return_value=("u1", "Admin")
        ):
            service(dict(CASES[case]))
        compiled = [
            " ".join(
                str(
                    getattr(q, "statement", q).compile(dialect=pyodbc.dialect(paramstyle="qmark"))
                ).split()
            )
            for q in queries
        ]
    for sql in compiled:
        assert "?" not in _group_by_text(sql), sql
