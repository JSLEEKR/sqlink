"""Tests for query diff module."""

import pytest
from sqlink.diff import diff_queries, diff_parsed, QueryDiff
from sqlink.parser import parse_query


class TestQueryDiff:
    def test_has_changes_false(self):
        d = QueryDiff()
        assert not d.has_changes
        assert d.change_count == 0

    def test_has_changes_true(self):
        d = QueryDiff(added_tables=["users"])
        assert d.has_changes
        assert d.change_count == 1

    def test_change_count(self):
        d = QueryDiff(added_tables=["a"], removed_tables=["b"], structural_changes=["c"])
        assert d.change_count == 3

    def test_to_dict(self):
        d = QueryDiff(added_tables=["users"])
        data = d.to_dict()
        assert data["has_changes"] is True
        assert data["added_tables"] == ["users"]

    def test_format_text_no_changes(self):
        d = QueryDiff()
        assert "No structural differences" in d.format_text()

    def test_format_text_with_changes(self):
        d = QueryDiff(added_tables=["orders"], removed_where=["ID = 1"])
        text = d.format_text()
        assert "+ Tables added" in text
        assert "- WHERE removed" in text


class TestDiffQueries:
    def test_identical_queries(self):
        d = diff_queries("SELECT * FROM users", "SELECT * FROM users")
        assert not d.has_changes

    def test_added_table(self):
        d = diff_queries("SELECT * FROM users", "SELECT * FROM users, orders")
        assert "orders" in d.added_tables

    def test_removed_table(self):
        d = diff_queries("SELECT * FROM users, orders", "SELECT * FROM users")
        assert "orders" in d.removed_tables

    def test_added_join(self):
        d = diff_queries(
            "SELECT * FROM users",
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id",
        )
        assert len(d.added_joins) >= 1

    def test_removed_join(self):
        d = diff_queries(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id",
            "SELECT * FROM users",
        )
        assert len(d.removed_joins) >= 1

    def test_added_where(self):
        d = diff_queries(
            "SELECT * FROM users",
            "SELECT * FROM users WHERE status = 'active'",
        )
        assert len(d.added_where) >= 1

    def test_removed_where(self):
        d = diff_queries(
            "SELECT * FROM users WHERE status = 'active'",
            "SELECT * FROM users",
        )
        assert len(d.removed_where) >= 1

    def test_added_limit(self):
        d = diff_queries(
            "SELECT * FROM users",
            "SELECT * FROM users LIMIT 10",
        )
        assert "LIMIT added" in d.structural_changes

    def test_removed_limit(self):
        d = diff_queries(
            "SELECT * FROM users LIMIT 10",
            "SELECT * FROM users",
        )
        assert "LIMIT removed" in d.structural_changes

    def test_added_order_by(self):
        d = diff_queries(
            "SELECT * FROM users",
            "SELECT * FROM users ORDER BY name",
        )
        assert "ORDER BY added" in d.structural_changes

    def test_added_group_by(self):
        d = diff_queries(
            "SELECT * FROM users",
            "SELECT status, COUNT(*) FROM users GROUP BY status",
        )
        assert "GROUP BY added" in d.structural_changes

    def test_select_star_removed(self):
        d = diff_queries(
            "SELECT * FROM users",
            "SELECT id, name FROM users",
        )
        assert "SELECT * removed" in d.structural_changes

    def test_distinct_added(self):
        d = diff_queries(
            "SELECT name FROM users",
            "SELECT DISTINCT name FROM users",
        )
        assert "DISTINCT added" in d.structural_changes

    def test_column_changes(self):
        d = diff_queries(
            "SELECT id FROM users",
            "SELECT id, name FROM users",
        )
        assert len(d.column_changes) >= 1

    def test_query_type_change(self):
        d = diff_queries(
            "SELECT * FROM users",
            "DELETE FROM users",
        )
        assert len(d.structural_changes) >= 1
        assert any("Query type changed" in s for s in d.structural_changes)

    def test_complex_diff(self):
        sql1 = "SELECT * FROM users WHERE status = 'active'"
        sql2 = """SELECT u.id, u.name FROM users u
                   JOIN orders o ON u.id = o.user_id
                   WHERE u.status = 'active' AND o.total > 100
                   ORDER BY u.name
                   LIMIT 50"""
        d = diff_queries(sql1, sql2)
        assert d.has_changes
        assert d.change_count >= 3
