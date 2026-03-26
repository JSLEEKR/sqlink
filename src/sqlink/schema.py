"""Schema definitions for sqlink — table and column metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlink.types import ColumnType
from sqlink.dialect import Dialect


@dataclass
class ForeignKey:
    """Foreign key constraint definition."""
    column: str
    references_table: str
    references_column: str
    on_delete: str | None = None
    on_update: str | None = None

    def to_sql(self, dialect: Dialect | None = None) -> str:
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        parts = [
            f"FOREIGN KEY ({quote(self.column)})",
            f"REFERENCES {quote(self.references_table)}({quote(self.references_column)})",
        ]
        if self.on_delete:
            parts.append(f"ON DELETE {self.on_delete}")
        if self.on_update:
            parts.append(f"ON UPDATE {self.on_update}")
        return " ".join(parts)


@dataclass
class Column:
    """Column definition for CREATE TABLE."""
    name: str
    type: ColumnType | str
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    default: Any = None
    check: str | None = None
    auto_increment: bool = False
    max_length: int | None = None

    def to_sql(self, dialect: Dialect | None = None) -> str:
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        type_str = self.type.value if isinstance(self.type, ColumnType) else self.type
        if self.max_length and type_str in ("VARCHAR", "CHAR"):
            type_str = f"{type_str}({self.max_length})"

        parts = [quote(self.name), type_str]

        if self.primary_key:
            parts.append("PRIMARY KEY")
        if self.auto_increment:
            if dialect and dialect.name() == "mysql":
                parts.append("AUTO_INCREMENT")
            elif dialect and dialect.name() == "sqlite":
                parts.append("AUTOINCREMENT")
            # PostgreSQL uses SERIAL type instead
        if not self.nullable and not self.primary_key:
            parts.append("NOT NULL")
        if self.unique and not self.primary_key:
            parts.append("UNIQUE")
        if self.default is not None:
            if isinstance(self.default, str):
                parts.append(f"DEFAULT '{self.default}'")
            elif isinstance(self.default, bool):
                bl = dialect.boolean_literal(self.default) if dialect else str(self.default)
                parts.append(f"DEFAULT {bl}")
            else:
                parts.append(f"DEFAULT {self.default}")
        if self.check:
            parts.append(f"CHECK ({self.check})")

        return " ".join(parts)


@dataclass
class Schema:
    """Table schema definition with columns and constraints."""
    table_name: str
    columns: list[Column] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    if_not_exists: bool = False

    def add_column(self, column: Column) -> Schema:
        self.columns.append(column)
        return self

    def add_foreign_key(self, fk: ForeignKey) -> Schema:
        self.foreign_keys.append(fk)
        return self

    def create_table_sql(self, dialect: Dialect | None = None) -> str:
        """Generate CREATE TABLE SQL."""
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        exists_clause = "IF NOT EXISTS " if self.if_not_exists else ""
        col_defs = [col.to_sql(dialect) for col in self.columns]
        fk_defs = [fk.to_sql(dialect) for fk in self.foreign_keys]
        all_defs = col_defs + fk_defs
        return (
            f"CREATE TABLE {exists_clause}{quote(self.table_name)} "
            f"({', '.join(all_defs)})"
        )

    def drop_table_sql(self, dialect: Dialect | None = None, if_exists: bool = True) -> str:
        """Generate DROP TABLE SQL."""
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        exists_clause = "IF EXISTS " if if_exists else ""
        return f"DROP TABLE {exists_clause}{quote(self.table_name)}"
