"""Tests for SQL parser."""

import pytest
from sqlink.parser import (
    detect_query_type,
    extract_columns,
    extract_joins,
    extract_subqueries,
    extract_tables,
    extract_where,
    normalize_sql,
    parse_query,
)
from sqlink.models import JoinType, QueryType


class TestNormalizeSql:
    def test_strips_whitespace(self):
        assert normalize_sql("  SELECT 1  ") == "SELECT 1"

    def test_removes_trailing_semicolon(self):
        assert normalize_sql("SELECT 1;") == "SELECT 1"

    def test_collapses_whitespace(self):
        assert normalize_sql("SELECT\n  1\n  FROM\n  t") == "SELECT 1 FROM t"

    def test_empty(self):
        assert normalize_sql("") == ""


class TestDetectQueryType:
    def test_select(self):
        assert detect_query_type("SELECT * FROM t") == QueryType.SELECT

    def test_insert(self):
        assert detect_query_type("INSERT INTO t VALUES (1)") == QueryType.INSERT

    def test_update(self):
        assert detect_query_type("UPDATE t SET x=1") == QueryType.UPDATE

    def test_delete(self):
        assert detect_query_type("DELETE FROM t") == QueryType.DELETE

    def test_create(self):
        assert detect_query_type("CREATE TABLE t (id INT)") == QueryType.CREATE

    def test_alter(self):
        assert detect_query_type("ALTER TABLE t ADD col INT") == QueryType.ALTER

    def test_drop(self):
        assert detect_query_type("DROP TABLE t") == QueryType.DROP

    def test_unknown(self):
        assert detect_query_type("EXPLAIN SELECT 1") == QueryType.UNKNOWN

    def test_case_insensitive(self):
        assert detect_query_type("select * from t") == QueryType.SELECT


class TestExtractTables:
    def test_single_table(self):
        tables = extract_tables("SELECT * FROM users")
        assert len(tables) == 1
        assert tables[0].name == "users"

    def test_multiple_tables(self):
        tables = extract_tables("SELECT * FROM users, orders")
        assert len(tables) == 2

    def test_table_with_alias(self):
        tables = extract_tables("SELECT * FROM users u")
        assert len(tables) == 1
        assert tables[0].name == "users"
        assert tables[0].alias == "u"

    def test_table_with_as_alias(self):
        tables = extract_tables("SELECT * FROM users AS u")
        assert len(tables) == 1
        assert tables[0].alias == "u"

    def test_schema_qualified(self):
        tables = extract_tables("SELECT * FROM public.users")
        assert tables[0].schema == "public"
        assert tables[0].name == "users"

    def test_insert_table(self):
        tables = extract_tables("INSERT INTO users (name) VALUES ('x')")
        assert tables[0].name == "users"

    def test_update_table(self):
        tables = extract_tables("UPDATE users SET name='x'")
        assert tables[0].name == "users"

    def test_delete_table(self):
        tables = extract_tables("DELETE FROM users WHERE id=1")
        assert tables[0].name == "users"

    def test_from_with_where(self):
        tables = extract_tables("SELECT * FROM users WHERE id = 1")
        assert len(tables) == 1
        assert tables[0].name == "users"


