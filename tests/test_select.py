"""Tests for SELECT query building."""

import pytest
from sqlink import Query, Table, F, Func, Raw, Subquery
from sqlink.expressions import OrderExpr


class TestBasicSelect:
    def test_select_all_default(self):
        sql, params = Query("users").select_all().build()
        assert sql == 'SELECT * FROM "users"'
        assert params == []

    def test_select_specific_columns(self):
        sql, params = Query("users").select("id", "name", "email").build()
        assert sql == 'SELECT "id", "name", "email" FROM "users"'
        assert params == []

    def test_select_star(self):
        sql, params = Query("users").select("*").build()
        assert sql == 'SELECT * FROM "users"'

    def test_select_with_alias(self):
        sql, params = Query("users", alias="u").select("id").build()
        assert sql == 'SELECT "id" FROM "users" AS "u"'

    def test_select_distinct(self):
        sql, params = Query("users").select("name").distinct().build()
        assert sql == 'SELECT DISTINCT "name" FROM "users"'

    def test_add_select(self):
        q = Query("users").select("id").add_select("name", "email")
        sql, params = q.build()
        assert sql == 'SELECT "id", "name", "email" FROM "users"'

    def test_from_table(self):
        sql, params = Query().select("id").from_table("users").build()
        assert sql == 'SELECT "id" FROM "users"'

    def test_from_table_with_alias(self):
        sql, params = Query().select("id").from_table("users", "u").build()
        assert sql == 'SELECT "id" FROM "users" AS "u"'


class TestWhere:
    def test_simple_eq(self):
        sql, params = Query("users").select("*").where(F("id") == 1).build()
        assert sql == 'SELECT * FROM "users" WHERE "id" = ?'
        assert params == [1]

    def test_not_equal(self):
        sql, params = Query("users").select("*").where(F("status") != "deleted").build()
        assert sql == 'SELECT * FROM "users" WHERE "status" != ?'
        assert params == ["deleted"]

    def test_greater_than(self):
        sql, params = Query("users").select("*").where(F("age") > 18).build()
        assert sql == 'SELECT * FROM "users" WHERE "age" > ?'
        assert params == [18]

    def test_greater_equal(self):
        sql, params = Query("users").select("*").where(F("age") >= 18).build()
        assert sql == 'SELECT * FROM "users" WHERE "age" >= ?'
        assert params == [18]

    def test_less_than(self):
        sql, params = Query("users").select("*").where(F("age") < 65).build()
        assert sql == 'SELECT * FROM "users" WHERE "age" < ?'
        assert params == [65]

    def test_less_equal(self):
        sql, params = Query("users").select("*").where(F("age") <= 65).build()
        assert sql == 'SELECT * FROM "users" WHERE "age" <= ?'
        assert params == [65]

    def test_multiple_where(self):
        sql, params = (
            Query("users")
            .select("*")
            .where(F("age") > 18, F("active") == True)
            .build()
        )
        assert "WHERE" in sql
        assert '"age" > ?' in sql
        assert '"active" = ?' in sql
        assert params == [18, True]

    def test_where_raw(self):
        sql, params = (
            Query("users")
            .select("*")
            .where_raw('"score" > ? AND "level" < ?', [100, 5])
            .build()
        )
        assert '"score" > ? AND "level" < ?' in sql
        assert params == [100, 5]

    def test_where_is_null(self):
        sql, params = Query("users").select("*").where(F("deleted_at") == None).build()
        assert '"deleted_at" IS NULL' in sql
        assert params == []

    def test_where_is_not_null(self):
        sql, params = Query("users").select("*").where(F("email") != None).build()
        assert '"email" IS NOT NULL' in sql
        assert params == []


