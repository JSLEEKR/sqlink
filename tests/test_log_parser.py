"""Tests for query log parser."""

import pytest
from sqlink.log_parser import (
    LogEntry,
    LogSummary,
    parse_log,
    parse_mysql_slow_log,
    parse_postgresql_log,
    summarize_log,
)


class TestLogEntry:
    def test_to_dict(self):
        e = LogEntry(query="SELECT 1", duration_ms=10.5, user="admin")
        d = e.to_dict()
        assert d["query"] == "SELECT 1"
        assert d["duration_ms"] == 10.5
        assert d["user"] == "admin"

    def test_defaults(self):
        e = LogEntry(query="SELECT 1")
        assert e.duration_ms is None
        assert e.timestamp is None
        assert e.source == ""


class TestLogSummary:
    def test_to_dict(self):
        s = LogSummary(total_entries=5, total_duration_ms=100.0)
        d = s.to_dict()
        assert d["total_entries"] == 5
        assert d["avg_duration_ms"] == 20.0

    def test_empty(self):
        s = LogSummary()
        d = s.to_dict()
        assert d["avg_duration_ms"] == 0


class TestPostgresqlLog:
    def test_basic_format(self):
        log = "2024-01-15 10:30:45.123 UTC [1234] admin@mydb LOG:  duration: 123.456 ms  statement: SELECT * FROM users\n\n"
        entries = parse_postgresql_log(log)
        assert len(entries) == 1
        assert entries[0].query == "SELECT * FROM users"
        assert entries[0].duration_ms == 123.456
        assert entries[0].user == "admin"
        assert entries[0].database == "mydb"

    def test_simple_format(self):
        log = "duration: 50.0 ms  statement: SELECT 1\n\n"
        entries = parse_postgresql_log(log)
        assert len(entries) == 1
        assert entries[0].duration_ms == 50.0

    def test_empty(self):
        assert parse_postgresql_log("") == []

    def test_no_matching_lines(self):
        assert parse_postgresql_log("some random log output") == []


class TestMysqlSlowLog:
    def test_basic_format(self):
        log = """# Time: 2024-01-15T10:30:45.123456Z
# User@Host: admin[admin] @ localhost []  Id:  1234
# Query_time: 1.234567  Lock_time: 0.000123 Rows_sent: 100  Rows_examined: 50000
SET timestamp=1705312245;
SELECT * FROM users WHERE status = 'active';
"""
        entries = parse_mysql_slow_log(log)
        assert len(entries) == 1
        assert "SELECT" in entries[0].query
        assert entries[0].duration_ms == pytest.approx(1234.567)
        assert entries[0].rows_sent == 100
        assert entries[0].rows_examined == 50000

    def test_multiple_entries(self):
        log = """# Time: 2024-01-15T10:30:45Z
# User@Host: admin[admin] @ localhost []
# Query_time: 1.0  Lock_time: 0.0 Rows_sent: 10  Rows_examined: 1000
SELECT * FROM a;
# Time: 2024-01-15T10:31:00Z
# User@Host: admin[admin] @ localhost []
# Query_time: 2.0  Lock_time: 0.0 Rows_sent: 20  Rows_examined: 2000
SELECT * FROM b;
"""
        entries = parse_mysql_slow_log(log)
        assert len(entries) == 2

    def test_empty(self):
        assert parse_mysql_slow_log("") == []


class TestParseLog:
    def test_auto_detect_mysql(self):
        log = """# Time: 2024-01-15T10:30:45Z
# Query_time: 1.0  Lock_time: 0.0 Rows_sent: 10  Rows_examined: 1000
SELECT * FROM users;
"""
        entries = parse_log(log)
        assert len(entries) >= 1

    def test_auto_detect_postgresql(self):
        log = "duration: 50.0 ms  statement: SELECT 1\n\n"
        entries = parse_log(log)
        assert len(entries) >= 1

    def test_unknown_format(self):
        # With no recognizable format markers, parse_log returns empty or minimal
        entries = parse_log("")
        assert entries == []


class TestSummarizeLog:
    def test_basic_summary(self):
        entries = [
            LogEntry(query="SELECT * FROM users WHERE id = 1", duration_ms=100),
            LogEntry(query="SELECT * FROM users WHERE id = 2", duration_ms=200),
            LogEntry(query="SELECT * FROM users WHERE id = 3", duration_ms=300),
            LogEntry(query="SELECT * FROM orders", duration_ms=50),
        ]
        summary = summarize_log(entries)
        assert summary.total_entries == 4
        assert summary.total_duration_ms == 650
        assert len(summary.slowest_queries) == 4
        assert summary.slowest_queries[0].duration_ms == 300

    def test_most_frequent(self):
        entries = [
            LogEntry(query="SELECT * FROM users WHERE id = 1", duration_ms=10),
            LogEntry(query="SELECT * FROM users WHERE id = 2", duration_ms=20),
            LogEntry(query="SELECT * FROM users WHERE id = 3", duration_ms=30),
        ]
        summary = summarize_log(entries)
        assert len(summary.most_frequent) >= 1
        assert summary.most_frequent[0]["count"] >= 3

    def test_empty(self):
        summary = summarize_log([])
        assert summary.total_entries == 0

    def test_top_n(self):
        entries = [LogEntry(query=f"SELECT {i}", duration_ms=float(i)) for i in range(20)]
        summary = summarize_log(entries, top_n=5)
        assert len(summary.slowest_queries) == 5

    def test_summary_to_dict(self):
        entries = [LogEntry(query="SELECT 1", duration_ms=100)]
        summary = summarize_log(entries)
        d = summary.to_dict()
        assert d["total_entries"] == 1
        assert d["avg_duration_ms"] == 100.0
