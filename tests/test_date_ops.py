"""Tests for date/time functions and operators."""

import pytest
from sqlink import Query, F, Raw
from sqlink.date_ops import (
    DateTrunc, Extract, DateAdd, DateSub, DateDiff, Age,
    CurrentDate, CurrentTime, Year, Month, Day, Hour, Minute,
)
from sqlink.dialect import PostgreSQLDialect, MySQLDialect


class TestDateTrunc:
    def test_month(self):
        dt = DateTrunc("month", "created_at")
        sql, params = dt.to_sql()
        assert sql == "DATE_TRUNC('month', created_at)"
        assert params == []

    def test_year(self):
        sql, _ = DateTrunc("year", "created_at").to_sql()
        assert "DATE_TRUNC('year'" in sql

    def test_day(self):
        sql, _ = DateTrunc("day", "created_at").to_sql()
        assert "DATE_TRUNC('day'" in sql

    def test_with_dialect(self):
        d = PostgreSQLDialect()
        sql, _ = DateTrunc("month", "created_at").to_sql(d)
        assert '"created_at"' in sql

    def test_in_query(self):
        sql, params = (
            Query("orders")
            .select(DateTrunc("month", "created_at"), Raw("COUNT(*)"))
            .group_by("created_at")
            .build()
        )
        assert "DATE_TRUNC" in sql
        assert "GROUP BY" in sql


class TestExtract:
    def test_year(self):
        sql, _ = Extract("year", "created_at").to_sql()
        assert sql == "EXTRACT(YEAR FROM created_at)"

    def test_month(self):
        sql, _ = Extract("month", "birth_date").to_sql()
        assert sql == "EXTRACT(MONTH FROM birth_date)"

    def test_day(self):
        sql, _ = Extract("day", "created_at").to_sql()
        assert "DAY" in sql

    def test_hour(self):
        sql, _ = Extract("hour", "timestamp").to_sql()
        assert "HOUR" in sql

    def test_case_insensitive(self):
        sql, _ = Extract("Year", "date").to_sql()
        assert "YEAR" in sql  # Should be uppercased

    def test_in_where(self):
        sql, params = (
            Query("users")
            .select("*")
            .where(Raw("EXTRACT(YEAR FROM created_at) = ?", [2024]))
            .build()
        )
        assert "EXTRACT" in sql
        assert params == [2024]


class TestDateAdd:
    def test_add_days(self):
        sql, _ = DateAdd("created_at", 7, "DAY").to_sql()
        assert sql == "created_at + INTERVAL '7 DAY'"

    def test_add_months(self):
        sql, _ = DateAdd("start_date", 3, "MONTH").to_sql()
        assert "3 MONTH" in sql

    def test_add_hours(self):
        sql, _ = DateAdd("timestamp", 2, "HOUR").to_sql()
        assert "2 HOUR" in sql

    def test_with_dialect(self):
        d = PostgreSQLDialect()
        sql, _ = DateAdd("created_at", 30, "DAY").to_sql(d)
        assert '"created_at"' in sql


class TestDateSub:
    def test_sub_days(self):
        sql, _ = DateSub("created_at", 30, "DAY").to_sql()
        assert sql == "created_at - INTERVAL '30 DAY'"

    def test_sub_months(self):
        sql, _ = DateSub("expire_date", 1, "MONTH").to_sql()
        assert "1 MONTH" in sql

    def test_in_query(self):
        sql, params = (
            Query("users")
            .select("*")
            .where(Raw("created_at > ?", ["2024-01-01"]))
            .build()
        )
        assert params == ["2024-01-01"]


class TestDateDiff:
    def test_diff(self):
        sql, _ = DateDiff("end_date", "start_date").to_sql()
        assert sql == "end_date - start_date"

    def test_with_dialect(self):
        d = PostgreSQLDialect()
        sql, _ = DateDiff("end_date", "start_date").to_sql(d)
        assert '"end_date" - "start_date"' == sql


class TestAge:
    def test_single_arg(self):
        sql, _ = Age("birth_date").to_sql()
        assert sql == "AGE(birth_date)"

    def test_two_args(self):
        sql, _ = Age("birth_date", "reference_date").to_sql()
        assert sql == "AGE(reference_date, birth_date)"


class TestConvenienceFunctions:
    def test_current_date(self):
        sql, _ = CurrentDate().to_sql()
        assert sql == "CURRENT_DATE"

    def test_current_time(self):
        sql, _ = CurrentTime().to_sql()
        assert sql == "CURRENT_TIME"

    def test_year_shortcut(self):
        y = Year("created_at")
        assert isinstance(y, Extract)
        sql, _ = y.to_sql()
        assert "YEAR" in sql

    def test_month_shortcut(self):
        m = Month("created_at")
        sql, _ = m.to_sql()
        assert "MONTH" in sql

    def test_day_shortcut(self):
        d = Day("created_at")
        sql, _ = d.to_sql()
        assert "DAY" in sql

    def test_hour_shortcut(self):
        h = Hour("timestamp_col")
        sql, _ = h.to_sql()
        assert "HOUR" in sql

    def test_minute_shortcut(self):
        m = Minute("timestamp_col")
        sql, _ = m.to_sql()
        assert "MINUTE" in sql


class TestDateInQueries:
    def test_group_by_month(self):
        sql, _ = (
            Query("orders")
            .select(DateTrunc("month", "created_at").as_("month"), Raw("SUM(total) as revenue"))
            .group_by("month")
            .order_by(F("month").asc())
            .build()
        )
        assert "DATE_TRUNC" in sql
        assert "GROUP BY" in sql

    def test_filter_by_year(self):
        sql, params = (
            Query("users")
            .select("*")
            .where(Raw("EXTRACT(YEAR FROM created_at) = ?", [2024]))
            .build()
        )
        assert "EXTRACT" in sql

    def test_date_range_query(self):
        sql, params = (
            Query("events")
            .select("*")
            .where(
                F("event_date") >= "2024-01-01",
                F("event_date") < "2025-01-01",
            )
            .build()
        )
        assert ">=" in sql
        assert "<" in sql
        assert len(params) == 2
