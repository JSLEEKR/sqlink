"""Tests for type safety and API ergonomics."""

import pytest
from sqlink import (
    Query, Table, F, Expr, Raw, Alias, Case, And, Or, Not,
    Func, Between, In, IsNull, IsNotNull, Like, Exists, Subquery, Window,
    Dialect, MySQLDialect, PostgreSQLDialect, SQLiteDialect,
    Column, Schema, ForeignKey,
    OrderDirection, JoinType, ConflictAction,
)
from sqlink.types import ColumnType, ParamValue, Params
from sqlink.aggregates import Count, Sum, Avg, Max, Min
from sqlink.compose import Scope, QueryTemplate, Paginator, ConditionalBuilder, BatchInsert
from sqlink.transaction import Transaction
from sqlink.migration import AlterTable
from sqlink.ddl import CreateIndex, DropIndex, Truncate, CreateView, DropView
from sqlink.json_ops import JsonField
from sqlink.debug import interpolate_params, explain_query, format_sql
from sqlink.validation import ValidationError, validate_identifier


class TestReturnTypes:
    """Verify that fluent methods return the correct type for chaining."""

    def test_query_select_returns_query(self):
        q = Query("users").select("id")
        assert isinstance(q, Query)

    def test_query_where_returns_query(self):
        q = Query("users").select("*").where(F("id") == 1)
        assert isinstance(q, Query)

    def test_query_join_returns_query(self):
        q = Query("users").select("*").join("orders", Raw("1=1"))
        assert isinstance(q, Query)

    def test_query_order_by_returns_query(self):
        q = Query("users").select("*").order_by("name")
        assert isinstance(q, Query)

    def test_query_limit_returns_query(self):
        q = Query("users").select("*").limit(10)
        assert isinstance(q, Query)

    def test_query_offset_returns_query(self):
        q = Query("users").select("*").offset(5)
        assert isinstance(q, Query)

    def test_query_group_by_returns_query(self):
        q = Query("users").select("*").group_by("status")
        assert isinstance(q, Query)

    def test_query_having_returns_query(self):
        q = Query("users").select("*").having(Raw("COUNT(*) > 5"))
        assert isinstance(q, Query)

    def test_query_distinct_returns_query(self):
        q = Query("users").select("*").distinct()
        assert isinstance(q, Query)

    def test_query_paginate_returns_query(self):
        q = Query("users").select("*").paginate(1, 10)
        assert isinstance(q, Query)

    def test_query_union_returns_query(self):
        q1 = Query("users").select("id")
        q2 = Query("admins").select("id")
        assert isinstance(q1.union(q2), Query)

    def test_query_clone_returns_query(self):
        q = Query("users").select("*").clone()
        assert isinstance(q, Query)

    def test_table_select_returns_query(self):
        t = Table("users")
        assert isinstance(t.select("id"), Query)


class TestBuildReturnTypes:
    """Verify build() returns (str, list)."""

    def test_select_build(self):
        sql, params = Query("users").select("*").build()
        assert isinstance(sql, str)
        assert isinstance(params, list)

    def test_insert_build(self):
        sql, params = Query("users").insert("name").values({"name": "X"}).build()
        assert isinstance(sql, str)
        assert isinstance(params, list)

    def test_update_build(self):
        sql, params = Query("users").update(name="X").build()
        assert isinstance(sql, str)
        assert isinstance(params, list)

    def test_delete_build(self):
        sql, params = Query("users").delete().build()
        assert isinstance(sql, str)
        assert isinstance(params, list)


class TestExprReturnTypes:
    """Verify expression operators return correct types."""

    def test_f_eq(self):
        assert isinstance(F("a") == 1, Expr)

    def test_f_ne(self):
        assert isinstance(F("a") != 1, Expr)

    def test_f_gt(self):
        assert isinstance(F("a") > 1, Expr)

    def test_f_lt(self):
        assert isinstance(F("a") < 1, Expr)

    def test_f_and(self):
        assert isinstance((F("a") > 1) & (F("b") < 2), And)

    def test_f_or(self):
        assert isinstance((F("a") > 1) | (F("b") < 2), Or)

    def test_f_not(self):
        assert isinstance(~(F("a") > 1), Not)

    def test_f_is_in(self):
        assert isinstance(F("a").is_in([1, 2]), In)

    def test_f_between(self):
        assert isinstance(F("a").between(1, 10), Between)

    def test_f_like(self):
        assert isinstance(F("a").like("%x%"), Like)

    def test_f_is_null(self):
        assert isinstance(F("a").is_null(), IsNull)

    def test_f_as(self):
        assert isinstance(F("a").as_("b"), Alias)

    def test_raw_as(self):
        assert isinstance(Raw("1").as_("one"), Alias)

    def test_case_returns_case(self):
        c = Case().when(F("a") > 1, "yes")
        assert isinstance(c, Case)


class TestEnumValues:
    def test_order_direction_values(self):
        assert OrderDirection.ASC.value == "ASC"
        assert OrderDirection.DESC.value == "DESC"

    def test_join_type_values(self):
        assert "INNER" in JoinType.INNER.value
        assert "LEFT" in JoinType.LEFT.value
        assert "RIGHT" in JoinType.RIGHT.value
        assert "FULL" in JoinType.FULL.value
        assert "CROSS" in JoinType.CROSS.value

    def test_conflict_action_values(self):
        assert ConflictAction.NOTHING.value == "NOTHING"
        assert ConflictAction.UPDATE.value == "UPDATE"

    def test_column_type_values(self):
        assert ColumnType.INTEGER.value == "INTEGER"
        assert ColumnType.TEXT.value == "TEXT"
        assert ColumnType.VARCHAR.value == "VARCHAR"
        assert ColumnType.BOOLEAN.value == "BOOLEAN"
        assert ColumnType.TIMESTAMP.value == "TIMESTAMP"
        assert ColumnType.UUID.value == "UUID"
        assert ColumnType.JSONB.value == "JSONB"
        assert ColumnType.SERIAL.value == "SERIAL"
        assert ColumnType.BIGSERIAL.value == "BIGSERIAL"


class TestImports:
    """Verify all public API is importable."""

    def test_all_exports(self):
        import sqlink
        for name in sqlink.__all__:
            assert hasattr(sqlink, name), f"Missing export: {name}"

    def test_version(self):
        import sqlink
        assert sqlink.__version__ == "1.0.0"
