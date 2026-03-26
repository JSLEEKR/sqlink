"""Tests for DDL builders (CREATE INDEX, TRUNCATE, views)."""

import pytest
from sqlink import Query, F
from sqlink.ddl import CreateIndex, DropIndex, Truncate, CreateView, DropView
from sqlink.dialect import PostgreSQLDialect, MySQLDialect


class TestCreateIndex:
    def test_basic(self):
        sql = CreateIndex("idx_email", "users", ["email"]).build()
        assert sql == 'CREATE INDEX "idx_email" ON "users" ("email")'

    def test_unique(self):
        sql = CreateIndex("idx_email", "users", ["email"]).unique().build()
        assert "UNIQUE INDEX" in sql

    def test_if_not_exists(self):
        sql = CreateIndex("idx_email", "users", ["email"]).if_not_exists().build()
        assert "IF NOT EXISTS" in sql

    def test_composite(self):
        sql = CreateIndex("idx_name", "users", ["first_name", "last_name"]).build()
        assert '"first_name", "last_name"' in sql

    def test_partial_index(self):
        sql = CreateIndex("idx_active", "users", ["email"]).where("active = true").build()
        assert "WHERE active = true" in sql

    def test_using_method(self):
        sql = CreateIndex("idx_data", "users", ["data"]).using("gin").build()
        assert "USING gin" in sql

    def test_concurrently(self):
        sql = CreateIndex("idx_email", "users", ["email"]).concurrently().build()
        assert "CONCURRENTLY" in sql

    def test_full_featured(self):
        sql = (
            CreateIndex("idx_email", "users", ["email"])
            .unique()
            .concurrently()
            .if_not_exists()
            .using("btree")
            .where("deleted_at IS NULL")
            .build()
        )
        assert "UNIQUE" in sql
        assert "CONCURRENTLY" in sql
        assert "IF NOT EXISTS" in sql
        assert "USING btree" in sql
        assert "WHERE deleted_at IS NULL" in sql

    def test_mysql_dialect(self):
        d = MySQLDialect()
        sql = CreateIndex("idx_email", "users", ["email"]).build(d)
        assert "`idx_email`" in sql
        assert "`users`" in sql


class TestDropIndex:
    def test_basic(self):
        sql = DropIndex("idx_email").build()
        assert sql == 'DROP INDEX "idx_email"'

    def test_if_exists(self):
        sql = DropIndex("idx_email").if_exists().build()
        assert "IF EXISTS" in sql

    def test_concurrently(self):
        sql = DropIndex("idx_email").concurrently().build()
        assert "CONCURRENTLY" in sql

    def test_cascade(self):
        sql = DropIndex("idx_email").cascade().build()
        assert "CASCADE" in sql


class TestTruncate:
    def test_single_table(self):
        sql = Truncate("users").build()
        assert sql == 'TRUNCATE TABLE "users"'

    def test_multiple_tables(self):
        sql = Truncate("users", "orders", "logs").build()
        assert '"users", "orders", "logs"' in sql

    def test_cascade(self):
        sql = Truncate("users").cascade().build()
        assert "CASCADE" in sql

    def test_restart_identity(self):
        sql = Truncate("users").restart_identity().build()
        assert "RESTART IDENTITY" in sql

    def test_only(self):
        sql = Truncate("users").only().build()
        assert "ONLY" in sql

    def test_full_featured(self):
        sql = Truncate("users").restart_identity().cascade().build()
        assert "RESTART IDENTITY" in sql
        assert "CASCADE" in sql

    def test_mysql_dialect(self):
        d = MySQLDialect()
        sql = Truncate("users").build(d)
        assert "`users`" in sql


class TestCreateView:
    def test_basic_view(self):
        q = Query("users").select("id", "name").where(F("active") == True)
        sql, params = CreateView("active_users", q).build()
        assert 'CREATE VIEW "active_users" AS' in sql
        assert "SELECT" in sql
        assert params == [True]

    def test_or_replace(self):
        q = Query("users").select("*")
        sql, _ = CreateView("all_users", q).or_replace().build()
        assert "OR REPLACE" in sql

    def test_materialized(self):
        q = Query("users").select("*")
        sql, _ = CreateView("user_cache", q).materialized().build()
        assert "MATERIALIZED VIEW" in sql

    def test_with_columns(self):
        q = Query("users").select("id", "name")
        sql, _ = CreateView("user_names", q).columns("user_id", "user_name").build()
        assert '("user_id", "user_name")' in sql

    def test_with_dialect(self):
        d = PostgreSQLDialect()
        q = Query("users").select("*").where(F("active") == True)
        sql, params = CreateView("active", q).build(d)
        assert "$1" in sql


class TestDropView:
    def test_basic(self):
        sql = DropView("active_users").build()
        assert sql == 'DROP VIEW "active_users"'

    def test_if_exists(self):
        sql = DropView("active_users").if_exists().build()
        assert "IF EXISTS" in sql

    def test_materialized(self):
        sql = DropView("user_cache").materialized().build()
        assert "MATERIALIZED VIEW" in sql

    def test_cascade(self):
        sql = DropView("active_users").cascade().build()
        assert "CASCADE" in sql

    def test_full_featured(self):
        sql = DropView("user_cache").materialized().if_exists().cascade().build()
        assert "MATERIALIZED" in sql
        assert "IF EXISTS" in sql
        assert "CASCADE" in sql
