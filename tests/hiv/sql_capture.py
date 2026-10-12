"""
Capture the queries a service would run, compiled for SQL Server.

Services finish their SQLAlchemy queries with ``.all()``, ``.one()`` or
``.count()``. Patching those lets a test run a real service with no
database and inspect the exact SQL it would send.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Query


def to_sql(query):
    """Compile a Query, select or clause with literal values, on one line."""
    statement = getattr(query, "statement", query)
    compiled = statement.compile(
        dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}
    )
    return " ".join(str(compiled).split())


@contextmanager
def captured_queries(results=None):
    """Record every Query that reaches ``.all()`` / ``.one()``.

    ``results`` is an optional list of return values handed out, in order,
    to successive ``.all()`` calls. Once it runs out, ``.all()`` returns [].
    ``.count()`` always returns 0.
    """
    queries = []
    pending = list(results or [])

    def fake_all(self):
        queries.append(self)
        return pending.pop(0) if pending else []

    def fake_one(self):
        queries.append(self)
        return MagicMock()

    with patch.object(Query, "all", fake_all), patch.object(
        Query, "one", fake_one
    ), patch.object(Query, "count", lambda self: 0):
        yield queries


def service_sql(app, service, req_args, results=None):
    """Run ``service`` with no database; return (result, [sql, ...])."""
    with app.app_context(), captured_queries(results) as queries:
        result = service(dict(req_args))
        sql = [to_sql(query) for query in queries]
    return result, sql
