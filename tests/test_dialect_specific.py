"""Tests for dialect-specific features and edge cases."""

import pytest
from sqlink import Query, F, Raw, Func
from sqlink.dialect import PostgreSQLDialect, MySQLDialect, SQLiteDialect, Dialect
from sqlink.aggregates import Count, Sum


class TestPostgreSQLSpecific:
    def setup_method(self):
        self.d = PostgreSQLDialect()

    def test_placeholder_resets_per_build(self):
        """Placeholders should reset for each build() call."""
        q = Query("users").select("*").where(F("a") == 1, F("b") == 2)
        sql1, _ = q.build(self.d)
        sql2, _ = q.build(PostgreSQLDialect())
        assert "$1" in sql1 and "$2" in sql1
        assert "$1" in sql2 and "$2" in sql2

    def test_returning_with_insert(self):
        sql, params = (
            Query("users").dialect(self.d)
            .insert("name", "email")
            .values({"name": "John", "email": "john@example.com"})
            .returning("id", "created_at")
            .build()
        )
        assert "RETURNING" in sql
        assert "$1" in sql

    def test_for_update_skip_locked(self):
        sql, _ = (
            Query("tasks").dialect(self.d)
            .select("*")
            .where(F("status") == "pending")
            .for_update()
            .limit(1)
            .build()
        )
        assert "FOR UPDATE" in sql

    def test_distinct_on(self):
        sql, _ = (
            Query("events").dialect(self.d)
            .select("user_id", "event_type", "created_at")
            .distinct_on("user_id")
            .order_by(F("user_id").asc(), F("created_at").desc())
            .build()
        )
        assert 'DISTINCT ON ("user_id")' in sql

    def test_ilike(self):
        sql, params = (
            Query("users").dialect(self.d)
            .select("*")
            .where(F("name").ilike("%john%"))
            .build()
        )
        assert "ILIKE" in sql
        assert params == ["%john%"]

    def test_upsert_pg_style(self):
        sql, params = (
            Query("users").dialect(self.d)
            .insert("email", "name")
            .values({"email": "john@example.com", "name": "John"})
            .on_conflict(["email"])
            .build()
        )
        assert "ON CONFLICT" in sql
        assert "EXCLUDED" in sql

    def test_cte_with_pg(self):
        sub = Query("users").select("id").where(F("active") == True)
        sql, params = (
            Query().dialect(self.d)
            .with_cte("active_ids", sub)
            .select("*")
            .from_table("active_ids")
            .build()
        )
        assert "$1" in sql


class TestMySQLSpecific:
    def setup_method(self):
        self.d = MySQLDialect()

    def test_backtick_everywhere(self):
        sql, _ = (
            Query("users").dialect(self.d)
            .select("id", "name")
            .where(F("active") == True)
            .order_by(F("name").asc())
            .build()
        )
        assert "`users`" in sql
        assert "`id`" in sql
        assert "`name`" in sql

    def test_on_duplicate_key(self):
        sql, _ = (
            Query("users").dialect(self.d)
            .insert("email", "name")
            .values({"email": "john@example.com", "name": "John"})
            .on_conflict(["email"])
            .build()
        )
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert "VALUES(" in sql

    def test_ilike_uses_lower(self):
        sql, params = (
            Query("users").dialect(self.d)
            .select("*")
            .where(F("name").ilike("%john%"))
            .build()
        )
        assert "LOWER(" in sql
        assert "ILIKE" not in sql

    def test_percent_s_placeholder(self):
        sql, params = (
            Query("users").dialect(self.d)
            .select("*")
            .where(F("id") == 1, F("name") == "John")
            .build()
        )
        assert sql.count("%s") == 2


class TestSQLiteSpecific:
    def setup_method(self):
        self.d = SQLiteDialect()

    def test_question_mark_placeholder(self):
        sql, params = (
            Query("users").dialect(self.d)
            .select("*")
            .where(F("id") == 1)
            .build()
        )
        assert "?" in sql

    def test_upsert_sqlite_style(self):
        sql, _ = (
            Query("users").dialect(self.d)
            .insert("email", "name")
            .values({"email": "john@example.com", "name": "John"})
            .on_conflict(["email"])
            .build()
        )
        assert "ON CONFLICT" in sql
        assert "EXCLUDED" in sql


class TestDialectConsistency:
    """Same query should produce valid SQL for all dialects."""

    @pytest.fixture(params=[
        PostgreSQLDialect(),
        MySQLDialect(),
        SQLiteDialect(),
        Dialect(),
    ])
    def dialect(self, request):
        return request.param

    def test_simple_select(self, dialect):
        sql, params = (
            Query("users")
            .select("id", "name")
            .where(F("active") == True)
            .limit(10)
            .build(dialect)
        )
        assert "SELECT" in sql
        assert "FROM" in sql
        assert "WHERE" in sql
        assert "LIMIT 10" in sql
        assert len(params) == 1

    def test_insert(self, dialect):
        sql, params = (
            Query("users")
            .insert("name")
            .values({"name": "Test"})
            .build(dialect)
        )
        assert "INSERT INTO" in sql
        assert "VALUES" in sql
        assert params == ["Test"]

    def test_update(self, dialect):
        sql, params = (
            Query("users")
            .update(name="New")
            .where(F("id") == 1)
            .build(dialect)
        )
        assert "UPDATE" in sql
        assert "SET" in sql
        assert params == ["New", 1]

    def test_delete(self, dialect):
        sql, params = (
            Query("users")
            .delete()
            .where(F("id") == 1)
            .build(dialect)
        )
        assert "DELETE FROM" in sql
        assert params == [1]

    def test_join(self, dialect):
        sql, _ = (
            Query("users")
            .select("*")
            .left_join("orders", Raw("1 = 1"))
            .build(dialect)
        )
        assert "LEFT JOIN" in sql

    def test_group_by(self, dialect):
        sql, _ = (
            Query("orders")
            .select("status", Count())
            .group_by("status")
            .build(dialect)
        )
        assert "GROUP BY" in sql
        assert "COUNT(*)" in sql
