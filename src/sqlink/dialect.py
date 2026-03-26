"""SQL dialect support for sqlink."""

from __future__ import annotations

from typing import Any


class Dialect:
    """Base SQL dialect with configurable quoting and placeholder styles."""

    def placeholder(self) -> str:
        """Return the parameter placeholder string."""
        return "?"

    def quote_identifier(self, name: str) -> str:
        """Quote a table or column identifier."""
        if "." in name:
            parts = name.split(".")
            return ".".join(self.quote_identifier(p) for p in parts)
        if name == "*":
            return name
        return f'"{name}"'

    def supports_ilike(self) -> bool:
        """Whether this dialect supports ILIKE."""
        return False

    def supports_returning(self) -> bool:
        """Whether this dialect supports RETURNING clause."""
        return False

    def supports_upsert(self) -> bool:
        """Whether this dialect supports ON CONFLICT / upsert."""
        return False

    def limit_offset_sql(self, limit: int | None, offset: int | None) -> str:
        """Generate LIMIT/OFFSET clause."""
        parts = []
        if limit is not None:
            parts.append(f"LIMIT {limit}")
        if offset is not None:
            parts.append(f"OFFSET {offset}")
        return " ".join(parts)

    def upsert_sql(
        self,
        conflict_columns: list[str],
        update_columns: list[str],
        placeholder: str,
    ) -> tuple[str, list[Any]]:
        """Generate upsert/ON CONFLICT clause."""
        conflict_cols = ", ".join(
            self.quote_identifier(c) for c in conflict_columns
        )
        set_parts = [
            f"{self.quote_identifier(c)} = EXCLUDED.{self.quote_identifier(c)}"
            for c in update_columns
        ]
        return (
            f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {', '.join(set_parts)}",
            [],
        )

    def boolean_literal(self, value: bool) -> str:
        """Return boolean literal for this dialect."""
        return "TRUE" if value else "FALSE"

    def name(self) -> str:
        """Return dialect name."""
        return "generic"


class SQLiteDialect(Dialect):
    """SQLite dialect."""

    def placeholder(self) -> str:
        return "?"

    def supports_returning(self) -> bool:
        return True  # SQLite 3.35+

    def supports_upsert(self) -> bool:
        return True

    def boolean_literal(self, value: bool) -> str:
        return "1" if value else "0"

    def name(self) -> str:
        return "sqlite"


class PostgreSQLDialect(Dialect):
    """PostgreSQL dialect with $1-style placeholders."""

    def __init__(self):
        self._counter = 0

    def placeholder(self) -> str:
        self._counter += 1
        return f"${self._counter}"

    def reset_counter(self) -> None:
        self._counter = 0

    def supports_ilike(self) -> bool:
        return True

    def supports_returning(self) -> bool:
        return True

    def supports_upsert(self) -> bool:
        return True

    def name(self) -> str:
        return "postgresql"


class MySQLDialect(Dialect):
    """MySQL dialect with backtick quoting."""

    def placeholder(self) -> str:
        return "%s"

    def quote_identifier(self, name: str) -> str:
        if "." in name:
            parts = name.split(".")
            return ".".join(self.quote_identifier(p) for p in parts)
        if name == "*":
            return name
        return f"`{name}`"

    def supports_upsert(self) -> bool:
        return True

    def upsert_sql(
        self,
        conflict_columns: list[str],
        update_columns: list[str],
        placeholder: str,
    ) -> tuple[str, list[Any]]:
        """MySQL uses ON DUPLICATE KEY UPDATE syntax."""
        set_parts = [
            f"{self.quote_identifier(c)} = VALUES({self.quote_identifier(c)})"
            for c in update_columns
        ]
        return f"ON DUPLICATE KEY UPDATE {', '.join(set_parts)}", []

    def boolean_literal(self, value: bool) -> str:
        return "1" if value else "0"

    def name(self) -> str:
        return "mysql"
