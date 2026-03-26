"""Tests for index advisor."""

import pytest
from sqlink.index_advisor import IndexSuggestion, suggest_indexes, _deduplicate
from sqlink.parser import parse_query


class TestIndexSuggestion:
    def test_index_name(self):
        s = IndexSuggestion(table="users", columns=["name"], reason="test")
        assert s.index_name == "idx_users_name"

    def test_composite_index_name(self):
        s = IndexSuggestion(table="users", columns=["first_name", "last_name"], reason="test")
        assert s.index_name == "idx_users_first_name_last_name"

    def test_create_sql_btree(self):
        s = IndexSuggestion(table="users", columns=["email"], reason="test")
        assert s.create_sql == "CREATE INDEX idx_users_email ON users (email);"

    def test_create_sql_gin(self):
        s = IndexSuggestion(table="users", columns=["tags"], reason="test", index_type="gin")
        assert "USING gin" in s.create_sql

    def test_to_dict(self):
        s = IndexSuggestion(table="users", columns=["id"], reason="test", priority=5)
        d = s.to_dict()
        assert d["table"] == "users"
        assert d["columns"] == ["id"]
        assert d["priority"] == 5
        assert "CREATE INDEX" in d["create_sql"]


class TestSuggestIndexes:
    def test_where_clause_suggestion(self):
        q = parse_query("SELECT * FROM users WHERE email = 'test@test.com'")
        suggestions = suggest_indexes(q)
        tables = [s.table for s in suggestions]
        assert "users" in tables

    def test_join_column_suggestion(self):
        q = parse_query("SELECT * FROM users u JOIN orders o ON u.id = o.user_id")
        suggestions = suggest_indexes(q)
        # Should suggest index on orders.user_id
        order_suggestions = [s for s in suggestions if s.table == "orders"]
        assert len(order_suggestions) >= 1
        all_cols = []
        for s in order_suggestions:
            all_cols.extend(s.columns)
        assert "user_id" in all_cols

    def test_order_by_suggestion(self):
        q = parse_query("SELECT * FROM users ORDER BY created_at")
        suggestions = suggest_indexes(q)
        has_created_at = any("created_at" in s.columns for s in suggestions)
        assert has_created_at

    def test_group_by_suggestion(self):
        q = parse_query("SELECT status, COUNT(*) FROM orders GROUP BY status")
        suggestions = suggest_indexes(q)
        has_status = any("status" in s.columns for s in suggestions)
        assert has_status

    def test_no_suggestions_for_insert(self):
        q = parse_query("INSERT INTO users (name) VALUES ('test')")
        suggestions = suggest_indexes(q)
        # INSERT shouldn't generate WHERE/ORDER BY suggestions
        where_suggestions = [s for s in suggestions if "WHERE" in s.reason]
        assert len(where_suggestions) == 0

    def test_join_priority_higher(self):
        q = parse_query("SELECT * FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = 'active'")
        suggestions = suggest_indexes(q)
        join_suggestions = [s for s in suggestions if "Join" in s.reason]
        where_suggestions = [s for s in suggestions if "WHERE" in s.reason]
        if join_suggestions and where_suggestions:
            assert join_suggestions[0].priority >= where_suggestions[0].priority

    def test_multiple_where_columns_composite(self):
        q = parse_query("SELECT * FROM users WHERE status = 'active' AND role = 'admin'")
        suggestions = suggest_indexes(q)
        composite = [s for s in suggestions if len(s.columns) > 1]
        assert len(composite) >= 1

    def test_sorted_by_priority(self):
        q = parse_query("SELECT * FROM users u JOIN orders o ON u.id = o.user_id WHERE u.status = 'active' ORDER BY u.name")
        suggestions = suggest_indexes(q)
        if len(suggestions) >= 2:
            for i in range(len(suggestions) - 1):
                assert suggestions[i].priority >= suggestions[i + 1].priority

    def test_table_qualified_where(self):
        q = parse_query("SELECT * FROM users u WHERE u.email = 'x'")
        suggestions = suggest_indexes(q)
        user_suggestions = [s for s in suggestions if s.table == "users"]
        assert len(user_suggestions) >= 1


class TestDeduplicate:
    def test_merges_same(self):
        suggestions = [
            IndexSuggestion(table="t", columns=["a"], reason="R1", priority=5),
            IndexSuggestion(table="t", columns=["a"], reason="R2", priority=8),
        ]
        result = _deduplicate(suggestions)
        assert len(result) == 1
        assert result[0].priority == 8
        assert "R1" in result[0].reason
        assert "R2" in result[0].reason

    def test_keeps_different(self):
        suggestions = [
            IndexSuggestion(table="t", columns=["a"], reason="R1"),
            IndexSuggestion(table="t", columns=["b"], reason="R2"),
        ]
        result = _deduplicate(suggestions)
        assert len(result) == 2

    def test_empty_list(self):
        assert _deduplicate([]) == []
