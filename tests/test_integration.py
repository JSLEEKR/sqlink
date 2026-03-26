"""Integration tests — end-to-end scenarios."""

import json
import os
import tempfile
import pytest
from sqlink.cli import main


class TestAnalyzeIntegration:
    def test_analyze_with_index_suggestions(self):
        result = main(["analyze", "--suggest-indexes", "--no-color",
                       "SELECT * FROM users WHERE email = 'test@test.com'"])
        assert result in (0, 1)

    def test_analyze_with_rewrites(self):
        result = main(["analyze", "--suggest-rewrites", "--no-color",
                       "SELECT * FROM users"])
        assert result in (0, 1)

    def test_analyze_with_complexity(self):
        result = main(["analyze", "--complexity", "--no-color",
                       "SELECT * FROM a JOIN b ON a.id = b.a_id WHERE a.x = 1"])
        assert result in (0, 1)

    def test_analyze_with_patterns(self):
        result = main(["analyze", "--patterns", "--no-color",
                       "SELECT COUNT(*) FROM users WHERE email = 'x'"])
        assert result in (0, 1)

    def test_analyze_all_features_json(self, capsys):
        result = main(["analyze", "--format", "json",
                       "--suggest-indexes", "--suggest-rewrites",
                       "--complexity", "--patterns",
                       "SELECT * FROM users WHERE email = 'test@test.com'"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "score" in data
        assert "index_suggestions" in data
        assert "rewrites" in data
        assert "complexity" in data
        assert "patterns" in data

    def test_analyze_clean_query(self, capsys):
        result = main(["analyze", "--format", "json",
                       "SELECT id, name FROM users WHERE id = 1 LIMIT 1"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["score"] >= 80


class TestBatchIntegration:
    def test_batch_with_n_plus_one(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("""
SELECT * FROM orders WHERE user_id = 1;
SELECT * FROM orders WHERE user_id = 2;
SELECT * FROM orders WHERE user_id = 3;
SELECT * FROM orders WHERE user_id = 4;
            """)
            f.flush()
            result = main(["batch", f.name, "--format", "json"])
        os.unlink(f.name)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["query_count"] == 4
        # Should detect N+1
        all_findings = []
        for r in data["results"]:
            all_findings.extend(r["findings"])
        rule_ids = [f["rule_id"] for f in all_findings]
        assert "NP001" in rule_ids

    def test_batch_mixed_queries(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("""
SELECT id FROM users WHERE id = 1 LIMIT 1;
UPDATE users SET name = 'x';
SELECT * FROM a, b;
DELETE FROM logs;
            """)
            f.flush()
            result = main(["batch", f.name, "--format", "json"])
        os.unlink(f.name)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["query_count"] == 4
        assert data["total_findings"] > 0


class TestFingerprintIntegration:
    def test_fingerprint_command(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("""
SELECT * FROM users WHERE id = 1;
SELECT * FROM users WHERE id = 2;
SELECT * FROM users WHERE id = 3;
SELECT * FROM orders WHERE id = 1;
            """)
            f.flush()
            result = main(["fingerprint", f.name])
        os.unlink(f.name)
        assert result == 0

    def test_fingerprint_json(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT * FROM t WHERE id = 1; SELECT * FROM t WHERE id = 2;")
            f.flush()
            result = main(["fingerprint", f.name, "--format", "json"])
        os.unlink(f.name)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) >= 1
        assert data[0]["count"] >= 2

    def test_fingerprint_no_duplicates(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT 1; DELETE FROM t;")
            f.flush()
            result = main(["fingerprint", f.name])
        os.unlink(f.name)
        assert result == 0


class TestPatternsIntegration:
    def test_patterns_command(self):
        result = main(["patterns"])
        assert result == 0

    def test_rules_command(self):
        result = main(["rules"])
        assert result == 0


class TestEndToEnd:
    def test_complex_real_world_query(self, capsys):
        sql = """
        SELECT u.id, u.name, COUNT(o.id) as order_count,
               SUM(o.total) as total_spent
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        LEFT JOIN order_items oi ON o.id = oi.order_id
        WHERE u.status = 'active'
        AND u.created_at > '2024-01-01'
        GROUP BY u.id, u.name
        HAVING COUNT(o.id) > 5
        ORDER BY total_spent DESC
        LIMIT 100
        """
        result = main(["analyze", "--format", "json",
                       "--suggest-indexes", "--complexity", sql])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "score" in data
        assert "complexity" in data
        assert data["complexity"]["level"] in ("medium", "high", "very high")

    def test_problematic_query(self, capsys):
        sql = "SELECT * FROM users, orders WHERE UPPER(users.name) LIKE '%test%' AND orders.total != 0"
        result = main(["analyze", "--format", "json", sql])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["score"] < 70  # Should have many findings
        assert data["summary"]["total"] >= 3


class TestCrossModuleIntegration:
    """Integration tests that exercise multiple modules together."""

    def test_analyze_then_fingerprint_then_diff(self):
        """Full pipeline: analyze -> fingerprint -> diff two query versions."""
        from sqlink.analyzer import QueryAnalyzer
        from sqlink.fingerprint import fingerprint, normalize_for_fingerprint
        from sqlink.diff import diff_queries
        from sqlink.rewriter import suggest_rewrites
        from sqlink.parser import parse_query
        from sqlink.complexity import calculate_complexity

        # 1. Start with a problematic query
        bad_sql = "SELECT * FROM orders WHERE UPPER(customer_name) LIKE '%smith%'"
        analyzer = QueryAnalyzer()
        result = analyzer.analyze(bad_sql)
        assert result.score < 100
        assert any(f.rule_id == "SQ001" for f in result.findings)  # SELECT *
        assert any(f.rule_id == "WH001" for f in result.findings)  # function on column

        # 2. Generate a rewrite suggestion
        parsed = parse_query(bad_sql)
        rewrites = suggest_rewrites(parsed)
        assert len(rewrites) > 0  # at least SELECT * rewrite

        # 3. Create an improved version and diff them
        good_sql = "SELECT id, customer_name, total FROM orders WHERE customer_name ILIKE 'smith%' LIMIT 100"
        diff = diff_queries(bad_sql, good_sql)
        assert diff.has_changes
        assert any("SELECT *" in c for c in diff.structural_changes)
        assert any("LIMIT" in c for c in diff.structural_changes)

        # 4. Verify improved query scores better
        good_result = analyzer.analyze(good_sql)
        assert good_result.score > result.score

        # 5. Fingerprints should be different for structurally different queries
        fp_bad = fingerprint(bad_sql)
        fp_good = fingerprint(good_sql)
        assert fp_bad != fp_good

        # 6. Complexity should differ
        bad_complexity = calculate_complexity(parse_query(bad_sql))
        good_complexity = calculate_complexity(parse_query(good_sql))
        assert bad_complexity.total >= 1
        assert good_complexity.total >= 1

    def test_cost_estimator_with_schema_and_index_advisor(self):
        """Cost estimation with schema context integrated with index advisor."""
        from sqlink.parser import parse_query
        from sqlink.cost_estimator import estimate_cost
        from sqlink.index_advisor import suggest_indexes
        from sqlink.statistics import SchemaContext, TableStats, ColumnStats
        from sqlink.analyzer import QueryAnalyzer
        from sqlink.complexity import calculate_complexity

        sql = """
        SELECT u.id, u.name, o.total
        FROM users u
        JOIN orders o ON u.id = o.user_id
        WHERE u.status = 'active' AND o.created_at > '2024-01-01'
        ORDER BY o.total DESC
        LIMIT 50
        """
        parsed = parse_query(sql)

        # Set up schema context with table stats
        schema = SchemaContext()
        users_table = TableStats(
            name="users",
            row_count=100000,
            columns={
                "id": ColumnStats(name="id", has_index=True, is_primary_key=True, distinct_count=100000),
                "name": ColumnStats(name="name", distinct_count=80000),
                "status": ColumnStats(name="status", distinct_count=5, has_index=True),
            },
        )
        orders_table = TableStats(
            name="orders",
            row_count=500000,
            columns={
                "id": ColumnStats(name="id", has_index=True, is_primary_key=True, distinct_count=500000),
                "user_id": ColumnStats(name="user_id", has_index=True, distinct_count=100000),
                "total": ColumnStats(name="total", distinct_count=10000),
                "created_at": ColumnStats(name="created_at", distinct_count=365),
            },
        )
        schema.add_table(users_table)
        schema.add_table(orders_table)

        # Cost without schema vs with schema should differ
        cost_no_schema = estimate_cost(parsed)
        cost_with_schema = estimate_cost(parsed, schema=schema)
        assert cost_no_schema.total > 0
        assert cost_with_schema.total > 0
        # With schema (has indexes), cost structure should differ
        assert cost_no_schema.total != cost_with_schema.total

        # Index advisor should suggest indexes
        suggestions = suggest_indexes(parsed)
        assert len(suggestions) > 0
        # Should suggest index on join or where columns
        all_suggested_cols = [col for s in suggestions for col in s.columns]
        assert any(c in all_suggested_cols for c in ["status", "user_id", "created_at", "total"])

        # Analyze the query with the analyzer
        analyzer = QueryAnalyzer()
        analysis = analyzer.analyze(sql)
        assert analysis.score > 0

        # Complexity check
        complexity = calculate_complexity(parsed)
        assert complexity.level in ("medium", "high", "very high")
        assert complexity.join_score > 0  # has a join

    def test_log_parser_to_batch_analysis_pipeline(self):
        """Parse a slow query log and feed results into batch analysis."""
        from sqlink.log_parser import parse_postgresql_log, summarize_log
        from sqlink.analyzer import QueryAnalyzer
        from sqlink.fingerprint import find_duplicates
        from sqlink.sanitizer import sanitize

        log_content = (
            "duration: 500.123 ms  statement: SELECT * FROM users WHERE id = 1\n\n"
            "duration: 750.456 ms  statement: SELECT * FROM users WHERE id = 2\n\n"
            "duration: 300.789 ms  statement: SELECT * FROM users WHERE id = 3\n\n"
            "duration: 1200.012 ms  statement: SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id WHERE u.status = 'active'\n\n"
        )
        # 1. Parse the log
        entries = parse_postgresql_log(log_content)
        assert len(entries) >= 3

        # 2. Summarize
        summary = summarize_log(entries)
        assert summary.total_entries >= 3
        assert summary.total_duration_ms > 0
        assert len(summary.slowest_queries) > 0

        # 3. Extract queries and run batch analysis
        queries = [e.query for e in entries]
        analyzer = QueryAnalyzer()
        results = analyzer.analyze_batch(queries)
        assert len(results) == len(queries)

        # 4. Check for N+1 pattern (3 similar SELECT * FROM users WHERE id = ?)
        all_findings = []
        for r in results:
            all_findings.extend(r.findings)
        n1_findings = [f for f in all_findings if f.rule_id == "NP001"]
        assert len(n1_findings) > 0, "Should detect N+1 pattern in repeated queries"

        # 5. Fingerprint the queries to find duplicates
        dups = find_duplicates(queries)
        assert len(dups) > 0
        assert dups[0]["count"] >= 3

        # 6. Sanitize a query for safe logging
        sanitized = sanitize(queries[0])
        assert "1" not in sanitized or "?" in sanitized

    def test_file_analyzer_to_formatter_pipeline(self):
        """Parse SQL file, analyze, format, and sanitize."""
        from sqlink.file_analyzer import split_sql_file, analyze_sql_content
        from sqlink.formatter import format_sql, compact
        from sqlink.sanitizer import sanitize, detect_sensitive_patterns

        sql_content = """
        -- User lookup query
        SELECT * FROM users WHERE email = 'admin@company.com';

        /* Order summary */
        SELECT u.name, COUNT(o.id) as order_count
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        GROUP BY u.name
        ORDER BY order_count DESC
        LIMIT 10;
        """

        # 1. Split the file
        queries = split_sql_file(sql_content)
        assert len(queries) == 2

        # 2. Analyze all queries
        results = analyze_sql_content(sql_content)
        assert len(results) == 2
        # First query has SELECT * so should have findings
        assert results[0].has_issues

        # 3. Format each query
        for q in queries:
            formatted = format_sql(q)
            assert "SELECT" in formatted
            # Compact should produce single-line
            compacted = compact(q)
            assert "\n" not in compacted

        # 4. Detect sensitive patterns
        warnings = detect_sensitive_patterns(queries[0])
        assert any("Email" in w for w in warnings)

        # 5. Sanitize
        sanitized = sanitize(queries[0])
        assert "admin@company.com" not in sanitized
