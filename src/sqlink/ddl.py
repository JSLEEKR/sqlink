"""DDL (Data Definition Language) builders beyond CREATE/ALTER TABLE."""

from __future__ import annotations

from typing import Any

from sqlink.dialect import Dialect


class CreateIndex:
    """Build CREATE INDEX statements.

    Usage:
        idx = CreateIndex("idx_users_email", "users", ["email"])
        idx.unique().where("active = true")
        sql = idx.build()
    """

    def __init__(self, name: str, table: str, columns: list[str]):
        self._name = name
        self._table = table
        self._columns = columns
        self._unique = False
        self._if_not_exists = False
        self._where_clause: str | None = None
        self._method: str | None = None  # btree, hash, gin, gist
        self._concurrently = False

    def unique(self) -> CreateIndex:
        self._unique = True
        return self

    def if_not_exists(self) -> CreateIndex:
        self._if_not_exists = True
        return self

    def where(self, condition: str) -> CreateIndex:
        """Partial index WHERE clause."""
        self._where_clause = condition
        return self

    def using(self, method: str) -> CreateIndex:
        """Set index method (btree, hash, gin, gist)."""
        self._method = method
        return self

    def concurrently(self) -> CreateIndex:
        """CREATE INDEX CONCURRENTLY (PostgreSQL)."""
        self._concurrently = True
        return self

    def build(self, dialect: Dialect | None = None) -> str:
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        parts = ["CREATE"]
        if self._unique:
            parts.append("UNIQUE")
        parts.append("INDEX")
        if self._concurrently:
            parts.append("CONCURRENTLY")
        if self._if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(quote(self._name))
        parts.append(f"ON {quote(self._table)}")
        if self._method:
            parts.append(f"USING {self._method}")
        cols = ", ".join(quote(c) for c in self._columns)
        parts.append(f"({cols})")
        if self._where_clause:
            parts.append(f"WHERE {self._where_clause}")
        return " ".join(parts)


class DropIndex:
    """Build DROP INDEX statements."""

    def __init__(self, name: str):
        self._name = name
        self._if_exists = False
        self._concurrently = False
        self._cascade = False

    def if_exists(self) -> DropIndex:
        self._if_exists = True
        return self

    def concurrently(self) -> DropIndex:
        self._concurrently = True
        return self

    def cascade(self) -> DropIndex:
        self._cascade = True
        return self

    def build(self, dialect: Dialect | None = None) -> str:
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        parts = ["DROP INDEX"]
        if self._concurrently:
            parts.append("CONCURRENTLY")
        if self._if_exists:
            parts.append("IF EXISTS")
        parts.append(quote(self._name))
        if self._cascade:
            parts.append("CASCADE")
        return " ".join(parts)


class Truncate:
    """Build TRUNCATE TABLE statements.

    Usage:
        Truncate("users").cascade().restart_identity().build()
    """

    def __init__(self, *tables: str):
        self._tables = list(tables)
        self._cascade = False
        self._restart_identity = False
        self._only = False

    def cascade(self) -> Truncate:
        self._cascade = True
        return self

    def restart_identity(self) -> Truncate:
        self._restart_identity = True
        return self

    def only(self) -> Truncate:
        """TRUNCATE ONLY (no child tables)."""
        self._only = True
        return self

    def build(self, dialect: Dialect | None = None) -> str:
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        parts = ["TRUNCATE TABLE"]
        if self._only:
            parts.append("ONLY")
        tables = ", ".join(quote(t) for t in self._tables)
        parts.append(tables)
        if self._restart_identity:
            parts.append("RESTART IDENTITY")
        if self._cascade:
            parts.append("CASCADE")
        return " ".join(parts)


class CreateView:
    """Build CREATE VIEW statements.

    Usage:
        view = CreateView("active_users", Query("users").select("*").where(F("active") == True))
        sql = view.build()
    """

    def __init__(self, name: str, query: Any):
        self._name = name
        self._query = query
        self._or_replace = False
        self._materialized = False
        self._columns: list[str] = []

    def or_replace(self) -> CreateView:
        self._or_replace = True
        return self

    def materialized(self) -> CreateView:
        self._materialized = True
        return self

    def columns(self, *cols: str) -> CreateView:
        self._columns = list(cols)
        return self

    def build(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        parts = ["CREATE"]
        if self._or_replace:
            parts.append("OR REPLACE")
        if self._materialized:
            parts.append("MATERIALIZED")
        parts.append("VIEW")
        parts.append(quote(self._name))
        if self._columns:
            cols = ", ".join(quote(c) for c in self._columns)
            parts.append(f"({cols})")
        parts.append("AS")

        query_sql, query_params = self._query.build(dialect)
        parts.append(query_sql)
        return " ".join(parts), query_params


class DropView:
    """Build DROP VIEW statements."""

    def __init__(self, name: str):
        self._name = name
        self._if_exists = False
        self._materialized = False
        self._cascade = False

    def if_exists(self) -> DropView:
        self._if_exists = True
        return self

    def materialized(self) -> DropView:
        self._materialized = True
        return self

    def cascade(self) -> DropView:
        self._cascade = True
        return self

    def build(self, dialect: Dialect | None = None) -> str:
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        parts = ["DROP"]
        if self._materialized:
            parts.append("MATERIALIZED")
        parts.append("VIEW")
        if self._if_exists:
            parts.append("IF EXISTS")
        parts.append(quote(self._name))
        if self._cascade:
            parts.append("CASCADE")
        return " ".join(parts)
