"""Tests for migration builder (ALTER TABLE operations)."""

import pytest
from sqlink.migration import AlterTable
from sqlink.schema import Column, ForeignKey
from sqlink.types import ColumnType
from sqlink.dialect import MySQLDialect, PostgreSQLDialect


class TestAddColumn:
    def test_add_simple_column(self):
        stmts = AlterTable("users").add_column(
            Column("phone", ColumnType.VARCHAR, max_length=20)
        ).build()
        assert len(stmts) == 1
        assert 'ALTER TABLE "users" ADD COLUMN' in stmts[0]
        assert "VARCHAR(20)" in stmts[0]

    def test_add_not_null_column(self):
        stmts = AlterTable("users").add_column(
            Column("email", ColumnType.TEXT, nullable=False)
        ).build()
        assert "NOT NULL" in stmts[0]

    def test_add_column_with_default(self):
        stmts = AlterTable("users").add_column(
            Column("status", ColumnType.VARCHAR, default="active", max_length=50)
        ).build()
        assert "DEFAULT 'active'" in stmts[0]


class TestDropColumn:
    def test_drop_column(self):
        stmts = AlterTable("users").drop_column("legacy_field").build()
        assert stmts[0] == 'ALTER TABLE "users" DROP COLUMN "legacy_field"'


class TestRenameColumn:
    def test_rename_column(self):
        stmts = AlterTable("users").rename_column("fname", "first_name").build()
        assert 'RENAME COLUMN "fname" TO "first_name"' in stmts[0]


class TestAlterType:
    def test_alter_column_type(self):
        stmts = AlterTable("users").alter_column_type("age", "BIGINT").build()
        assert 'ALTER COLUMN "age" TYPE BIGINT' in stmts[0]


class TestNotNull:
    def test_set_not_null(self):
        stmts = AlterTable("users").set_not_null("email").build()
        assert 'SET NOT NULL' in stmts[0]

    def test_drop_not_null(self):
        stmts = AlterTable("users").drop_not_null("phone").build()
        assert 'DROP NOT NULL' in stmts[0]


class TestUnique:
    def test_add_unique(self):
        stmts = AlterTable("users").add_unique("email").build()
        assert 'ADD UNIQUE ("email")' in stmts[0]

    def test_add_unique_named(self):
        stmts = AlterTable("users").add_unique("email", name="uq_email").build()
        assert 'ADD CONSTRAINT "uq_email" UNIQUE ("email")' in stmts[0]

    def test_add_composite_unique(self):
        stmts = AlterTable("users").add_unique("first_name", "last_name").build()
        assert '"first_name", "last_name"' in stmts[0]


class TestConstraints:
    def test_drop_constraint(self):
        stmts = AlterTable("users").drop_constraint("uq_email").build()
        assert 'DROP CONSTRAINT "uq_email"' in stmts[0]


class TestIndex:
    def test_add_index(self):
        stmts = AlterTable("users").add_index("email").build()
        assert 'CREATE INDEX' in stmts[0]
        assert "ON" in stmts[0]

    def test_add_named_index(self):
        stmts = AlterTable("users").add_index("email", name="idx_email").build()
        assert '"idx_email"' in stmts[0]

    def test_add_unique_index(self):
        stmts = AlterTable("users").add_index("email", unique=True).build()
        assert "UNIQUE INDEX" in stmts[0]

    def test_add_composite_index(self):
        stmts = AlterTable("users").add_index("last_name", "first_name").build()
        assert '"last_name", "first_name"' in stmts[0]

    def test_auto_generated_index_name(self):
        stmts = AlterTable("users").add_index("email").build()
        assert "idx_users_email" in stmts[0]

    def test_drop_index(self):
        stmts = AlterTable("orders").drop_index("idx_orders_user_id").build()
        assert 'DROP INDEX "idx_orders_user_id"' in stmts[0]


class TestForeignKey:
    def test_add_fk(self):
        fk = ForeignKey("user_id", "users", "id", on_delete="CASCADE")
        stmts = AlterTable("orders").add_foreign_key(fk).build()
        assert "FOREIGN KEY" in stmts[0]
        assert "REFERENCES" in stmts[0]
        assert "ON DELETE CASCADE" in stmts[0]

    def test_add_named_fk(self):
        fk = ForeignKey("user_id", "users", "id")
        stmts = AlterTable("orders").add_foreign_key(fk, name="fk_order_user").build()
        assert 'ADD CONSTRAINT "fk_order_user"' in stmts[0]


class TestDefault:
    def test_set_default_string(self):
        stmts = AlterTable("users").set_default("status", "active").build()
        assert "SET DEFAULT 'active'" in stmts[0]

    def test_set_default_number(self):
        stmts = AlterTable("users").set_default("count", 0).build()
        assert "SET DEFAULT 0" in stmts[0]

    def test_set_default_bool(self):
        stmts = AlterTable("users").set_default("active", True).build()
        assert "SET DEFAULT TRUE" in stmts[0]

    def test_drop_default(self):
        stmts = AlterTable("users").drop_default("count").build()
        assert "DROP DEFAULT" in stmts[0]


class TestRenameTable:
    def test_rename_table(self):
        stmts = AlterTable("users").rename_table("accounts").build()
        assert 'RENAME TO "accounts"' in stmts[0]


class TestMultipleOperations:
    def test_multiple_ops(self):
        stmts = (
            AlterTable("users")
            .add_column(Column("phone", ColumnType.VARCHAR, max_length=20))
            .drop_column("fax")
            .rename_column("fname", "first_name")
            .build()
        )
        assert len(stmts) == 3

    def test_chaining(self):
        alter = AlterTable("users")
        result = alter.add_column(Column("a", ColumnType.TEXT))
        assert result is alter  # Chaining returns same object


class TestWithDialect:
    def test_mysql_dialect(self):
        d = MySQLDialect()
        stmts = AlterTable("users").add_column(
            Column("phone", ColumnType.VARCHAR, max_length=20)
        ).build(d)
        assert "`users`" in stmts[0]
        assert "`phone`" in stmts[0]

    def test_pg_dialect(self):
        d = PostgreSQLDialect()
        stmts = AlterTable("users").drop_column("legacy").build(d)
        assert '"users"' in stmts[0]
        assert '"legacy"' in stmts[0]
