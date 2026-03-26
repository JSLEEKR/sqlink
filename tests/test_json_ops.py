"""Tests for JSON/JSONB operators."""

import pytest
from sqlink import Query, F
from sqlink.json_ops import JsonField
from sqlink.dialect import PostgreSQLDialect, MySQLDialect


class TestJsonFieldAccess:
    def test_simple_text_access(self):
        jf = JsonField("data", "name")
        sql, params = jf.to_sql()
        assert sql == "data->>'name'"

    def test_nested_path(self):
        jf = JsonField("data", "address.city")
        sql, params = jf.to_sql()
        assert sql == "data->'address'->>'city'"

    def test_json_access(self):
        jf = JsonField("data", "address", as_text=False)
        sql, params = jf.to_sql()
        assert sql == "data->'address'"

    def test_arrow_method(self):
        jf = JsonField("data").arrow("config")
        sql, params = jf.to_sql()
        assert sql == "data->'config'"

    def test_text_method(self):
        jf = JsonField("data").text("name")
        sql, params = jf.to_sql()
        assert sql == "data->>'name'"

    def test_chained_access(self):
        jf = JsonField("data").arrow("settings").text("theme")
        sql, params = jf.to_sql()
        assert sql == "data->'settings'->>'theme'"

    def test_array_index(self):
        jf = JsonField("data").arrow_index(0)
        sql, params = jf.to_sql()
        assert sql == "data->0"

    def test_with_dialect(self):
        d = PostgreSQLDialect()
        jf = JsonField("data", "name")
        sql, params = jf.to_sql(d)
        assert '"data"' in sql
        assert "->>" in sql


class TestJsonComparison:
    def test_eq(self):
        jf = JsonField("data", "status")
        expr = jf == "active"
        sql, params = expr.to_sql()
        assert "= ?" in sql
        assert params == ["active"]

    def test_ne(self):
        expr = JsonField("data", "status") != "deleted"
        sql, params = expr.to_sql()
        assert "!= ?" in sql

    def test_gt(self):
        expr = JsonField("data", "score") > 90
        sql, params = expr.to_sql()
        assert "> ?" in sql
        assert params == [90]

    def test_lt(self):
        expr = JsonField("data", "age") < 30
        sql, params = expr.to_sql()
        assert "< ?" in sql

    def test_gte(self):
        expr = JsonField("data", "level") >= 5
        sql, params = expr.to_sql()
        assert ">= ?" in sql

    def test_lte(self):
        expr = JsonField("data", "count") <= 100
        sql, params = expr.to_sql()
        assert "<= ?" in sql

    def test_in_query(self):
        jf = JsonField("profile", "country")
        sql, params = (
            Query("users")
            .select("id", "name")
            .where(jf == "US")
            .build()
        )
        assert "->>" in sql
        assert params == ["US"]


class TestJsonContains:
    def test_contains(self):
        jf = JsonField("data")
        expr = jf.contains('{"key": "value"}')
        sql, params = expr.to_sql()
        assert "@>" in sql
        assert params == ['{"key": "value"}']

    def test_contained_by(self):
        jf = JsonField("data")
        expr = jf.contained_by('{"a": 1, "b": 2}')
        sql, params = expr.to_sql()
        assert "<@" in sql


class TestJsonKeyOps:
    def test_has_key(self):
        jf = JsonField("data")
        expr = jf.has_key("email")
        sql, params = expr.to_sql()
        assert "?" in sql
        assert params == ["email"]

    def test_has_any_keys(self):
        jf = JsonField("data")
        expr = jf.has_any_keys(["email", "phone"])
        sql, params = expr.to_sql()
        assert "?|" in sql
        assert params == [["email", "phone"]]

    def test_has_all_keys(self):
        jf = JsonField("data")
        expr = jf.has_all_keys(["name", "email"])
        sql, params = expr.to_sql()
        assert "?&" in sql


class TestJsonInQuery:
    def test_select_json_field(self):
        jf = JsonField("data", "email")
        sql, params = (
            Query("users")
            .select("id", jf)
            .build()
        )
        assert "->>" in sql

    def test_where_json_field(self):
        sql, params = (
            Query("users")
            .select("*")
            .where(JsonField("profile", "role") == "admin")
            .build()
        )
        assert "->>" in sql
        assert params == ["admin"]

    def test_nested_json_where(self):
        sql, params = (
            Query("users")
            .select("*")
            .where(JsonField("data", "address.zip") == "10001")
            .build()
        )
        assert "->" in sql
        assert "->>" in sql
        assert params == ["10001"]

    def test_json_with_pg_dialect(self):
        d = PostgreSQLDialect()
        sql, params = (
            Query("users")
            .select("*")
            .where(JsonField("data", "active") == "true")
            .build(d)
        )
        assert "$1" in sql
        assert params == ["true"]
