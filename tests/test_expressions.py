"""Tests for SQL expressions."""

import pytest
from sqlink import F, Raw, Case, Func, And, Or, Not, Between, In, IsNull, IsNotNull, Like
from sqlink.expressions import ILike, NotIn, Condition, OrderExpr
from sqlink.dialect import PostgreSQLDialect, MySQLDialect


class TestF:
    def test_f_to_sql(self):
        sql, params = F("name").to_sql()
        assert sql == "name"
        assert params == []

    def test_f_with_dialect(self):
        d = MySQLDialect()
        sql, params = F("name").to_sql(d)
        assert sql == "`name`"

    def test_f_hash(self):
        assert hash(F("name")) == hash(F("name"))

    def test_f_eq_none(self):
        expr = F("col") == None
        assert isinstance(expr, IsNull)

    def test_f_ne_none(self):
        expr = F("col") != None
        assert isinstance(expr, IsNotNull)


class TestRaw:
    def test_raw_simple(self):
        r = Raw("COUNT(*)")
        sql, params = r.to_sql()
        assert sql == "COUNT(*)"
        assert params == []

    def test_raw_with_params(self):
        r = Raw("age > ?", [18])
        sql, params = r.to_sql()
        assert sql == "age > ?"
        assert params == [18]

    def test_raw_params_copied(self):
        original = [1, 2]
        r = Raw("a IN (?, ?)", original)
        _, params = r.to_sql()
        params.append(3)
        assert len(original) == 2  # Original not modified


class TestCondition:
    def test_condition_basic(self):
        c = Condition("age", ">", 18)
        sql, params = c.to_sql()
        assert sql == "age > ?"
        assert params == [18]

    def test_condition_with_expr_value(self):
        c = Condition("a", "=", F("b"))
        sql, params = c.to_sql()
        assert sql == "a = b"

    def test_condition_with_dialect(self):
        d = MySQLDialect()
        c = Condition("name", "=", "John")
        sql, params = c.to_sql(d)
        assert sql == "`name` = %s"
        assert params == ["John"]


class TestLogical:
    def test_and(self):
        expr = And(Condition("a", ">", 1), Condition("b", "<", 10))
        sql, params = expr.to_sql()
        assert sql == "(a > ? AND b < ?)"
        assert params == [1, 10]

    def test_or(self):
        expr = Or(Condition("a", ">", 1), Condition("b", "<", 10))
        sql, params = expr.to_sql()
        assert sql == "(a > ? OR b < ?)"
        assert params == [1, 10]

    def test_not(self):
        expr = Not(Condition("active", "=", True))
        sql, params = expr.to_sql()
        assert sql == "NOT (active = ?)"
        assert params == [True]

    def test_operator_overload_and(self):
        expr = (F("a") > 1) & (F("b") < 10)
        assert isinstance(expr, And)

    def test_operator_overload_or(self):
        expr = (F("a") > 1) | (F("b") < 10)
        assert isinstance(expr, Or)

    def test_operator_overload_not(self):
        expr = ~(F("a") > 1)
        assert isinstance(expr, Not)

    def test_nested_logic(self):
        expr = ((F("a") > 1) & (F("b") < 10)) | (F("c") == "x")
        sql, params = expr.to_sql()
        assert "AND" in sql
        assert "OR" in sql
        assert len(params) == 3


class TestBetween:
    def test_between(self):
        b = Between("age", 18, 65)
        sql, params = b.to_sql()
        assert sql == "age BETWEEN ? AND ?"
        assert params == [18, 65]

    def test_between_with_dialect(self):
        d = MySQLDialect()
        b = Between("age", 18, 65)
        sql, params = b.to_sql(d)
        assert sql == "`age` BETWEEN %s AND %s"


class TestIn:
    def test_in(self):
        i = In("id", [1, 2, 3])
        sql, params = i.to_sql()
        assert sql == "id IN (?, ?, ?)"
        assert params == [1, 2, 3]

    def test_in_empty(self):
        i = In("id", [])
        sql, params = i.to_sql()
        assert sql == "1 = 0"

    def test_not_in(self):
        ni = NotIn("id", [4, 5])
        sql, params = ni.to_sql()
        assert sql == "id NOT IN (?, ?)"
        assert params == [4, 5]

    def test_not_in_empty(self):
        ni = NotIn("id", [])
        sql, params = ni.to_sql()
        assert sql == "1 = 1"


class TestLike:
    def test_like(self):
        l = Like("name", "%john%")
        sql, params = l.to_sql()
        assert sql == "name LIKE ?"
        assert params == ["%john%"]

    def test_ilike_postgres(self):
        d = PostgreSQLDialect()
        il = ILike("name", "%john%")
        sql, params = il.to_sql(d)
        assert "ILIKE" in sql

    def test_ilike_fallback(self):
        d = MySQLDialect()
        il = ILike("name", "%john%")
        sql, params = il.to_sql(d)
        assert "LOWER(" in sql
        assert "ILIKE" not in sql


class TestIsNull:
    def test_is_null(self):
        n = IsNull("email")
        sql, params = n.to_sql()
        assert sql == "email IS NULL"
        assert params == []

    def test_is_not_null(self):
        nn = IsNotNull("email")
        sql, params = nn.to_sql()
        assert sql == "email IS NOT NULL"


class TestFunc:
    def test_count(self):
        f = Func("COUNT", "*")
        sql, params = f.to_sql()
        assert sql == "COUNT(*)"

    def test_sum_with_field(self):
        f = Func("SUM", F("amount"))
        sql, params = f.to_sql()
        assert sql == "SUM(amount)"

    def test_func_with_value(self):
        f = Func("ROUND", F("price"), 2)
        sql, params = f.to_sql()
        assert sql == "ROUND(price, ?)"
        assert params == [2]

    def test_coalesce(self):
        """String args in Func are treated as SQL identifiers/literals."""
        f = Func("COALESCE", F("nickname"), "'Unknown'")
        sql, params = f.to_sql()
        assert sql == "COALESCE(nickname, 'Unknown')"
        assert params == []

    def test_func_with_param_value(self):
        """Non-string, non-Expr args are parameterized."""
        f = Func("IFNULL", F("count"), 0)
        sql, params = f.to_sql()
        assert sql == "IFNULL(count, ?)"
        assert params == [0]


class TestCase:
    def test_simple_case(self):
        c = Case().when(F("status") == "active", "Active").when(F("status") == "inactive", "Inactive").else_("Unknown")
        sql, params = c.to_sql()
        assert "CASE" in sql
        assert "WHEN" in sql
        assert "THEN" in sql
        assert "ELSE" in sql
        assert "END" in sql
        assert params == ["active", "Active", "inactive", "Inactive", "Unknown"]

    def test_case_without_else(self):
        c = Case().when(F("age") > 18, "Adult")
        sql, params = c.to_sql()
        assert "ELSE" not in sql

    def test_case_with_expr_then(self):
        c = Case().when(F("type") == "premium", F("price"))
        sql, params = c.to_sql()
        assert "THEN price" in sql


class TestOrderExpr:
    def test_asc(self):
        o = OrderExpr("name", "ASC")
        assert o.to_sql() == "name ASC"

    def test_desc(self):
        o = OrderExpr("name", "DESC")
        assert o.to_sql() == "name DESC"

    def test_with_dialect(self):
        d = MySQLDialect()
        o = OrderExpr("name", "ASC")
        assert o.to_sql(d) == "`name` ASC"
