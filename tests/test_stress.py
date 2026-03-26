"""Stress tests — verify performance and correctness at scale."""

import pytest
from sqlink import Query, F, Raw, Func
from sqlink.compose import BatchInsert
from sqlink.dialect import PostgreSQLDialect, MySQLDialect, SQLiteDialect


class TestLargeQueries:
    def test_many_where_conditions(self):
        """50 WHERE conditions."""
        q = Query("users").select("*")
        for i in range(50):
            q = q.where(F(f"col{i}") == i)
        sql, params = q.build()
        assert sql.count("AND") == 49
        assert len(params) == 50

    def test_many_columns(self):
        """Select 100 columns."""
        cols = [f"col{i}" for i in range(100)]
        sql, _ = Query("wide_table").select(*cols).build()
        assert sql.count(",") == 99

    def test_many_joins(self):
        """10 JOINs."""
        q = Query("t0").select("*")
        for i in range(1, 11):
            q = q.left_join(f"t{i}", Raw(f'"t0"."id" = "t{i}"."t0_id"'))
        sql, _ = q.build()
        assert sql.count("LEFT JOIN") == 10

    def test_large_in_list(self):
        """IN with 500 values."""
        ids = list(range(500))
        sql, params = Query("users").select("*").where(F("id").is_in(ids)).build()
        assert len(params) == 500

    def test_many_order_by(self):
        """10 ORDER BY columns."""
        q = Query("users").select("*")
        for i in range(10):
            q = q.order_by(F(f"col{i}").asc())
        sql, _ = q.build()
        assert sql.count("ASC") == 10

    def test_deep_cte_chain(self):
        """5 CTEs chained."""
        q = Query()
        for i in range(5):
            sub = Query(f"table{i}").select("id", "name")
            q = q.with_cte(f"cte{i}", sub)
        q = q.select("*").from_table("cte4")
        sql, _ = q.build()
        assert sql.count("AS (SELECT") == 5

    def test_batch_insert_large(self):
        """1000 row batch insert."""
        batch = BatchInsert("events", ["name", "value"], chunk_size=250)
        for i in range(1000):
            batch.add({"name": f"event{i}", "value": i})
        chunks = batch.build_chunks()
        assert len(chunks) == 4
        for sql, params in chunks:
            assert "INSERT INTO" in sql

    def test_union_many(self):
        """5 UNION queries."""
        q = Query("t1").select("id")
        for i in range(2, 6):
            q = q.union(Query(f"t{i}").select("id"))
        sql, _ = q.build()
        assert sql.count("UNION") == 4

    def test_complex_nested_expressions(self):
        """Deeply nested expression tree."""
        expr = F("a") == 1
        for i in range(20):
            expr = expr & (F(f"x{i}") == i)
        sql, params = Query("t").select("*").where(expr).build()
        assert len(params) == 21


class TestDialectConsistency:
    """Same complex query across all dialects."""

    def test_complex_query_all_dialects(self):
        for dialect in [PostgreSQLDialect(), MySQLDialect(), SQLiteDialect()]:
            q = (
                Query("users")
                .select("id", "name", "email")
                .where(F("active") == True, F("age") > 18)
                .order_by(F("name").asc())
                .limit(10)
                .offset(20)
            )
            sql, params = q.build(dialect)
            assert "SELECT" in sql
            assert "WHERE" in sql
            assert "ORDER BY" in sql
            assert "LIMIT 10" in sql
            assert "OFFSET 20" in sql
            assert params == [True, 18]


class TestCloneStability:
    def test_clone_does_not_affect_original(self):
        """Verify clone isolation over many mutations."""
        original = Query("users").select("*")
        for i in range(20):
            clone = original.clone()
            clone.where(F(f"col{i}") == i)
            clone.limit(i)
        # Original should have no WHERE or LIMIT
        sql, params = original.build()
        assert "WHERE" not in sql
        assert "LIMIT" not in sql
        assert params == []

    def test_many_clones(self):
        """Create 100 clones."""
        base = Query("users").select("*").where(F("active") == True)
        clones = [base.clone().where(F("id") == i) for i in range(100)]
        for i, c in enumerate(clones):
            _, params = c.build()
            assert params == [True, i]
