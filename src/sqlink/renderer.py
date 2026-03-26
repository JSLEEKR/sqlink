"""Query rendering utilities for sqlink — convert queries to different output formats."""

from __future__ import annotations

import json
from typing import Any

from sqlink.builder import Query
from sqlink.dialect import Dialect, PostgreSQLDialect, MySQLDialect, SQLiteDialect
from sqlink.debug import interpolate_params, explain_query


def to_dict(query: Query, dialect: Dialect | None = None) -> dict[str, Any]:
    """Render a query as a dictionary with SQL, params, and metadata.

    Returns:
        Dictionary with 'sql', 'params', 'dialect', and 'type' keys.
    """
    sql, params = query.build(dialect)
    info = explain_query(sql, params)
    return {
        "sql": sql,
        "params": params,
        "type": info["type"],
        "dialect": dialect.name() if dialect else "generic",
        "param_count": len(params),
        "complexity": info["complexity"],
    }


def to_json(query: Query, dialect: Dialect | None = None, indent: int = 2) -> str:
    """Render a query as a JSON string."""
    return json.dumps(to_dict(query, dialect), indent=indent, default=str)


def to_prepared(query: Query, dialect: Dialect | None = None) -> dict[str, Any]:
    """Render as a prepared statement format compatible with DB drivers.

    Returns:
        Dictionary with 'text' (SQL) and 'values' (params) keys,
        matching common DB driver conventions.
    """
    sql, params = query.build(dialect)
    return {"text": sql, "values": params}


def to_raw_sql(query: Query, dialect: Dialect | None = None) -> str:
    """Render as raw SQL with parameters interpolated inline.

    WARNING: Only for debugging. Never use in production queries.
    """
    sql, params = query.build(dialect)
    return interpolate_params(sql, params, dialect)


def to_all_dialects(query: Query) -> dict[str, dict[str, Any]]:
    """Render a query in all supported dialects.

    Returns:
        Dictionary mapping dialect name to {sql, params}.
    """
    dialects = {
        "postgresql": PostgreSQLDialect(),
        "mysql": MySQLDialect(),
        "sqlite": SQLiteDialect(),
        "generic": Dialect(),
    }
    result = {}
    for name, d in dialects.items():
        sql, params = query.build(d)
        result[name] = {"sql": sql, "params": params}
    return result


def render_migration(statements: list[str], separator: str = ";\n") -> str:
    """Render a list of migration SQL statements into a single script.

    Args:
        statements: List of SQL strings from AlterTable.build()
        separator: Statement separator (default: ';\\n')

    Returns:
        Combined SQL migration script.
    """
    # Ensure each statement ends with semicolon, then join with separator
    terminated = [s.rstrip(";") + ";" for s in statements]
    # Use separator without the semicolon if separator already includes it
    if separator.startswith(";"):
        return separator.join(s.rstrip(";") for s in statements) + ";"
    return separator.join(terminated)
