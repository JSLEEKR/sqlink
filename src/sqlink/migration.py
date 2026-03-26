"""Schema migration builder for sqlink — ALTER TABLE operations."""

from __future__ import annotations

from typing import Any

from sqlink.dialect import Dialect
from sqlink.schema import Column, ForeignKey


class AlterTable:
    """Builder for ALTER TABLE operations.

    Usage:
        alter = AlterTable("users")
        alter.add_column(Column("phone", ColumnType.VARCHAR, max_length=20))
        alter.drop_column("legacy_field")
        sqls = alter.build()
    """

    def __init__(self, table_name: str):
        self.table_name = table_name
        self._operations: list[tuple[str, Any]] = []

    def add_column(self, column: Column) -> AlterTable:
        """Add a new column."""
        self._operations.append(("ADD_COLUMN", column))
        return self

    def drop_column(self, column_name: str) -> AlterTable:
        """Drop a column."""
        self._operations.append(("DROP_COLUMN", column_name))
        return self

    def rename_column(self, old_name: str, new_name: str) -> AlterTable:
        """Rename a column."""
        self._operations.append(("RENAME_COLUMN", (old_name, new_name)))
        return self

    def alter_column_type(self, column_name: str, new_type: str) -> AlterTable:
        """Change a column's data type."""
        self._operations.append(("ALTER_TYPE", (column_name, new_type)))
        return self

    def set_not_null(self, column_name: str) -> AlterTable:
        """Set a column as NOT NULL."""
        self._operations.append(("SET_NOT_NULL", column_name))
        return self

    def drop_not_null(self, column_name: str) -> AlterTable:
        """Drop NOT NULL constraint."""
        self._operations.append(("DROP_NOT_NULL", column_name))
        return self

    def add_unique(self, *columns: str, name: str | None = None) -> AlterTable:
        """Add a UNIQUE constraint."""
        self._operations.append(("ADD_UNIQUE", (columns, name)))
        return self

    def drop_constraint(self, name: str) -> AlterTable:
        """Drop a named constraint."""
        self._operations.append(("DROP_CONSTRAINT", name))
        return self

    def add_index(self, *columns: str, name: str | None = None, unique: bool = False) -> AlterTable:
        """Add an index (CREATE INDEX)."""
        self._operations.append(("ADD_INDEX", (columns, name, unique)))
        return self

    def drop_index(self, name: str) -> AlterTable:
        """Drop an index."""
        self._operations.append(("DROP_INDEX", name))
        return self

    def add_foreign_key(self, fk: ForeignKey, name: str | None = None) -> AlterTable:
        """Add a foreign key constraint."""
        self._operations.append(("ADD_FK", (fk, name)))
        return self

    def set_default(self, column_name: str, default_value: Any) -> AlterTable:
        """Set a default value for a column."""
        self._operations.append(("SET_DEFAULT", (column_name, default_value)))
        return self

    def drop_default(self, column_name: str) -> AlterTable:
        """Drop the default value for a column."""
        self._operations.append(("DROP_DEFAULT", column_name))
        return self

    def rename_table(self, new_name: str) -> AlterTable:
        """Rename the table."""
        self._operations.append(("RENAME_TABLE", new_name))
        return self

    def build(self, dialect: Dialect | None = None) -> list[str]:
        """Build all ALTER TABLE SQL statements.

        Returns a list of SQL strings (one per operation).
        """
        quote = dialect.quote_identifier if dialect else lambda x: f'"{x}"'
        table = quote(self.table_name)
        statements: list[str] = []

        for op_type, op_data in self._operations:
            if op_type == "ADD_COLUMN":
                col_sql = op_data.to_sql(dialect)
                statements.append(f"ALTER TABLE {table} ADD COLUMN {col_sql}")

            elif op_type == "DROP_COLUMN":
                statements.append(
                    f"ALTER TABLE {table} DROP COLUMN {quote(op_data)}"
                )

            elif op_type == "RENAME_COLUMN":
                old, new = op_data
                statements.append(
                    f"ALTER TABLE {table} RENAME COLUMN {quote(old)} TO {quote(new)}"
                )

            elif op_type == "ALTER_TYPE":
                col, new_type = op_data
                statements.append(
                    f"ALTER TABLE {table} ALTER COLUMN {quote(col)} TYPE {new_type}"
                )

            elif op_type == "SET_NOT_NULL":
                statements.append(
                    f"ALTER TABLE {table} ALTER COLUMN {quote(op_data)} SET NOT NULL"
                )

            elif op_type == "DROP_NOT_NULL":
                statements.append(
                    f"ALTER TABLE {table} ALTER COLUMN {quote(op_data)} DROP NOT NULL"
                )

            elif op_type == "ADD_UNIQUE":
                cols, name = op_data
                col_list = ", ".join(quote(c) for c in cols)
                if name:
                    statements.append(
                        f"ALTER TABLE {table} ADD CONSTRAINT {quote(name)} UNIQUE ({col_list})"
                    )
                else:
                    statements.append(
                        f"ALTER TABLE {table} ADD UNIQUE ({col_list})"
                    )

            elif op_type == "DROP_CONSTRAINT":
                statements.append(
                    f"ALTER TABLE {table} DROP CONSTRAINT {quote(op_data)}"
                )

            elif op_type == "ADD_INDEX":
                cols, name, unique = op_data
                col_list = ", ".join(quote(c) for c in cols)
                unique_kw = "UNIQUE " if unique else ""
                if name:
                    statements.append(
                        f"CREATE {unique_kw}INDEX {quote(name)} ON {table} ({col_list})"
                    )
                else:
                    idx_name = f"idx_{self.table_name}_{'_'.join(cols)}"
                    statements.append(
                        f"CREATE {unique_kw}INDEX {quote(idx_name)} ON {table} ({col_list})"
                    )

            elif op_type == "DROP_INDEX":
                statements.append(f"DROP INDEX {quote(op_data)}")

            elif op_type == "ADD_FK":
                fk, name = op_data
                fk_sql = fk.to_sql(dialect)
                if name:
                    statements.append(
                        f"ALTER TABLE {table} ADD CONSTRAINT {quote(name)} {fk_sql}"
                    )
                else:
                    statements.append(f"ALTER TABLE {table} ADD {fk_sql}")

            elif op_type == "SET_DEFAULT":
                col, val = op_data
                if isinstance(val, str):
                    val_str = f"'{val}'"
                elif isinstance(val, bool):
                    val_str = "TRUE" if val else "FALSE"
                else:
                    val_str = str(val)
                statements.append(
                    f"ALTER TABLE {table} ALTER COLUMN {quote(col)} SET DEFAULT {val_str}"
                )

            elif op_type == "DROP_DEFAULT":
                statements.append(
                    f"ALTER TABLE {table} ALTER COLUMN {quote(op_data)} DROP DEFAULT"
                )

            elif op_type == "RENAME_TABLE":
                statements.append(
                    f"ALTER TABLE {table} RENAME TO {quote(op_data)}"
                )

        return statements
