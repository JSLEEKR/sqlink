"""SQL query analyzer — detects anti-patterns and suggests optimizations."""

from __future__ import annotations

import re
from collections import Counter

from sqlink.explain_parser import parse_explain
from sqlink.models import (
    AnalysisResult,
    ExplainResult,
    Finding,
    ParsedQuery,
    QueryType,
    ScanType,
    Severity,
)
from sqlink.parser import parse_query
from sqlink.rules import (
    ACTUAL_VS_ESTIMATED_MISMATCH,
    FULL_TABLE_SCAN,
    FUNCTION_ON_INDEXED_COLUMN,
    HIGH_COST,
    IMPLICIT_CROSS_JOIN,
    IN_SUBQUERY,
    IS_NULL_CHECK,
    LARGE_ROW_ESTIMATE,
    LEADING_WILDCARD,
    MISSING_LIMIT,
    MISSING_WHERE,
    N_PLUS_ONE,
    NESTED_LOOP_LARGE,
    NOT_EQUAL_FILTER,
    OFFSET_PAGINATION,
    OR_CONDITIONS,
    ORDER_WITHOUT_LIMIT,
    REPEATED_QUERY,
    HAVING_WITHOUT_GROUP,
    SELECT_DISTINCT_SMELL,
    SELECT_STAR,
    SORT_WITHOUT_INDEX,
    TOO_MANY_JOINS,
    UNION_WITHOUT_ALL,
)


# Scoring penalties per severity
SEVERITY_PENALTY = {
    Severity.CRITICAL: 25,
    Severity.ERROR: 15,
    Severity.WARNING: 8,
    Severity.INFO: 3,
}


