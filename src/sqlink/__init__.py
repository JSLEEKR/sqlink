"""sqlink — Fluent SQL query builder with chain API and dialect support."""

from sqlink.builder import Query, Table
from sqlink.dialect import Dialect, MySQLDialect, PostgreSQLDialect, SQLiteDialect
from sqlink.expressions import (
    F,
    Expr,
    Raw,
    Case,
    And,
    Or,
    Not,
    Func,
    Between,
    In,
    IsNull,
    IsNotNull,
    Like,
    Exists,
    Subquery,
    Window,
)
from sqlink.schema import Column, Schema, ForeignKey
from sqlink.types import OrderDirection, JoinType, ConflictAction

__version__ = "1.0.0"

__all__ = [
    "Query",
    "Table",
    "Dialect",
    "MySQLDialect",
    "PostgreSQLDialect",
    "SQLiteDialect",
    "F",
    "Expr",
    "Raw",
    "Case",
    "And",
    "Or",
    "Not",
    "Func",
    "Between",
    "In",
    "IsNull",
    "IsNotNull",
    "Like",
    "Exists",
    "Subquery",
    "Window",
    "Column",
    "Schema",
    "ForeignKey",
    "OrderDirection",
    "JoinType",
    "ConflictAction",
]
