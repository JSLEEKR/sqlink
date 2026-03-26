"""Tests for expression aliases and DISTINCT ON."""

import pytest
from sqlink import Query, F, Func, Raw, Alias
from sqlink.dialect import PostgreSQLDialect, MySQLDialect
from sqlink.aggregates import Count, Sum


class TestAlias:
    def test_f_as(self):
        expr = F("name").as_("user_name")
        sql, params = expr.to_sql()
        assert sql == "name AS user_name"

    def test_f_as_with_dialect(self):
        d = PostgreSQLDialect()
        expr = F("name").as_("user_name")
        sql, params = expr.to_sql(d)
        assert '"name" AS "user_name"' == sql

    def test_func_as(self):
        expr = Count().as_("total")
        sql, params = expr.to_sql()
        assert sql == "COUNT(*) AS total"

    def test_sum_as(self):
        expr = Sum("amount").as_("total_amount")
        sql, params = expr.to_sql()
        assert sql == "SUM(amount) AS total_amount"

    def test_raw_as(self):
        expr = Raw("NOW()").as_("current_time")
        sql, params = expr.to_sql()
        assert sql == "NOW() AS current_time"

    def test_alias_in_select(self):
        sql, params = (
            Query("orders")
            .select("user_id", Count().as_("order_count"))
            .group_by("user_id")
            .build()
        )
        assert "COUNT(*) AS" in sql

    def test_alias_constructor(self):
        a = Alias(F("name"), "n")
        sql, params = a.to_sql()
        assert sql == "name AS n"

    def test_complex_expr_alias(self):
        expr = Func("COALESCE", F("nickname"), F("name")).as_("display_name")
        sql, params = expr.to_sql()
        assert "COALESCE(nickname, name) AS display_name" == sql


class TestDistinctOn:
    def test_distinct_on_single(self):
        d = PostgreSQLDialect()
        sql, params = (
            Query("events")
            .select("user_id", "event_type", "created_at")
            .distinct_on("user_id")
            .order_by(F("user_id").asc(), F("created_at").desc())
            .build(d)
        )
        assert 'DISTINCT ON ("user_id")' in sql

    def test_distinct_on_multiple(self):
        sql, params = (
            Query("events")
            .select("*")
            .distinct_on("user_id", "event_type")
            .build()
        )
        assert "DISTINCT ON" in sql
        assert '"user_id"' in sql
        assert '"event_type"' in sql

    def test_distinct_on_overrides_distinct(self):
        sql, params = (
            Query("events")
            .select("*")
            .distinct_on("user_id")
            .build()
        )
        assert "DISTINCT ON" in sql
        # Should not have bare DISTINCT
        assert sql.count("DISTINCT") == 1

    def test_distinct_on_with_pg(self):
        d = PostgreSQLDialect()
        sql, params = (
            Query("logs")
            .select("source", "message")
            .distinct_on("source")
            .order_by(F("source").asc(), F("created_at").desc())
            .build(d)
        )
        assert 'DISTINCT ON ("source")' in sql
        assert 'ORDER BY "source" ASC' in sql
