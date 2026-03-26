"""Cost estimator — estimate query cost without database connection."""

from __future__ import annotations

from dataclasses import dataclass, field
from sqlink.models import ParsedQuery, QueryType
from sqlink.statistics import SchemaContext


@dataclass
class CostEstimate:
    """Estimated cost breakdown."""

    scan_cost: float = 0.0
    join_cost: float = 0.0
    sort_cost: float = 0.0
    filter_cost: float = 0.0
    aggregation_cost: float = 0.0
    details: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return self.scan_cost + self.join_cost + self.sort_cost + self.filter_cost + self.aggregation_cost

    @property
    def rating(self) -> str:
        t = self.total
        if t <= 100:
            return "low"
        elif t <= 1000:
            return "moderate"
        elif t <= 10000:
            return "high"
        else:
            return "very high"

    def to_dict(self) -> dict[str, object]:
        return {
            "total": round(self.total, 2),
            "rating": self.rating,
            "breakdown": {
                "scan": round(self.scan_cost, 2),
                "join": round(self.join_cost, 2),
                "sort": round(self.sort_cost, 2),
                "filter": round(self.filter_cost, 2),
                "aggregation": round(self.aggregation_cost, 2),
            },
            "details": self.details,
        }


# Cost constants (inspired by PostgreSQL planner)
SEQ_SCAN_COST_PER_ROW = 1.0
INDEX_SCAN_COST_PER_ROW = 0.005
RANDOM_IO_COST = 4.0
CPU_TUPLE_COST = 0.01
CPU_OPERATOR_COST = 0.0025
SORT_COST_FACTOR = 2.0  # n * log(n) approximation factor
HASH_JOIN_COST_FACTOR = 1.5


def estimate_cost(
    parsed: ParsedQuery,
    schema: SchemaContext | None = None,
) -> CostEstimate:
    """Estimate the cost of a query without running it."""
    estimate = CostEstimate()

    # Default row estimate if no schema
    default_rows = 1000

    # Scan cost for main tables
    for table in parsed.tables:
        table_name = table.name
        rows = default_rows
        has_index_on_where = False

        if schema:
            stats = schema.get_table(table_name)
            if stats:
                rows = stats.row_count

                # Check if WHERE columns have indexes
                for cond in parsed.where_conditions:
                    for col in cond.columns:
                        resolved_table = col.table or table_name
                        if resolved_table in (table_name, table.alias):
                            if stats.has_index_on(col.name):
                                has_index_on_where = True

        if has_index_on_where:
            cost = rows * INDEX_SCAN_COST_PER_ROW + RANDOM_IO_COST
            estimate.details.append(f"Index scan on {table_name}: {cost:.1f}")
        else:
            cost = rows * SEQ_SCAN_COST_PER_ROW
            estimate.details.append(f"Sequential scan on {table_name}: {cost:.1f}")

        estimate.scan_cost += cost

    # Join cost
    if parsed.joins:
        accumulated_rows = default_rows
        if schema and parsed.tables:
            first_table = schema.get_table(parsed.tables[0].name)
            if first_table:
                accumulated_rows = first_table.row_count

        for join in parsed.joins:
            join_rows = default_rows
            if schema:
                stats = schema.get_table(join.table.name)
                if stats:
                    join_rows = stats.row_count

            # Nested loop cost (worst case)
            cost = accumulated_rows * join_rows * CPU_TUPLE_COST
            # Check for index on join column
            if schema and join.condition:
                import re
                col_refs = re.findall(r"(\w+)\.(\w+)", join.condition)
                for tbl, col in col_refs:
                    t = schema.get_table(tbl) or schema.get_table(join.table.name)
                    if t and t.has_index_on(col):
                        cost = accumulated_rows * INDEX_SCAN_COST_PER_ROW * HASH_JOIN_COST_FACTOR
                        break

            estimate.join_cost += cost
            estimate.details.append(f"Join {join.table.name}: {cost:.1f}")
            accumulated_rows = int(accumulated_rows * 0.1)  # assume selectivity

    # Filter cost
    if parsed.where_conditions:
        rows = sum(
            (schema.get_table(t.name).row_count if schema and schema.get_table(t.name) else default_rows)
            for t in parsed.tables
        )
        filter_cost = len(parsed.where_conditions) * rows * CPU_OPERATOR_COST
        estimate.filter_cost = filter_cost
        estimate.details.append(f"Filter ({len(parsed.where_conditions)} conditions): {filter_cost:.1f}")

    # Sort cost (ORDER BY)
    if parsed.has_order_by:
        rows = default_rows
        if schema and parsed.tables:
            stats = schema.get_table(parsed.tables[0].name)
            if stats:
                rows = stats.row_count

        import math
        sort_cost = rows * math.log2(max(rows, 2)) * CPU_OPERATOR_COST * SORT_COST_FACTOR
        estimate.sort_cost = sort_cost
        estimate.details.append(f"Sort: {sort_cost:.1f}")

    # Aggregation cost
    if parsed.has_group_by or parsed.has_distinct:
        rows = default_rows
        if schema and parsed.tables:
            stats = schema.get_table(parsed.tables[0].name)
            if stats:
                rows = stats.row_count
        agg_cost = rows * CPU_OPERATOR_COST
        estimate.aggregation_cost = agg_cost
        estimate.details.append(f"Aggregation: {agg_cost:.1f}")

    return estimate
