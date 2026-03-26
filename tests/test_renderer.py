"""Tests for query rendering utilities."""

import json
import pytest
from sqlink import Query, F
from sqlink.dialect import PostgreSQLDialect, MySQLDialect, SQLiteDialect
from sqlink.renderer import to_dict, to_json, to_prepared, to_raw_sql, to_all_dialects, render_migration


class TestToDict:
    def test_basic(self):
        q = Query("users").select("*").where(F("id") == 1)
        d = to_dict(q)
        assert d["type"] == "SELECT"
        assert d["param_count"] == 1
        assert d["dialect"] == "generic"
        assert isinstance(d["sql"], str)
        assert isinstance(d["params"], list)

    def test_with_dialect(self):
        q = Query("users").select("*")
        d = to_dict(q, PostgreSQLDialect())
        assert d["dialect"] == "postgresql"

    def test_complexity(self):
        q = Query("users").select("*")
        d = to_dict(q)
        assert d["complexity"] == "simple"

    def test_insert_type(self):
        q = Query("users").insert("name").values({"name": "X"})
        d = to_dict(q)
        assert d["type"] == "INSERT"


class TestToJson:
    def test_valid_json(self):
        q = Query("users").select("*").where(F("id") == 1)
        j = to_json(q)
        parsed = json.loads(j)
        assert "sql" in parsed
        assert "params" in parsed

    def test_indent(self):
        q = Query("users").select("*")
        j = to_json(q, indent=4)
        assert "    " in j  # 4-space indent

    def test_with_dialect(self):
        q = Query("users").select("*")
        j = to_json(q, MySQLDialect())
        parsed = json.loads(j)
        assert parsed["dialect"] == "mysql"


class TestToPrepared:
    def test_basic(self):
        q = Query("users").select("*").where(F("id") == 1)
        p = to_prepared(q)
        assert "text" in p
        assert "values" in p
        assert isinstance(p["text"], str)
        assert isinstance(p["values"], list)

    def test_with_dialect(self):
        q = Query("users").select("*").where(F("id") == 1)
        p = to_prepared(q, PostgreSQLDialect())
        assert "$1" in p["text"]

    def test_no_params(self):
        q = Query("users").select("*")
        p = to_prepared(q)
        assert p["values"] == []


class TestToRawSql:
    def test_basic(self):
        q = Query("users").select("*").where(F("name") == "John")
        raw = to_raw_sql(q)
        assert "'John'" in raw
        assert "?" not in raw

    def test_with_number(self):
        q = Query("users").select("*").where(F("id") == 42)
        raw = to_raw_sql(q)
        assert "42" in raw

    def test_with_pg_dialect(self):
        q = Query("users").select("*").where(F("id") == 1)
        raw = to_raw_sql(q, PostgreSQLDialect())
        assert "1" in raw
        assert "$1" not in raw


class TestToAllDialects:
    def test_returns_all_four(self):
        q = Query("users").select("*").where(F("active") == True)
        result = to_all_dialects(q)
        assert "postgresql" in result
        assert "mysql" in result
        assert "sqlite" in result
        assert "generic" in result

    def test_each_has_sql_and_params(self):
        q = Query("users").select("*").where(F("id") == 1)
        result = to_all_dialects(q)
        for name, data in result.items():
            assert "sql" in data
            assert "params" in data
            assert data["params"] == [1]

    def test_different_placeholders(self):
        q = Query("users").select("*").where(F("id") == 1)
        result = to_all_dialects(q)
        assert "$1" in result["postgresql"]["sql"]
        assert "%s" in result["mysql"]["sql"]
        assert "?" in result["sqlite"]["sql"]

    def test_different_quoting(self):
        q = Query("users").select("id")
        result = to_all_dialects(q)
        assert '`id`' in result["mysql"]["sql"]
        assert '"id"' in result["postgresql"]["sql"]


class TestRenderMigration:
    def test_single_statement(self):
        result = render_migration(['ALTER TABLE "users" ADD COLUMN "phone" TEXT'])
        assert result == 'ALTER TABLE "users" ADD COLUMN "phone" TEXT;'

    def test_multiple_statements(self):
        stmts = [
            'ALTER TABLE "users" ADD COLUMN "phone" TEXT',
            'ALTER TABLE "users" DROP COLUMN "fax"',
        ]
        result = render_migration(stmts)
        assert result.count(";") == 2
        assert "\n" in result

    def test_custom_separator(self):
        stmts = ["SELECT 1", "SELECT 2"]
        result = render_migration(stmts, separator="\n\n")
        assert "\n\n" in result

    def test_already_has_semicolon(self):
        result = render_migration(["SELECT 1;"])
        assert result.count(";") == 1  # No double semicolons
