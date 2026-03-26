"""Tests for WHERE clause helpers and advanced filtering patterns."""

import pytest
from sqlink import Query, F, Raw, And, Or, Not


class TestComplexWherePatterns:
    def test_nested_and_or(self):
        """Complex nested logical expression."""
        expr = (
            ((F("status") == "active") & (F("age") > 18))
            | ((F("role") == "admin") & (F("verified") == True))
        )
        sql, params = Query("users").select("*").where(expr).build()
        assert "AND" in sql
        assert "OR" in sql
        assert len(params) == 4

    def test_deeply_nested(self):
        """Three levels of nesting."""
        inner = (F("a") == 1) & (F("b") == 2)
        middle = inner | (F("c") == 3)
        outer = middle & (F("d") == 4)
        sql, params = Query("t").select("*").where(outer).build()
        assert len(params) == 4

    def test_multiple_or_conditions(self):
        """OR across many conditions."""
        expr = (
            (F("status") == "pending")
            | (F("status") == "processing")
            | (F("status") == "shipped")
        )
        sql, params = Query("orders").select("*").where(expr).build()
        assert sql.count("OR") == 2

    def test_not_with_in(self):
        """NOT combined with IN."""
        expr = ~(F("id").is_in([1, 2, 3]))
        sql, params = Query("users").select("*").where(expr).build()
        assert "NOT" in sql
        assert "IN" in sql

    def test_not_with_like(self):
        expr = ~(F("name").like("%admin%"))
        sql, params = Query("users").select("*").where(expr).build()
        assert "NOT" in sql
        assert "LIKE" in sql

    def test_mixed_where_and_where_raw(self):
        sql, params = (
            Query("users")
            .select("*")
            .where(F("active") == True)
            .where_raw('"score" > ? OR "level" > ?', [80, 5])
            .build()
        )
        assert '"active" = ?' in sql
        assert '"score" > ? OR "level" > ?' in sql
        assert params == [True, 80, 5]

    def test_where_with_subquery_expr(self):
        """WHERE with a subquery comparison."""
        sub = Query("orders").select(Raw("MAX(total)"))
        from sqlink import Subquery
        sql, params = (
            Query("orders")
            .select("*")
            .where(Raw('"total" = (' + sub.sql() + ')'))
            .build()
        )
        assert "MAX(total)" in sql


class TestChainedFiltering:
    def test_progressive_filtering(self):
        """Build query step by step."""
        q = Query("products").select("*")
        q = q.where(F("active") == True)
        q = q.where(F("price") > 0)
        q = q.where(F("stock") > 0)
        q = q.order_by(F("price").asc())
        q = q.limit(50)
        sql, params = q.build()
        assert sql.count("AND") == 2
        assert params == [True, 0, 0]
        assert "LIMIT 50" in sql

    def test_scope_composition(self):
        """Multiple scopes applied."""
        from sqlink.compose import Scope
        active = Scope(lambda q: q.where(F("active") == True))
        premium = Scope(lambda q: q.where(F("plan") == "premium"))
        recent = Scope(lambda q: q.order_by(F("created_at").desc()))

        q = Query("users").select("*")
        q = active(q)
        q = premium(q)
        q = recent(q)
        sql, params = q.build()
        assert len(params) == 2
        assert "ORDER BY" in sql


class TestNullHandling:
    def test_eq_none_produces_is_null(self):
        sql, _ = Query("users").select("*").where(F("deleted_at") == None).build()
        assert "IS NULL" in sql
        assert "= ?" not in sql

    def test_ne_none_produces_is_not_null(self):
        sql, _ = Query("users").select("*").where(F("email") != None).build()
        assert "IS NOT NULL" in sql
        assert "!= ?" not in sql

    def test_is_null_method(self):
        sql, _ = Query("users").select("*").where(F("deleted_at").is_null()).build()
        assert "IS NULL" in sql

    def test_is_not_null_method(self):
        sql, _ = Query("users").select("*").where(F("email").is_not_null()).build()
        assert "IS NOT NULL" in sql


class TestInEmptyEdgeCases:
    def test_empty_in_returns_false(self):
        """IN with empty list should return FALSE condition."""
        sql, params = Query("users").select("*").where(F("id").is_in([])).build()
        assert "1 = 0" in sql
        assert params == []

    def test_empty_not_in_returns_true(self):
        """NOT IN with empty list should return TRUE condition."""
        sql, params = Query("users").select("*").where(F("id").not_in([])).build()
        assert "1 = 1" in sql
        assert params == []

    def test_single_value_in(self):
        sql, params = Query("users").select("*").where(F("id").is_in([42])).build()
        assert "IN (?)" in sql
        assert params == [42]

    def test_large_in_list(self):
        ids = list(range(100))
        sql, params = Query("users").select("*").where(F("id").is_in(ids)).build()
        assert sql.count("?") == 100
        assert len(params) == 100