class QueryAnalyzer:
    """Analyzes SQL queries for anti-patterns."""

    def __init__(
        self,
        *,
        max_joins: int = 5,
        large_row_threshold: int = 10000,
        high_cost_threshold: float = 1000.0,
        row_estimate_mismatch_ratio: float = 10.0,
        disabled_rules: set[str] | None = None,
    ):
        self.max_joins = max_joins
        self.large_row_threshold = large_row_threshold
        self.high_cost_threshold = high_cost_threshold
        self.row_estimate_mismatch_ratio = row_estimate_mismatch_ratio
        self.disabled_rules = disabled_rules or set()

    def _is_enabled(self, rule_id: str) -> bool:
        return rule_id not in self.disabled_rules

    def analyze(self, sql: str, explain_text: str | None = None) -> AnalysisResult:
        """Analyze a single SQL query."""
        parsed = parse_query(sql)
        explain_result = None
        if explain_text:
            explain_result = parse_explain(explain_text)

        findings: list[Finding] = []
        findings.extend(self._check_query_structure(parsed))
        findings.extend(self._check_where_clause(parsed))
        if explain_result:
            findings.extend(self._check_explain(explain_result))

        # Calculate score
        score = 100
        for f in findings:
            score -= SEVERITY_PENALTY.get(f.severity, 0)
        score = max(0, score)

        return AnalysisResult(
            query=sql,
            findings=findings,
            parsed_query=parsed,
            explain_result=explain_result,
            score=score,
        )

    def analyze_batch(self, queries: list[str]) -> list[AnalysisResult]:
        """Analyze a batch of queries, including N+1 detection."""
        results = [self.analyze(q) for q in queries]

        # N+1 detection across the batch
        n1_findings = self._detect_n_plus_one(queries)
        if n1_findings and results:
            results[0].findings.extend(n1_findings)
            for f in n1_findings:
                results[0].score -= SEVERITY_PENALTY.get(f.severity, 0)
            results[0].score = max(0, results[0].score)

        return results

    def _check_query_structure(self, parsed: ParsedQuery) -> list[Finding]:
        """Check for query structure anti-patterns."""
        findings: list[Finding] = []

        # SQ001: SELECT *
        if parsed.has_select_star and self._is_enabled("SQ001"):
            findings.append(Finding(
                rule_id=SELECT_STAR.id,
                title=SELECT_STAR.title,
                description=SELECT_STAR.description,
                severity=SELECT_STAR.severity,
                suggestion=SELECT_STAR.suggestion,
                context=parsed.raw[:100],
            ))

        # SQ002: Missing WHERE on UPDATE/DELETE
        if parsed.query_type in (QueryType.UPDATE, QueryType.DELETE) and not parsed.where_conditions:
            if self._is_enabled("SQ002"):
                findings.append(Finding(
                    rule_id=MISSING_WHERE.id,
                    title=MISSING_WHERE.title,
                    description=MISSING_WHERE.description,
                    severity=MISSING_WHERE.severity,
                    suggestion=MISSING_WHERE.suggestion,
                    context=f"{parsed.query_type.value} without WHERE",
                ))

        # SQ003: DISTINCT
        if parsed.has_distinct and parsed.joins and self._is_enabled("SQ003"):
            findings.append(Finding(
                rule_id=SELECT_DISTINCT_SMELL.id,
                title=SELECT_DISTINCT_SMELL.title,
                description=SELECT_DISTINCT_SMELL.description,
                severity=SELECT_DISTINCT_SMELL.severity,
                suggestion=SELECT_DISTINCT_SMELL.suggestion,
            ))

        # SQ004: OFFSET pagination
        if parsed.has_offset and self._is_enabled("SQ004"):
            findings.append(Finding(
                rule_id=OFFSET_PAGINATION.id,
                title=OFFSET_PAGINATION.title,
                description=OFFSET_PAGINATION.description,
                severity=OFFSET_PAGINATION.severity,
                suggestion=OFFSET_PAGINATION.suggestion,
            ))

        # SQ005: Implicit cross join
        if len(parsed.tables) > 1 and not parsed.joins and parsed.query_type == QueryType.SELECT:
            if self._is_enabled("SQ005"):
                # Only flag if there are multiple tables in FROM without join conditions in WHERE
                has_join_in_where = any(
                    "=" in c.raw and "." in c.raw
                    for c in parsed.where_conditions
                )
                if not has_join_in_where:
                    findings.append(Finding(
                        rule_id=IMPLICIT_CROSS_JOIN.id,
                        title=IMPLICIT_CROSS_JOIN.title,
                        description=IMPLICIT_CROSS_JOIN.description,
                        severity=IMPLICIT_CROSS_JOIN.severity,
                        suggestion=IMPLICIT_CROSS_JOIN.suggestion,
                        context=f"Tables: {', '.join(t.name for t in parsed.tables)}",
                    ))

        # SQ006: Too many joins
        if len(parsed.joins) > self.max_joins and self._is_enabled("SQ006"):
            findings.append(Finding(
                rule_id=TOO_MANY_JOINS.id,
                title=TOO_MANY_JOINS.title,
                description=TOO_MANY_JOINS.description,
                severity=TOO_MANY_JOINS.severity,
                suggestion=TOO_MANY_JOINS.suggestion,
                metadata={"join_count": len(parsed.joins)},
            ))

        # SQ007: UNION without ALL
        if parsed.has_union and "UNION ALL" not in parsed.raw.upper():
            if self._is_enabled("SQ007"):
                findings.append(Finding(
                    rule_id=UNION_WITHOUT_ALL.id,
                    title=UNION_WITHOUT_ALL.title,
                    description=UNION_WITHOUT_ALL.description,
                    severity=UNION_WITHOUT_ALL.severity,
                    suggestion=UNION_WITHOUT_ALL.suggestion,
                ))

        # SD001: SELECT without LIMIT
        if parsed.query_type == QueryType.SELECT and not parsed.has_limit:
            if self._is_enabled("SD001"):
                findings.append(Finding(
                    rule_id=MISSING_LIMIT.id,
                    title=MISSING_LIMIT.title,
                    description=MISSING_LIMIT.description,
                    severity=MISSING_LIMIT.severity,
                    suggestion=MISSING_LIMIT.suggestion,
                ))

        # SD002: ORDER BY without LIMIT
        if parsed.has_order_by and not parsed.has_limit:
            if self._is_enabled("SD002"):
                findings.append(Finding(
                    rule_id=ORDER_WITHOUT_LIMIT.id,
                    title=ORDER_WITHOUT_LIMIT.title,
                    description=ORDER_WITHOUT_LIMIT.description,
                    severity=ORDER_WITHOUT_LIMIT.severity,
                    suggestion=ORDER_WITHOUT_LIMIT.suggestion,
                ))

        # SD003: HAVING without GROUP BY
        if parsed.has_having and not parsed.has_group_by:
            if self._is_enabled("SD003"):
                findings.append(Finding(
                    rule_id=HAVING_WITHOUT_GROUP.id,
                    title=HAVING_WITHOUT_GROUP.title,
                    description=HAVING_WITHOUT_GROUP.description,
                    severity=HAVING_WITHOUT_GROUP.severity,
                    suggestion=HAVING_WITHOUT_GROUP.suggestion,
                ))

        return findings

    def _check_where_clause(self, parsed: ParsedQuery) -> list[Finding]:
        """Check WHERE clause for anti-patterns."""
        findings: list[Finding] = []

        for cond in parsed.where_conditions:
            # WH001: Function on column
            if cond.has_function and self._is_enabled("WH001"):
                findings.append(Finding(
                    rule_id=FUNCTION_ON_INDEXED_COLUMN.id,
                    title=FUNCTION_ON_INDEXED_COLUMN.title,
                    description=FUNCTION_ON_INDEXED_COLUMN.description,
                    severity=FUNCTION_ON_INDEXED_COLUMN.severity,
                    suggestion=FUNCTION_ON_INDEXED_COLUMN.suggestion,
                    context=cond.raw,
                ))

            # WH002: Leading wildcard
            if cond.has_like_wildcard_prefix and self._is_enabled("WH002"):
                findings.append(Finding(
                    rule_id=LEADING_WILDCARD.id,
                    title=LEADING_WILDCARD.title,
                    description=LEADING_WILDCARD.description,
                    severity=LEADING_WILDCARD.severity,
                    suggestion=LEADING_WILDCARD.suggestion,
                    context=cond.raw,
                ))

            # WH003: OR conditions
            if cond.has_or and self._is_enabled("WH003"):
                findings.append(Finding(
                    rule_id=OR_CONDITIONS.id,
                    title=OR_CONDITIONS.title,
                    description=OR_CONDITIONS.description,
                    severity=OR_CONDITIONS.severity,
                    suggestion=OR_CONDITIONS.suggestion,
                    context=cond.raw,
                ))

            # WH004: NOT EQUAL
            if cond.has_not_equal and self._is_enabled("WH004"):
                findings.append(Finding(
                    rule_id=NOT_EQUAL_FILTER.id,
                    title=NOT_EQUAL_FILTER.title,
                    description=NOT_EQUAL_FILTER.description,
                    severity=NOT_EQUAL_FILTER.severity,
                    suggestion=NOT_EQUAL_FILTER.suggestion,
                    context=cond.raw,
                ))

            # WH005: IS NULL
            if cond.has_is_null and self._is_enabled("WH005"):
                findings.append(Finding(
                    rule_id=IS_NULL_CHECK.id,
                    title=IS_NULL_CHECK.title,
                    description=IS_NULL_CHECK.description,
                    severity=IS_NULL_CHECK.severity,
                    suggestion=IS_NULL_CHECK.suggestion,
                    context=cond.raw,
                ))

            # WH006: IN subquery
            if cond.has_in_subquery and self._is_enabled("WH006"):
                findings.append(Finding(
                    rule_id=IN_SUBQUERY.id,
                    title=IN_SUBQUERY.title,
                    description=IN_SUBQUERY.description,
                    severity=IN_SUBQUERY.severity,
                    suggestion=IN_SUBQUERY.suggestion,
                    context=cond.raw,
                ))

        return findings

    def _check_explain(self, explain: ExplainResult) -> list[Finding]:
        """Check EXPLAIN output for performance issues."""
        findings: list[Finding] = []

        for node in explain.nodes:
            # EX001: Full table scan
            if node.scan_type in (ScanType.SEQ_SCAN, ScanType.FULL_TABLE_SCAN):
                if self._is_enabled("EX001"):
                    findings.append(Finding(
                        rule_id=FULL_TABLE_SCAN.id,
                        title=FULL_TABLE_SCAN.title,
                        description=FULL_TABLE_SCAN.description,
                        severity=FULL_TABLE_SCAN.severity,
                        suggestion=FULL_TABLE_SCAN.suggestion,
                        context=f"Table: {node.table or 'unknown'}",
                        metadata={"rows": node.rows},
                    ))

            # EX002: High cost
            if node.cost and node.cost > self.high_cost_threshold:
                if self._is_enabled("EX002"):
                    findings.append(Finding(
                        rule_id=HIGH_COST.id,
                        title=HIGH_COST.title,
                        description=HIGH_COST.description,
                        severity=HIGH_COST.severity,
                        suggestion=HIGH_COST.suggestion,
                        metadata={"cost": node.cost},
                    ))

            # EX003: Large row estimate
            if node.rows and node.rows > self.large_row_threshold:
                if self._is_enabled("EX003"):
                    findings.append(Finding(
                        rule_id=LARGE_ROW_ESTIMATE.id,
                        title=LARGE_ROW_ESTIMATE.title,
                        description=LARGE_ROW_ESTIMATE.description,
                        severity=LARGE_ROW_ESTIMATE.severity,
                        suggestion=LARGE_ROW_ESTIMATE.suggestion,
                        metadata={"rows": node.rows},
                    ))

            # EX004: Nested loop on large dataset
            if node.scan_type == ScanType.NESTED_LOOP:
                if node.rows and node.rows > self.large_row_threshold:
                    if self._is_enabled("EX004"):
                        findings.append(Finding(
                            rule_id=NESTED_LOOP_LARGE.id,
                            title=NESTED_LOOP_LARGE.title,
                            description=NESTED_LOOP_LARGE.description,
                            severity=NESTED_LOOP_LARGE.severity,
                            suggestion=NESTED_LOOP_LARGE.suggestion,
                            metadata={"rows": node.rows},
                        ))

            # EX005: Sort operation
            if node.scan_type == ScanType.SORT:
                if self._is_enabled("EX005"):
                    findings.append(Finding(
                        rule_id=SORT_WITHOUT_INDEX.id,
                        title=SORT_WITHOUT_INDEX.title,
                        description=SORT_WITHOUT_INDEX.description,
                        severity=SORT_WITHOUT_INDEX.severity,
                        suggestion=SORT_WITHOUT_INDEX.suggestion,
                    ))

            # EX006: Row estimate mismatch
            if node.rows and node.actual_rows is not None:
                ratio = max(node.rows, node.actual_rows) / max(min(node.rows, node.actual_rows), 1)
                if ratio > self.row_estimate_mismatch_ratio:
                    if self._is_enabled("EX006"):
                        findings.append(Finding(
                            rule_id=ACTUAL_VS_ESTIMATED_MISMATCH.id,
                            title=ACTUAL_VS_ESTIMATED_MISMATCH.title,
                            description=ACTUAL_VS_ESTIMATED_MISMATCH.description,
                            severity=ACTUAL_VS_ESTIMATED_MISMATCH.severity,
                            suggestion=ACTUAL_VS_ESTIMATED_MISMATCH.suggestion,
                            metadata={"estimated": node.rows, "actual": node.actual_rows, "ratio": ratio},
                        ))

        return findings

    def _detect_n_plus_one(self, queries: list[str]) -> list[Finding]:
        """Detect N+1 query patterns in a batch."""
        findings: list[Finding] = []
        if len(queries) < 3:
            return findings

        # Normalize queries by replacing literal values with placeholders
        def _normalize(q: str) -> str:
            q = re.sub(r"'[^']*'", "?", q)
            q = re.sub(r"\b\d+\b", "?", q)
            q = re.sub(r"\s+", " ", q).strip().upper()
            return q

        normalized = [_normalize(q) for q in queries]
        counter = Counter(normalized)

        # N+1: same pattern appears many times
        for pattern, count in counter.items():
            if count >= 3 and self._is_enabled("NP001"):
                # Find an example query
                example = next(q for q, n in zip(queries, normalized) if n == pattern)
                findings.append(Finding(
                    rule_id=N_PLUS_ONE.id,
                    title=N_PLUS_ONE.title,
                    description=f"{N_PLUS_ONE.description} Pattern repeated {count} times.",
                    severity=N_PLUS_ONE.severity,
                    suggestion=N_PLUS_ONE.suggestion,
                    context=example[:200],
                    metadata={"count": count, "pattern": pattern[:200]},
                ))

        # Repeated identical queries
        exact_counter = Counter(queries)
        for query, count in exact_counter.items():
            if count >= 2 and self._is_enabled("NP002"):
                findings.append(Finding(
                    rule_id=REPEATED_QUERY.id,
                    title=REPEATED_QUERY.title,
                    description=f"{REPEATED_QUERY.description} Repeated {count} times.",
                    severity=REPEATED_QUERY.severity,
                    suggestion=REPEATED_QUERY.suggestion,
                    context=query[:200],
                    metadata={"count": count},
                ))

        return findings
