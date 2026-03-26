"""Tests for schema definitions."""

import pytest
from sqlink import Column, Schema, ForeignKey
from sqlink.types import ColumnType
from sqlink.dialect import SQLiteDialect, MySQLDialect, PostgreSQLDialect


class TestColumn:
    def test_basic_column(self):
        col = Column("name", ColumnType.TEXT)
        sql = col.to_sql()
        assert '"name"' in sql
        assert "TEXT" in sql

    def test_varchar_with_length(self):
        col = Column("name", ColumnType.VARCHAR, max_length=255)
        sql = col.to_sql()
        assert "VARCHAR(255)" in sql

    def test_primary_key(self):
        col = Column("id", ColumnType.INTEGER, primary_key=True)
        sql = col.to_sql()
        assert "PRIMARY KEY" in sql

    def test_not_null(self):
        col = Column("email", ColumnType.TEXT, nullable=False)
        sql = col.to_sql()
        assert "NOT NULL" in sql

    def test_unique(self):
        col = Column("email", ColumnType.TEXT, unique=True)
        sql = col.to_sql()
        assert "UNIQUE" in sql

    def test_default_string(self):
        col = Column("status", ColumnType.VARCHAR, default="active", max_length=50)
        sql = col.to_sql()
        assert "DEFAULT 'active'" in sql

    def test_default_number(self):
        col = Column("count", ColumnType.INTEGER, default=0)
        sql = col.to_sql()
        assert "DEFAULT 0" in sql

    def test_default_boolean(self):
        col = Column("active", ColumnType.BOOLEAN, default=True)
        sql = col.to_sql()
        assert "DEFAULT" in sql

    def test_check_constraint(self):
        col = Column("age", ColumnType.INTEGER, check="age >= 0")
        sql = col.to_sql()
        assert "CHECK (age >= 0)" in sql

    def test_auto_increment_sqlite(self):
        col = Column("id", ColumnType.INTEGER, primary_key=True, auto_increment=True)
        d = SQLiteDialect()
        sql = col.to_sql(d)
        assert "AUTOINCREMENT" in sql

    def test_auto_increment_mysql(self):
        col = Column("id", ColumnType.INTEGER, primary_key=True, auto_increment=True)
        d = MySQLDialect()
        sql = col.to_sql(d)
        assert "AUTO_INCREMENT" in sql

    def test_string_type(self):
        col = Column("data", "JSONB")
        sql = col.to_sql()
        assert "JSONB" in sql


class TestForeignKey:
    def test_basic_fk(self):
        fk = ForeignKey("user_id", "users", "id")
        sql = fk.to_sql()
        assert "FOREIGN KEY" in sql
        assert "REFERENCES" in sql

    def test_fk_on_delete(self):
        fk = ForeignKey("user_id", "users", "id", on_delete="CASCADE")
        sql = fk.to_sql()
        assert "ON DELETE CASCADE" in sql

    def test_fk_on_update(self):
        fk = ForeignKey("user_id", "users", "id", on_update="SET NULL")
        sql = fk.to_sql()
        assert "ON UPDATE SET NULL" in sql

    def test_fk_with_dialect(self):
        fk = ForeignKey("user_id", "users", "id")
        d = MySQLDialect()
        sql = fk.to_sql(d)
        assert "`user_id`" in sql
        assert "`users`" in sql


class TestSchema:
    def test_create_table(self):
        schema = Schema("users")
        schema.add_column(Column("id", ColumnType.INTEGER, primary_key=True))
        schema.add_column(Column("name", ColumnType.TEXT, nullable=False))
        schema.add_column(Column("email", ColumnType.VARCHAR, unique=True, max_length=255))
        sql = schema.create_table_sql()
        assert 'CREATE TABLE "users"' in sql
        assert "PRIMARY KEY" in sql
        assert "NOT NULL" in sql
        assert "UNIQUE" in sql

    def test_create_table_if_not_exists(self):
        schema = Schema("users", if_not_exists=True)
        schema.add_column(Column("id", ColumnType.INTEGER, primary_key=True))
        sql = schema.create_table_sql()
        assert "IF NOT EXISTS" in sql

    def test_create_table_with_fk(self):
        schema = Schema("orders")
        schema.add_column(Column("id", ColumnType.INTEGER, primary_key=True))
        schema.add_column(Column("user_id", ColumnType.INTEGER, nullable=False))
        schema.add_foreign_key(ForeignKey("user_id", "users", "id", on_delete="CASCADE"))
        sql = schema.create_table_sql()
        assert "FOREIGN KEY" in sql
        assert "ON DELETE CASCADE" in sql

    def test_drop_table(self):
        schema = Schema("users")
        sql = schema.drop_table_sql()
        assert 'DROP TABLE IF EXISTS "users"' == sql

    def test_drop_table_no_if_exists(self):
        schema = Schema("users")
        sql = schema.drop_table_sql(if_exists=False)
        assert 'DROP TABLE "users"' == sql

    def test_create_table_mysql(self):
        d = MySQLDialect()
        schema = Schema("users")
        schema.add_column(Column("id", ColumnType.INTEGER, primary_key=True))
        sql = schema.create_table_sql(d)
        assert "CREATE TABLE `users`" in sql

    def test_schema_chaining(self):
        schema = (
            Schema("tasks")
            .add_column(Column("id", ColumnType.SERIAL, primary_key=True))
            .add_column(Column("title", ColumnType.TEXT, nullable=False))
        )
        sql = schema.create_table_sql()
        assert "SERIAL" in sql
        assert "TEXT" in sql
