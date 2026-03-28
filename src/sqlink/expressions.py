"""SQL expressions, functions, and conditions for sqlink."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlink.dialect import Dialect


class Expr:
    """Base expression that can be used in SQL queries."""

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        """Render this expression to SQL string and parameters."""
        raise NotImplementedError

    def __and__(self, other: Expr) -> And:
        return And(self, other)

    def __or__(self, other: Expr) -> Or:
        return Or(self, other)

    def __invert__(self) -> Not:
        return Not(self)

    def __repr__(self) -> str:
        try:
            sql, params = self.to_sql()
            return f"{self.__class__.__name__}({sql!r})"
        except Exception:
            return f"{self.__class__.__name__}()"

    def as_(self, alias: str) -> Alias:
        """Create an aliased expression: expr AS alias."""
        return Alias(self, alias)


class Alias(Expr):
    """Aliased expression: expr AS alias."""

    def __init__(self, expr: Expr, alias: str):
        self.expr = expr
        self.alias_name = alias

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        sql, params = self.expr.to_sql(dialect)
        quote = dialect.quote_identifier if dialect else lambda x: x
        return f"{sql} AS {quote(self.alias_name)}", params


class Raw(Expr):
    """Raw SQL expression with optional parameters."""

    def __init__(self, sql: str, params: list[Any] | None = None):
        self.sql = sql
        self.params = params or []

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        return self.sql, list(self.params)


class F(Expr):
    """Field/column reference with operator support.

    Usage:
        F("name") == "John"      -> Condition("name", "=", "John")
        F("age") > 18            -> Condition("age", ">", 18)
        F("status").is_in(["a"]) -> In("status", ["a"])
    """

    def __init__(self, name: str):
        self.name = name

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        if dialect:
            return dialect.quote_identifier(self.name), []
        return self.name, []

    def __eq__(self, other: Any) -> Condition:
        if other is None:
            return IsNull(self.name)
        return Condition(self.name, "=", other)

    def __ne__(self, other: Any) -> Condition:
        if other is None:
            return IsNotNull(self.name)
        return Condition(self.name, "!=", other)

    def __gt__(self, other: Any) -> Condition:
        return Condition(self.name, ">", other)

    def __ge__(self, other: Any) -> Condition:
        return Condition(self.name, ">=", other)

    def __lt__(self, other: Any) -> Condition:
        return Condition(self.name, "<", other)

    def __le__(self, other: Any) -> Condition:
        return Condition(self.name, "<=", other)

    def is_in(self, values: list[Any]) -> In:
        return In(self.name, values)

    def not_in(self, values: list[Any]) -> NotIn:
        return NotIn(self.name, values)

    def between(self, low: Any, high: Any) -> Between:
        return Between(self.name, low, high)

    def like(self, pattern: str) -> Like:
        return Like(self.name, pattern)

    def ilike(self, pattern: str) -> ILike:
        return ILike(self.name, pattern)

    def is_null(self) -> IsNull:
        return IsNull(self.name)

    def is_not_null(self) -> IsNotNull:
        return IsNotNull(self.name)

    def as_(self, alias: str) -> Alias:
        """Create an aliased expression: column AS alias."""
        return Alias(self, alias)

    def asc(self) -> OrderExpr:
        return OrderExpr(self.name, "ASC")

    def desc(self) -> OrderExpr:
        return OrderExpr(self.name, "DESC")

    def __hash__(self) -> int:
        return hash(self.name)


class Condition(Expr):
    """A binary comparison condition."""

    def __init__(self, field: str, op: str, value: Any):
        self.field = field
        self.op = op
        self.value = value

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        placeholder = dialect.placeholder() if dialect else "?"
        col = dialect.quote_identifier(self.field) if dialect else self.field
        if isinstance(self.value, Expr):
            val_sql, val_params = self.value.to_sql(dialect)
            return f"{col} {self.op} {val_sql}", val_params
        return f"{col} {self.op} {placeholder}", [self.value]


class And(Expr):
    """Logical AND of two expressions."""

    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        l_sql, l_params = self.left.to_sql(dialect)
        r_sql, r_params = self.right.to_sql(dialect)
        return f"({l_sql} AND {r_sql})", l_params + r_params


class Or(Expr):
    """Logical OR of two expressions."""

    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        l_sql, l_params = self.left.to_sql(dialect)
        r_sql, r_params = self.right.to_sql(dialect)
        return f"({l_sql} OR {r_sql})", l_params + r_params


class Not(Expr):
    """Logical NOT of an expression."""

    def __init__(self, expr: Expr):
        self.expr = expr

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        sql, params = self.expr.to_sql(dialect)
        return f"NOT ({sql})", params


class Between(Expr):
    """BETWEEN low AND high."""

    def __init__(self, field: str, low: Any, high: Any):
        self.field = field
        self.low = low
        self.high = high

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        ph1 = dialect.placeholder() if dialect else "?"
        ph2 = dialect.placeholder() if dialect else "?"
        col = dialect.quote_identifier(self.field) if dialect else self.field
        return f"{col} BETWEEN {ph1} AND {ph2}", [self.low, self.high]


class In(Expr):
    """field IN (values)."""

    def __init__(self, field: str, values: list[Any]):
        self.field = field
        self.values = values

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        if not self.values:
            return "1 = 0", []
        col = dialect.quote_identifier(self.field) if dialect else self.field
        placeholders = ", ".join(
            dialect.placeholder() if dialect else "?" for _ in self.values
        )
        return f"{col} IN ({placeholders})", list(self.values)


class NotIn(Expr):
    """field NOT IN (values)."""

    def __init__(self, field: str, values: list[Any]):
        self.field = field
        self.values = values

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        if not self.values:
            return "1 = 1", []
        col = dialect.quote_identifier(self.field) if dialect else self.field
        placeholders = ", ".join(
            dialect.placeholder() if dialect else "?" for _ in self.values
        )
        return f"{col} NOT IN ({placeholders})", list(self.values)


class IsNull(Expr):
    """field IS NULL."""

    def __init__(self, field: str):
        self.field = field

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        col = dialect.quote_identifier(self.field) if dialect else self.field
        return f"{col} IS NULL", []


class IsNotNull(Expr):
    """field IS NOT NULL."""

    def __init__(self, field: str):
        self.field = field

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        col = dialect.quote_identifier(self.field) if dialect else self.field
        return f"{col} IS NOT NULL", []


class Like(Expr):
    """field LIKE pattern."""

    def __init__(self, field: str, pattern: str):
        self.field = field
        self.pattern = pattern

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        placeholder = dialect.placeholder() if dialect else "?"
        col = dialect.quote_identifier(self.field) if dialect else self.field
        return f"{col} LIKE {placeholder}", [self.pattern]


class ILike(Expr):
    """field ILIKE pattern (case-insensitive LIKE, PostgreSQL)."""

    def __init__(self, field: str, pattern: str):
        self.field = field
        self.pattern = pattern

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        placeholder = dialect.placeholder() if dialect else "?"
        col = dialect.quote_identifier(self.field) if dialect else self.field
        # PostgreSQL supports ILIKE natively; others use LOWER()
        if dialect and hasattr(dialect, 'supports_ilike') and dialect.supports_ilike():
            return f"{col} ILIKE {placeholder}", [self.pattern]
        return f"LOWER({col}) LIKE LOWER({placeholder})", [self.pattern]


class Func(Expr):
    """SQL function call: COUNT, SUM, AVG, MAX, MIN, etc."""

    def __init__(self, name: str, *args: Any):
        self.func_name = name
        self.args = args

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        parts = []
        params: list[Any] = []
        for arg in self.args:
            if isinstance(arg, Expr):
                s, p = arg.to_sql(dialect)
                parts.append(s)
                params.extend(p)
            elif isinstance(arg, str):
                parts.append(arg)
            else:
                placeholder = dialect.placeholder() if dialect else "?"
                parts.append(placeholder)
                params.append(arg)
        return f"{self.func_name}({', '.join(parts)})", params


class Case(Expr):
    """SQL CASE WHEN ... THEN ... ELSE ... END."""

    def __init__(self):
        self._whens: list[tuple[Expr, Any]] = []
        self._else: Any = None

    def when(self, condition: Expr, then: Any) -> Case:
        self._whens.append((condition, then))
        return self

    def else_(self, value: Any) -> Case:
        self._else = value
        return self

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        placeholder = dialect.placeholder() if dialect else "?"
        parts = ["CASE"]
        params: list[Any] = []
        for cond, then_val in self._whens:
            cond_sql, cond_params = cond.to_sql(dialect)
            parts.append(f"WHEN {cond_sql}")
            params.extend(cond_params)
            if isinstance(then_val, Expr):
                then_sql, then_params = then_val.to_sql(dialect)
                parts.append(f"THEN {then_sql}")
                params.extend(then_params)
            else:
                parts.append(f"THEN {placeholder}")
                params.append(then_val)
        if self._else is not None:
            if isinstance(self._else, Expr):
                else_sql, else_params = self._else.to_sql(dialect)
                parts.append(f"ELSE {else_sql}")
                params.extend(else_params)
            else:
                parts.append(f"ELSE {placeholder}")
                params.append(self._else)
        parts.append("END")
        return " ".join(parts), params


class Exists(Expr):
    """EXISTS (subquery)."""

    def __init__(self, subquery: Any):
        self.subquery = subquery

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        if isinstance(self.subquery, Expr):
            sql, params = self.subquery.to_sql(dialect)
        else:
            # Assume it's a builder with build() method
            sql, params = self.subquery.build(dialect)
        return f"EXISTS ({sql})", params


class Subquery(Expr):
    """Wrap a query builder as a subquery expression."""

    def __init__(self, query: Any, alias: str | None = None):
        self.query = query
        self.alias = alias

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        if isinstance(self.query, Expr):
            sql, params = self.query.to_sql(dialect)
        else:
            sql, params = self.query.build(dialect)
        if self.alias:
            return f"({sql}) AS {self.alias}", params
        return f"({sql})", params


class Window(Expr):
    """SQL window function: func OVER (PARTITION BY ... ORDER BY ...).

    Usage:
        Window(Func("ROW_NUMBER")).partition_by("dept").order_by("salary", "DESC")
        Window(Func("SUM", F("amount"))).partition_by("user_id")
    """

    def __init__(self, func: Expr):
        self.func = func
        self._partition_by: list[str] = []
        self._order_by: list[tuple[str, str]] = []
        self._frame: str | None = None
        self._alias: str | None = None

    def partition_by(self, *columns: str) -> Window:
        self._partition_by.extend(columns)
        return self

    def order_by(self, column: str, direction: str = "ASC") -> Window:
        self._order_by.append((column, direction))
        return self

    def frame(self, spec: str) -> Window:
        """Set window frame: e.g. 'ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW'."""
        self._frame = spec
        return self

    def alias(self, name: str) -> Window:
        self._alias = name
        return self

    def to_sql(self, dialect: Dialect | None = None) -> tuple[str, list[Any]]:
        func_sql, params = self.func.to_sql(dialect)
        quote = dialect.quote_identifier if dialect else lambda x: x

        over_parts = []
        if self._partition_by:
            cols = ", ".join(quote(c) for c in self._partition_by)
            over_parts.append(f"PARTITION BY {cols}")
        if self._order_by:
            order_cols = ", ".join(
                f"{quote(c)} {d}" for c, d in self._order_by
            )
            over_parts.append(f"ORDER BY {order_cols}")
        if self._frame:
            over_parts.append(self._frame)

        over_clause = " ".join(over_parts)
        result = f"{func_sql} OVER ({over_clause})"
        if self._alias:
            result += f" AS {quote(self._alias)}"
        return result, params


class OrderExpr:
    """Order expression for ORDER BY."""

    def __init__(self, field: str, direction: str = "ASC"):
        self.field = field
        self.direction = direction

    def to_sql(self, dialect: Dialect | None = None) -> str:
        col = dialect.quote_identifier(self.field) if dialect else self.field
        return f"{col} {self.direction}"
