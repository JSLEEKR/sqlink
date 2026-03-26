"""Tests for INSERT query building."""

import pytest
from sqlink import Query, Table, F, Raw


class TestBasicInsert:
    def test_insert_dict(self):
        sql, params = (
            Query("users")
            .insert("name", "email")
            .values({"name": "John", "email": "john@example.com"})
            .build()
        )
        assert 'INSERT INTO "users"' in sql
        assert "VALUES" in sql
        assert params == ["John", "john@example.com"]

    def test_insert_multiple_rows(self):
        sql, params = (
            Query("users")
            .insert("name", "email")
            .values(
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bob", "email": "bob@example.com"},
            )
            .build()
        )
        assert sql.count("(?, ?)") == 2
        assert len(params) == 4

    def test_insert_list_values(self):
        sql, params = (
            Query("users")
            .insert("name", "email")
            .values(["John", "john@example.com"])
            .build()
        )
        assert params == ["John", "john@example.com"]

    def test_insert_tuple_values(self):
        sql, params = (
            Query("users")
            .insert("name", "email")
            .values(("John", "john@example.com"))
            .build()
        )
        assert params == ["John", "john@example.com"]

    def test_insert_auto_columns_from_dict(self):
        sql, params = (
            Query("users")
            .insert()
            .values({"name": "John", "age": 30})
            .build()
        )
        assert '"name"' in sql
        assert '"age"' in sql
        assert params == ["John", 30]

    def test_insert_with_raw_expr(self):
        sql, params = (
            Query("users")
            .insert("name", "created_at")
            .values({"name": "John", "created_at": Raw("NOW()")})
            .build()
        )
        assert "NOW()" in sql
        assert params == ["John"]


class TestInsertReturning:
    def test_returning_single(self):
        sql, params = (
            Query("users")
            .insert("name")
            .values({"name": "John"})
            .returning("id")
            .build()
        )
        assert 'RETURNING "id"' in sql

    def test_returning_multiple(self):
        sql, params = (
            Query("users")
            .insert("name")
            .values({"name": "John"})
            .returning("id", "created_at")
            .build()
        )
        assert 'RETURNING "id", "created_at"' in sql


class TestUpsert:
    def test_on_conflict_do_nothing(self):
        sql, params = (
            Query("users")
            .insert("email", "name")
            .values({"email": "john@example.com", "name": "John"})
            .on_conflict_do_nothing(["email"])
            .build()
        )
        assert 'ON CONFLICT ("email") DO NOTHING' in sql

    def test_on_conflict_update(self):
        sql, params = (
            Query("users")
            .insert("email", "name")
            .values({"email": "john@example.com", "name": "John"})
            .on_conflict(["email"])
            .build()
        )
        assert "ON CONFLICT" in sql
        assert "DO UPDATE SET" in sql


class TestTableInsert:
    def test_table_insert(self):
        users = Table("users")
        sql, params = (
            users.insert("name", "email")
            .values({"name": "Jane", "email": "jane@example.com"})
            .build()
        )
        assert 'INSERT INTO "users"' in sql
        assert params == ["Jane", "jane@example.com"]
