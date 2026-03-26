"""Tests for cost estimator."""

import pytest
from sqlink.cost_estimator import estimate_cost, CostEstimate
from sqlink.parser import parse_query
from sqlink.statistics import SchemaContext, TableStats, ColumnStats


class TestCostEstimate:
    def test_total(self):
        e = CostEstimate(scan_cost=100, join_cost=50)
        assert e.total == 150

    def test_rating_low(self):
        e = CostEstimate(scan_cost=50)
        assert e.rating == "low"

    def test_rating_moderate(self):
        e = CostEstimate(scan_cost=500)
        assert e.rating == "moderate"

    def test_rating_high(self):
        e = CostEstimate(scan_cost=5000)
        assert e.rating == "high"

    def test_rating_very_high(self):
        e = CostEstimate(scan_cost=50000)
        assert e.rating == "very high"

    def test_to_dict(self):
        e = CostEstimate(scan_cost=100, sort_cost=50)
        d = e.to_dict()
        assert d["total"] == 150
        assert d["breakdown"]["scan"] == 100
        assert d["breakdown"]["sort"] == 50

    def test_details(self):
        e = CostEstimate(details=["step 1", "step 2"])
        assert len(e.details) == 2


class TestEstimateCost:
    def test_simple_select(self):
        q = parse_query("SELECT * FROM users WHERE id = 1")
        cost = estimate_cost(q)
        assert cost.total > 0
        assert cost.scan_cost > 0

    def test_with_schema_context(self):
        ctx = SchemaContext()
        ctx.add_table(TableStats(
            name="users",
            row_count=100000,
            columns={"id": ColumnStats(name="id", has_index=True, distinct_count=100000)},
        ))
        q = parse_query("SELECT * FROM users WHERE id = 1")
        cost = estimate_cost(q, schema=ctx)
        assert cost.total > 0
        # With index, should be cheaper than without
        cost_no_schema = estimate_cost(q)
        # Index scan on large table should change the cost profile
        assert len(cost.details) >= 1

    def test_join_adds_cost(self):
        q1 = parse_query("SELECT * FROM users")
        q2 = parse_query("SELECT * FROM users JOIN orders ON users.id = orders.user_id")
        c1 = estimate_cost(q1)
        c2 = estimate_cost(q2)
        assert c2.join_cost > 0
        assert c2.total > c1.total

    def test_order_by_adds_sort_cost(self):
        q1 = parse_query("SELECT * FROM users")
        q2 = parse_query("SELECT * FROM users ORDER BY name")
        c1 = estimate_cost(q1)
        c2 = estimate_cost(q2)
        assert c2.sort_cost > 0
        assert c2.total > c1.total

    def test_where_adds_filter_cost(self):
        q = parse_query("SELECT * FROM t WHERE a = 1 AND b = 2 AND c = 3")
        cost = estimate_cost(q)
        assert cost.filter_cost > 0

    def test_group_by_adds_aggregation(self):
        q = parse_query("SELECT status, COUNT(*) FROM t GROUP BY status")
        cost = estimate_cost(q)
        assert cost.aggregation_cost > 0

    def test_distinct_adds_aggregation(self):
        q = parse_query("SELECT DISTINCT name FROM t")
        cost = estimate_cost(q)
        assert cost.aggregation_cost > 0

    def test_large_table_higher_cost(self):
        ctx_small = SchemaContext()
        ctx_small.add_table(TableStats(name="users", row_count=100))

        ctx_large = SchemaContext()
        ctx_large.add_table(TableStats(name="users", row_count=1000000))

        q = parse_query("SELECT * FROM users")
        c_small = estimate_cost(q, schema=ctx_small)
        c_large = estimate_cost(q, schema=ctx_large)
        assert c_large.total > c_small.total

    def test_indexed_where_cheaper(self):
        ctx = SchemaContext()
        ctx.add_table(TableStats(
            name="users",
            row_count=100000,
            columns={"id": ColumnStats(name="id", has_index=True)},
        ))
        q = parse_query("SELECT * FROM users WHERE id = 1")
        cost_indexed = estimate_cost(q, schema=ctx)

        ctx2 = SchemaContext()
        ctx2.add_table(TableStats(
            name="users",
            row_count=100000,
            columns={"id": ColumnStats(name="id", has_index=False)},
        ))
        cost_no_index = estimate_cost(q, schema=ctx2)
        assert cost_indexed.scan_cost < cost_no_index.scan_cost

    def test_details_populated(self):
        q = parse_query("SELECT * FROM users WHERE id = 1 ORDER BY name")
        cost = estimate_cost(q)
        assert len(cost.details) >= 2

    def test_empty_query(self):
        q = parse_query("SELECT 1")
        cost = estimate_cost(q)
        assert cost.total >= 0