class TestExtractJoins:
    def test_inner_join(self):
        joins = extract_joins("SELECT * FROM a INNER JOIN b ON a.id = b.a_id")
        assert len(joins) == 1
        assert joins[0].join_type == JoinType.INNER
        assert joins[0].table.name == "b"

    def test_left_join(self):
        joins = extract_joins("SELECT * FROM a LEFT JOIN b ON a.id = b.a_id")
        assert len(joins) == 1
        assert joins[0].join_type == JoinType.LEFT

    def test_right_join(self):
        joins = extract_joins("SELECT * FROM a RIGHT JOIN b ON a.id = b.a_id")
        assert joins[0].join_type == JoinType.RIGHT

    def test_multiple_joins(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.a_id JOIN c ON b.id = c.b_id"
        joins = extract_joins(sql)
        assert len(joins) == 2

    def test_join_with_alias(self):
        joins = extract_joins("SELECT * FROM a JOIN b AS bb ON a.id = bb.a_id")
        assert joins[0].table.name == "b"

    def test_cross_join(self):
        joins = extract_joins("SELECT * FROM a CROSS JOIN b")
        assert joins[0].join_type == JoinType.CROSS


class TestExtractColumns:
    def test_select_star(self):
        cols, has_star = extract_columns("SELECT * FROM t")
        assert has_star

    def test_specific_columns(self):
        cols, has_star = extract_columns("SELECT id, name FROM t")
        assert not has_star
        assert len(cols) == 2
        assert cols[0].name == "id"
        assert cols[1].name == "name"

    def test_table_qualified(self):
        cols, _ = extract_columns("SELECT u.id, u.name FROM users u")
        assert cols[0].table == "u"
        assert cols[0].name == "id"

    def test_with_alias(self):
        cols, _ = extract_columns("SELECT id AS user_id FROM t")
        assert len(cols) >= 1


class TestExtractWhere:
    def test_simple_where(self):
        conds = extract_where("SELECT * FROM t WHERE id = 1")
        assert len(conds) == 1
        assert "id = 1" in conds[0].raw

    def test_and_conditions(self):
        conds = extract_where("SELECT * FROM t WHERE id = 1 AND name = 'x'")
        assert len(conds) == 2

    def test_function_detection(self):
        conds = extract_where("SELECT * FROM t WHERE UPPER(name) = 'X'")
        assert conds[0].has_function

    def test_like_wildcard(self):
        conds = extract_where("SELECT * FROM t WHERE name LIKE '%test'")
        assert conds[0].has_like_wildcard_prefix

    def test_or_detection(self):
        conds = extract_where("SELECT * FROM t WHERE a = 1 OR b = 2")
        assert conds[0].has_or

    def test_not_equal(self):
        conds = extract_where("SELECT * FROM t WHERE status != 'active'")
        assert conds[0].has_not_equal

    def test_is_null(self):
        conds = extract_where("SELECT * FROM t WHERE deleted_at IS NULL")
        assert conds[0].has_is_null

    def test_in_subquery(self):
        conds = extract_where("SELECT * FROM t WHERE id IN (SELECT id FROM t2)")
        assert conds[0].has_in_subquery

    def test_no_where(self):
        conds = extract_where("SELECT * FROM t")
        assert len(conds) == 0


class TestExtractSubqueries:
    def test_in_where(self):
        subs = extract_subqueries("SELECT * FROM t WHERE id IN (SELECT id FROM t2)")
        assert len(subs) >= 1

    def test_no_subquery(self):
        subs = extract_subqueries("SELECT * FROM t WHERE id = 1")
        assert len(subs) == 0


class TestParseQuery:
    def test_basic_select(self):
        q = parse_query("SELECT id, name FROM users WHERE id = 1")
        assert q.query_type == QueryType.SELECT
        assert len(q.tables) == 1
        assert not q.has_select_star

    def test_select_star(self):
        q = parse_query("SELECT * FROM users")
        assert q.has_select_star

    def test_distinct(self):
        q = parse_query("SELECT DISTINCT name FROM users")
        assert q.has_distinct

    def test_group_by(self):
        q = parse_query("SELECT status, COUNT(*) FROM orders GROUP BY status")
        assert q.has_group_by

    def test_order_by(self):
        q = parse_query("SELECT * FROM users ORDER BY name")
        assert q.has_order_by

    def test_limit(self):
        q = parse_query("SELECT * FROM users LIMIT 10")
        assert q.has_limit

    def test_offset(self):
        q = parse_query("SELECT * FROM users LIMIT 10 OFFSET 20")
        assert q.has_offset

    def test_having(self):
        q = parse_query("SELECT status, COUNT(*) FROM orders GROUP BY status HAVING COUNT(*) > 5")
        assert q.has_having

    def test_union(self):
        q = parse_query("SELECT id FROM a UNION SELECT id FROM b")
        assert q.has_union

    def test_complex_query(self):
        sql = """
        SELECT u.id, u.name, o.total
        FROM users u
        INNER JOIN orders o ON u.id = o.user_id
        LEFT JOIN products p ON o.product_id = p.id
        WHERE u.status = 'active'
        AND o.created_at > '2024-01-01'
        GROUP BY u.id, u.name, o.total
        ORDER BY o.total DESC
        LIMIT 10
        """
        q = parse_query(sql)
        assert q.query_type == QueryType.SELECT
        assert q.has_group_by
        assert q.has_order_by
        assert q.has_limit
        assert len(q.joins) >= 1
