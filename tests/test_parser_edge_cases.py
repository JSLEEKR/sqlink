"""Edge case tests for the SQL parser."""

import pytest
from sqlink.parser import (
    parse_query,
    extract_tables,
    extract_joins,
    extract_where,
    extract_columns,
    normalize_sql,
    detect_query_type,
    extract_subqueries,
)
from sqlink.models import QueryType, JoinType


class TestParserEdgeCases:
    def test_deeply_nested_subquery(self):
        sql = "SELECT * FROM t WHERE id IN (SELECT id FROM t2 WHERE x IN (SELECT x FROM t3))"
        q = parse_query(sql)
        assert len(q.subqueries) >= 1

    def test_cte_like_pattern(self):
        # CTE/WITH not fully supported, but shouldn't crash
        sql = "WITH cte AS (SELECT 1) SELECT * FROM cte"
        q = parse_query(sql)
        assert q is not None

    def test_multiline_query(self):
        sql = """
        SELECT
            id,
            name,
            email
        FROM
            users
        WHERE
            status = 'active'
        ORDER BY
            name
        LIMIT 10
        """
        q = parse_query(sql)
        assert q.query_type == QueryType.SELECT
        assert q.has_order_by
        assert q.has_limit

    def test_mixed_case_keywords(self):
        sql = "sElEcT * FrOm UsErS wHeRe Id = 1"
        q = parse_query(sql)
        assert q.query_type == QueryType.SELECT
        assert len(q.tables) >= 1

    def test_backtick_quoted_identifiers(self):
        sql = "SELECT * FROM `my table` WHERE `my column` = 1"
        q = parse_query(sql)
        assert len(q.tables) >= 1

    def test_empty_query(self):
        q = parse_query("")
        assert q.query_type == QueryType.UNKNOWN
        assert q.raw == ""

    def test_whitespace_only(self):
        q = parse_query("   \n\t  ")
        assert q.query_type == QueryType.UNKNOWN

    def test_multiple_where_or(self):
        sql = "SELECT * FROM t WHERE a = 1 OR b = 2 OR c = 3"
        q = parse_query(sql)
        assert len(q.where_conditions) >= 1
        assert any(c.has_or for c in q.where_conditions)

    def test_between_condition(self):
        sql = "SELECT * FROM t WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31'"
        q = parse_query(sql)
        assert len(q.where_conditions) >= 1

    def test_exists_subquery(self):
        sql = "SELECT * FROM t WHERE EXISTS (SELECT 1 FROM t2 WHERE t2.id = t.id)"
        q = parse_query(sql)
        assert len(q.subqueries) >= 1

    def test_case_expression(self):
        sql = "SELECT CASE WHEN status = 'a' THEN 1 ELSE 0 END FROM t"
        q = parse_query(sql)
        assert q.query_type == QueryType.SELECT

    def test_aggregate_functions(self):
        sql = "SELECT COUNT(*), SUM(total), AVG(price), MIN(id), MAX(id) FROM orders"
        q = parse_query(sql)
        assert q.query_type == QueryType.SELECT

    def test_insert_with_select(self):
        sql = "INSERT INTO t2 SELECT * FROM t1 WHERE id > 100"
        q = parse_query(sql)
        assert q.query_type == QueryType.INSERT

    def test_update_with_join(self):
        sql = "UPDATE users SET status = 'inactive' WHERE id IN (SELECT user_id FROM banned)"
        q = parse_query(sql)
        assert q.query_type == QueryType.UPDATE
        assert len(q.where_conditions) >= 1

    def test_delete_with_conditions(self):
        sql = "DELETE FROM logs WHERE created_at < '2023-01-01' AND level = 'debug'"
        q = parse_query(sql)
        assert q.query_type == QueryType.DELETE
        assert len(q.where_conditions) >= 2

    def test_left_outer_join(self):
        joins = extract_joins("SELECT * FROM a LEFT OUTER JOIN b ON a.id = b.a_id")
        assert len(joins) >= 1
        assert joins[0].join_type == JoinType.LEFT

    def test_natural_join(self):
        joins = extract_joins("SELECT * FROM a NATURAL JOIN b")
        assert len(joins) >= 1

    def test_self_join(self):
        sql = "SELECT a.name, b.name FROM employees a JOIN employees b ON a.manager_id = b.id"
        q = parse_query(sql)
        assert len(q.joins) >= 1

    def test_cross_join_explicit(self):
        joins = extract_joins("SELECT * FROM a CROSS JOIN b")
        assert len(joins) >= 1
        assert joins[0].join_type == JoinType.CROSS

    def test_column_alias(self):
        cols, _ = extract_columns("SELECT id AS user_id, name AS user_name FROM t")
        assert len(cols) >= 1

    def test_count_star_column(self):
        cols, has_star = extract_columns("SELECT COUNT(*) FROM t")
        # COUNT(*) has a star inside function, should not be treated as SELECT *
        # This is a known limitation but shouldn't crash

    def test_table_with_dots_in_schema(self):
        tables = extract_tables("SELECT * FROM catalog.schema_name.table_name")
        assert len(tables) >= 1

    def test_where_with_not_in(self):
        conds = extract_where("SELECT * FROM t WHERE id NOT IN (1, 2, 3)")
        assert len(conds) >= 1

    def test_order_by_desc(self):
        q = parse_query("SELECT * FROM t ORDER BY name DESC, id ASC")
        assert q.has_order_by
        assert len(q.order_by_columns) >= 1

    def test_group_by_multiple(self):
        q = parse_query("SELECT a, b, COUNT(*) FROM t GROUP BY a, b")
        assert q.has_group_by
        assert len(q.group_by_columns) >= 2

    def test_having_with_group(self):
        q = parse_query("SELECT status, COUNT(*) FROM t GROUP BY status HAVING COUNT(*) > 5")
        assert q.has_group_by
        assert q.has_having

    def test_union_all(self):
        q = parse_query("SELECT id FROM a UNION ALL SELECT id FROM b")
        assert q.has_union
