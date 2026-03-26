"""Tests for DELETE query building."""

import pytest
from sqlink import Query, Table, F


class TestBasicDelete:
    def test_delete_with_where(self):
        sql, params = Query("users").delete().where(F("id") == 1).build()
        assert sql == 'DELETE FROM "users" WHERE "id" = ?'
        assert params == [1]

    def test_delete_all(self):
        sql, params = Query("users").delete().build()
        assert sql == 'DELETE FROM "users"'
        assert params == []

    def test_delete_multiple_conditions(self):
        sql, params = (
            Query("users")
            .delete()
            .where(F("active") == False, F("last_login") < "2023-01-01")
            .build()
        )
        assert '"active" = ?' in sql
        assert '"last_login" < ?' in sql
        assert params == [False, "2023-01-01"]

    def test_delete_returning(self):
        sql, params = (
            Query("users")
            .delete()
            .where(F("id") == 1)
            .returning("id", "email")
            .build()
        )
        assert 'RETURNING "id", "email"' in sql


class TestTableDelete:
    def test_table_delete(self):
        users = Table("users")
        sql, params = users.delete().where(F("id") == 5).build()
        assert 'DELETE FROM "users" WHERE "id" = ?' == sql
        assert params == [5]
