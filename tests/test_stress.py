"""Stress tests — verify performance and correctness under heavy load."""

import time
import pytest
from sqlink.analyzer import QueryAnalyzer
from sqlink.parser import parse_query
from sqlink.fingerprint import fingerprint, find_duplicates, group_by_fingerprint
from sqlink.complexity import calculate_complexity
from sqlink.cost_estimator import estimate_cost
from sqlink.index_advisor import suggest_indexes
from sqlink.rewriter import suggest_rewrites
from sqlink.sanitizer import sanitize
from sqlink.formatter import format_sql
from sqlink.diff import diff_queries
from sqlink.file_analyzer import split_sql_file
from sqlink.patterns import match_patterns
from sqlink.statistics import SchemaContext, TableStats, ColumnStats


class TestLargeQueryStress:
    """Stress tests with large or complex queries."""

    def test_query_with_many_joins(self):
        """Analyze a query with 20 JOINs."""
        tables = [f"t{i}" for i in range(21)]
        joins = "\n".join(
            f"JOIN {tables[i]} ON {tables[i]}.id = {tables[i-1]}.{tables[i]}_id"
            for i in range(1, 21)
        )
        sql = f"SELECT * FROM {tables[0]}\n{joins}\nWHERE {tables[0]}.status = 'active'"

        analyzer = QueryAnalyzer(max_joins=5)
        start = time.perf_counter()
        result = analyzer.analyze(sql)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"Took {elapsed:.2f}s for 20-join query"
        assert result.score >= 0
        # Should flag too many joins (SQ006)
        assert any(f.rule_id == "SQ006" for f in result.findings)
        # Should flag SELECT * (SQ001)
        assert any(f.rule_id == "SQ001" for f in result.findings)

    def test_query_with_many_where_conditions(self):
        """Analyze a query with 50 WHERE conditions."""
        conditions = " AND ".join(
            f"col_{i} = {i}" for i in range(50)
        )
        sql = f"SELECT id FROM large_table WHERE {conditions} LIMIT 10"

        analyzer = QueryAnalyzer()
        start = time.perf_counter()
        result = analyzer.analyze(sql)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"Took {elapsed:.2f}s for 50-condition query"
        assert result.score >= 0

    def test_deeply_nested_subqueries(self):
        """Parse and analyze a query with nested subqueries."""
        sql = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE total > (SELECT AVG(total) FROM orders WHERE status IN (SELECT id FROM statuses WHERE name = 'active')))"

        analyzer = QueryAnalyzer()
        start = time.perf_counter()
        result = analyzer.analyze(sql)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0
        assert result.score >= 0

    def test_very_long_query_string(self):
        """Analyze a query that is 10KB+ long."""
        # Build a long IN list
        values = ", ".join(f"'{i:06d}'" for i in range(500))
        sql = f"SELECT id, name FROM users WHERE code IN ({values}) LIMIT 100"
        assert len(sql) > 5000

        analyzer = QueryAnalyzer()
        start = time.perf_counter()
        result = analyzer.analyze(sql)
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0, f"Took {elapsed:.2f}s for {len(sql)}-byte query"
        assert result.score >= 0

    def test_many_columns_select(self):
        """Analyze a SELECT with 100 columns."""
        cols = ", ".join(f"col_{i}" for i in range(100))
        sql = f"SELECT {cols} FROM wide_table WHERE id = 1 LIMIT 1"

        parsed = parse_query(sql)
        assert len(parsed.columns) >= 50  # parser should capture many

        analyzer = QueryAnalyzer()
        result = analyzer.analyze(sql)
        assert result.score >= 0


class TestBatchStress:
    """Stress tests with large batches of queries."""

    def test_batch_1000_queries(self):
        """Analyze a batch of 1000 queries."""
        queries = [
            f"SELECT * FROM users WHERE id = {i}"
            for i in range(1000)
        ]

        analyzer = QueryAnalyzer()
        start = time.perf_counter()
        results = analyzer.analyze_batch(queries)
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0, f"Took {elapsed:.2f}s for 1000 queries"
        assert len(results) == 1000
        # Should detect N+1 pattern
        all_findings = []
        for r in results:
            all_findings.extend(r.findings)
        assert any(f.rule_id == "NP001" for f in all_findings)

    def test_fingerprint_1000_queries(self):
        """Fingerprint 1000 queries for duplicates."""
        queries = [
            f"SELECT * FROM users WHERE id = {i % 10}"
            for i in range(1000)
        ]

        start = time.perf_counter()
        dups = find_duplicates(queries)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"Took {elapsed:.2f}s for 1000 fingerprints"
        # All queries normalize to the same fingerprint
        assert len(dups) >= 1
        assert dups[0]["count"] == 1000

    def test_group_by_fingerprint_diverse(self):
        """Group 500 queries into fingerprint groups."""
        queries = []
        for i in range(100):
            queries.append(f"SELECT * FROM users WHERE id = {i}")
            queries.append(f"SELECT name FROM orders WHERE total > {i * 10}")
            queries.append(f"DELETE FROM logs WHERE created_at < '2024-01-{(i % 28) + 1:02d}'")
            queries.append(f"UPDATE users SET name = 'user_{i}' WHERE id = {i}")
            queries.append(f"INSERT INTO audit (action) VALUES ('action_{i}')")

        start = time.perf_counter()
        groups = group_by_fingerprint(queries)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0
        # Should have ~5 groups (one per template)
        assert len(groups) <= 10

    def test_split_large_sql_file(self):
        """Split a SQL file with 500 statements."""
        statements = [
            f"SELECT col_{i} FROM table_{i % 10} WHERE id = {i}"
            for i in range(500)
        ]
        content = ";\n".join(statements) + ";"

        start = time.perf_counter()
        result = split_sql_file(content)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"Took {elapsed:.2f}s for 500 statements"
        assert len(result) == 500


