"""Core query builder with fluent chain API for sqlink."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sqlink.dialect import Dialect, PostgreSQLDialect
from sqlink.expressions import Expr, F, Raw, Func, OrderExpr, Subquery
from sqlink.types import JoinType, OrderDirection


def _sanitize_comment(text: str) -> str:
    """Strip comment-closing sequences to prevent SQL comment injection."""
    return text.replace("*/", "* /").replace("/*", "/ *")


@dataclass
class _JoinClause:
    join_type: JoinType
    table: str
    alias: str | None
    on_expr: Expr | None
    on_raw: str | None


@dataclass
class _CTEClause:
    name: str
    query: Any  # Query builder
    recursive: bool = False


class Query:
    """Fluent SQL query builder.

    Usage:
        q = Query("users").select("id", "name").where(F("age") > 18)
        sql, params = q.build()
        # -> 'SELECT id, name FROM users WHERE age > ?', [18]
    """

    def __init__(self, table: str | None = None, alias: str | None = None):
        self._table = table
        self._table_alias = alias
        self._dialect: Dialect | None = None
        self._type: str = "SELECT"
        self._columns: list[str | Expr] = []
        self._distinct: bool = False
        self._where_clauses: list[Expr] = []
        self._joins: list[_JoinClause] = []
        self._group_by: list[str] = []
        self._having: list[Expr] = []
        self._order_by: list[str | OrderExpr] = []
        self._limit: int | None = None
        self._offset: int | None = None
        self._insert_columns: list[str] = []
        self._insert_values: list[list[Any]] = []
        self._update_sets: dict[str, Any] = {}
        self._returning: list[str] = []
        self._conflict_columns: list[str] = []
        self._conflict_update: list[str] = []
        self._conflict_action: str | None = None
        self._ctes: list[_CTEClause] = []
        self._union_queries: list[tuple[str, Any]] = []
        self._subquery_from: Subquery | None = None
        self._lock: str | None = None
        self._distinct_on: list[str] = []
        self._insert_from_select: Query | None = None
        self._comment: str | None = None
        self._label: str | None = None

    def clone(self) -> Query:
        """Return a deep copy of this query for safe reuse."""
        return deepcopy(self)

    def __repr__(self) -> str:
        """Return a string representation of the query."""
        try:
            sql, params = self.build()
            if params:
                return f"Query({sql!r}, params={params!r})"
            return f"Query({sql!r})"
        except Exception:
            return f"Query(table={self._table!r}, type={self._type!r})"

    def __str__(self) -> str:
        """Return the SQL string."""
        try:
            sql, _ = self.build()
            return sql
        except Exception:
            return f"<Query {self._type} on {self._table}>"

    def dialect(self, d: Dialect) -> Query:
        """Set the SQL dialect for this query."""
        self._dialect = d
        return self

    def comment(self, text: str) -> Query:
        """Add a SQL comment to the query (/* ... */)."""
        self._comment = _sanitize_comment(text)
        return self

    def label(self, name: str) -> Query:
        """Add a label/tag comment (/* app:label */) for query tracing."""
        self._label = _sanitize_comment(name)
        return self

    # ── SELECT ──────────────────────────────────────────────

    def select(self, *columns: str | Expr) -> Query:
        """Set columns to select."""
        self._type = "SELECT"
        self._columns = list(columns)
        return self

    def select_all(self) -> Query:
        """SELECT *."""
        self._type = "SELECT"
        self._columns = ["*"]
        return self

    def add_select(self, *columns: str | Expr) -> Query:
        """Add columns to existing select."""
        self._columns.extend(columns)
        return self

    def distinct(self) -> Query:
        """Add DISTINCT to SELECT."""
        self._distinct = True
        return self

    def distinct_on(self, *columns: str) -> Query:
        """Add DISTINCT ON (columns) — PostgreSQL only."""
        self._distinct = True
        self._distinct_on = list(columns)
        return self

    # ── FROM ────────────────────────────────────────────────

    def from_table(self, table: str, alias: str | None = None) -> Query:
        """Set the FROM table (alternative to constructor)."""
        self._table = table
        self._table_alias = alias
        return self

    def from_subquery(self, subquery: Query, alias: str) -> Query:
        """Use a subquery as the FROM source."""
        self._subquery_from = Subquery(subquery, alias)
        return self

    # ── WHERE ───────────────────────────────────────────────

    def where(self, *conditions: Expr) -> Query:
        """Add WHERE conditions (AND)."""
        self._where_clauses.extend(conditions)
        return self

    def where_raw(self, sql: str, params: list[Any] | None = None) -> Query:
        """Add raw WHERE clause."""
        self._where_clauses.append(Raw(sql, params))
        return self

    # ── JOIN ────────────────────────────────────────────────

    def join(
        self,
        table: str,
        on: Expr | None = None,
        alias: str | None = None,
        join_type: JoinType = JoinType.INNER,
    ) -> Query:
        """Add a JOIN clause."""
        self._joins.append(_JoinClause(join_type, table, alias, on, None))
        return self

    def left_join(self, table: str, on: Expr, alias: str | None = None) -> Query:
        return self.join(table, on, alias, JoinType.LEFT)

    def right_join(self, table: str, on: Expr, alias: str | None = None) -> Query:
        return self.join(table, on, alias, JoinType.RIGHT)

    def full_join(self, table: str, on: Expr, alias: str | None = None) -> Query:
        return self.join(table, on, alias, JoinType.FULL)

    def cross_join(self, table: str, alias: str | None = None) -> Query:
        self._joins.append(_JoinClause(JoinType.CROSS, table, alias, None, None))
        return self

    def join_raw(self, raw_sql: str) -> Query:
        """Add a raw JOIN clause."""
        self._joins.append(_JoinClause(JoinType.INNER, "", None, None, raw_sql))
        return self

    # ── GROUP BY / HAVING ───────────────────────────────────

    def group_by(self, *columns: str) -> Query:
        self._group_by.extend(columns)
        return self

    def having(self, *conditions: Expr) -> Query:
        self._having.extend(conditions)
        return self

    # ── ORDER BY ────────────────────────────────────────────

    def order_by(self, *columns: str | OrderExpr) -> Query:
        self._order_by.extend(columns)
        return self

    def order_by_asc(self, column: str) -> Query:
        self._order_by.append(OrderExpr(column, "ASC"))
        return self

    def order_by_desc(self, column: str) -> Query:
        self._order_by.append(OrderExpr(column, "DESC"))
        return self

    # ── LIMIT / OFFSET ──────────────────────────────────────

    def limit(self, n: int) -> Query:
        self._limit = n
        return self

    def offset(self, n: int) -> Query:
        self._offset = n
        return self

    def paginate(self, page: int, per_page: int) -> Query:
        """Set pagination: page is 1-indexed."""
        self._limit = per_page
        self._offset = (page - 1) * per_page
        return self

    # ── INSERT ──────────────────────────────────────────────

    def insert(self, *columns: str) -> Query:
        """Start an INSERT query."""
        self._type = "INSERT"
        self._insert_columns = list(columns)
        return self

    def values(self, *rows: dict[str, Any] | list[Any] | tuple[Any, ...]) -> Query:
        """Add values for INSERT."""
        for row in rows:
            if isinstance(row, dict):
                if not self._insert_columns:
                    self._insert_columns = list(row.keys())
                self._insert_values.append(
                    [row.get(c) for c in self._insert_columns]
                )
            elif isinstance(row, (list, tuple)):
                self._insert_values.append(list(row))
        return self

    def from_select(self, select_query: Query) -> Query:
        """INSERT INTO ... SELECT ... (insert from select query)."""
        self._insert_from_select = select_query
        return self

    def on_conflict(
        self,
        columns: list[str],
        action: str = "UPDATE",
        update_columns: list[str] | None = None,
    ) -> Query:
        """Handle INSERT conflicts (upsert)."""
        self._conflict_columns = columns
        self._conflict_action = action
        self._conflict_update = update_columns or [
            c for c in self._insert_columns if c not in columns
        ]
        return self

    def on_conflict_do_nothing(self, columns: list[str]) -> Query:
        """INSERT ... ON CONFLICT DO NOTHING."""
        self._conflict_columns = columns
        self._conflict_action = "NOTHING"
        return self

    # ── UPDATE ──────────────────────────────────────────────

    def update(self, **kwargs: Any) -> Query:
        """Start an UPDATE query with column=value pairs."""
        self._type = "UPDATE"
        self._update_sets.update(kwargs)
        return self

    def set(self, column: str, value: Any) -> Query:
        """Set a column value for UPDATE."""
        self._update_sets[column] = value
        return self

    # ── DELETE ──────────────────────────────────────────────

    def delete(self) -> Query:
        """Start a DELETE query."""
        self._type = "DELETE"
        return self

    # ── RETURNING ───────────────────────────────────────────

    def returning(self, *columns: str) -> Query:
        """Add RETURNING clause."""
        self._returning.extend(columns)
        return self

    # ── CTE (WITH) ──────────────────────────────────────────

    def with_cte(self, name: str, query: Query, recursive: bool = False) -> Query:
        """Add a Common Table Expression."""
        self._ctes.append(_CTEClause(name, query, recursive))
        return self

    # ── UNION ───────────────────────────────────────────────

    def union(self, other: Query) -> Query:
        self._union_queries.append(("UNION", other))
        return self

    def union_all(self, other: Query) -> Query:
        self._union_queries.append(("UNION ALL", other))
        return self

    def intersect(self, other: Query) -> Query:
        self._union_queries.append(("INTERSECT", other))
        return self

    def except_(self, other: Query) -> Query:
        self._union_queries.append(("EXCEPT", other))
        return self

    # ── LOCK ────────────────────────────────────────────────

    def for_update(self) -> Query:
        self._lock = "FOR UPDATE"
        return self

    def for_share(self) -> Query:
        self._lock = "FOR SHARE"
        return self

    # ── BUILD ───────────────────────────────────────────────

    def build(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        """Build the SQL query string and parameters."""
        d = dialect or self._dialect or Dialect()
        if isinstance(d, PostgreSQLDialect):
            d.reset_counter()

        parts: list[str] = []
        params: list[Any] = []

        # Comment / Label
        if self._label:
            parts.append(f"/* {self._label} */")
        elif self._comment:
            parts.append(f"/* {self._comment} */")

        # CTEs
        if self._ctes:
            cte_parts = []
            recursive = any(c.recursive for c in self._ctes)
            for cte in self._ctes:
                cte_sql, cte_params = cte.query.build(d)
                quote = d.quote_identifier
                cte_parts.append(f"{quote(cte.name)} AS ({cte_sql})")
                params.extend(cte_params)
            keyword = "WITH RECURSIVE" if recursive else "WITH"
            parts.append(f"{keyword} {', '.join(cte_parts)}")

        if self._type == "SELECT":
            sql, p = self._build_select(d)
        elif self._type == "INSERT":
            sql, p = self._build_insert(d)
        elif self._type == "UPDATE":
            sql, p = self._build_update(d)
        elif self._type == "DELETE":
            sql, p = self._build_delete(d)
        else:
            raise ValueError(f"Unknown query type: {self._type}")

        parts.append(sql)
        params.extend(p)

        # UNION queries
        for union_type, union_query in self._union_queries:
            u_sql, u_params = union_query.build(d)
            parts.append(f"{union_type} {u_sql}")
            params.extend(u_params)

        return " ".join(parts), params

    def sql(self, dialect: Dialect | None = None) -> str:
        """Return just the SQL string (no params)."""
        sql, _ = self.build(dialect)
        return sql

    def _build_select(self, d: Dialect | None) -> tuple[str, list[Any]]:
        parts: list[str] = []
        params: list[Any] = []
        quote = d.quote_identifier

        # SELECT
        cols = []
        for col in self._columns:
            if isinstance(col, Expr):
                s, p = col.to_sql(d)
                cols.append(s)
                params.extend(p)
            else:
                if col == "*":
                    cols.append("*")
                else:
                    cols.append(quote(col))
        if self._distinct_on:
            on_cols = ", ".join(quote(c) for c in self._distinct_on)
            distinct = f"DISTINCT ON ({on_cols}) "
        elif self._distinct:
            distinct = "DISTINCT "
        else:
            distinct = ""
        col_str = ", ".join(cols) if cols else "*"
        parts.append(f"SELECT {distinct}{col_str}")

        # FROM
        if self._subquery_from:
            s, p = self._subquery_from.to_sql(d)
            parts.append(f"FROM {s}")
            params.extend(p)
        elif self._table:
            table_ref = quote(self._table)
            if self._table_alias:
                table_ref += f" AS {quote(self._table_alias)}"
            parts.append(f"FROM {table_ref}")

        # JOINs
        for j in self._joins:
            if j.on_raw:
                parts.append(j.on_raw)
            else:
                table_ref = quote(j.table)
                if j.alias:
                    table_ref += f" AS {quote(j.alias)}"
                if j.on_expr:
                    on_sql, on_params = j.on_expr.to_sql(d)
                    parts.append(f"{j.join_type.value} {table_ref} ON {on_sql}")
                    params.extend(on_params)
                else:
                    parts.append(f"{j.join_type.value} {table_ref}")

        # WHERE
        where_sql, where_params = self._build_where(d)
        if where_sql:
            parts.append(f"WHERE {where_sql}")
            params.extend(where_params)

        # GROUP BY
        if self._group_by:
            cols = [quote(c) for c in self._group_by]
            parts.append(f"GROUP BY {', '.join(cols)}")

        # HAVING
        if self._having:
            having_parts = []
            for h in self._having:
                h_sql, h_params = h.to_sql(d)
                having_parts.append(h_sql)
                params.extend(h_params)
            parts.append(f"HAVING {' AND '.join(having_parts)}")

        # ORDER BY
        if self._order_by:
            order_parts = []
            for o in self._order_by:
                if isinstance(o, OrderExpr):
                    order_parts.append(o.to_sql(d))
                else:
                    order_parts.append(quote(o))
            parts.append(f"ORDER BY {', '.join(order_parts)}")

        # LIMIT/OFFSET
        if self._limit is not None or self._offset is not None:
            if d:
                lo = d.limit_offset_sql(self._limit, self._offset)
            else:
                lo_parts = []
                if self._limit is not None:
                    lo_parts.append(f"LIMIT {self._limit}")
                if self._offset is not None:
                    lo_parts.append(f"OFFSET {self._offset}")
                lo = " ".join(lo_parts)
            parts.append(lo)

        # LOCK
        if self._lock:
            parts.append(self._lock)

        return " ".join(parts), params

    def _build_insert(self, d: Dialect | None) -> tuple[str, list[Any]]:
        parts: list[str] = []
        params: list[Any] = []
        quote = d.quote_identifier
        placeholder = d.placeholder

        if self._insert_columns:
            cols = ", ".join(quote(c) for c in self._insert_columns)
            parts.append(f"INSERT INTO {quote(self._table)} ({cols})")
        else:
            parts.append(f"INSERT INTO {quote(self._table)}")

        # INSERT FROM SELECT
        if self._insert_from_select is not None:
            select_sql, select_params = self._insert_from_select.build(d)
            parts.append(select_sql)
            params.extend(select_params)
        else:
            # VALUES
            val_rows = []
            for row in self._insert_values:
                row_placeholders = []
                for v in row:
                    if isinstance(v, Expr):
                        s, p = v.to_sql(d)
                        row_placeholders.append(s)
                        params.extend(p)
                    else:
                        row_placeholders.append(placeholder())
                        params.append(v)
                val_rows.append(f"({', '.join(row_placeholders)})")
            parts.append(f"VALUES {', '.join(val_rows)}")

        # ON CONFLICT
        if self._conflict_action:
            if self._conflict_action == "NOTHING":
                conflict_cols = ", ".join(quote(c) for c in self._conflict_columns)
                parts.append(f"ON CONFLICT ({conflict_cols}) DO NOTHING")
            elif d and d.supports_upsert():
                upsert_sql, upsert_params = d.upsert_sql(
                    self._conflict_columns, self._conflict_update, "?"
                )
                parts.append(upsert_sql)
                params.extend(upsert_params)
            else:
                # Generic upsert
                conflict_cols = ", ".join(quote(c) for c in self._conflict_columns)
                set_parts = [
                    f"{quote(c)} = EXCLUDED.{quote(c)}" for c in self._conflict_update
                ]
                parts.append(
                    f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {', '.join(set_parts)}"
                )

        # RETURNING
        if self._returning:
            ret_cols = ", ".join(quote(c) for c in self._returning)
            parts.append(f"RETURNING {ret_cols}")

        return " ".join(parts), params

    def _build_update(self, d: Dialect | None) -> tuple[str, list[Any]]:
        parts: list[str] = []
        params: list[Any] = []
        quote = d.quote_identifier
        placeholder = d.placeholder

        parts.append(f"UPDATE {quote(self._table)}")

        # SET
        set_parts = []
        for col, val in self._update_sets.items():
            if isinstance(val, Expr):
                s, p = val.to_sql(d)
                set_parts.append(f"{quote(col)} = {s}")
                params.extend(p)
            else:
                set_parts.append(f"{quote(col)} = {placeholder()}")
                params.append(val)
        parts.append(f"SET {', '.join(set_parts)}")

        # WHERE
        where_sql, where_params = self._build_where(d)
        if where_sql:
            parts.append(f"WHERE {where_sql}")
            params.extend(where_params)

        # RETURNING
        if self._returning:
            ret_cols = ", ".join(quote(c) for c in self._returning)
            parts.append(f"RETURNING {ret_cols}")

        return " ".join(parts), params

    def _build_delete(self, d: Dialect | None) -> tuple[str, list[Any]]:
        parts: list[str] = []
        params: list[Any] = []
        quote = d.quote_identifier

        parts.append(f"DELETE FROM {quote(self._table)}")

        # WHERE
        where_sql, where_params = self._build_where(d)
        if where_sql:
            parts.append(f"WHERE {where_sql}")
            params.extend(where_params)

        # RETURNING
        if self._returning:
            ret_cols = ", ".join(quote(c) for c in self._returning)
            parts.append(f"RETURNING {ret_cols}")

        return " ".join(parts), params

    def _build_where(self, d: Dialect | None) -> tuple[str, list[Any]]:
        if not self._where_clauses:
            return "", []
        parts = []
        params: list[Any] = []
        for clause in self._where_clauses:
            sql, p = clause.to_sql(d)
            parts.append(sql)
            params.extend(p)
        return " AND ".join(parts), params


class Table:
    """Table reference helper for building queries.

    Usage:
        users = Table("users")
        q = users.select("id", "name").where(F("active") == True)
    """

    def __init__(self, name: str, alias: str | None = None, dialect: Dialect | None = None):
        self.name = name
        self.alias = alias
        self._dialect = dialect

    def _new_query(self) -> Query:
        q = Query(self.name, self.alias)
        if self._dialect:
            q.dialect(self._dialect)
        return q

    def select(self, *columns: str | Expr) -> Query:
        return self._new_query().select(*columns)

    def select_all(self) -> Query:
        return self._new_query().select_all()

    def insert(self, *columns: str) -> Query:
        return self._new_query().insert(*columns)

    def update(self, **kwargs: Any) -> Query:
        return self._new_query().update(**kwargs)

    def delete(self) -> Query:
        return self._new_query().delete()
