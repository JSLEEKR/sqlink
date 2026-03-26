"""Tests for SQL comments and query labeling."""

import pytest
from sqlink import Query, F


class TestComment:
    def test_basic_comment(self):
        sql, _ = Query("users").select("*").comment("Fetch all users").build()
        assert "/* Fetch all users */" in sql

    def test_comment_position(self):
        sql, _ = Query("users").select("*").comment("Load users").build()
        assert sql.startswith("/* Load users */")

    def test_comment_with_where(self):
        sql, params = (
            Query("users")
            .select("*")
            .where(F("active") == True)
            .comment("Active users only")
            .build()
        )
        assert "/* Active users only */" in sql
        assert "WHERE" in sql

    def test_comment_with_insert(self):
        sql, _ = (
            Query("users")
            .insert("name")
            .values({"name": "John"})
            .comment("Create user")
            .build()
        )
        assert "/* Create user */" in sql
        assert "INSERT" in sql

    def test_comment_with_update(self):
        sql, _ = (
            Query("users")
            .update(name="New")
            .comment("Update name")
            .build()
        )
        assert "/* Update name */" in sql

    def test_comment_with_delete(self):
        sql, _ = (
            Query("users")
            .delete()
            .where(F("id") == 1)
            .comment("Remove user")
            .build()
        )
        assert "/* Remove user */" in sql


class TestLabel:
    def test_basic_label(self):
        sql, _ = Query("users").select("*").label("api:get-users").build()
        assert "/* api:get-users */" in sql

    def test_label_overrides_comment(self):
        sql, _ = (
            Query("users")
            .select("*")
            .comment("This comment")
            .label("this-label")
            .build()
        )
        assert "/* this-label */" in sql
        assert "This comment" not in sql

    def test_label_for_tracing(self):
        sql, _ = (
            Query("orders")
            .select("*")
            .where(F("user_id") == 42)
            .label("order-service:list-orders")
            .build()
        )
        assert "order-service:list-orders" in sql

    def test_label_preserved_in_clone(self):
        q = Query("users").select("*").label("base-query")
        q2 = q.clone().where(F("active") == True)
        sql, _ = q2.build()
        assert "/* base-query */" in sql

    def test_no_comment_by_default(self):
        sql, _ = Query("users").select("*").build()
        assert "/*" not in sql
