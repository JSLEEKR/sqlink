"""Tests for CLI module."""

import os
import tempfile
import pytest
from sqlink.cli import create_parser, main, _read_queries_from_file


class TestCreateParser:
    def test_creates_parser(self):
        parser = create_parser()
        assert parser.prog == "sqlink"

    def test_analyze_command(self):
        parser = create_parser()
        args = parser.parse_args(["analyze", "SELECT * FROM t"])
        assert args.command == "analyze"
        assert args.query == "SELECT * FROM t"

    def test_rules_command(self):
        parser = create_parser()
        args = parser.parse_args(["rules"])
        assert args.command == "rules"

    def test_batch_command(self):
        parser = create_parser()
        args = parser.parse_args(["batch", "queries.sql"])
        assert args.command == "batch"
        assert args.file == "queries.sql"

    def test_format_option(self):
        parser = create_parser()
        args = parser.parse_args(["analyze", "--format", "json", "SELECT 1"])
        assert args.format == "json"

    def test_no_color_option(self):
        parser = create_parser()
        args = parser.parse_args(["analyze", "--no-color", "SELECT 1"])
        assert args.no_color is True

    def test_disable_rules(self):
        parser = create_parser()
        args = parser.parse_args(["analyze", "--disable-rules", "SQ001", "SD001", "--", "SELECT 1"])
        assert args.disable_rules == ["SQ001", "SD001"]


class TestReadQueriesFromFile:
    def test_semicolon_separated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT 1; SELECT 2; SELECT 3;")
            f.flush()
            queries = _read_queries_from_file(f.name)
        os.unlink(f.name)
        assert len(queries) == 3

    def test_newline_separated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT 1\n\nSELECT 2\n\nSELECT 3")
            f.flush()
            queries = _read_queries_from_file(f.name)
        os.unlink(f.name)
        assert len(queries) == 3

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("")
            f.flush()
            queries = _read_queries_from_file(f.name)
        os.unlink(f.name)
        assert len(queries) == 0


class TestMain:
    def test_no_command(self):
        assert main([]) == 0

    def test_rules(self):
        assert main(["rules"]) == 0

    def test_analyze_query(self):
        result = main(["analyze", "--no-color", "SELECT id FROM users WHERE id = 1 LIMIT 1"])
        assert result == 0

    def test_analyze_json(self):
        result = main(["analyze", "--format", "json", "SELECT id FROM users WHERE id = 1 LIMIT 1"])
        assert result == 0

    def test_analyze_no_query(self):
        result = main(["analyze"])
        assert result == 1

    def test_analyze_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT id FROM users WHERE id = 1 LIMIT 1")
            f.flush()
            result = main(["analyze", "--file", f.name, "--no-color"])
        os.unlink(f.name)
        assert result == 0

    def test_batch_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT id FROM users LIMIT 1; SELECT id FROM orders LIMIT 1;")
            f.flush()
            result = main(["batch", f.name, "--no-color"])
        os.unlink(f.name)
        assert result == 0

    def test_batch_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT id FROM users LIMIT 1; SELECT id FROM orders LIMIT 1;")
            f.flush()
            result = main(["batch", f.name, "--format", "json"])
        os.unlink(f.name)
        assert result == 0

    def test_analyze_with_explain_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as qf:
            qf.write("SELECT * FROM users")
            qf.flush()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as ef:
            ef.write("Seq Scan on users  (cost=0.00..100.00 rows=5000 width=100)")
            ef.flush()
        result = main(["analyze", "--file", qf.name, "--explain", ef.name, "--no-color"])
        os.unlink(qf.name)
        os.unlink(ef.name)
        # May return 1 due to low score, but shouldn't crash
        assert result in (0, 1)

    def test_disable_rules(self):
        result = main(["analyze", "--disable-rules", "SQ001", "SD001", "--no-color", "SELECT * FROM users LIMIT 10"])
        assert result == 0
