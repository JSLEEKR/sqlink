"""Tests for statistics module."""

import pytest
from sqlink.statistics import ColumnStats, TableStats, SchemaContext


class TestColumnStats:
    def test_defaults(self):
        c = ColumnStats(name="id")
        assert c.distinct_count is None
        assert c.null_fraction == 0.0
        assert not c.has_index
        assert not c.is_primary_key

    def test_with_index(self):
        c = ColumnStats(name="email", has_index=True, index_name="idx_email")
        assert c.has_index
        assert c.index_name == "idx_email"


class TestTableStats:
    def test_is_large(self):
        t = TableStats(name="users", row_count=200_000)
        assert t.is_large
        assert not t.is_very_large

    def test_is_very_large(self):
        t = TableStats(name="events", row_count=5_000_000)
        assert t.is_large
        assert t.is_very_large

    def test_not_large(self):
        t = TableStats(name="config", row_count=100)
        assert not t.is_large

    def test_selectivity_with_stats(self):
        t = TableStats(
            name="users",
            row_count=1000,
            columns={"status": ColumnStats(name="status", distinct_count=5)},
        )
        sel = t.selectivity("status")
        assert sel == pytest.approx(0.2)

    def test_selectivity_unique(self):
        t = TableStats(
            name="users",
            row_count=1000,
            columns={"id": ColumnStats(name="id", distinct_count=1000)},
        )
        sel = t.selectivity("id")
        assert sel == pytest.approx(0.001)

    def test_selectivity_unknown(self):
        t = TableStats(name="users", row_count=1000)
        assert t.selectivity("unknown") == 0.5

    def test_selectivity_no_distinct(self):
        t = TableStats(
            name="users",
            row_count=1000,
            columns={"x": ColumnStats(name="x")},
        )
        assert t.selectivity("x") == 0.5

    def test_selectivity_zero_rows(self):
        t = TableStats(
            name="users",
            row_count=0,
            columns={"id": ColumnStats(name="id", distinct_count=10)},
        )
        assert t.selectivity("id") == 0.5

    def test_has_index_on(self):
        t = TableStats(
            name="users",
            columns={"email": ColumnStats(name="email", has_index=True)},
        )
        assert t.has_index_on("email")
        assert not t.has_index_on("name")

    def test_to_dict(self):
        t = TableStats(
            name="users",
            row_count=1000,
            columns={"id": ColumnStats(name="id", is_primary_key=True)},
            indexes=["idx_users_pkey"],
        )
        d = t.to_dict()
        assert d["name"] == "users"
        assert d["row_count"] == 1000
        assert d["is_large"] is False
        assert "id" in d["columns"]
        assert d["columns"]["id"]["is_primary_key"] is True


class TestSchemaContext:
    def test_add_and_get_table(self):
        ctx = SchemaContext()
        ctx.add_table(TableStats(name="users", row_count=1000))
        assert ctx.has_table("users")
        assert ctx.get_table("users").row_count == 1000

    def test_get_nonexistent_table(self):
        ctx = SchemaContext()
        assert ctx.get_table("nonexistent") is None
        assert not ctx.has_table("nonexistent")

    def test_estimate_join_rows(self):
        ctx = SchemaContext()
        ctx.add_table(TableStats(
            name="users",
            row_count=1000,
            columns={"id": ColumnStats(name="id", distinct_count=1000)},
        ))
        ctx.add_table(TableStats(
            name="orders",
            row_count=5000,
            columns={"user_id": ColumnStats(name="user_id", distinct_count=1000)},
        ))
        rows = ctx.estimate_join_rows("users", "id", "orders", "user_id")
        assert rows > 0
        assert rows <= 5000  # Should be approximately 5000

    def test_estimate_join_unknown_table(self):
        ctx = SchemaContext()
        assert ctx.estimate_join_rows("a", "id", "b", "id") == 0

    def test_estimate_filtered_rows(self):
        ctx = SchemaContext()
        ctx.add_table(TableStats(
            name="users",
            row_count=10000,
            columns={"status": ColumnStats(name="status", distinct_count=5)},
        ))
        rows = ctx.estimate_filtered_rows("users", "status")
        assert rows == 2000

    def test_estimate_filtered_unknown(self):
        ctx = SchemaContext()
        assert ctx.estimate_filtered_rows("unknown", "col") == 0

    def test_to_dict(self):
        ctx = SchemaContext()
        ctx.add_table(TableStats(name="users", row_count=100))
        d = ctx.to_dict()
        assert "users" in d["tables"]

    def test_from_dict(self):
        data = {
            "tables": {
                "users": {
                    "row_count": 1000,
                    "schema": "public",
                    "indexes": ["idx_pkey"],
                    "columns": {
                        "id": {
                            "distinct_count": 1000,
                            "null_fraction": 0.0,
                            "has_index": True,
                            "is_primary_key": True,
                        },
                        "name": {
                            "distinct_count": 800,
                        },
                    },
                },
            },
        }
        ctx = SchemaContext.from_dict(data)
        assert ctx.has_table("users")
        t = ctx.get_table("users")
        assert t.row_count == 1000
        assert t.schema == "public"
        assert t.columns["id"].is_primary_key
        assert t.columns["id"].has_index
        assert t.columns["name"].distinct_count == 800

    def test_from_dict_empty(self):
        ctx = SchemaContext.from_dict({})
        assert len(ctx.tables) == 0

    def test_roundtrip(self):
        ctx = SchemaContext()
        ctx.add_table(TableStats(
            name="t",
            row_count=500,
            columns={"id": ColumnStats(name="id", distinct_count=500, has_index=True)},
        ))
        d = ctx.to_dict()
        ctx2 = SchemaContext.from_dict(d)
        assert ctx2.get_table("t").row_count == 500
