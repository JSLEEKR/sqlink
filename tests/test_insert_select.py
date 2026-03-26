"""Tests for INSERT FROM SELECT and edge cases."""

import pytest
from sqlink import Query, F, Raw
from sqlink.dialect import PostgreSQLDialect, MySQLDialect, SQLiteDialect


class TestInsertFromSelect:
    def test_basic_insert_select(self):
        select_q = Query("temp_users").select("name", "email").where(F("verified") == True)
        sql, params = (
            Query("users")
            .insert("name", "email")
            .from_select(select_q)
            .build()
        )
        assert 'INSERT INTO "users"' in sql
        assert "SELECT" in sql
        assert "FROM" in sql
        assert params == [True]

    def test_insert_select_without_columns(self):
        select_q = Query("temp_users").select("*")
        sql, params = (
            Query("users")
            .insert()
            .from_select(select_q)
            .build()
        )
        assert 'INSERT INTO "users"' in sql
        assert "SELECT" in sql

    def test_insert_select_with_where(self):
        select_q = (
            Query("old_orders")
            .select("user_id", "total")
            .where(F("status") == "completed", F("year") == 2024)
        )
        sql, params = (
            Query("archive_orders")
            .insert("user_id", "total")
            .from_select(select_q)
            .build()
        )
        assert "completed" in str(params)
        assert 2024 in params

    def test_insert_select_with_pg(self):
        d = PostgreSQLDialect()
        select_q = Query("staging").select("name").where(F("valid") == True)
        sql, params = (
            Query("users")
            .insert("name")
            .from_select(select_q)
            .build(d)
        )
        assert "$1" in sql

    def test_insert_select_with_returning(self):
        select_q = Query("temp").select("name", "email")
        sql, params = (
            Query("users")
            .insert("name", "email")
            .from_select(select_q)
            .returning("id")
            .build()
        )
        assert "RETURNING" in sql

    def test_insert_select_on_conflict(self):
        select_q = Query("staging").select("email", "name")
        sql, params = (
            Query("users")
            .insert("email", "name")
            .from_select(select_q)
            .on_conflict_do_nothing(["email"])
            .build()
        )
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql


class TestEdgeCases:
    def test_empty_select_columns(self):
        """SELECT * when no columns specified."""
        sql, params = Query("users").select_all().build()
        assert "SELECT * FROM" in sql

    def test_where_with_no_from(self):
        """Query with WHERE but no FROM (some DBs support this)."""
        sql, params = Query().select(Raw("1")).build()
        assert "SELECT 1" in sql

    def test_multiple_where_calls(self):
        sql, params = (
            Query("users")
            .select("*")
            .where(F("a") == 1)
            .where(F("b") == 2)
            .where(F("c") == 3)
            .build()
        )
        assert sql.count("AND") == 2
        assert params == [1, 2, 3]

    def test_clone_with_insert(self):
        base = Query("users").insert("name", "email")
        q1 = base.clone().values({"name": "A", "email": "a@x.com"})
        q2 = base.clone().values({"name": "B", "email": "b@x.com"})
        _, p1 = q1.build()
        _, p2 = q2.build()
        assert p1 == ["A", "a@x.com"]
        assert p2 == ["B", "b@x.com"]

    def test_update_with_multiple_set(self):
        sql, params = (
            Query("users")
            .update()
            .set("a", 1)
            .set("b", 2)
            .set("c", 3)
            .build()
        )
        assert sql.count("=") == 3

    def test_delete_with_complex_where(self):
        expr = (F("status") == "inactive") & (F("last_login") < "2023-01-01")
        sql, params = Query("users").delete().where(expr).build()
        assert "DELETE FROM" in sql
        assert "AND" in sql

    def test_nested_subquery(self):
        inner = Query("orders").select("user_id").where(F("total") > 100)
        from sqlink import Exists
        outer = (
            Query("users")
            .select("*")
            .where(Exists(inner))
            .build()
        )
        assert "EXISTS" in outer[0]

    def test_union_with_order_by(self):
        q1 = Query("users").select("id", "name")
        q2 = Query("admins").select("id", "name")
        sql, params = q1.union(q2).order_by(F("name").asc()).build()
        assert "UNION" in sql
        assert "ORDER BY" in sql
