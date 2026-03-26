"""Table statistics for cost estimation and analysis context."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ColumnStats:
    """Statistics for a table column."""

    name: str
    distinct_count: int | None = None
    null_fraction: float = 0.0
    avg_width: int | None = None
    has_index: bool = False
    index_name: str | None = None
    is_primary_key: bool = False
    is_foreign_key: bool = False


@dataclass
class TableStats:
    """Statistics for a database table."""

    name: str
    row_count: int = 0
    columns: dict[str, ColumnStats] = field(default_factory=dict)
    indexes: list[str] = field(default_factory=list)
    schema: str | None = None

    @property
    def is_large(self) -> bool:
        return self.row_count > 100_000

    @property
    def is_very_large(self) -> bool:
        return self.row_count > 1_000_000

    def selectivity(self, column: str) -> float:
        """Estimate selectivity of a column (0.0 = very selective, 1.0 = not selective)."""
        col = self.columns.get(column)
        if not col or not col.distinct_count or self.row_count == 0:
            return 0.5  # default
        return 1.0 / col.distinct_count

    def has_index_on(self, column: str) -> bool:
        """Check if column has an index."""
        col = self.columns.get(column)
        return col.has_index if col else False

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "row_count": self.row_count,
            "schema": self.schema,
            "is_large": self.is_large,
            "columns": {
                name: {
                    "distinct_count": c.distinct_count,
                    "null_fraction": c.null_fraction,
                    "has_index": c.has_index,
                    "is_primary_key": c.is_primary_key,
                }
                for name, c in self.columns.items()
            },
            "indexes": self.indexes,
        }


@dataclass
class SchemaContext:
    """Schema context with table statistics for enhanced analysis."""

    tables: dict[str, TableStats] = field(default_factory=dict)

    def add_table(self, stats: TableStats) -> None:
        self.tables[stats.name] = stats

    def get_table(self, name: str) -> TableStats | None:
        return self.tables.get(name)

    def has_table(self, name: str) -> bool:
        return name in self.tables

    def estimate_join_rows(self, table1: str, col1: str, table2: str, col2: str) -> int:
        """Estimate the number of rows from a join."""
        t1 = self.get_table(table1)
        t2 = self.get_table(table2)
        if not t1 or not t2:
            return 0

        sel1 = t1.selectivity(col1)
        sel2 = t2.selectivity(col2)

        # Use the lower selectivity as the join multiplier
        min_sel = min(sel1, sel2)
        return int(t1.row_count * t2.row_count * min_sel)

    def estimate_filtered_rows(self, table: str, column: str) -> int:
        """Estimate rows after filtering by a column."""
        t = self.get_table(table)
        if not t:
            return 0
        sel = t.selectivity(column)
        return max(1, int(t.row_count * sel))

    def to_dict(self) -> dict[str, object]:
        return {
            "tables": {name: t.to_dict() for name, t in self.tables.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> SchemaContext:
        """Create SchemaContext from a dictionary."""
        ctx = cls()
        for name, table_data in data.get("tables", {}).items():
            columns = {}
            for col_name, col_data in table_data.get("columns", {}).items():
                columns[col_name] = ColumnStats(
                    name=col_name,
                    distinct_count=col_data.get("distinct_count"),
                    null_fraction=col_data.get("null_fraction", 0.0),
                    has_index=col_data.get("has_index", False),
                    is_primary_key=col_data.get("is_primary_key", False),
                )

            stats = TableStats(
                name=name,
                row_count=table_data.get("row_count", 0),
                columns=columns,
                indexes=table_data.get("indexes", []),
                schema=table_data.get("schema"),
            )
            ctx.add_table(stats)
        return ctx
