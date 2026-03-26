"""SQL query parser — tokenizes and extracts structure from SQL queries."""

from __future__ import annotations

import re

from sqlink.models import (
    ColumnReference,
    JoinClause,
    JoinType,
    ParsedQuery,
    QueryType,
    SubQuery,
    TableReference,
    WhereCondition,
)


def normalize_sql(sql: str) -> str:
    """Normalize SQL whitespace and casing for analysis."""
    sql = sql.strip().rstrip(";")
    sql = re.sub(r"\s+", " ", sql)
    return sql


def detect_query_type(sql: str) -> QueryType:
    """Detect the type of SQL query."""
    upper = sql.strip().upper()
    for qt in QueryType:
        if qt != QueryType.UNKNOWN and upper.startswith(qt.value):
            return qt
    return QueryType.UNKNOWN


def _extract_balanced_parens(sql: str, start: int) -> str | None:
    """Extract content within balanced parentheses starting at position."""
    if start >= len(sql) or sql[start] != "(":
        return None
    depth = 0
    for i in range(start, len(sql)):
        if sql[i] == "(":
            depth += 1
        elif sql[i] == ")":
            depth -= 1
            if depth == 0:
                return sql[start + 1 : i]
    return None


def _strip_string_literals(sql: str) -> str:
    """Replace string literals with placeholders to avoid false matches."""
    result = re.sub(r"'[^']*'", "'__STR__'", sql)
    result = re.sub(r'"[^"]*"', '"__STR__"', result)
    return result


def extract_subqueries(sql: str) -> list[SubQuery]:
    """Extract subqueries from SQL."""
    subqueries: list[SubQuery] = []
    stripped = _strip_string_literals(sql)
    upper = stripped.upper()

    # Find SELECT within parentheses
    pattern = re.compile(r"\(\s*SELECT\s", re.IGNORECASE)
    for match in pattern.finditer(stripped):
        start = match.start()
        content = _extract_balanced_parens(stripped, start)
        if content:
            # Determine location
            before = upper[:start].rstrip()
            location = "UNKNOWN"
            if before.endswith("IN") or before.endswith("EXISTS") or before.endswith("ANY") or before.endswith("ALL"):
                location = "WHERE"
            elif "FROM" in before and "WHERE" not in before[before.rfind("FROM") :]:
                location = "FROM"
            elif before.endswith(",") or before.endswith("SELECT"):
                location = "SELECT"
            subqueries.append(SubQuery(raw=content, location=location))

    return subqueries


def extract_tables(sql: str) -> list[TableReference]:
    """Extract table references from SQL."""
    tables: list[TableReference] = []
    normalized = normalize_sql(sql)
    upper = normalized.upper()

    # FROM clause tables
    from_match = re.search(r"\bFROM\s+", upper)
    if from_match:
        from_pos = from_match.end()
        # Find end of FROM clause (before WHERE, JOIN, GROUP, ORDER, LIMIT, HAVING, UNION, or end)
        end_keywords = r"\b(WHERE|(?:INNER|LEFT|RIGHT|FULL|CROSS|NATURAL)\s+(?:OUTER\s+)?JOIN|JOIN|GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING|UNION)\b"
        end_match = re.search(end_keywords, upper[from_pos:])
        end_pos = from_pos + end_match.start() if end_match else len(normalized)
        from_clause = normalized[from_pos:end_pos].strip()

        # Parse comma-separated table list (skip subqueries)
        if not from_clause.upper().startswith("("):
            for table_expr in _split_ignoring_parens(from_clause, ","):
                table_expr = table_expr.strip()
                if table_expr:
                    table = _parse_table_ref(table_expr)
                    if table:
                        tables.append(table)

    # INSERT INTO
    insert_match = re.search(r"\bINSERT\s+INTO\s+(\S+)", normalized, re.IGNORECASE)
    if insert_match:
        tables.append(_parse_table_name(insert_match.group(1)))

    # UPDATE
    update_match = re.search(r"\bUPDATE\s+(\S+)", normalized, re.IGNORECASE)
    if update_match:
        tables.append(_parse_table_name(update_match.group(1)))

    # DELETE FROM
    delete_match = re.search(r"\bDELETE\s+FROM\s+(\S+)", normalized, re.IGNORECASE)
    if delete_match:
        tables.append(_parse_table_name(delete_match.group(1)))

    return tables


