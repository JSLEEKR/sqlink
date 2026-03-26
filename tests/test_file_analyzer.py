"""Tests for file_analyzer module."""

import os
import tempfile
import pytest
from sqlink.file_analyzer import analyze_file, analyze_sql_content, split_sql_file


class TestSplitSqlFile:
    def test_semicolon_separated(self):
        content = "SELECT 1; SELECT 2; SELECT 3;"
        queries = split_sql_file(content)
        assert len(queries) == 3
        assert queries[0] == "SELECT 1"

    def test_no_trailing_semicolon(self):
        content = "SELECT 1; SELECT 2"
        queries = split_sql_file(content)
        assert len(queries) == 2

    def test_single_query(self):
        content = "SELECT * FROM users"
        queries = split_sql_file(content)
        assert len(queries) == 1

    def test_empty_content(self):
        assert split_sql_file("") == []

    def test_whitespace_only(self):
        assert split_sql_file("   \n\n  ") == []

    def test_line_comments(self):
        content = "-- This is a comment\nSELECT 1;\n-- Another comment\nSELECT 2;"
        queries = split_sql_file(content)
        assert len(queries) == 2
        assert "comment" not in queries[0]

    def test_block_comments(self):
        content = "/* block comment */ SELECT 1; SELECT /* inline */ 2;"
        queries = split_sql_file(content)
        assert len(queries) == 2

    def test_multiline_block_comment(self):
        content = """
        /*
         * Multi-line
         * comment
         */
        SELECT 1;
        """
        queries = split_sql_file(content)
        assert len(queries) == 1

    def test_semicolon_in_string(self):
        content = "SELECT 'hello; world' FROM t;"
        queries = split_sql_file(content)
        assert len(queries) == 1
        assert "hello; world" in queries[0]

    def test_semicolon_in_double_quoted_string(self):
        content = 'SELECT "col;name" FROM t;'
        queries = split_sql_file(content)
        assert len(queries) == 1

    def test_complex_mixed(self):
        content = """
        -- Create table
        CREATE TABLE users (
            id INT PRIMARY KEY,
            name VARCHAR(100) -- inline comment
        );

        /* Insert some data */
        INSERT INTO users VALUES (1, 'John;Doe');
        INSERT INTO users VALUES (2, 'Jane');

        SELECT * FROM users;
        """
        queries = split_sql_file(content)
        assert len(queries) == 4

    def test_multiple_semicolons(self):
        content = "SELECT 1;;; SELECT 2;"
        queries = split_sql_file(content)
        assert len(queries) == 2

    def test_dash_not_comment(self):
        content = "SELECT a - b FROM t;"
        queries = split_sql_file(content)
        assert len(queries) == 1
        assert "a - b" in queries[0]


class TestAnalyzeFile:
    def test_analyze_simple_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT * FROM users;\nSELECT id FROM orders LIMIT 10;")
            f.flush()
            results = analyze_file(f.name)
        os.unlink(f.name)
        assert len(results) == 2

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            analyze_file("/nonexistent/path/file.sql")

    def test_not_a_file(self):
        with pytest.raises(ValueError):
            analyze_file(tempfile.gettempdir())

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("")
            f.flush()
            results = analyze_file(f.name)
        os.unlink(f.name)
        assert len(results) == 0


class TestAnalyzeSqlContent:
    def test_basic(self):
        results = analyze_sql_content("SELECT * FROM users; SELECT id FROM orders LIMIT 10;")
        assert len(results) == 2

    def test_empty(self):
        results = analyze_sql_content("")
        assert len(results) == 0

    def test_with_custom_analyzer(self):
        from sqlink.analyzer import QueryAnalyzer
        analyzer = QueryAnalyzer(disabled_rules={"SQ001"})
        results = analyze_sql_content("SELECT * FROM users;", analyzer=analyzer)
        assert len(results) == 1
        rule_ids = [f.rule_id for f in results[0].findings]
        assert "SQ001" not in rule_ids

    def test_n_plus_one_detection(self):
        content = """
        SELECT * FROM orders WHERE user_id = 1;
        SELECT * FROM orders WHERE user_id = 2;
        SELECT * FROM orders WHERE user_id = 3;
        SELECT * FROM orders WHERE user_id = 4;
        """
        results = analyze_sql_content(content)
        all_rules = []
        for r in results:
            all_rules.extend(f.rule_id for f in r.findings)
        assert "NP001" in all_rules
