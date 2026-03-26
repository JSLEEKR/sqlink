"""Integration tests — real-world query patterns."""

import pytest
from sqlink import (
    Query, Table, F, Raw, Func, Case, Exists, Subquery, Window,
    PostgreSQLDialect, MySQLDialect, SQLiteDialect,
    Schema, Column, ForeignKey,
)
from sqlink.types import ColumnType
from sqlink.aggregates import Count, Sum, Avg, Max, Min
from sqlink.compose import Paginator, ConditionalBuilder, Scope, BatchInsert
from sqlink.transaction import Transaction
from sqlink.json_ops import JsonField


class TestEcommerceQueries:
    """Real-world e-commerce query patterns."""

    def test_product_listing_with_filters(self):
        """Product catalog with price filter, category, and pagination."""
        sql, params = (
            Query("products", alias="p")
            .select("p.id", "p.name", "p.price", "c.name")
            .left_join("categories", Raw('"p"."category_id" = "c"."id"'), alias="c")
            .where(
                F("p.price").between(10, 100),
                F("p.active") == True,
                F("c.name") == "Electronics",
            )
            .order_by(F("p.price").asc())
            .paginate(page=1, per_page=20)
            .build()
        )
        assert "LEFT JOIN" in sql
        assert "BETWEEN" in sql
        assert "LIMIT 20" in sql
        assert len(params) == 4  # low, high, True, "Electronics"

    def test_order_summary_report(self):
        """Monthly order summary grouped by status."""
        sql, params = (
            Query("orders")
            .select(
                "status",
                Count().as_("order_count"),
                Sum("total").as_("total_revenue"),
                Avg("total").as_("avg_order_value"),
            )
            .where(F("created_at") >= "2024-01-01")
            .group_by("status")
            .having(Raw("COUNT(*) > ?", [10]))
            .order_by(F("total_revenue").desc())
            .build()
        )
        assert "COUNT(*)" in sql
        assert "SUM(" in sql
        assert "AVG(" in sql
        assert "GROUP BY" in sql
        assert "HAVING" in sql

    def test_top_customers_with_cte(self):
        """Find top customers using CTE."""
        customer_totals = (
            Query("orders")
            .select("user_id", Sum("total").as_("lifetime_value"))
            .group_by("user_id")
        )
        sql, params = (
            Query()
            .with_cte("totals", customer_totals)
            .select("u.name", "u.email", "t.lifetime_value")
            .from_table("totals", "t")
            .join("users", Raw('"t"."user_id" = "u"."id"'), alias="u")
            .order_by(F("t.lifetime_value").desc())
            .limit(10)
            .build()
        )
        assert "WITH" in sql
        assert "SUM(" in sql
        assert "LIMIT 10" in sql

    def test_upsert_inventory(self):
        """Update or insert inventory count."""
        sql, params = (
            Query("inventory")
            .insert("product_id", "quantity", "warehouse_id")
            .values({"product_id": 42, "quantity": 100, "warehouse_id": 1})
            .on_conflict(["product_id", "warehouse_id"], update_columns=["quantity"])
            .returning("product_id", "quantity")
            .build()
        )
        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql
        assert "RETURNING" in sql

    def test_bulk_price_update(self):
        """Update prices with CASE expression."""
        price_case = (
            Case()
            .when(F("category") == "electronics", Raw('"price" * 1.1'))
            .when(F("category") == "clothing", Raw('"price" * 0.9'))
            .else_(Raw('"price"'))
        )
        sql, params = (
            Query("products")
            .update()
            .set("price", price_case)
            .where(F("active") == True)
            .build()
        )
        assert "CASE" in sql
        assert "WHEN" in sql
        assert "ELSE" in sql


class TestAnalyticsQueries:
    """Analytics and reporting query patterns."""

    def test_running_total(self):
        """Running total with window function."""
        w = Window(Func("SUM", F("amount"))).partition_by("account_id").order_by("date").alias("running_total")
        sql, params = (
            Query("transactions")
            .select("date", "amount", w)
            .where(F("account_id") == 123)
            .order_by(F("date").asc())
            .build()
        )
        assert "SUM(" in sql
        assert "OVER" in sql
        assert "PARTITION BY" in sql

    def test_rank_within_group(self):
        """Rank employees by salary within department."""
        w = Window(Func("RANK")).partition_by("department").order_by("salary", "DESC").alias("salary_rank")
        sql, params = (
            Query("employees")
            .select("name", "department", "salary", w)
            .build()
        )
        assert "RANK()" in sql
        assert "PARTITION BY" in sql

    def test_union_report(self):
        """Combine multiple report queries."""
        q1 = Query("orders").select(Raw("'orders' as source"), Count().as_("count"))
        q2 = Query("returns").select(Raw("'returns' as source"), Count().as_("count"))
        q3 = Query("complaints").select(Raw("'complaints' as source"), Count().as_("count"))
        sql, params = q1.union_all(q2).union_all(q3).build()
        assert sql.count("UNION ALL") == 2


