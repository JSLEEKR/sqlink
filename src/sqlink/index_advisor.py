"""Index suggestion engine — recommends indexes based on query patterns."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlink.models import ColumnReference, JoinType, ParsedQuery, QueryType


@dataclass
class IndexSuggestion:
    """A suggested index."""

    table: str
    columns: list[str]
    reason: str
    index_type: str = "btree"  # btree, hash, gin, gist
    priority: int = 0  # higher = more important

    @property
    def index_name(self) -> str:
        cols = "_".join(self.columns)
        return f"idx_{self.table}_{cols}"

    @property
    def create_sql(self) -> str:
        cols = ", ".join(self.columns)
        if self.index_type == "btree":
            return f"CREATE INDEX {self.index_name} ON {self.table} ({cols});"
        return f"CREATE INDEX {self.index_name} ON {self.table} USING {self.index_type} ({cols});"

    def to_dict(self) -> dict[str, object]:
        return {
            "table": self.table,
            "columns": self.columns,
            "reason": self.reason,
            "index_type": self.index_type,
            "priority": self.priority,
            "index_name": self.index_name,
            "create_sql": self.create_sql,
        }


def suggest_indexes(parsed: ParsedQuery) -> list[IndexSuggestion]:
    """Suggest indexes for a parsed query."""
    suggestions: list[IndexSuggestion] = []

    # Build a map of aliases to table names
    alias_map: dict[str, str] = {}
    for table in parsed.tables:
        if table.alias:
            alias_map[table.alias] = table.name
        alias_map[table.name] = table.name

    def _resolve_table(ref: str) -> str | None:
        return alias_map.get(ref)

    # 1. WHERE clause columns → index candidates
    where_columns: dict[str, list[str]] = {}  # table -> [columns]
    for cond in parsed.where_conditions:
        for col in cond.columns:
            table_name = None
            if col.table:
                table_name = _resolve_table(col.table)
            elif len(parsed.tables) == 1:
                table_name = parsed.tables[0].name

            if table_name:
                where_columns.setdefault(table_name, [])
                if col.name not in where_columns[table_name]:
                    where_columns[table_name].append(col.name)

    for table, cols in where_columns.items():
        if cols:
            suggestions.append(IndexSuggestion(
                table=table,
                columns=cols[:3],  # Limit composite index to 3 columns
                reason="Columns used in WHERE clause",
                priority=8,
            ))

    # 2. JOIN columns → index candidates (high priority)
    for join in parsed.joins:
        join_table = join.table.name
        if join.condition:
            # Extract column from ON condition
            import re
            # Look for join_table.column or alias.column patterns
            col_refs = re.findall(r"(\w+)\.(\w+)", join.condition)
            for tbl, col in col_refs:
                resolved = _resolve_table(tbl)
                if resolved and resolved == join_table:
                    suggestions.append(IndexSuggestion(
                        table=join_table,
                        columns=[col],
                        reason=f"Join condition column ({join.join_type.value} JOIN)",
                        priority=9,
                    ))

    # 3. ORDER BY columns → index for avoiding sort
    if parsed.has_order_by and parsed.order_by_columns:
        for col in parsed.order_by_columns:
            table_name = None
            if col.table:
                table_name = _resolve_table(col.table)
            elif len(parsed.tables) == 1:
                table_name = parsed.tables[0].name

            if table_name:
                suggestions.append(IndexSuggestion(
                    table=table_name,
                    columns=[col.name],
                    reason="Column used in ORDER BY",
                    priority=5,
                ))

    # 4. GROUP BY columns → index for avoiding sort/hash
    if parsed.has_group_by and parsed.group_by_columns:
        for col in parsed.group_by_columns:
            table_name = None
            if col.table:
                table_name = _resolve_table(col.table)
            elif len(parsed.tables) == 1:
                table_name = parsed.tables[0].name

            if table_name:
                suggestions.append(IndexSuggestion(
                    table=table_name,
                    columns=[col.name],
                    reason="Column used in GROUP BY",
                    priority=6,
                ))

    # Deduplicate: merge suggestions for same table with same columns
    suggestions = _deduplicate(suggestions)

    # Sort by priority (descending)
    suggestions.sort(key=lambda s: -s.priority)

    return suggestions


def _deduplicate(suggestions: list[IndexSuggestion]) -> list[IndexSuggestion]:
    """Merge duplicate index suggestions."""
    seen: dict[str, IndexSuggestion] = {}
    for s in suggestions:
        key = f"{s.table}:{','.join(s.columns)}"
        if key in seen:
            existing = seen[key]
            existing.priority = max(existing.priority, s.priority)
            if s.reason not in existing.reason:
                existing.reason = f"{existing.reason}; {s.reason}"
        else:
            seen[key] = IndexSuggestion(
                table=s.table,
                columns=list(s.columns),
                reason=s.reason,
                index_type=s.index_type,
                priority=s.priority,
            )
    return list(seen.values())
