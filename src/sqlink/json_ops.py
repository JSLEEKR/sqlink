"""JSON/JSONB operators for PostgreSQL and other dialects."""

from __future__ import annotations

from typing import Any

from sqlink.expressions import Expr, F


class JsonField(Expr):
    """JSON field accessor with operator chain support.

    Usage:
        JsonField("data", "name")          -> data->>'name'
        JsonField("data", "address.city")  -> data->'address'->>'city'
        JsonField("data").arrow("key")     -> data->'key'
        JsonField("data").text("key")      -> data->>'key'
    """

    def __init__(self, column: str, path: str | None = None, as_text: bool = True):
        self.column = column
        self.path = path
        self._as_text = as_text
        self._ops: list[tuple[str, str]] = []

        if path:
            parts = path.split(".")
            for i, part in enumerate(parts):
                is_last = i == len(parts) - 1
                if is_last and as_text:
                    self._ops.append(("->>", part))
                else:
                    self._ops.append(("->", part))

    def arrow(self, key: str) -> JsonField:
        """Access JSON key with -> (returns JSON)."""
        new = JsonField(self.column)
        new._ops = list(self._ops)
        new._ops.append(("->", key))
        return new

    def text(self, key: str) -> JsonField:
        """Access JSON key with ->> (returns text)."""
        new = JsonField(self.column)
        new._ops = list(self._ops)
        new._ops.append(("->>", key))
        return new

    def arrow_index(self, index: int) -> JsonField:
        """Access JSON array element by index."""
        new = JsonField(self.column)
        new._ops = list(self._ops)
        new._ops.append(("->", str(index)))
        return new

    def contains(self, value: Any) -> JsonContains:
        """PostgreSQL @> operator."""
        return JsonContains(self, value)

    def contained_by(self, value: Any) -> JsonContainedBy:
        """PostgreSQL <@ operator."""
        return JsonContainedBy(self, value)

    def has_key(self, key: str) -> JsonHasKey:
        """PostgreSQL ? operator."""
        return JsonHasKey(self, key)

    def has_any_keys(self, keys: list[str]) -> JsonHasAnyKey:
        """PostgreSQL ?| operator."""
        return JsonHasAnyKey(self, keys)

    def has_all_keys(self, keys: list[str]) -> JsonHasAllKeys:
        """PostgreSQL ?& operator."""
        return JsonHasAllKeys(self, keys)

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        quote = dialect.quote_identifier if dialect else lambda x: x
        col = quote(self.column)

        for op, key in self._ops:
            if key.isdigit():
                col = f"{col}{op}{key}"
            else:
                col = f"{col}{op}'{key}'"

        return col, []

    # Comparison operators for WHERE clauses
    def __eq__(self, other: Any) -> _JsonComparison:
        return _JsonComparison(self, "=", other)

    def __ne__(self, other: Any) -> _JsonComparison:
        return _JsonComparison(self, "!=", other)

    def __gt__(self, other: Any) -> _JsonComparison:
        return _JsonComparison(self, ">", other)

    def __lt__(self, other: Any) -> _JsonComparison:
        return _JsonComparison(self, "<", other)

    def __ge__(self, other: Any) -> _JsonComparison:
        return _JsonComparison(self, ">=", other)

    def __le__(self, other: Any) -> _JsonComparison:
        return _JsonComparison(self, "<=", other)


class _JsonComparison(Expr):
    def __init__(self, field: JsonField, op: str, value: Any):
        self.field = field
        self.op = op
        self.value = value

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        field_sql, field_params = self.field.to_sql(dialect)
        placeholder = dialect.placeholder() if dialect else "?"
        return f"{field_sql} {self.op} {placeholder}", field_params + [self.value]


class JsonContains(Expr):
    """PostgreSQL @> operator."""
    def __init__(self, field: JsonField, value: Any):
        self.field = field
        self.value = value

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        field_sql, _ = self.field.to_sql(dialect)
        placeholder = dialect.placeholder() if dialect else "?"
        return f"{field_sql} @> {placeholder}", [self.value]


class JsonContainedBy(Expr):
    """PostgreSQL <@ operator."""
    def __init__(self, field: JsonField, value: Any):
        self.field = field
        self.value = value

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        field_sql, _ = self.field.to_sql(dialect)
        placeholder = dialect.placeholder() if dialect else "?"
        return f"{field_sql} <@ {placeholder}", [self.value]


class JsonHasKey(Expr):
    """PostgreSQL ? operator."""
    def __init__(self, field: JsonField, key: str):
        self.field = field
        self.key = key

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        field_sql, _ = self.field.to_sql(dialect)
        placeholder = dialect.placeholder() if dialect else "?"
        return f"{field_sql} ? {placeholder}", [self.key]


class JsonHasAnyKey(Expr):
    """PostgreSQL ?| operator."""
    def __init__(self, field: JsonField, keys: list[str]):
        self.field = field
        self.keys = keys

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        field_sql, _ = self.field.to_sql(dialect)
        placeholder = dialect.placeholder() if dialect else "?"
        return f"{field_sql} ?| {placeholder}", [self.keys]


class JsonHasAllKeys(Expr):
    """PostgreSQL ?& operator."""
    def __init__(self, field: JsonField, keys: list[str]):
        self.field = field
        self.keys = keys

    def to_sql(self, dialect: Any | None = None) -> tuple[str, list[Any]]:
        field_sql, _ = self.field.to_sql(dialect)
        placeholder = dialect.placeholder() if dialect else "?"
        return f"{field_sql} ?& {placeholder}", [self.keys]
