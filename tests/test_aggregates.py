"""Tests for aggregate and function helpers."""

import pytest
from sqlink.aggregates import (
    Count, Sum, Avg, Max, Min,
    Coalesce, Greatest, Least,
    Concat, Lower, Upper, Trim, Length,
    Now, CurrentTimestamp, Abs, Round,
)
from sqlink import Query, F
from sqlink.dialect import MySQLDialect, PostgreSQLDialect


class TestCountAggregate:
    def test_count_star(self):
        f = Count()
        sql, params = f.to_sql()
        assert sql == "COUNT(*)"
        assert params == []

    def test_count_column(self):
        f = Count("id")
        sql, params = f.to_sql()
        assert sql == "COUNT(id)"

    def test_count_distinct(self):
        f = Count("email", distinct=True)
        sql, params = f.to_sql()
        assert sql == "COUNT(DISTINCT email)"

    def test_count_in_query(self):
        sql, params = (
            Query("users")
            .select(Count())
            .build()
        )
        assert "COUNT(*)" in sql


class TestSumAggregate:
    def test_sum(self):
        f = Sum("amount")
        sql, params = f.to_sql()
        assert sql == "SUM(amount)"

    def test_sum_in_query(self):
        sql, params = (
            Query("orders")
            .select(Sum("total"))
            .group_by("user_id")
            .build()
        )
        assert "SUM(" in sql
        assert "GROUP BY" in sql


class TestAvgAggregate:
    def test_avg(self):
        sql, params = Avg("price").to_sql()
        assert sql == "AVG(price)"


class TestMaxMinAggregate:
    def test_max(self):
        sql, params = Max("score").to_sql()
        assert sql == "MAX(score)"

    def test_min(self):
        sql, params = Min("score").to_sql()
        assert sql == "MIN(score)"


class TestCoalesce:
    def test_coalesce_strings(self):
        f = Coalesce("nickname", "name")
        sql, params = f.to_sql()
        assert sql == "COALESCE(nickname, name)"

    def test_coalesce_with_expr(self):
        f = Coalesce(F("nickname"), F("name"))
        sql, params = f.to_sql()
        assert sql == "COALESCE(nickname, name)"


class TestGreatestLeast:
    def test_greatest(self):
        sql, params = Greatest("a", "b", "c").to_sql()
        assert sql == "GREATEST(a, b, c)"

    def test_least(self):
        sql, params = Least("a", "b").to_sql()
        assert sql == "LEAST(a, b)"


class TestStringFunctions:
    def test_concat(self):
        sql, params = Concat("first_name", "last_name").to_sql()
        assert sql == "CONCAT(first_name, last_name)"

    def test_lower(self):
        sql, params = Lower("email").to_sql()
        assert sql == "LOWER(email)"

    def test_upper(self):
        sql, params = Upper("name").to_sql()
        assert sql == "UPPER(name)"

    def test_trim(self):
        sql, params = Trim("name").to_sql()
        assert sql == "TRIM(name)"

    def test_length(self):
        sql, params = Length("description").to_sql()
        assert sql == "LENGTH(description)"


class TestMathFunctions:
    def test_abs(self):
        sql, params = Abs("balance").to_sql()
        assert sql == "ABS(balance)"

    def test_round(self):
        sql, params = Round("price", 2).to_sql()
        assert sql == "ROUND(price, ?)"
        assert params == [2]

    def test_round_no_decimals(self):
        sql, params = Round("price").to_sql()
        assert sql == "ROUND(price, ?)"
        assert params == [0]


class TestDateFunctions:
    def test_now(self):
        sql, params = Now().to_sql()
        assert sql == "NOW()"

    def test_current_timestamp(self):
        sql, params = CurrentTimestamp().to_sql()
        assert sql == "CURRENT_TIMESTAMP"


class TestAggregatesWithDialect:
    def test_count_mysql(self):
        d = MySQLDialect()
        sql, params = Count("id").to_sql(d)
        assert "COUNT" in sql

    def test_sum_postgres(self):
        d = PostgreSQLDialect()
        sql, params = Sum("amount").to_sql(d)
        assert "SUM" in sql

    def test_aggregate_in_query_with_dialect(self):
        d = PostgreSQLDialect()
        sql, params = (
            Query("orders")
            .dialect(d)
            .select("user_id", Sum("total"))
            .group_by("user_id")
            .having(F("total") > 100)
            .build()
        )
        assert "SUM" in sql
        assert "$1" in sql
