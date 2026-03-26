"""Tests for UPDATE query building."""

import pytest
from sqlink import Query, Table, F, Raw


class TestBasicUpdate:
    def test_update_simple(self):
        sql, params = (
            Query("users")
            .update(name="John", age=30)
            .where(F("id") == 1)
            .build()
        )
        assert 'UPDATE "users"' in sql
        assert "SET" in sql
        assert params == ["John", 30, 1]

    def test_update_set_method(self):
        sql, params = (
            Query("users")
            .update()
            .set("name", "John")
            .set("age", 30)
            .where(F("id") == 1)
            .build()
        )
        assert '"name" = ?' in sql
        assert '"age" = ?' in sql

    def test_update_with_raw_expr(self):
        sql, params = (
            Query("users")
            .update()
            .set("login_count", Raw('"login_count" + 1'))
            .where(F("id") == 1)
            .build()
        )
        assert '"login_count" = "login_count" + 1' in sql

    def test_update_without_where(self):
        sql, params = Query("users").update(active=False).build()
        assert 'UPDATE "users" SET "active" = ?' == sql
        assert params == [False]

    def test_update_returning(self):
        sql, params = (
            Query("users")
            .update(name="New Name")
            .where(F("id") == 1)
            .returning("id", "name")
            .build()
        )
        assert 'RETURNING "id", "name"' in sql


class TestTableUpdate:
    def test_table_update(self):
        users = Table("users")
        sql, params = users.update(active=False).where(F("id") == 1).build()
        assert 'UPDATE "users"' in sql
        assert params == [False, 1]
