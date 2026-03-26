"""Query composition and reusable query fragments for sqlink."""

from __future__ import annotations

from typing import Any, Callable

from sqlink.builder import Query
from sqlink.expressions import Expr, F


class Scope:
    """Reusable query scope (predefined filter/modifier).

    Usage:
        active = Scope(lambda q: q.where(F("active") == True))
        recent = Scope(lambda q: q.where(F("created_at") > "2024-01-01"))

        query = Query("users").select("*")
        query = active.apply(query)
        query = recent.apply(query)
    """

    def __init__(self, modifier: Callable[[Query], Query]):
        self._modifier = modifier

    def apply(self, query: Query) -> Query:
        """Apply this scope to a query."""
        return self._modifier(query)

    def __call__(self, query: Query) -> Query:
        return self.apply(query)

    def __and__(self, other: Scope) -> Scope:
        """Combine scopes with AND (both applied)."""
        def combined(q: Query) -> Query:
            return other.apply(self.apply(q))
        return Scope(combined)


class QueryTemplate:
    """Reusable query template with parameter placeholders.

    Usage:
        template = QueryTemplate(
            lambda user_id: Query("orders")
            .select("*")
            .where(F("user_id") == user_id)
        )
        sql, params = template.build(user_id=42)
    """

    def __init__(self, builder_fn: Callable[..., Query]):
        self._builder_fn = builder_fn

    def build(self, **kwargs: Any) -> tuple[str, list[Any]]:
        """Build the query with the given parameters."""
        query = self._builder_fn(**kwargs)
        return query.build()

    def query(self, **kwargs: Any) -> Query:
        """Get the Query object with the given parameters."""
        return self._builder_fn(**kwargs)


class Paginator:
    """Query pagination helper.

    Usage:
        base = Query("users").select("*").where(F("active") == True)
        paginator = Paginator(base, per_page=25)

        page1_sql, page1_params = paginator.page(1)
        page2_sql, page2_params = paginator.page(2)
    """

    def __init__(self, base_query: Query, per_page: int = 20):
        self._base = base_query
        self.per_page = per_page

    def page(self, page_num: int) -> tuple[str, list[Any]]:
        """Build query for specific page number (1-indexed)."""
        if page_num < 1:
            page_num = 1
        return (
            self._base.clone()
            .paginate(page=page_num, per_page=self.per_page)
            .build()
        )

    def count_query(self) -> tuple[str, list[Any]]:
        """Build a COUNT query for the base query (for total pages)."""
        from sqlink.expressions import Raw
        count_q = self._base.clone()
        count_q._columns = [Raw("COUNT(*) AS total")]
        count_q._order_by = []
        count_q._limit = None
        count_q._offset = None
        return count_q.build()


class ConditionalBuilder:
    """Build queries with conditional clauses.

    Usage:
        builder = ConditionalBuilder(Query("users").select("*"))
        builder.when(name is not None, lambda q: q.where(F("name") == name))
        builder.when(age > 0, lambda q: q.where(F("age") > age))
        sql, params = builder.build()
    """

    def __init__(self, base_query: Query):
        self._query = base_query

    def when(self, condition: bool, modifier: Callable[[Query], Query]) -> ConditionalBuilder:
        """Apply modifier only if condition is truthy."""
        if condition:
            self._query = modifier(self._query)
        return self

    def unless(self, condition: bool, modifier: Callable[[Query], Query]) -> ConditionalBuilder:
        """Apply modifier only if condition is falsy."""
        if not condition:
            self._query = modifier(self._query)
        return self

    def build(self) -> tuple[str, list[Any]]:
        return self._query.build()

    @property
    def query(self) -> Query:
        return self._query


class BatchInsert:
    """Efficient batch insert builder.

    Usage:
        batch = BatchInsert("users", ["name", "email"], chunk_size=100)
        batch.add({"name": "A", "email": "a@example.com"})
        batch.add({"name": "B", "email": "b@example.com"})
        for sql, params in batch.build_chunks():
            cursor.execute(sql, params)
    """

    def __init__(self, table: str, columns: list[str], chunk_size: int = 1000):
        self.table = table
        self.columns = columns
        self.chunk_size = chunk_size
        self._rows: list[dict[str, Any]] = []

    def add(self, row: dict[str, Any]) -> BatchInsert:
        self._rows.append(row)
        return self

    def add_many(self, rows: list[dict[str, Any]]) -> BatchInsert:
        self._rows.extend(rows)
        return self

    @property
    def row_count(self) -> int:
        return len(self._rows)

    def build_chunks(self) -> list[tuple[str, list[Any]]]:
        """Build INSERT statements in chunks."""
        results = []
        for i in range(0, len(self._rows), self.chunk_size):
            chunk = self._rows[i:i + self.chunk_size]
            q = Query(self.table).insert(*self.columns)
            for row in chunk:
                q = q.values(row)
            results.append(q.build())
        return results

    def build(self) -> tuple[str, list[Any]]:
        """Build a single INSERT statement with all rows."""
        q = Query(self.table).insert(*self.columns)
        for row in self._rows:
            q = q.values(row)
        return q.build()
