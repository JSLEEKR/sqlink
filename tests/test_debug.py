"""Tests for query debugging tools."""

import pytest
from sqlink import Query, F
from sqlink.dialect import PostgreSQLDialect, MySQLDialect, SQLiteDialect
from sqlink.debug import interpolate_params, explain_query, format_sql


class TestInterpolateParams:
    def test_string_param(self):
        result = interpolate_params("SELECT * FROM users WHERE name = ?", ["John"])
        assert result == "SELECT * FROM users WHERE name = 'John'"

    def test_int_param(self):
        result = interpolate_params("SELECT * FROM users WHERE id = ?", [42])
        assert result == "SELECT * FROM users WHERE id = 42"

    def test_float_param(self):
        result = interpolate_params("SELECT * FROM users WHERE score > ?", [3.14])
        assert result == "SELECT * FROM users WHERE score > 3.14"

    def test_bool_true(self):
        result = interpolate_params("SELECT * FROM users WHERE active = ?", [True])
        assert result == "SELECT * FROM users WHERE active = TRUE"

    def test_bool_false(self):
        result = interpolate_params("SELECT * FROM users WHERE active = ?", [False])
        assert result == "SELECT * FROM users WHERE active = FALSE"

    def test_none_param(self):
        result = interpolate_params("SELECT * FROM users WHERE email = ?", [None])
        assert "NULL" in result

    def test_multiple_params(self):
        result = interpolate_params(
            "SELECT * FROM users WHERE age > ? AND name = ?",
            [18, "John"]
        )
        assert "18" in result
        assert "'John'" in result

    def test_string_with_quote(self):
        result = interpolate_params("SELECT * WHERE name = ?", ["O'Brien"])
        assert "O''Brien" in result

    def test_pg_placeholders(self):
        d = PostgreSQLDialect()
        sql = "SELECT * FROM users WHERE id = $1 AND name = $2"
        result = interpolate_params(sql, [1, "John"], d)
        assert "1" in result
        assert "'John'" in result

    def test_mysql_placeholders(self):
        d = MySQLDialect()
        result = interpolate_params("SELECT * WHERE id = %s", [42], d)
        assert "42" in result

    def test_no_params(self):
        result = interpolate_params("SELECT * FROM users", [])
        assert result == "SELECT * FROM users"


class TestExplainQuery:
    def test_select_query(self):
        sql, params = Query("users").select("*").where(F("id") == 1).build()
        info = explain_query(sql, params)
        assert info["type"] == "SELECT"
        assert info["param_count"] == 1
        assert info["clauses"]["WHERE"] == 1

    def test_insert_query(self):
        sql, params = (
            Query("users")
            .insert("name")
            .values({"name": "John"})
            .build()
        )
        info = explain_query(sql, params)
        assert info["type"] == "INSERT"

    def test_update_query(self):
        sql, params = Query("users").update(name="John").where(F("id") == 1).build()
        info = explain_query(sql, params)
        assert info["type"] == "UPDATE"

    def test_delete_query(self):
        sql, params = Query("users").delete().where(F("id") == 1).build()
        info = explain_query(sql, params)
        assert info["type"] == "DELETE"

    def test_complexity_simple(self):
        sql, params = Query("users").select("*").build()
        info = explain_query(sql, params)
        assert info["complexity"] == "simple"

    def test_complexity_moderate(self):
        from sqlink import Raw
        sql, params = (
            Query("users")
            .select("*")
            .left_join("orders", Raw('"users"."id" = "orders"."user_id"'))
            .where(F("active") == True)
            .group_by("status")
            .build()
        )
        info = explain_query(sql, params)
        assert info["complexity"] in ("moderate", "complex")

    def test_join_count(self):
        from sqlink import Raw
        sql, params = (
            Query("users")
            .select("*")
            .left_join("orders", Raw("1=1"))
            .left_join("payments", Raw("1=1"))
            .build()
        )
        info = explain_query(sql, params)
        assert info["clauses"]["JOIN"] >= 2

    def test_length(self):
        sql, params = Query("users").select("*").build()
        info = explain_query(sql, params)
        assert info["length"] == len(sql)

    def test_sql_included(self):
        sql, params = Query("users").select("*").build()
        info = explain_query(sql, params)
        assert info["sql"] == sql

    def test_params_included(self):
        sql, params = Query("users").select("*").where(F("id") == 1).build()
        info = explain_query(sql, params)
        assert info["params"] == [1]


class TestFormatSql:
    def test_simple_select(self):
        sql = 'SELECT "id", "name" FROM "users" WHERE "active" = ?'
        formatted = format_sql(sql)
        assert "SELECT" in formatted
        assert "\n" in formatted

    def test_join_formatting(self):
        sql = 'SELECT * FROM "users" INNER JOIN "orders" ON "users"."id" = "orders"."user_id" WHERE "active" = ?'
        formatted = format_sql(sql)
        assert "INNER JOIN" in formatted

    def test_group_by_formatting(self):
        sql = 'SELECT "status", COUNT(*) FROM "orders" GROUP BY "status" HAVING COUNT(*) > 5'
        formatted = format_sql(sql)
        assert "GROUP BY" in formatted
        assert "HAVING" in formatted

    def test_preserves_content(self):
        sql = 'SELECT "id" FROM "users"'
        formatted = format_sql(sql)
        assert '"id"' in formatted
        assert '"users"' in formatted