class TestExpressions:
    def test_and_expr(self):
        expr = (F("a") > 1) & (F("b") < 10)
        sql, params = Query("t").select("*").where(expr).build()
        assert '("a" > ? AND "b" < ?)' in sql
        assert params == [1, 10]

    def test_or_expr(self):
        expr = (F("a") > 1) | (F("b") < 10)
        sql, params = Query("t").select("*").where(expr).build()
        assert '("a" > ? OR "b" < ?)' in sql
        assert params == [1, 10]

    def test_not_expr(self):
        expr = ~(F("active") == True)
        sql, params = Query("t").select("*").where(expr).build()
        assert 'NOT ("active" = ?)' in sql
        assert params == [True]

    def test_in_expr(self):
        sql, params = Query("users").select("*").where(F("id").is_in([1, 2, 3])).build()
        assert '"id" IN (?, ?, ?)' in sql
        assert params == [1, 2, 3]

    def test_in_empty(self):
        sql, params = Query("users").select("*").where(F("id").is_in([])).build()
        assert "1 = 0" in sql
        assert params == []

    def test_not_in(self):
        sql, params = Query("users").select("*").where(F("id").not_in([4, 5])).build()
        assert '"id" NOT IN (?, ?)' in sql
        assert params == [4, 5]

    def test_not_in_empty(self):
        sql, params = Query("users").select("*").where(F("id").not_in([])).build()
        assert "1 = 1" in sql

    def test_between(self):
        sql, params = Query("users").select("*").where(F("age").between(18, 65)).build()
        assert '"age" BETWEEN ? AND ?' in sql
        assert params == [18, 65]

    def test_like(self):
        sql, params = Query("users").select("*").where(F("name").like("%john%")).build()
        assert '"name" LIKE ?' in sql
        assert params == ["%john%"]

    def test_is_null_method(self):
        sql, params = Query("users").select("*").where(F("email").is_null()).build()
        assert '"email" IS NULL' in sql

    def test_is_not_null_method(self):
        sql, params = Query("users").select("*").where(F("email").is_not_null()).build()
        assert '"email" IS NOT NULL' in sql


class TestOrderBy:
    def test_order_by_string(self):
        sql, _ = Query("users").select("*").order_by("name").build()
        assert 'ORDER BY "name"' in sql

    def test_order_by_asc(self):
        sql, _ = Query("users").select("*").order_by_asc("name").build()
        assert 'ORDER BY "name" ASC' in sql

    def test_order_by_desc(self):
        sql, _ = Query("users").select("*").order_by_desc("created_at").build()
        assert 'ORDER BY "created_at" DESC' in sql

    def test_order_by_f_asc(self):
        sql, _ = Query("users").select("*").order_by(F("name").asc()).build()
        assert 'ORDER BY "name" ASC' in sql

    def test_order_by_f_desc(self):
        sql, _ = Query("users").select("*").order_by(F("age").desc()).build()
        assert 'ORDER BY "age" DESC' in sql

    def test_multiple_order_by(self):
        sql, _ = (
            Query("users")
            .select("*")
            .order_by(F("name").asc(), F("age").desc())
            .build()
        )
        assert '"name" ASC' in sql
        assert '"age" DESC' in sql


class TestLimitOffset:
    def test_limit(self):
        sql, _ = Query("users").select("*").limit(10).build()
        assert "LIMIT 10" in sql

    def test_offset(self):
        sql, _ = Query("users").select("*").offset(20).build()
        assert "OFFSET 20" in sql

    def test_limit_offset(self):
        sql, _ = Query("users").select("*").limit(10).offset(20).build()
        assert "LIMIT 10" in sql
        assert "OFFSET 20" in sql

    def test_paginate(self):
        sql, _ = Query("users").select("*").paginate(page=3, per_page=10).build()
        assert "LIMIT 10" in sql
        assert "OFFSET 20" in sql

    def test_paginate_first_page(self):
        sql, _ = Query("users").select("*").paginate(page=1, per_page=25).build()
        assert "LIMIT 25" in sql
        assert "OFFSET 0" in sql


