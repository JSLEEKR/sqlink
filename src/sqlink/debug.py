"""Query debugging and inspection tools for sqlink."""

from __future__ import annotations

from typing import Any

from sqlink.dialect import Dialect


def interpolate_params(sql: str, params: list[Any], dialect: Dialect | None = None) -> str:
    """Interpolate parameters into SQL for debugging purposes only.

    WARNING: Never use the output of this function for actual database queries.
    It is intended solely for logging and debugging.

    Args:
        sql: SQL string with placeholders
        params: List of parameter values
        dialect: Optional dialect for placeholder format

    Returns:
        SQL string with parameters interpolated inline
    """
    result = sql
    for param in params:
        if param is None:
            replacement = "NULL"
        elif isinstance(param, bool):
            replacement = "TRUE" if param else "FALSE"
        elif isinstance(param, (int, float)):
            replacement = str(param)
        elif isinstance(param, str):
            # Escape single quotes
            escaped = param.replace("'", "''")
            replacement = f"'{escaped}'"
        else:
            replacement = f"'{param}'"

        # Replace first placeholder occurrence
        placeholder = "?"
        if dialect:
            from sqlink.dialect import PostgreSQLDialect, MySQLDialect
            if isinstance(dialect, PostgreSQLDialect):
                # For PG, find $N pattern
                import re
                match = re.search(r'\$\d+', result)
                if match:
                    result = result[:match.start()] + replacement + result[match.end():]
                    continue
            elif isinstance(dialect, MySQLDialect):
                placeholder = "%s"

        idx = result.find(placeholder)
        if idx >= 0:
            result = result[:idx] + replacement + result[idx + len(placeholder):]

    return result


def explain_query(sql: str, params: list[Any]) -> dict[str, Any]:
    """Analyze a built query and return information about it.

    Returns:
        Dictionary with query analysis info
    """
    sql_upper = sql.upper().strip()

    # Determine query type
    query_type = "UNKNOWN"
    for qt in ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH"):
        if sql_upper.startswith(qt):
            query_type = qt
            break

    # Count clauses
    clauses = {
        "JOIN": sql_upper.count(" JOIN "),
        "WHERE": 1 if " WHERE " in sql_upper else 0,
        "GROUP BY": 1 if " GROUP BY " in sql_upper else 0,
        "HAVING": 1 if " HAVING " in sql_upper else 0,
        "ORDER BY": 1 if " ORDER BY " in sql_upper else 0,
        "LIMIT": 1 if " LIMIT " in sql_upper else 0,
        "OFFSET": 1 if " OFFSET " in sql_upper else 0,
        "UNION": sql_upper.count(" UNION "),
        "SUBQUERY": sql.count("(SELECT"),
        "CTE": sql_upper.count(" AS (SELECT"),
    }

    # Count parameters
    param_count = len(params)

    # Estimate complexity (rough heuristic)
    complexity = 1
    complexity += clauses["JOIN"] * 2
    complexity += clauses["SUBQUERY"] * 3
    complexity += clauses["CTE"] * 2
    complexity += clauses["UNION"]
    if clauses["GROUP BY"]:
        complexity += 1
    if clauses["HAVING"]:
        complexity += 1

    complexity_label = "simple"
    if complexity > 5:
        complexity_label = "complex"
    elif complexity > 2:
        complexity_label = "moderate"

    return {
        "type": query_type,
        "sql": sql,
        "params": params,
        "param_count": param_count,
        "clauses": clauses,
        "length": len(sql),
        "complexity": complexity_label,
    }


def format_sql(sql: str) -> str:
    """Pretty-format a SQL string with line breaks and indentation.

    Args:
        sql: Raw SQL string

    Returns:
        Formatted SQL string
    """
    keywords = [
        "SELECT", "FROM", "WHERE", "AND", "OR",
        "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN",
        "CROSS JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN",
        "GROUP BY", "HAVING", "ORDER BY",
        "LIMIT", "OFFSET",
        "INSERT INTO", "VALUES",
        "UPDATE", "SET",
        "DELETE FROM",
        "RETURNING",
        "ON CONFLICT",
        "UNION ALL", "UNION", "INTERSECT", "EXCEPT",
        "WITH RECURSIVE", "WITH",
        "FOR UPDATE", "FOR SHARE",
    ]

    result = sql
    for kw in sorted(keywords, key=len, reverse=True):
        # Add newline before keyword (but not at start)
        import re
        pattern = re.compile(r'(?<!^)\b' + re.escape(kw) + r'\b', re.IGNORECASE)
        result = pattern.sub(f"\n  {kw}", result)

    # Clean up double newlines
    while "\n\n" in result:
        result = result.replace("\n\n", "\n")

    return result.strip()
