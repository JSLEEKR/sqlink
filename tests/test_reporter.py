"""Tests for reporter module."""

import json
import pytest
from sqlink.reporter import (
    format_batch_json,
    format_batch_text,
    format_json,
    format_summary,
    format_text,
)
from sqlink.models import AnalysisResult, Finding, Severity


@pytest.fixture
def result_with_findings():
    return AnalysisResult(
        query="SELECT * FROM users",
        findings=[
            Finding(rule_id="SQ001", title="SELECT *", description="Bad", severity=Severity.WARNING, suggestion="Fix"),
            Finding(rule_id="SQ002", title="No WHERE", description="Danger", severity=Severity.ERROR, suggestion="Add WHERE"),
        ],
        score=77,
    )


@pytest.fixture
def clean_result():
    return AnalysisResult(query="SELECT id FROM users LIMIT 10", score=100)


class TestFormatText:
    def test_with_findings(self, result_with_findings):
        text = format_text(result_with_findings, color=False)
        assert "sqlink Analysis Report" in text
        assert "77/100" in text
        assert "SELECT *" in text
        assert "SQ001" in text

    def test_clean_result(self, clean_result):
        text = format_text(clean_result, color=False)
        assert "No issues found" in text

    def test_with_color(self, result_with_findings):
        text = format_text(result_with_findings, color=True)
        assert "\033[" in text  # Contains ANSI codes

    def test_query_preview_truncation(self):
        long_query = "SELECT " + ", ".join(f"col{i}" for i in range(100)) + " FROM t"
        r = AnalysisResult(query=long_query, score=100)
        text = format_text(r, color=False)
        assert "..." in text

    def test_finding_context(self):
        r = AnalysisResult(
            query="SELECT * FROM t",
            findings=[
                Finding(rule_id="X", title="T", description="D", severity=Severity.INFO, suggestion="S", context="ctx123"),
            ],
        )
        text = format_text(r, color=False)
        assert "ctx123" in text


class TestFormatJson:
    def test_valid_json(self, result_with_findings):
        text = format_json(result_with_findings)
        data = json.loads(text)
        assert data["score"] == 77
        assert len(data["findings"]) == 2

    def test_clean_result(self, clean_result):
        data = json.loads(format_json(clean_result))
        assert data["score"] == 100
        assert len(data["findings"]) == 0


class TestFormatBatchText:
    def test_batch(self, result_with_findings, clean_result):
        text = format_batch_text([result_with_findings, clean_result], color=False)
        assert "Batch Analysis" in text
        assert "Queries analyzed: 2" in text

    def test_empty_batch(self):
        text = format_batch_text([], color=False)
        assert "0" in text


class TestFormatBatchJson:
    def test_batch(self, result_with_findings, clean_result):
        text = format_batch_json([result_with_findings, clean_result])
        data = json.loads(text)
        assert data["query_count"] == 2
        assert len(data["results"]) == 2


class TestFormatSummary:
    def test_with_findings(self, result_with_findings):
        text = format_summary([result_with_findings], color=False)
        assert "SQ001" in text

    def test_no_findings(self, clean_result):
        text = format_summary([clean_result], color=False)
        assert "No issues" in text
