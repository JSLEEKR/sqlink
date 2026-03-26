"""Tests for transaction builder."""

import pytest
from sqlink import Query, F
from sqlink.transaction import Transaction
from sqlink.dialect import PostgreSQLDialect


class TestBasicTransaction:
    def test_empty_transaction(self):
        tx = Transaction()
        stmts = tx.build()
        assert len(stmts) == 2  # BEGIN + COMMIT
        assert stmts[0] == ("BEGIN", [])
        assert stmts[1] == ("COMMIT", [])

    def test_single_query(self):
        tx = Transaction()
        tx.add(Query("users").update(name="John").where(F("id") == 1))
        stmts = tx.build()
        assert len(stmts) == 3  # BEGIN + query + COMMIT
        assert stmts[0][0] == "BEGIN"
        assert "UPDATE" in stmts[1][0]
        assert stmts[2][0] == "COMMIT"

    def test_multiple_queries(self):
        tx = Transaction()
        tx.add(Query("users").update(balance=100).where(F("id") == 1))
        tx.add(Query("logs").insert("action").values({"action": "update"}))
        stmts = tx.build()
        assert len(stmts) == 4
        assert "UPDATE" in stmts[1][0]
        assert "INSERT" in stmts[2][0]

    def test_raw_sql(self):
        tx = Transaction()
        tx.add("SET LOCAL timezone = 'UTC'")
        tx.add(Query("users").select("*"))
        stmts = tx.build()
        assert stmts[1] == ("SET LOCAL timezone = 'UTC'", [])

    def test_query_count(self):
        tx = Transaction()
        assert tx.query_count == 0
        tx.add(Query("users").select("*"))
        tx.add(Query("orders").select("*"))
        assert tx.query_count == 2


class TestIsolationLevel:
    def test_serializable(self):
        tx = Transaction(isolation_level="SERIALIZABLE")
        stmts = tx.build()
        assert stmts[0][0] == "BEGIN ISOLATION LEVEL SERIALIZABLE"

    def test_read_committed(self):
        tx = Transaction(isolation_level="READ COMMITTED")
        stmts = tx.build()
        assert "READ COMMITTED" in stmts[0][0]

    def test_repeatable_read(self):
        tx = Transaction(isolation_level="REPEATABLE READ")
        stmts = tx.build()
        assert "REPEATABLE READ" in stmts[0][0]


class TestSavepoint:
    def test_savepoint(self):
        tx = Transaction()
        tx.add(Query("users").update(name="A").where(F("id") == 1))
        tx.savepoint("sp1")
        tx.add(Query("users").update(name="B").where(F("id") == 2))
        stmts = tx.build()
        savepoint_found = any("SAVEPOINT sp1" in s[0] for s in stmts)
        assert savepoint_found

    def test_rollback_to_savepoint(self):
        tx = Transaction()
        tx.savepoint("sp1")
        tx.rollback_to("sp1")
        stmts = tx.build()
        assert any("ROLLBACK TO SAVEPOINT sp1" in s[0] for s in stmts)

    def test_release_savepoint(self):
        tx = Transaction()
        tx.savepoint("sp1")
        tx.release_savepoint("sp1")
        stmts = tx.build()
        assert any("RELEASE SAVEPOINT sp1" in s[0] for s in stmts)


class TestRollback:
    def test_rollback(self):
        tx = Transaction()
        stmts = tx.build_rollback()
        assert stmts == [("ROLLBACK", [])]


class TestChaining:
    def test_chain_add(self):
        tx = (
            Transaction()
            .add(Query("users").select("*"))
            .add(Query("orders").select("*"))
        )
        assert tx.query_count == 2

    def test_chain_savepoint(self):
        tx = (
            Transaction()
            .add(Query("users").update(x=1))
            .savepoint("sp1")
            .add(Query("orders").update(y=2))
        )
        assert tx.query_count == 3  # 2 queries + 1 savepoint string


class TestWithDialect:
    def test_pg_dialect(self):
        d = PostgreSQLDialect()
        tx = Transaction()
        tx.add(Query("users").update(name="John").where(F("id") == 1))
        stmts = tx.build(d)
        assert "$1" in stmts[1][0] or "$2" in stmts[1][0]
