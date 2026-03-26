"""Tests for advanced query features: CTE, UNION, subqueries, locking."""

import pytest
from sqlink import Query, F, Raw, Func, Subquery, Exists


class TestCTE:
    def test_simple_cte(self):
        active_users = Query("users").select("id", "name").where(F("active") == True)
        sql, params = (
            Query()
            .with_cte("active", active_users)
            .select("*")
            .from_table("active")
            .build()
        )
        assert "WITH" in sql
        assert '"active" AS' in sql
        assert "SELECT" in sql

    def test_recursive_cte(self):
        base = Query("categories").select("id", "name", "parent_id").where(F("parent_id") == None)
        sql, params = (
            Query()
            .with_cte("tree", base, recursive=True)
            .select("*")
            .from_table("tree")
            .build()
        )
        assert "WITH RECURSIVE" in sql


class TestUnion:
    def test_union(self):
        q1 = Query("users").select("id", "name").where(F("active") == True)
        q2 = Query("admins").select("id", "name")
        sql, params = q1.union(q2).build()
        assert "UNION" in sql
        assert params == [True]

    def test_union_all(self):
        q1 = Query("users").select("id")
        q2 = Query("admins").select("id")
        sql, params = q1.union_all(q2).build()
        assert "UNION ALL" in sql

    def test_intersect(self):
        q1 = Query("users").select("id")
        q2 = Query("premium_users").select("id")
        sql, params = q1.intersect(q2).build()
        assert "INTERSECT" in sql

    def test_except(self):
        q1 = Query("users").select("id")
        q2 = Query("banned_users").select("id")
        sql, params = q1.except_(q2).build()
        assert "EXCEPT" in sql


class TestLocking:
    def test_for_update(self):
        sql, _ = Query("users").select("*").where(F("id") == 1).for_update().build()
        assert "FOR UPDATE" in sql

    def test_for_share(self):
        sql, _ = Query("users").select("*").where(F("id") == 1).for_share().build()
        assert "FOR SHARE" in sql


class TestExists:
    def test_exists_subquery(self):
        sub = Query("orders").select(Raw("1")).where(Raw('"orders"."user_id" = "users"."id"'))
        sql, params = (
            Query("users")
            .select("*")
            .where(Exists(sub))
            .build()
        )
        assert "EXISTS" in sql
        assert "SELECT 1" in sql


class TestSubquery:
    def test_subquery_in_select(self):
        sub = Query("orders").select(Raw("COUNT(*)")).where(Raw('"orders"."user_id" = "users"."id"'))
        sq = Subquery(sub, "order_count")
        sql, params = Query("users").select("id", sq).build()
        assert "AS order_count" in sql

    def test_subquery_in_from(self):
        inner = Query("orders").select("user_id", Raw("SUM(total) as total"))
        sql, params = (
            Query()
            .select("*")
            .from_subquery(inner, "totals")
            .where(Raw("total > ?", [1000]))
            .build()
        )
        assert "FROM (SELECT" in sql
        assert "AS totals" in sql
        assert params == [1000]


class TestComplexQueries:
    def test_full_select(self):
        """Test a complex real-world query."""
        sql, params = (
            Query("users", alias="u")
            .select("u.id", "u.name", Raw("COUNT(o.id) as order_count"))
            .left_join("orders", Raw('"u"."id" = "o"."user_id"'), alias="o")
            .where(F("u.active") == True)
            .group_by("u.id", "u.name")
            .having(Raw("COUNT(o.id) > ?", [5]))
            .order_by(F("order_count").desc())
            .limit(10)
            .build()
        )
        assert "SELECT" in sql
        assert "LEFT JOIN" in sql
        assert "WHERE" in sql
        assert "GROUP BY" in sql
        assert "HAVING" in sql
        assert "ORDER BY" in sql
        assert "LIMIT 10" in sql

    def test_chained_where(self):
        sql, params = (
            Query("products")
            .select("*")
            .where(F("price") > 10)
            .where(F("category") == "electronics")
            .where(F("stock") > 0)
            .build()
        )
        assert sql.count("AND") == 2
        assert len(params) == 3

    def test_sql_method(self):
        q = Query("users").select("*").where(F("id") == 1)
        sql = q.sql()
        assert isinstance(sql, str)
        assert "SELECT" in sql
