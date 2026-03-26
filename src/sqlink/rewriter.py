"""Query rewriter — suggests improved versions of SQL queries."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlink.models import ParsedQuery, QueryType


@dataclass
class Rewrite:
    """A suggested query rewrite."""

    original: str
    rewritten: str
    rule_id: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "original": self.original,
            "rewritten": self.rewritten,
            "rule_id": self.rule_id,
            "description": self.description,
        }


def suggest_rewrites(parsed: ParsedQuery) -> list[Rewrite]:
    """Suggest rewrites for a parsed query."""
    rewrites: list[Rewrite] = []

    if parsed.query_type == QueryType.SELECT:
        rewrites.extend(_rewrite_select_star(parsed))
        rewrites.extend(_rewrite_offset_pagination(parsed))
        rewrites.extend(_rewrite_union_to_union_all(parsed))
        rewrites.extend(_rewrite_in_subquery_to_exists(parsed))
        rewrites.extend(_rewrite_add_limit(parsed))

    return rewrites


def _rewrite_select_star(parsed: ParsedQuery) -> list[Rewrite]:
    """Suggest replacing SELECT * with explicit columns."""
    if not parsed.has_select_star:
        return []

    # We can't know the actual columns, but we can suggest the pattern
    tables = ", ".join(t.effective_name for t in parsed.tables)
    suggestion = parsed.raw.replace("*", f"/* TODO: list columns from {tables} */", 1)

    return [Rewrite(
        original=parsed.raw,
        rewritten=suggestion,
        rule_id="SQ001",
        description="Replace SELECT * with explicit column list for better performance and clarity.",
    )]


def _rewrite_offset_pagination(parsed: ParsedQuery) -> list[Rewrite]:
    """Suggest keyset pagination instead of OFFSET."""
    if not parsed.has_offset:
        return []

    # Replace OFFSET with keyset approach hint
    rewritten = re.sub(
        r"\bLIMIT\s+(\d+)\s+OFFSET\s+\d+",
        r"WHERE id > :last_seen_id ORDER BY id LIMIT \1",
        parsed.raw,
        flags=re.IGNORECASE,
    )

    if rewritten == parsed.raw:
        return []

    return [Rewrite(
        original=parsed.raw,
        rewritten=rewritten,
        rule_id="SQ004",
        description="Use keyset pagination instead of OFFSET for consistent performance at any page.",
    )]


def _rewrite_union_to_union_all(parsed: ParsedQuery) -> list[Rewrite]:
    """Suggest UNION ALL if deduplication isn't needed."""
    if not parsed.has_union:
        return []

    upper = parsed.raw.upper()
    if "UNION ALL" in upper:
        return []

    rewritten = re.sub(r"\bUNION\b(?!\s+ALL)", "UNION ALL", parsed.raw, flags=re.IGNORECASE)
    if rewritten == parsed.raw:
        return []

    return [Rewrite(
        original=parsed.raw,
        rewritten=rewritten,
        rule_id="SQ007",
        description="Use UNION ALL to skip deduplication step if duplicate rows are acceptable.",
    )]


def _rewrite_in_subquery_to_exists(parsed: ParsedQuery) -> list[Rewrite]:
    """Suggest EXISTS instead of IN (SELECT ...)."""
    rewrites: list[Rewrite] = []

    for cond in parsed.where_conditions:
        if not cond.has_in_subquery:
            continue

        # Try to find and rewrite IN (SELECT ...) to EXISTS
        match = re.search(
            r"(\w+(?:\.\w+)?)\s+IN\s*\(\s*(SELECT\s+\w+(?:\.\w+)?\s+FROM\s+(\w+).*?)\)",
            cond.raw,
            re.IGNORECASE,
        )
        if match:
            col = match.group(1)
            inner_table = match.group(3)
            rewritten_cond = f"EXISTS (SELECT 1 FROM {inner_table} WHERE {inner_table}.id = {col})"
            rewritten = parsed.raw.replace(cond.raw, rewritten_cond)

            rewrites.append(Rewrite(
                original=parsed.raw,
                rewritten=rewritten,
                rule_id="WH006",
                description="Use EXISTS instead of IN (SELECT ...) for potentially better performance.",
            ))

    return rewrites


def _rewrite_add_limit(parsed: ParsedQuery) -> list[Rewrite]:
    """Suggest adding LIMIT to unbounded SELECTs."""
    if parsed.has_limit or parsed.query_type != QueryType.SELECT:
        return []

    if parsed.has_group_by:
        # Aggregation queries often need all rows
        return []

    rewritten = parsed.raw + " LIMIT 1000"

    return [Rewrite(
        original=parsed.raw,
        rewritten=rewritten,
        rule_id="SD001",
        description="Add LIMIT to prevent unbounded result sets.",
    )]