class TestCostEstimatorStress:
    """Stress tests for the cost estimator with large schemas."""

    def test_cost_with_large_schema(self):
        """Estimate cost with schema containing 50 tables."""
        schema = SchemaContext()
        for i in range(50):
            cols = {}
            for j in range(20):
                cols[f"col_{j}"] = ColumnStats(
                    name=f"col_{j}",
                    has_index=(j < 3),
                    distinct_count=1000 * (j + 1),
                )
            schema.add_table(TableStats(
                name=f"table_{i}",
                row_count=10000 * (i + 1),
                columns=cols,
            ))

        sql = """
        SELECT t.col_0, t.col_1
        FROM table_0 t
        JOIN table_1 t1 ON t.col_0 = t1.col_0
        JOIN table_2 t2 ON t1.col_0 = t2.col_0
        WHERE t.col_5 = 'test'
        ORDER BY t.col_1
        LIMIT 100
        """
        parsed = parse_query(sql)

        start = time.perf_counter()
        cost = estimate_cost(parsed, schema=schema)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0
        assert cost.total > 0
        assert cost.scan_cost > 0
        assert cost.join_cost > 0

    def test_index_advisor_complex_query(self):
        """Index advisor on a query touching many tables."""
        tables = ["users", "orders", "products", "categories", "reviews"]
        sql = """
        SELECT u.name, o.total, p.title, c.name, r.rating
        FROM users u
        JOIN orders o ON u.id = o.user_id
        JOIN products p ON o.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        LEFT JOIN reviews r ON p.id = r.product_id
        WHERE u.status = 'active'
        AND o.created_at > '2024-01-01'
        AND p.price > 100
        GROUP BY u.name, o.total, p.title, c.name, r.rating
        ORDER BY o.total DESC
        LIMIT 50
        """
        parsed = parse_query(sql)

        start = time.perf_counter()
        suggestions = suggest_indexes(parsed)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0
        assert len(suggestions) > 0
        # Should suggest indexes on join columns and where columns
        suggested_tables = {s.table for s in suggestions}
        assert len(suggested_tables) >= 2


class TestFormatterStress:
    """Stress tests for the SQL formatter."""

    def test_format_very_long_query(self):
        """Format a query with many clauses."""
        cols = ", ".join(f"t.col_{i}" for i in range(50))
        conditions = " AND ".join(f"t.col_{i} > {i}" for i in range(20))
        sql = f"SELECT {cols} FROM big_table t WHERE {conditions} ORDER BY t.col_0 LIMIT 100"

        start = time.perf_counter()
        formatted = format_sql(sql)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0
        assert "SELECT" in formatted
        assert "\n" in formatted  # Should be multi-line

    def test_sanitize_batch_1000(self):
        """Sanitize 1000 queries."""
        queries = [
            f"SELECT * FROM users WHERE email = 'user{i}@example.com' AND id = {i}"
            for i in range(1000)
        ]

        start = time.perf_counter()
        sanitized = [sanitize(q) for q in queries]
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0
        for s in sanitized:
            assert "example.com" not in s

    def test_diff_many_queries(self):
        """Diff 100 pairs of queries."""
        start = time.perf_counter()
        for i in range(100):
            q1 = f"SELECT col_{i} FROM table_{i} WHERE id = {i}"
            q2 = f"SELECT col_{i}, col_{i+1} FROM table_{i} JOIN table_{i+1} ON table_{i}.id = table_{i+1}.fk WHERE id = {i} LIMIT 10"
            diff = diff_queries(q1, q2)
            assert diff.has_changes
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0

    def test_pattern_matching_1000_queries(self):
        """Match patterns against 1000 queries."""
        queries = [
            f"SELECT COUNT(*) FROM users WHERE email = 'user{i}@test.com'"
            for i in range(1000)
        ]

        start = time.perf_counter()
        for q in queries:
            matches = match_patterns(q)
            assert len(matches) >= 1  # AP001 should match
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0


class TestComplexityStress:
    """Stress tests for complexity calculation."""

    def test_complexity_100_queries(self):
        """Calculate complexity for 100 diverse queries."""
        queries = [
            "SELECT * FROM t",
            "SELECT a FROM t WHERE x = 1 LIMIT 10",
            "SELECT a FROM t JOIN t2 ON t.id = t2.fk WHERE x > 1 ORDER BY a LIMIT 10",
            "SELECT DISTINCT a, b FROM t JOIN t2 ON t.id = t2.fk JOIN t3 ON t2.id = t3.fk WHERE x > 1 GROUP BY a, b HAVING COUNT(*) > 1 ORDER BY a LIMIT 10",
            "UPDATE t SET a = 1 WHERE id = 1",
        ]

        start = time.perf_counter()
        for _ in range(20):
            for sql in queries:
                parsed = parse_query(sql)
                comp = calculate_complexity(parsed)
                assert comp.total >= 1
                assert comp.level in ("low", "medium", "high", "very high")
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0

    def test_rewrite_suggestions_batch(self):
        """Generate rewrite suggestions for 200 queries."""
        queries = [
            f"SELECT * FROM table_{i} UNION SELECT * FROM table_{i+1}"
            for i in range(200)
        ]

        start = time.perf_counter()
        total_rewrites = 0
        for sql in queries:
            parsed = parse_query(sql)
            rewrites = suggest_rewrites(parsed)
            total_rewrites += len(rewrites)
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0
        assert total_rewrites > 0  # Should suggest UNION ALL and SELECT * fix
