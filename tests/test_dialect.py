"""Tests for SQL dialect support."""

import pytest
from sqlink import (
    Query, Table, F, Raw,
    SQLiteDialect, PostgreSQLDialect, MySQLDialect, Dialect,
)
from sqlink.expressions import ILike


class TestSQLiteDialect:
    def setup_method(self):
        self.d = SQLiteDialect()

    def test_placeholder(self):
        assert self.d.placeholder() == "?"

    def test_quote_identifier(self):
        assert self.d.quote_identifier("users") == '"users"'

    def test_boolean_literal(self):
        assert self.d.boolean_literal(True) == "1"
        assert self.d.boolean_literal(False) == "0"

    def test_select_query(self):
        sql, params = (
            Query("users").dialect(self.d)
            .select("id", "name")
            .where(F("active") == True)
            .build()
        )
        assert '"id"' in sql
        assert '"active" = ?' in sql

    def test_supports_returning(self):
        assert self.d.supports_returning() is True

    def test_supports_upsert(self):
        assert self.d.supports_upsert() is True

    def test_name(self):
        assert self.d.name() == "sqlite"


class TestPostgreSQLDialect:
    def setup_method(self):
        self.d = PostgreSQLDialect()

    def test_placeholder_increments(self):
        assert self.d.placeholder() == "$1"
        assert self.d.placeholder() == "$2"
        assert self.d.placeholder() == "$3"

    def test_reset_counter(self):
        self.d.placeholder()
        self.d.placeholder()
        self.d.reset_counter()
        assert self.d.placeholder() == "$1"

    def test_select_query(self):
        sql, params = (
            Query("users").dialect(self.d)
            .select("id", "name")
            .where(F("age") > 18)
            .build()
        )
        assert "$1" in sql
        assert params == [18]

    def test_multiple_params(self):
        sql, params = (
            Query("users").dialect(self.d)
            .select("*")
            .where(F("age") > 18, F("active") == True)
            .build()
        )
        assert "$1" in sql
        assert "$2" in sql
        assert params == [18, True]

    def test_supports_ilike(self):
        assert self.d.supports_ilike() is True

    def test_ilike_query(self):
        sql, params = (
            Query("users").dialect(self.d)
            .select("*")
            .where(F("name").ilike("%john%"))
            .build()
        )
        assert "ILIKE" in sql
        assert params == ["%john%"]

    def test_supports_returning(self):
        assert self.d.supports_returning() is True

    def test_name(self):
        assert self.d.name() == "postgresql"

    def test_insert_with_pg_placeholders(self):
        sql, params = (
            Query("users").dialect(self.d)
            .insert("name", "email")
            .values({"name": "John", "email": "john@example.com"})
            .build()
        )
        assert "$1" in sql
        assert "$2" in sql
        assert params == ["John", "john@example.com"]


class TestMySQLDialect:
    def setup_method(self):
        self.d = MySQLDialect()

    def test_placeholder(self):
        assert self.d.placeholder() == "%s"

    def test_backtick_quoting(self):
        assert self.d.quote_identifier("users") == "`users`"

    def test_dotted_identifier(self):
        assert self.d.quote_identifier("users.id") == "`users`.`id`"

    def test_star_identifier(self):
        assert self.d.quote_identifier("*") == "*"

    def test_boolean_literal(self):
        assert self.d.boolean_literal(True) == "1"
        assert self.d.boolean_literal(False) == "0"

    def test_select_query(self):
        sql, params = (
            Query("users").dialect(self.d)
            .select("id", "name")
            .where(F("active") == True)
            .build()
        )
        assert "`id`" in sql
        assert "`active` = %s" in sql

    def test_ilike_fallback(self):
        """MySQL doesn't support ILIKE, should use LOWER()."""
        sql, params = (
            Query("users").dialect(self.d)
            .select("*")
            .where(F("name").ilike("%john%"))
            .build()
        )
        assert "LOWER(" in sql
        assert "ILIKE" not in sql

    def test_upsert_mysql_style(self):
        sql, params = (
            Query("users").dialect(self.d)
            .insert("email", "name")
            .values({"email": "john@example.com", "name": "John"})
            .on_conflict(["email"])
            .build()
        )
        assert "ON DUPLICATE KEY UPDATE" in sql

    def test_name(self):
        assert self.d.name() == "mysql"


class TestGenericDialect:
    def setup_method(self):
        self.d = Dialect()

    def test_name(self):
        assert self.d.name() == "generic"

    def test_placeholder(self):
        assert self.d.placeholder() == "?"

    def test_no_ilike(self):
        assert self.d.supports_ilike() is False

    def test_no_returning(self):
        assert self.d.supports_returning() is False

    def test_dotted_identifier(self):
        assert self.d.quote_identifier("t.col") == '"t"."col"'

    def test_star_not_quoted(self):
        assert self.d.quote_identifier("*") == "*"

    def test_limit_offset_sql(self):
        assert self.d.limit_offset_sql(10, 20) == "LIMIT 10 OFFSET 20"
        assert self.d.limit_offset_sql(10, None) == "LIMIT 10"
        assert self.d.limit_offset_sql(None, 20) == "OFFSET 20"
        assert self.d.limit_offset_sql(None, None) == ""
