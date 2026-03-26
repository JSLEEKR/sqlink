"""Tests for sqlink models."""

import pytest
from sqlink.models import (
    AnalysisResult,
    ColumnReference,
    ExplainNode,
    ExplainResult,
    Finding,
    JoinClause,
    JoinType,
    ParsedQuery,
    QueryType,
    ScanType,
    Severity,
    SubQuery,
    TableReference,
    WhereCondition,
)


class TestSeverity:
    def test_values(self):
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
        assert Severity.CRITICAL.value == "critical"

    def test_ordering(self):
        assert Severity.INFO < Severity.WARNING
        assert Severity.WARNING < Severity.ERROR
        assert Severity.ERROR < Severity.CRITICAL
        assert not (Severity.CRITICAL < Severity.INFO)

    def test_le(self):
        assert Severity.INFO <= Severity.INFO
        assert Severity.INFO <= Severity.WARNING
        assert not (Severity.ERROR <= Severity.WARNING)

    def test_lt_not_implemented(self):
        assert Severity.INFO.__lt__("string") is NotImplemented

    def test_le_not_implemented(self):
        assert Severity.INFO.__le__(42) is NotImplemented


class TestTableReference:
    def test_basic(self):
        t = TableReference(name="users")
        assert t.full_name == "users"
        assert t.effective_name == "users"

    def test_with_alias(self):
        t = TableReference(name="users", alias="u")
        assert t.full_name == "users"
        assert t.effective_name == "u"

    def test_with_schema(self):
        t = TableReference(name="users", schema="public")
        assert t.full_name == "public.users"

    def test_with_all(self):
        t = TableReference(name="users", alias="u", schema="public")
        assert t.full_name == "public.users"
        assert t.effective_name == "u"


class TestColumnReference:
    def test_basic(self):
        c = ColumnReference(name="id")
        assert c.full_name == "id"

    def test_with_table(self):
        c = ColumnReference(name="id", table="users")
        assert c.full_name == "users.id"


class TestFinding:
    def test_to_dict(self):
        f = Finding(
            rule_id="SQ001",
            title="Test",
            description="Desc",
            severity=Severity.WARNING,
            suggestion="Fix it",
            location="line 1",
            context="ctx",
        )
        d = f.to_dict()
        assert d["rule_id"] == "SQ001"
        assert d["severity"] == "warning"
        assert d["suggestion"] == "Fix it"

    def test_to_dict_with_metadata(self):
        f = Finding(
            rule_id="SQ001",
            title="T",
            description="D",
            severity=Severity.INFO,
            suggestion="S",
            metadata={"count": 5},
        )
        assert f.to_dict()["metadata"]["count"] == 5


class TestAnalysisResult:
    def test_empty(self):
        r = AnalysisResult(query="SELECT 1")
        assert not r.has_issues
        assert r.critical_count == 0
        assert r.error_count == 0
        assert r.warning_count == 0
        assert r.info_count == 0
        assert r.score == 100

    def test_with_findings(self):
        r = AnalysisResult(
            query="SELECT *",
            findings=[
                Finding(rule_id="A", title="", description="", severity=Severity.CRITICAL, suggestion=""),
                Finding(rule_id="B", title="", description="", severity=Severity.ERROR, suggestion=""),
                Finding(rule_id="C", title="", description="", severity=Severity.WARNING, suggestion=""),
                Finding(rule_id="D", title="", description="", severity=Severity.INFO, suggestion=""),
            ],
        )
        assert r.has_issues
        assert r.critical_count == 1
        assert r.error_count == 1
        assert r.warning_count == 1
        assert r.info_count == 1

    def test_to_dict(self):
        r = AnalysisResult(query="SELECT 1", score=85)
        d = r.to_dict()
        assert d["query"] == "SELECT 1"
        assert d["score"] == 85
        assert d["summary"]["total"] == 0


class TestQueryType:
    def test_values(self):
        assert QueryType.SELECT.value == "SELECT"
        assert QueryType.INSERT.value == "INSERT"
        assert QueryType.DELETE.value == "DELETE"


class TestJoinType:
    def test_values(self):
        assert JoinType.INNER.value == "INNER"
        assert JoinType.LEFT.value == "LEFT"
        assert JoinType.CROSS.value == "CROSS"


class TestScanType:
    def test_seq_scan(self):
        assert ScanType.SEQ_SCAN.value == "Seq Scan"

    def test_index_scan(self):
        assert ScanType.INDEX_SCAN.value == "Index Scan"


class TestWhereCondition:
    def test_defaults(self):
        w = WhereCondition(raw="x = 1")
        assert not w.has_function
        assert not w.has_or
        assert not w.has_like_wildcard_prefix


class TestSubQuery:
    def test_basic(self):
        s = SubQuery(raw="SELECT 1", location="WHERE")
        assert s.location == "WHERE"


class TestExplainNode:
    def test_defaults(self):
        n = ExplainNode(scan_type=ScanType.SEQ_SCAN)
        assert n.table is None
        assert n.rows is None
        assert n.children == []


class TestExplainResult:
    def test_defaults(self):
        r = ExplainResult(raw="test")
        assert r.nodes == []
        assert r.dialect == "unknown"
