"""Tests for window function support."""

import pytest
from sqlink import Query, F, Func, Window
from sqlink.dialect import MySQLDialect, PostgreSQLDialect


class TestWindow:
    def test_row_number(self):
        w = Window(Func("ROW_NUMBER")).order_by("id")
        sql, params = w.to_sql()
        assert sql == "ROW_NUMBER() OVER (ORDER BY id ASC)"
        assert params == []

    def test_partition_by(self):
        w = Window(Func("ROW_NUMBER")).partition_by("dept").order_by("salary", "DESC")
        sql, params = w.to_sql()
        assert "PARTITION BY dept" in sql
        assert "ORDER BY salary DESC" in sql

    def test_multiple_partition_by(self):
        w = Window(Func("SUM", F("amount"))).partition_by("user_id", "category")
        sql, params = w.to_sql()
        assert "PARTITION BY user_id, category" in sql
        assert "SUM(amount)" in sql

    def test_with_alias(self):
        w = Window(Func("RANK")).order_by("score", "DESC").alias("rank")
        sql, params = w.to_sql()
        assert "AS rank" in sql

    def test_frame_spec(self):
        w = (
            Window(Func("SUM", F("amount")))
            .partition_by("user_id")
            .order_by("created_at")
            .frame("ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW")
        )
        sql, params = w.to_sql()
        assert "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" in sql

    def test_in_query(self):
        w = Window(Func("ROW_NUMBER")).partition_by("dept").order_by("salary", "DESC").alias("rn")
        sql, params = (
            Query("employees")
            .select("name", "dept", "salary", w)
            .build()
        )
        assert "ROW_NUMBER() OVER" in sql
        assert "SELECT" in sql

    def test_with_mysql_dialect(self):
        d = MySQLDialect()
        w = Window(Func("RANK")).partition_by("dept").order_by("salary", "DESC")
        sql, params = w.to_sql(d)
        assert "PARTITION BY `dept`" in sql
        assert "ORDER BY `salary` DESC" in sql

    def test_with_pg_dialect(self):
        d = PostgreSQLDialect()
        w = Window(Func("SUM", F("amount"))).partition_by("user_id")
        sql, params = w.to_sql(d)
        assert 'PARTITION BY "user_id"' in sql

    def test_lag_function(self):
        w = Window(Func("LAG", F("price"), 1)).partition_by("product_id").order_by("date")
        sql, params = w.to_sql()
        assert "LAG(price, ?)" in sql
        assert params == [1]

    def test_ntile(self):
        w = Window(Func("NTILE", 4)).order_by("score", "DESC")
        sql, params = w.to_sql()
        assert "NTILE(?)" in sql
        assert "ORDER BY score DESC" in sql
        assert params == [4]

    def test_count_over(self):
        w = Window(Func("COUNT", "*")).partition_by("status")
        sql, params = w.to_sql()
        assert "COUNT(*) OVER (PARTITION BY status)" == sql

    def test_empty_over(self):
        w = Window(Func("COUNT", "*"))
        sql, params = w.to_sql()
        assert "COUNT(*) OVER ()" == sql

    def test_multiple_order_by(self):
        w = (
            Window(Func("DENSE_RANK"))
            .order_by("dept")
            .order_by("salary", "DESC")
        )
        sql, params = w.to_sql()
        assert "ORDER BY dept ASC, salary DESC" in sql