def _split_ignoring_parens(s: str, delimiter: str) -> list[str]:
    """Split string by delimiter, ignoring content in parentheses."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in s:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == delimiter and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def _parse_table_name(name: str) -> TableReference:
    """Parse a simple table name, potentially with schema."""
    name = name.strip().strip("`\"[]")
    if "." in name:
        parts = name.split(".", 1)
        return TableReference(name=parts[1], schema=parts[0])
    return TableReference(name=name)


def _parse_table_ref(expr: str) -> TableReference | None:
    """Parse a table reference like 'table_name alias' or 'schema.table AS alias'."""
    expr = expr.strip()
    if not expr or expr.upper().startswith("("):
        return None

    # Handle AS keyword
    as_match = re.match(r"(\S+)\s+(?:AS\s+)?(\w+)\s*$", expr, re.IGNORECASE)
    if as_match:
        table = _parse_table_name(as_match.group(1))
        table.alias = as_match.group(2)
        return table

    return _parse_table_name(expr)


def extract_joins(sql: str) -> list[JoinClause]:
    """Extract JOIN clauses from SQL."""
    joins: list[JoinClause] = []
    normalized = normalize_sql(sql)

    pattern = re.compile(
        r"\b(INNER|LEFT\s+OUTER|LEFT|RIGHT\s+OUTER|RIGHT|FULL\s+OUTER|FULL|CROSS|NATURAL)?\s*JOIN\s+(\S+)(?:\s+(?:AS\s+)?(\w+))?\s*(?:ON\s+(.*?))?(?=\s+(?:INNER|LEFT|RIGHT|FULL|CROSS|NATURAL)\s+JOIN|\s+JOIN\s|\s+WHERE\b|\s+GROUP\s+BY\b|\s+ORDER\s+BY\b|\s+LIMIT\b|\s+HAVING\b|\s+UNION\b|$)",
        re.IGNORECASE,
    )

    for match in pattern.finditer(normalized):
        join_type_str = (match.group(1) or "INNER").upper().split()[0]
        try:
            jt = JoinType(join_type_str)
        except ValueError:
            jt = JoinType.INNER

        table = _parse_table_name(match.group(2))
        if match.group(3):
            table.alias = match.group(3)

        condition = match.group(4).strip() if match.group(4) else None
        joins.append(JoinClause(join_type=jt, table=table, condition=condition))

    return joins


def extract_columns(sql: str) -> tuple[list[ColumnReference], bool]:
    """Extract selected columns. Returns (columns, has_select_star)."""
    normalized = normalize_sql(sql)
    upper = normalized.upper()

    if not upper.startswith("SELECT"):
        return [], False

    # Find column list between SELECT and FROM
    select_end = 6  # len("SELECT")
    if upper[select_end:].strip().startswith("DISTINCT"):
        select_end = upper.index("DISTINCT") + 8

    from_match = re.search(r"\bFROM\b", upper[select_end:])
    if not from_match:
        col_str = normalized[select_end:].strip()
    else:
        col_str = normalized[select_end : select_end + from_match.start()].strip()

    has_star = "*" in col_str

    columns: list[ColumnReference] = []
    for part in _split_ignoring_parens(col_str, ","):
        part = part.strip()
        if not part:
            continue

        # Skip subqueries
        if "(" in part and "SELECT" in part.upper():
            continue

        # Handle aliases: col AS alias or col alias
        as_match = re.match(r"(.+?)\s+(?:AS\s+)?(\w+)\s*$", part, re.IGNORECASE)
        col_name = as_match.group(1).strip() if as_match else part

        # Handle table.column
        if "." in col_name and "(" not in col_name:
            parts = col_name.split(".", 1)
            columns.append(ColumnReference(name=parts[1], table=parts[0]))
        elif col_name != "*":
            columns.append(ColumnReference(name=col_name))

    return columns, has_star


def extract_where(sql: str) -> list[WhereCondition]:
    """Extract WHERE conditions."""
    normalized = normalize_sql(sql)
    upper = normalized.upper()

    where_match = re.search(r"\bWHERE\s+", upper)
    if not where_match:
        return []

    start = where_match.end()
    # Find end
    end_match = re.search(r"\b(GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING|UNION)\b", upper[start:])
    end = start + end_match.start() if end_match else len(normalized)
    where_clause = normalized[start:end].strip()

    if not where_clause:
        return []

    conditions: list[WhereCondition] = []

    # Split by AND (top-level)
    parts = re.split(r"\bAND\b", where_clause, flags=re.IGNORECASE)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        upper_part = part.upper()

        # Extract column refs
        cols: list[ColumnReference] = []
        col_matches = re.findall(r"\b(\w+)\.(\w+)\b", part)
        for table, col in col_matches:
            if table.upper() not in ("IS", "NOT", "AND", "OR", "IN", "LIKE", "BETWEEN"):
                cols.append(ColumnReference(name=col, table=table))

        # Single column refs (left side of comparisons)
        simple_cols = re.findall(r"^(\w+)\s*(?:[=<>!]|IS|IN|LIKE|BETWEEN)", part, re.IGNORECASE)
        for col in simple_cols:
            if col.upper() not in ("IS", "NOT", "AND", "OR", "IN", "LIKE", "BETWEEN", "EXISTS", "NULL"):
                cols.append(ColumnReference(name=col))

        cond = WhereCondition(
            raw=part,
            columns=cols,
            has_function=bool(re.search(r"\b\w+\s*\(", part) and not re.search(r"\bIN\s*\(", upper_part)),
            has_or=bool(re.search(r"\bOR\b", upper_part)),
            has_like_wildcard_prefix=bool(re.search(r"LIKE\s+'%", upper_part)),
            has_not_equal=bool(re.search(r"[!<>]=|<>|!=", part)),
            has_is_null=bool(re.search(r"\bIS\s+NULL\b", upper_part)),
            has_in_subquery=bool(re.search(r"\bIN\s*\(\s*SELECT\b", upper_part)),
        )
        conditions.append(cond)

    return conditions


def parse_query(sql: str) -> ParsedQuery:
    """Parse a SQL query into a structured representation."""
    normalized = normalize_sql(sql)
    upper = normalized.upper()

    query_type = detect_query_type(normalized)
    tables = extract_tables(normalized)
    joins = extract_joins(normalized)
    columns, has_star = extract_columns(normalized)
    where_conditions = extract_where(normalized)
    subqueries = extract_subqueries(normalized)

    # Add join tables to table list
    join_table_names = {j.table.name for j in joins}
    for join in joins:
        if join.table.name not in {t.name for t in tables}:
            tables.append(join.table)

    # Detect GROUP BY columns
    group_by_cols: list[ColumnReference] = []
    gb_match = re.search(r"\bGROUP\s+BY\s+(.*?)(?:\bHAVING\b|\bORDER\b|\bLIMIT\b|\bUNION\b|$)", upper)
    if gb_match:
        for col in gb_match.group(1).split(","):
            col = col.strip()
            if "." in col:
                parts = col.split(".", 1)
                group_by_cols.append(ColumnReference(name=parts[1].lower(), table=parts[0].lower()))
            elif col:
                group_by_cols.append(ColumnReference(name=col.lower()))

    # Detect ORDER BY columns
    order_by_cols: list[ColumnReference] = []
    ob_match = re.search(r"\bORDER\s+BY\s+(.*?)(?:\bLIMIT\b|\bUNION\b|$)", upper)
    if ob_match:
        for col in ob_match.group(1).split(","):
            col = re.sub(r"\s+(ASC|DESC)\s*$", "", col.strip(), flags=re.IGNORECASE).strip()
            if "." in col:
                parts = col.split(".", 1)
                order_by_cols.append(ColumnReference(name=parts[1].lower(), table=parts[0].lower()))
            elif col:
                order_by_cols.append(ColumnReference(name=col.lower()))

    return ParsedQuery(
        raw=normalized,
        query_type=query_type,
        tables=tables,
        columns=columns,
        joins=joins,
        where_conditions=where_conditions,
        has_select_star=has_star,
        has_distinct="DISTINCT" in upper.split("FROM")[0] if "FROM" in upper else False,
        has_group_by=bool(re.search(r"\bGROUP\s+BY\b", upper)),
        has_order_by=bool(re.search(r"\bORDER\s+BY\b", upper)),
        has_limit=bool(re.search(r"\bLIMIT\b", upper)),
        has_offset=bool(re.search(r"\bOFFSET\b", upper)),
        has_having=bool(re.search(r"\bHAVING\b", upper)),
        has_union=bool(re.search(r"\bUNION\b", upper)),
        subqueries=subqueries,
        group_by_columns=group_by_cols,
        order_by_columns=order_by_cols,
    )
