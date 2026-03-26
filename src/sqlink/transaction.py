"""Transaction builder for sqlink — generate transaction SQL blocks."""

from __future__ import annotations

from typing import Any

from sqlink.builder import Query
from sqlink.dialect import Dialect


class Transaction:
    """Build a sequence of SQL statements wrapped in a transaction.

    Usage:
        tx = Transaction()
        tx.add(Query("users").update(balance=100).where(F("id") == 1))
        tx.add(Query("logs").insert("action").values({"action": "update_balance"}))
        statements = tx.build()
        # -> ["BEGIN", "UPDATE ...", "INSERT ...", "COMMIT"]
    """

    def __init__(self, isolation_level: str | None = None):
        self._queries: list[Query | str] = []
        self._isolation_level = isolation_level
        self._savepoints: list[str] = []

    def add(self, query: Query | str) -> Transaction:
        """Add a query to the transaction."""
        self._queries.append(query)
        return self

    def savepoint(self, name: str) -> Transaction:
        """Add a SAVEPOINT."""
        self._queries.append(f"SAVEPOINT {name}")
        self._savepoints.append(name)
        return self

    def rollback_to(self, savepoint: str) -> Transaction:
        """Add ROLLBACK TO SAVEPOINT."""
        self._queries.append(f"ROLLBACK TO SAVEPOINT {savepoint}")
        return self

    def release_savepoint(self, name: str) -> Transaction:
        """Add RELEASE SAVEPOINT."""
        self._queries.append(f"RELEASE SAVEPOINT {name}")
        return self

    def build(self, dialect: Dialect | None = None) -> list[tuple[str, list[Any]]]:
        """Build all transaction statements.

        Returns list of (sql, params) tuples including BEGIN and COMMIT.
        """
        result: list[tuple[str, list[Any]]] = []

        # BEGIN
        begin = "BEGIN"
        if self._isolation_level:
            begin = f"BEGIN ISOLATION LEVEL {self._isolation_level}"
        result.append((begin, []))

        # Queries
        for q in self._queries:
            if isinstance(q, str):
                result.append((q, []))
            else:
                result.append(q.build(dialect))

        # COMMIT
        result.append(("COMMIT", []))
        return result

    def build_rollback(self) -> list[tuple[str, list[Any]]]:
        """Build a ROLLBACK statement."""
        return [("ROLLBACK", [])]

    @property
    def query_count(self) -> int:
        """Number of queries in the transaction (excluding BEGIN/COMMIT)."""
        return len(self._queries)
