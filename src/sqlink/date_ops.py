"""Date/time functions and operators for sqlink."""

from __future__ import annotations

from typing import Any

from sqlink.expressions import Expr, F, Raw, Func


class DateTrunc(Expr):
    """DATE_TRUNC function (PostgreSQL) / equivalent for other dialects.

    Usage:
        DateTrunc("month", "created_at")  -> DATE_TRUNC('month', "created_at")
    """

    def __init__(self, precision: str, column: str):
        self.precision = precision
        self.column = column

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        quote = dialect.quote_identifier if dialect else lambda x: x
        col = quote(self.column)
        return f"DATE_TRUNC('{self.precision}', {col})", []


class Extract(Expr):
    """EXTRACT(part FROM column).

    Usage:
        Extract("year", "created_at")  -> EXTRACT(YEAR FROM "created_at")
    """

    def __init__(self, part: str, column: str):
        self.part = part.upper()
        self.column = column

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        quote = dialect.quote_identifier if dialect else lambda x: x
        col = quote(self.column)
        return f"EXTRACT({self.part} FROM {col})", []


class DateAdd(Expr):
    """Date addition: column + INTERVAL.

    Usage:
        DateAdd("created_at", 7, "DAY")  -> "created_at" + INTERVAL '7 DAY'
    """

    def __init__(self, column: str, value: int, unit: str):
        self.column = column
        self.value = value
        self.unit = unit.upper()

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        quote = dialect.quote_identifier if dialect else lambda x: x
        col = quote(self.column)
        return f"{col} + INTERVAL '{self.value} {self.unit}'", []


class DateSub(Expr):
    """Date subtraction: column - INTERVAL.

    Usage:
        DateSub("created_at", 30, "DAY")  -> "created_at" - INTERVAL '30 DAY'
    """

    def __init__(self, column: str, value: int, unit: str):
        self.column = column
        self.value = value
        self.unit = unit.upper()

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        quote = dialect.quote_identifier if dialect else lambda x: x
        col = quote(self.column)
        return f"{col} - INTERVAL '{self.value} {self.unit}'", []


class DateDiff(Expr):
    """Date difference between two columns or values.

    Usage:
        DateDiff("end_date", "start_date")  -> "end_date" - "start_date"
    """

    def __init__(self, column1: str, column2: str):
        self.column1 = column1
        self.column2 = column2

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        quote = dialect.quote_identifier if dialect else lambda x: x
        return f"{quote(self.column1)} - {quote(self.column2)}", []


class Age(Expr):
    """PostgreSQL AGE function.

    Usage:
        Age("birth_date")  -> AGE("birth_date")
    """

    def __init__(self, column: str, reference: str | None = None):
        self.column = column
        self.reference = reference

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        quote = dialect.quote_identifier if dialect else lambda x: x
        if self.reference:
            return f"AGE({quote(self.reference)}, {quote(self.column)})", []
        return f"AGE({quote(self.column)})", []


# Convenience functions

def CurrentDate() -> Raw:
    """CURRENT_DATE."""
    return Raw("CURRENT_DATE")


def CurrentTime() -> Raw:
    """CURRENT_TIME."""
    return Raw("CURRENT_TIME")


def Year(column: str) -> Extract:
    """Extract year from date column."""
    return Extract("YEAR", column)


def Month(column: str) -> Extract:
    """Extract month from date column."""
    return Extract("MONTH", column)


def Day(column: str) -> Extract:
    """Extract day from date column."""
    return Extract("DAY", column)


def Hour(column: str) -> Extract:
    """Extract hour from timestamp column."""
    return Extract("HOUR", column)


def Minute(column: str) -> Extract:
    """Extract minute from timestamp column."""
    return Extract("MINUTE", column)
