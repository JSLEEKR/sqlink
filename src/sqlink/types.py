"""Type definitions for sqlink."""

from __future__ import annotations

from enum import Enum
from typing import Any


class OrderDirection(Enum):
    """Sort direction for ORDER BY clauses."""
    ASC = "ASC"
    DESC = "DESC"


class JoinType(Enum):
    """SQL JOIN types."""
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL OUTER JOIN"
    CROSS = "CROSS JOIN"
    LEFT_OUTER = "LEFT OUTER JOIN"
    RIGHT_OUTER = "RIGHT OUTER JOIN"


class ConflictAction(Enum):
    """Action on INSERT conflict (upsert)."""
    NOTHING = "NOTHING"
    UPDATE = "UPDATE"


class ColumnType(Enum):
    """SQL column types for schema definitions."""
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    SMALLINT = "SMALLINT"
    TEXT = "TEXT"
    VARCHAR = "VARCHAR"
    CHAR = "CHAR"
    BOOLEAN = "BOOLEAN"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    TIMESTAMPTZ = "TIMESTAMPTZ"
    TIME = "TIME"
    JSON = "JSON"
    JSONB = "JSONB"
    UUID = "UUID"
    BLOB = "BLOB"
    BYTEA = "BYTEA"
    SERIAL = "SERIAL"
    BIGSERIAL = "BIGSERIAL"
    ARRAY = "ARRAY"


# Type alias for parameter values
ParamValue = Any
Params = list[ParamValue]