class TestMultiDialect:
    """Same query across different dialects."""

    def test_same_query_three_dialects(self):
        q = Query("users").select("id", "name").where(F("active") == True).limit(10)

        pg_sql, pg_params = q.clone().build(PostgreSQLDialect())
        my_sql, my_params = q.clone().build(MySQLDialect())
        sq_sql, sq_params = q.clone().build(SQLiteDialect())

        # PostgreSQL: $1 placeholder, double-quote identifiers
        assert "$1" in pg_sql
        assert '"users"' in pg_sql

        # MySQL: %s placeholder, backtick identifiers
        assert "%s" in my_sql
        assert "`users`" in my_sql

        # SQLite: ? placeholder, double-quote identifiers
        assert "?" in sq_sql
        assert '"users"' in sq_sql

        # All have same params
        assert pg_params == my_params == sq_params == [True]


class TestConditionalSearch:
    """Dynamic search with conditional filters."""

    def test_dynamic_search_api(self):
        """Simulate API with optional filters."""
        name = "John"
        min_age = 18
        max_age = None
        status = "active"
        sort_by = "name"

        builder = ConditionalBuilder(Query("users").select("id", "name", "age", "status"))
        builder.when(name is not None, lambda q: q.where(F("name").like(f"%{name}%")))
        builder.when(min_age is not None, lambda q: q.where(F("age") >= min_age))
        builder.when(max_age is not None, lambda q: q.where(F("age") <= max_age))
        builder.when(status is not None, lambda q: q.where(F("status") == status))
        builder.when(sort_by is not None, lambda q: q.order_by(F(sort_by).asc()))

        sql, params = builder.build()
        assert "LIKE" in sql
        assert '"age" >=' in sql
        assert '"status" =' in sql
        assert "ORDER BY" in sql
        # max_age is None, so no <= condition
        assert "<=" not in sql


class TestSchemaWorkflow:
    """Schema creation workflow."""

    def test_create_full_schema(self):
        """Create a multi-table schema."""
        users = Schema("users", if_not_exists=True)
        users.add_column(Column("id", ColumnType.SERIAL, primary_key=True))
        users.add_column(Column("email", ColumnType.VARCHAR, max_length=255, unique=True, nullable=False))
        users.add_column(Column("name", ColumnType.VARCHAR, max_length=100, nullable=False))
        users.add_column(Column("created_at", ColumnType.TIMESTAMP, default="CURRENT_TIMESTAMP"))

        orders = Schema("orders", if_not_exists=True)
        orders.add_column(Column("id", ColumnType.SERIAL, primary_key=True))
        orders.add_column(Column("user_id", ColumnType.INTEGER, nullable=False))
        orders.add_column(Column("total", ColumnType.DECIMAL, nullable=False))
        orders.add_foreign_key(ForeignKey("user_id", "users", "id", on_delete="CASCADE"))

        users_sql = users.create_table_sql()
        orders_sql = orders.create_table_sql()

        assert "IF NOT EXISTS" in users_sql
        assert "UNIQUE" in users_sql
        assert "FOREIGN KEY" in orders_sql
        assert "CASCADE" in orders_sql


class TestTransactionWorkflow:
    """Transaction patterns."""

    def test_transfer_funds(self):
        """Bank transfer transaction."""
        tx = Transaction(isolation_level="SERIALIZABLE")
        tx.add(
            Query("accounts").update().set("balance", Raw('"balance" - 100'))
            .where(F("id") == 1)
        )
        tx.add(
            Query("accounts").update().set("balance", Raw('"balance" + 100'))
            .where(F("id") == 2)
        )
        tx.add(
            Query("transfers").insert("from_id", "to_id", "amount")
            .values({"from_id": 1, "to_id": 2, "amount": 100})
        )
        stmts = tx.build()
        assert stmts[0][0] == "BEGIN ISOLATION LEVEL SERIALIZABLE"
        assert len(stmts) == 5  # BEGIN + 3 queries + COMMIT
        assert stmts[-1][0] == "COMMIT"


class TestBatchOperations:
    def test_batch_insert_users(self):
        batch = BatchInsert("users", ["name", "email"], chunk_size=2)
        for i in range(5):
            batch.add({"name": f"User{i}", "email": f"user{i}@example.com"})
        chunks = batch.build_chunks()
        assert len(chunks) == 3
        for sql, params in chunks:
            assert "INSERT INTO" in sql


class TestJsonQueries:
    def test_filter_by_json_field(self):
        sql, params = (
            Query("users")
            .select("id", "name")
            .where(JsonField("profile", "country") == "US")
            .where(JsonField("settings", "theme") == "dark")
            .build()
        )
        assert sql.count("->>") == 2
        assert params == ["US", "dark"]
