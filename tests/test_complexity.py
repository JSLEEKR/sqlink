"""Tests for complexity scorer."""

import pytest
from sqlink.complexity import calculate_complexity, ComplexityBreakdown
from sqlink.parser import parse_query


class TestComplexityBreakdown:
    def test_total(self):
        b = ComplexityBreakdown(base_score=1, join_score=4, where_score=2)
        assert b.total == 7

    def test_level_low(self):
        b = ComplexityBreakdown(base_score=1)
        assert b.level == "low"

    def test_level_medium(self):
        b = ComplexityBreakdown(base_score=1, join_score=4)
        assert b.level == "medium"

    def test_level_high(self):
        b = ComplexityBreakdown(base_score=1, join_score=6, where_score=3)
        assert b.level == "high"

    def test_level_very_high(self):
        b = ComplexityBreakdown(base_score=2, join_score=6, subquery_score=6)
        assert b.level == "very high"

    def test_to_dict(self):
        b = ComplexityBreakdown(base_score=1, join_score=2)
        d = b.to_dict()
        assert d["total"] == 3
        assert d["level"] == "low"
        assert d["breakdown"]["joins"] == 2

    def test_default_details(self):
        b = ComplexityBreakdown()
        assert b.details == []


class TestCalculateComplexity:
    def test_simple_select(self):
        q = parse_query("SELECT id FROM users WHERE id = 1 LIMIT 10")
        c = calculate_complexity(q)
        assert c.total <= 5
        assert c.level in ("low", "medium")

    def test_select_star_simple(self):
        q = parse_query("SELECT * FROM users")
        c = calculate_complexity(q)
        assert c.base_score == 1

    def test_update_higher_base(self):
        q = parse_query("UPDATE users SET name = 'x' WHERE id = 1")
        c = calculate_complexity(q)
        assert c.base_score == 2

    def test_delete_higher_base(self):
        q = parse_query("DELETE FROM users WHERE id = 1")
        c = calculate_complexity(q)
        assert c.base_score == 2

    def test_joins_add_complexity(self):
        q = parse_query("SELECT * FROM a JOIN b ON a.id = b.a_id JOIN c ON b.id = c.b_id")
        c = calculate_complexity(q)
        assert c.join_score >= 4

    def test_subqueries_add_complexity(self):
        q = parse_query("SELECT * FROM t WHERE id IN (SELECT id FROM t2)")
        c = calculate_complexity(q)
        assert c.subquery_score >= 3

    def test_where_conditions(self):
        q = parse_query("SELECT * FROM t WHERE a = 1 AND b = 2 AND c = 3")
        c = calculate_complexity(q)
        assert c.where_score >= 3

    def test_function_in_where_adds(self):
        q = parse_query("SELECT * FROM t WHERE UPPER(name) = 'X'")
        c = calculate_complexity(q)
        assert c.where_score >= 2

    def test_or_in_where_adds(self):
        q = parse_query("SELECT * FROM t WHERE a = 1 OR b = 2")
        c = calculate_complexity(q)
        assert c.where_score >= 2

    def test_group_by_adds(self):
        q = parse_query("SELECT status, COUNT(*) FROM t GROUP BY status")
        c = calculate_complexity(q)
        assert c.aggregation_score >= 2

    def test_having_adds(self):
        q = parse_query("SELECT status, COUNT(*) FROM t GROUP BY status HAVING COUNT(*) > 5")
        c = calculate_complexity(q)
        assert c.aggregation_score >= 4

    def test_distinct_adds(self):
        q = parse_query("SELECT DISTINCT name FROM t")
        c = calculate_complexity(q)
        assert c.aggregation_score >= 1

    def test_order_by_adds(self):
        q = parse_query("SELECT * FROM t ORDER BY name")
        c = calculate_complexity(q)
        assert c.modifier_score >= 1

    def test_union_adds(self):
        q = parse_query("SELECT id FROM a UNION SELECT id FROM b")
        c = calculate_complexity(q)
        assert c.modifier_score >= 2

    def test_offset_adds(self):
        q = parse_query("SELECT * FROM t LIMIT 10 OFFSET 20")
        c = calculate_complexity(q)
        assert c.modifier_score >= 1

    def test_complex_query_high(self):
        sql = """
        SELECT DISTINCT u.id, u.name, COUNT(o.id)
        FROM users u
        JOIN orders o ON u.id = o.user_id
        JOIN products p ON o.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        WHERE u.status = 'active'
        AND o.created_at > '2024-01-01'
        AND p.price > 100
        GROUP BY u.id, u.name
        HAVING COUNT(o.id) > 5
        ORDER BY COUNT(o.id) DESC
        """
        q = parse_query(sql)
        c = calculate_complexity(q)
        assert c.total >= 10
        assert c.level in ("high", "very high")

    def test_details_populated(self):
        q = parse_query("SELECT * FROM a JOIN b ON a.id = b.id WHERE a.x = 1 ORDER BY a.x")
        c = calculate_complexity(q)
        assert len(c.details) >= 2

    def test_in_subquery_where_adds_extra(self):
        q = parse_query("SELECT * FROM t WHERE id IN (SELECT id FROM t2) AND x = 1")
        c = calculate_complexity(q)
        assert c.where_score >= 4  # 1 for each cond, +2 for in_subquery