class TestGroupBy:
    def test_group_by(self):
        sql, _ = Query("orders").select("status").group_by("status").build()
        assert 'GROUP BY "status"' in sql

    def test_group_by_multiple(self):
        sql, _ = (
            Query("orders")
            .select("status", "country")
            .group_by("status", "country")
            .build()
        )
        assert 'GROUP BY "status", "country"' in sql

    def test_having(self):
        sql, params = (
            Query("orders")
            .select("status", Raw("COUNT(*) as cnt"))
            .group_by("status")
            .having(Raw("COUNT(*) > ?", [5]))
            .build()
        )
        assert "HAVING COUNT(*) > ?" in sql
        assert params == [5]


class TestJoin:
    def test_inner_join(self):
        sql, params = (
            Query("users")
            .select("users.id", "orders.total")
            .join("orders", Raw('"users"."id" = "orders"."user_id"'))
            .build()
        )
        assert 'INNER JOIN "orders"' in sql

    def test_left_join(self):
        sql, _ = (
            Query("users")
            .select("*")
            .left_join("orders", Raw('"users"."id" = "orders"."user_id"'))
            .build()
        )
        assert 'LEFT JOIN "orders"' in sql

    def test_right_join(self):
        sql, _ = (
            Query("users")
            .select("*")
            .right_join("orders", Raw('"users"."id" = "orders"."user_id"'))
            .build()
        )
        assert 'RIGHT JOIN "orders"' in sql

    def test_full_join(self):
        sql, _ = (
            Query("users")
            .select("*")
            .full_join("orders", Raw('"users"."id" = "orders"."user_id"'))
            .build()
        )
        assert 'FULL OUTER JOIN "orders"' in sql

    def test_cross_join(self):
        sql, _ = Query("users").select("*").cross_join("colors").build()
        assert 'CROSS JOIN "colors"' in sql

    def test_join_with_alias(self):
        sql, _ = (
            Query("users")
            .select("*")
            .join("orders", Raw('"u"."id" = "o"."user_id"'), alias="o")
            .build()
        )
        assert '"orders" AS "o"' in sql

    def test_join_raw(self):
        sql, _ = (
            Query("users")
            .select("*")
            .join_raw("NATURAL JOIN orders")
            .build()
        )
        assert "NATURAL JOIN orders" in sql


class TestSubquery:
    def test_from_subquery(self):
        inner = Query("orders").select("user_id", Raw("SUM(total) as total_sum")).group_by("user_id")
        sql, params = (
            Query()
            .select("user_id", "total_sum")
            .from_subquery(inner, "sub")
            .build()
        )
        assert "FROM (SELECT" in sql
        assert "AS sub" in sql

    def test_where_subquery(self):
        from sqlink import Exists
        sub = Query("orders").select("1").where(Raw('"orders"."user_id" = "users"."id"'))
        sql, params = (
            Query("users")
            .select("*")
            .where(Exists(sub))
            .build()
        )
        assert "EXISTS (SELECT" in sql


class TestClone:
    def test_clone_independence(self):
        q1 = Query("users").select("*").where(F("active") == True)
        q2 = q1.clone().where(F("age") > 18)
        sql1, p1 = q1.build()
        sql2, p2 = q2.build()
        assert len(p1) == 1
        assert len(p2) == 2

    def test_clone_preserves_original(self):
        q = Query("users").select("id", "name")
        q2 = q.clone().limit(10)
        sql1, _ = q.build()
        sql2, _ = q2.build()
        assert "LIMIT" not in sql1
        assert "LIMIT 10" in sql2


class TestTable:
    def test_table_select(self):
        users = Table("users")
        sql, _ = users.select("id", "name").build()
        assert 'SELECT "id", "name" FROM "users"' == sql

    def test_table_delete(self):
        users = Table("users")
        sql, params = users.delete().where(F("id") == 1).build()
        assert 'DELETE FROM "users"' in sql
        assert params == [1]

    def test_table_with_alias(self):
        users = Table("users", alias="u")
        sql, _ = users.select("id").build()
        assert '"users" AS "u"' in sql
