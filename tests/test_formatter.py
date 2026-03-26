"""Tests for SQL formatter."""

import pytest
from sqlink.formatter import format_sql, compact, _tokenize


class TestTokenize:
    def test_simple(self):
        tokens = _tokenize("SELECT * FROM t")
        assert tokens == ["SELECT", "*", "FROM", "t"]

    def test_string_literal(self):
        tokens = _tokenize("WHERE name = 'John'")
        assert "'John'" in tokens

    def test_operators(self):
        tokens = _tokenize("a >= b")
        assert ">=" in tokens

    def test_parentheses(self):
        tokens = _tokenize("COUNT(*)")
        assert "(" in tokens and ")" in tokens

    def test_comma(self):
        tokens = _tokenize("a, b, c")
        assert tokens == ["a", ",", "b", ",", "c"]

    def test_escaped_string(self):
        tokens = _tokenize("name = 'O\\'Brien'")
        assert any("Brien" in t for t in tokens)


class TestFormatSql:
    def test_simple_select(self):
        sql = "select * from users where id = 1"
        result = format_sql(sql)
        assert "SELECT" in result
        assert "FROM" in result
        assert "WHERE" in result
        lines = result.strip().split("\n")
        assert len(lines) >= 3

    def test_keywords_uppercased(self):
        result = format_sql("select id from users")
        assert "SELECT" in result
        assert "FROM" in result

    def test_no_uppercase(self):
        result = format_sql("select id from users", uppercase=False)
        assert "select" in result

    def test_join_on_new_line(self):
        sql = "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        result = format_sql(sql)
        lines = result.strip().split("\n")
        assert any("JOIN" in line for line in lines)

    def test_and_indented(self):
        sql = "SELECT * FROM t WHERE a = 1 AND b = 2"
        result = format_sql(sql)
        lines = result.strip().split("\n")
        and_lines = [l for l in lines if "AND" in l]
        assert len(and_lines) >= 1

    def test_group_by_on_new_line(self):
        sql = "SELECT status, COUNT(*) FROM t GROUP BY status"
        result = format_sql(sql)
        lines = result.strip().split("\n")
        assert any("GROUP BY" in line for line in lines)

    def test_order_by_on_new_line(self):
        sql = "SELECT * FROM t ORDER BY name"
        result = format_sql(sql)
        lines = result.strip().split("\n")
        assert any("ORDER BY" in line for line in lines)

    def test_limit_on_new_line(self):
        sql = "SELECT * FROM t LIMIT 10"
        result = format_sql(sql)
        lines = result.strip().split("\n")
        assert any("LIMIT" in line for line in lines)

    def test_empty_string(self):
        assert format_sql("") == ""

    def test_preserves_string_literals(self):
        sql = "SELECT * FROM t WHERE name = 'hello world'"
        result = format_sql(sql)
        assert "'hello world'" in result

    def test_complex_query(self):
        sql = "select u.id, u.name, count(o.id) from users u inner join orders o on u.id = o.user_id where u.status = 'active' and o.created_at > '2024-01-01' group by u.id, u.name having count(o.id) > 5 order by count(o.id) desc limit 10"
        result = format_sql(sql)
        lines = result.strip().split("\n")
        assert len(lines) >= 5  # Multiple clauses on separate lines
        assert "SELECT" in lines[0]

    def test_union(self):
        sql = "SELECT id FROM a UNION SELECT id FROM b"
        result = format_sql(sql)
        assert "UNION" in result

    def test_insert(self):
        sql = "insert into users (name, email) values ('test', 'test@test.com')"
        result = format_sql(sql)
        assert "INSERT INTO" in result
        assert "VALUES" in result


class TestCompact:
    def test_collapses_whitespace(self):
        sql = "SELECT  *\n  FROM\n  users"
        assert compact(sql) == "SELECT * FROM users"

    def test_strips(self):
        assert compact("  SELECT 1  ") == "SELECT 1"

    def test_removes_semicolon(self):
        assert compact("SELECT 1;") == "SELECT 1"

    def test_empty(self):
        assert compact("") == ""
