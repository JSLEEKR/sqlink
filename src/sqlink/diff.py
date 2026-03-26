"""Query diff — compare two SQL queries for structural differences."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlink.models import ParsedQuery
from sqlink.parser import parse_query


@dataclass
class QueryDiff:
    """Differences between two parsed queries."""

    added_tables: list[str] = field(default_factory=list)
    removed_tables: list[str] = field(default_factory=list)
    added_joins: list[str] = field(default_factory=list)
    removed_joins: list[str] = field(default_factory=list)
    added_where: list[str] = field(default_factory=list)
    removed_where: list[str] = field(default_factory=list)
    structural_changes: list[str] = field(default_factory=list)
    column_changes: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_tables
            or self.removed_tables
            or self.added_joins
            or self.removed_joins
            or self.added_where
            or self.removed_where
            or self.structural_changes
            or self.column_changes
        )

    @property
    def change_count(self) -> int:
        return (
            len(self.added_tables)
            + len(self.removed_tables)
            + len(self.added_joins)
            + len(self.removed_joins)
            + len(self.added_where)
            + len(self.removed_where)
            + len(self.structural_changes)
            + len(self.column_changes)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "has_changes": self.has_changes,
            "change_count": self.change_count,
            "added_tables": self.added_tables,
            "removed_tables": self.removed_tables,
            "added_joins": self.added_joins,
            "removed_joins": self.removed_joins,
            "added_where": self.added_where,
            "removed_where": self.removed_where,
            "structural_changes": self.structural_changes,
            "column_changes": self.column_changes,
        }

    def format_text(self) -> str:
        """Format diff as human-readable text."""
        if not self.has_changes:
            return "No structural differences found."

        lines: list[str] = []
        if self.added_tables:
            lines.append(f"+ Tables added: {', '.join(self.added_tables)}")
        if self.removed_tables:
            lines.append(f"- Tables removed: {', '.join(self.removed_tables)}")
        if self.added_joins:
            for j in self.added_joins:
                lines.append(f"+ Join added: {j}")
        if self.removed_joins:
            for j in self.removed_joins:
                lines.append(f"- Join removed: {j}")
        if self.added_where:
            for w in self.added_where:
                lines.append(f"+ WHERE added: {w}")
        if self.removed_where:
            for w in self.removed_where:
                lines.append(f"- WHERE removed: {w}")
        if self.column_changes:
            for c in self.column_changes:
                lines.append(f"~ Column change: {c}")
        if self.structural_changes:
            for s in self.structural_changes:
                lines.append(f"~ {s}")
        return "\n".join(lines)


def diff_queries(sql1: str, sql2: str) -> QueryDiff:
    """Compare two SQL queries structurally."""
    p1 = parse_query(sql1)
    p2 = parse_query(sql2)
    return diff_parsed(p1, p2)


def diff_parsed(p1: ParsedQuery, p2: ParsedQuery) -> QueryDiff:
    """Compare two parsed queries."""
    result = QueryDiff()

    # Query type change
    if p1.query_type != p2.query_type:
        result.structural_changes.append(
            f"Query type changed: {p1.query_type.value} -> {p2.query_type.value}"
        )

    # Table changes
    tables1 = {t.name for t in p1.tables}
    tables2 = {t.name for t in p2.tables}
    result.added_tables = sorted(tables2 - tables1)
    result.removed_tables = sorted(tables1 - tables2)

    # Join changes
    joins1 = {f"{j.join_type.value} JOIN {j.table.name}" for j in p1.joins}
    joins2 = {f"{j.join_type.value} JOIN {j.table.name}" for j in p2.joins}
    result.added_joins = sorted(joins2 - joins1)
    result.removed_joins = sorted(joins1 - joins2)

    # WHERE changes
    where1 = {c.raw.strip().upper() for c in p1.where_conditions}
    where2 = {c.raw.strip().upper() for c in p2.where_conditions}
    result.added_where = sorted(where2 - where1)
    result.removed_where = sorted(where1 - where2)

    # Structural flags
    _check_flag(result, "SELECT *", p1.has_select_star, p2.has_select_star)
    _check_flag(result, "DISTINCT", p1.has_distinct, p2.has_distinct)
    _check_flag(result, "GROUP BY", p1.has_group_by, p2.has_group_by)
    _check_flag(result, "ORDER BY", p1.has_order_by, p2.has_order_by)
    _check_flag(result, "LIMIT", p1.has_limit, p2.has_limit)
    _check_flag(result, "OFFSET", p1.has_offset, p2.has_offset)
    _check_flag(result, "HAVING", p1.has_having, p2.has_having)
    _check_flag(result, "UNION", p1.has_union, p2.has_union)

    # Column changes (for SELECT queries)
    cols1 = {c.full_name for c in p1.columns}
    cols2 = {c.full_name for c in p2.columns}
    added_cols = cols2 - cols1
    removed_cols = cols1 - cols2
    if added_cols:
        result.column_changes.append(f"Added: {', '.join(sorted(added_cols))}")
    if removed_cols:
        result.column_changes.append(f"Removed: {', '.join(sorted(removed_cols))}")

    return result


def _check_flag(result: QueryDiff, name: str, val1: bool, val2: bool) -> None:
    """Check if a structural flag changed."""
    if val1 and not val2:
        result.structural_changes.append(f"{name} removed")
    elif not val1 and val2:
        result.structural_changes.append(f"{name} added")
