"""Tests for query composition and reusable fragments."""

import pytest
from sqlink import Query, F
from sqlink.compose import Scope, QueryTemplate, Paginator, ConditionalBuilder, BatchInsert


class TestScope:
    def test_apply_scope(self):
        active = Scope(lambda q: q.where(F("active") == True))
        sql, params = active.apply(Query("users").select("*")).build()
        assert '"active" = ?' in sql
        assert params == [True]

    def test_callable_scope(self):
        active = Scope(lambda q: q.where(F("active") == True))
        sql, params = active(Query("users").select("*")).build()
        assert '"active" = ?' in sql

    def test_combine_scopes(self):
        active = Scope(lambda q: q.where(F("active") == True))
        recent = Scope(lambda q: q.where(F("age") > 18))
        combined = active & recent
        sql, params = combined.apply(Query("users").select("*")).build()
        assert len(params) == 2

    def test_scope_preserves_query(self):
        limit_10 = Scope(lambda q: q.limit(10))
        q = Query("users").select("*")
        modified = limit_10.apply(q)
        sql, _ = modified.build()
        assert "LIMIT 10" in sql


class TestQueryTemplate:
    def test_basic_template(self):
        template = QueryTemplate(
            lambda user_id: Query("orders").select("*").where(F("user_id") == user_id)
        )
        sql, params = template.build(user_id=42)
        assert '"user_id" = ?' in sql
        assert params == [42]

    def test_template_multiple_params(self):
        template = QueryTemplate(
            lambda status, min_age: (
                Query("users").select("*")
                .where(F("status") == status, F("age") > min_age)
            )
        )
        sql, params = template.build(status="active", min_age=18)
        assert len(params) == 2

    def test_template_query_method(self):
        template = QueryTemplate(
            lambda name: Query("users").select("*").where(F("name") == name)
        )
        q = template.query(name="John")
        assert isinstance(q, Query)

    def test_template_reusable(self):
        template = QueryTemplate(
            lambda id: Query("users").select("*").where(F("id") == id)
        )
        _, p1 = template.build(id=1)
        _, p2 = template.build(id=2)
        assert p1 == [1]
        assert p2 == [2]


class TestPaginator:
    def test_page_1(self):
        base = Query("users").select("*")
        paginator = Paginator(base, per_page=10)
        sql, _ = paginator.page(1)
        assert "LIMIT 10" in sql
        assert "OFFSET 0" in sql

    def test_page_3(self):
        base = Query("users").select("*")
        paginator = Paginator(base, per_page=10)
        sql, _ = paginator.page(3)
        assert "LIMIT 10" in sql
        assert "OFFSET 20" in sql

    def test_negative_page(self):
        base = Query("users").select("*")
        paginator = Paginator(base, per_page=10)
        sql, _ = paginator.page(-1)
        assert "OFFSET 0" in sql

    def test_count_query(self):
        base = Query("users").select("*").where(F("active") == True).order_by("name")
        paginator = Paginator(base, per_page=10)
        sql, params = paginator.count_query()
        assert "COUNT(*)" in sql
        assert "ORDER BY" not in sql
        assert "LIMIT" not in sql
        assert params == [True]

    def test_preserves_base_query(self):
        base = Query("users").select("*")
        paginator = Paginator(base, per_page=10)
        paginator.page(1)
        paginator.page(2)
        sql, _ = base.build()
        assert "LIMIT" not in sql  # Base query unchanged

    def test_custom_per_page(self):
        paginator = Paginator(Query("users").select("*"), per_page=50)
        sql, _ = paginator.page(1)
        assert "LIMIT 50" in sql


class TestConditionalBuilder:
    def test_when_true(self):
        builder = ConditionalBuilder(Query("users").select("*"))
        builder.when(True, lambda q: q.where(F("active") == True))
        sql, params = builder.build()
        assert '"active" = ?' in sql

    def test_when_false(self):
        builder = ConditionalBuilder(Query("users").select("*"))
        builder.when(False, lambda q: q.where(F("active") == True))
        sql, params = builder.build()
        assert "WHERE" not in sql
        assert params == []

    def test_unless_true(self):
        builder = ConditionalBuilder(Query("users").select("*"))
        builder.unless(True, lambda q: q.where(F("active") == True))
        sql, params = builder.build()
        assert "WHERE" not in sql

    def test_unless_false(self):
        builder = ConditionalBuilder(Query("users").select("*"))
        builder.unless(False, lambda q: q.where(F("active") == True))
        sql, params = builder.build()
        assert '"active" = ?' in sql

    def test_chained_conditions(self):
        name = "John"
        age = None
        builder = (
            ConditionalBuilder(Query("users").select("*"))
            .when(name is not None, lambda q: q.where(F("name") == "John"))
            .when(age is not None, lambda q: q.where(F("age") > 0))
        )
        sql, params = builder.build()
        assert '"name" = ?' in sql
        assert '"age"' not in sql
        assert params == ["John"]

    def test_query_property(self):
        builder = ConditionalBuilder(Query("users").select("*"))
        assert isinstance(builder.query, Query)


class TestBatchInsert:
    def test_single_row(self):
        batch = BatchInsert("users", ["name", "email"])
        batch.add({"name": "John", "email": "john@example.com"})
        sql, params = batch.build()
        assert "INSERT INTO" in sql
        assert params == ["John", "john@example.com"]

    def test_multiple_rows(self):
        batch = BatchInsert("users", ["name", "email"])
        batch.add({"name": "A", "email": "a@example.com"})
        batch.add({"name": "B", "email": "b@example.com"})
        sql, params = batch.build()
        assert len(params) == 4

    def test_add_many(self):
        batch = BatchInsert("users", ["name"])
        batch.add_many([{"name": "A"}, {"name": "B"}, {"name": "C"}])
        assert batch.row_count == 3

    def test_chunked_build(self):
        batch = BatchInsert("users", ["name"], chunk_size=2)
        batch.add_many([{"name": f"User{i}"} for i in range(5)])
        chunks = batch.build_chunks()
        assert len(chunks) == 3  # 2 + 2 + 1
        _, p1 = chunks[0]
        assert len(p1) == 2
        _, p3 = chunks[2]
        assert len(p3) == 1

    def test_row_count(self):
        batch = BatchInsert("users", ["name"])
        assert batch.row_count == 0
        batch.add({"name": "A"})
        assert batch.row_count == 1

    def test_chaining(self):
        batch = (
            BatchInsert("users", ["name"])
            .add({"name": "A"})
            .add({"name": "B"})
        )
        assert batch.row_count == 2
