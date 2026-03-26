"""Query complexity scoring — measures how complex a SQL query is."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlink.models import ParsedQuery, QueryType


@dataclass
class ComplexityBreakdown:
    """Breakdown of query complexity factors."""

    base_score: int = 1
    join_score: int = 0
    subquery_score: int = 0
    where_score: int = 0
    aggregation_score: int = 0
    modifier_score: int = 0
    details: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            self.base_score
            + self.join_score
            + self.subquery_score
            + self.where_score
            + self.aggregation_score
            + self.modifier_score
        )

    @property
    def level(self) -> str:
        """Human-readable complexity level."""
        t = self.total
        if t <= 3:
            return "low"
        elif t <= 7:
            return "medium"
        elif t <= 12:
            return "high"
        else:
            return "very high"

    def to_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "level": self.level,
            "breakdown": {
                "base": self.base_score,
                "joins": self.join_score,
                "subqueries": self.subquery_score,
                "where_conditions": self.where_score,
                "aggregation": self.aggregation_score,
                "modifiers": self.modifier_score,
            },
            "details": self.details,
        }


def calculate_complexity(parsed: ParsedQuery) -> ComplexityBreakdown:
    """Calculate the complexity score for a parsed query."""
    breakdown = ComplexityBreakdown()

    # Base score varies by query type
    type_scores = {
        QueryType.SELECT: 1,
        QueryType.INSERT: 1,
        QueryType.UPDATE: 2,
        QueryType.DELETE: 2,
        QueryType.CREATE: 1,
        QueryType.ALTER: 2,
        QueryType.DROP: 1,
        QueryType.UNKNOWN: 1,
    }
    breakdown.base_score = type_scores.get(parsed.query_type, 1)
    breakdown.details.append(f"Base ({parsed.query_type.value}): {breakdown.base_score}")

    # Joins: each join adds complexity
    if parsed.joins:
        breakdown.join_score = len(parsed.joins) * 2
        breakdown.details.append(f"Joins ({len(parsed.joins)}): +{breakdown.join_score}")

    # Subqueries: each adds significant complexity
    if parsed.subqueries:
        breakdown.subquery_score = len(parsed.subqueries) * 3
        breakdown.details.append(f"Subqueries ({len(parsed.subqueries)}): +{breakdown.subquery_score}")

    # WHERE conditions
    if parsed.where_conditions:
        where_pts = 0
        for cond in parsed.where_conditions:
            where_pts += 1
            if cond.has_function:
                where_pts += 1
            if cond.has_or:
                where_pts += 1
            if cond.has_in_subquery:
                where_pts += 2
        breakdown.where_score = where_pts
        breakdown.details.append(f"WHERE conditions: +{where_pts}")

    # Aggregation
    agg_pts = 0
    if parsed.has_group_by:
        agg_pts += 2
    if parsed.has_having:
        agg_pts += 2
    if parsed.has_distinct:
        agg_pts += 1
    if agg_pts:
        breakdown.aggregation_score = agg_pts
        breakdown.details.append(f"Aggregation: +{agg_pts}")

    # Modifiers
    mod_pts = 0
    if parsed.has_order_by:
        mod_pts += 1
    if parsed.has_union:
        mod_pts += 2
    if parsed.has_offset:
        mod_pts += 1
    if mod_pts:
        breakdown.modifier_score = mod_pts
        breakdown.details.append(f"Modifiers: +{mod_pts}")

    return breakdown
