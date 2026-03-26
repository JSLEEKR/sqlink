"""Aggregate function helpers for sqlink."""

from __future__ import annotations

from sqlink.expressions import Expr, F, Func, Raw


def Count(column: str = "*", distinct: bool = False) -> Func:
    """COUNT aggregate."""
    if distinct:
        return Func("COUNT", Raw(f"DISTINCT {column}"))
    return Func("COUNT", column)


def Sum(column: str) -> Func:
    """SUM aggregate."""
    return Func("SUM", F(column))


def Avg(column: str) -> Func:
    """AVG aggregate."""
    return Func("AVG", F(column))


def Max(column: str) -> Func:
    """MAX aggregate."""
    return Func("MAX", F(column))


def Min(column: str) -> Func:
    """MIN aggregate."""
    return Func("MIN", F(column))


def Coalesce(*args: Expr | str) -> Func:
    """COALESCE function."""
    converted = []
    for arg in args:
        if isinstance(arg, Expr):
            converted.append(arg)
        else:
            converted.append(F(arg))
    return Func("COALESCE", *converted)


def Greatest(*args: Expr | str) -> Func:
    """GREATEST function (max of values)."""
    converted = [F(a) if isinstance(a, str) else a for a in args]
    return Func("GREATEST", *converted)


def Least(*args: Expr | str) -> Func:
    """LEAST function (min of values)."""
    converted = [F(a) if isinstance(a, str) else a for a in args]
    return Func("LEAST", *converted)


def Cast(expr: Expr | str, as_type: str) -> Raw:
    """CAST expression."""
    if isinstance(expr, str):
        return Raw(f"CAST({expr} AS {as_type})")
    # For Expr objects, we need to convert inline
    return Raw(f"CAST({{}} AS {as_type})")  # placeholder


def Concat(*args: Expr | str) -> Func:
    """CONCAT function."""
    converted = [F(a) if isinstance(a, str) else a for a in args]
    return Func("CONCAT", *converted)


def Lower(column: str) -> Func:
    """LOWER function."""
    return Func("LOWER", F(column))


def Upper(column: str) -> Func:
    """UPPER function."""
    return Func("UPPER", F(column))


def Trim(column: str) -> Func:
    """TRIM function."""
    return Func("TRIM", F(column))


def Length(column: str) -> Func:
    """LENGTH function."""
    return Func("LENGTH", F(column))


def Now() -> Raw:
    """NOW() function."""
    return Raw("NOW()")


def CurrentTimestamp() -> Raw:
    """CURRENT_TIMESTAMP."""
    return Raw("CURRENT_TIMESTAMP")


def Abs(column: str) -> Func:
    """ABS function."""
    return Func("ABS", F(column))


def Round(column: str, decimals: int = 0) -> Func:
    """ROUND function."""
    return Func("ROUND", F(column), decimals)
