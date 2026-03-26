"""Tests for EXPLAIN output parser."""

import json
import pytest
from sqlink.explain_parser import (
    detect_dialect,
    parse_explain,
    parse_mysql_json,
    parse_mysql_tabular,
    parse_postgresql_json,
    parse_postgresql_text,
)
from sqlink.models import ScanType


class TestDetectDialect:
    def test_postgresql_text(self):
        text = "Seq Scan on users  (cost=0.00..100.00 rows=1000 width=100)"
        assert detect_dialect(text) == "postgresql"

    def test_postgresql_json(self):
        data = [{"Plan": {"Node Type": "Seq Scan"}}]
        assert detect_dialect(json.dumps(data)) == "postgresql"

    def test_mysql_tabular(self):
        text = "| id | select_type | table | type | possible_keys | key | rows | Extra |\n| 1 | SIMPLE | users | ALL | NULL | NULL | 1000 | |"
        assert detect_dialect(text) == "mysql"

    def test_mysql_json(self):
        data = {"query_block": {"select_id": 1}}
        assert detect_dialect(json.dumps(data)) == "mysql"

    def test_unknown(self):
        assert detect_dialect("hello world") == "unknown"

    def test_postgresql_with_arrow(self):
        text = "->  Seq Scan on t  (cost=0.00..10.00 rows=100 width=4)"
        assert detect_dialect(text) == "postgresql"


class TestPostgresqlTextParser:
    def test_seq_scan(self):
        text = "Seq Scan on users  (cost=0.00..100.00 rows=5000 width=100)"
        result = parse_postgresql_text(text)
        assert len(result.nodes) == 1
        assert result.nodes[0].scan_type == ScanType.SEQ_SCAN
        assert result.nodes[0].table == "users"
        assert result.nodes[0].rows == 5000

    def test_index_scan(self):
        text = "Index Scan on users users_pkey  (cost=0.00..8.27 rows=1 width=100)"
        result = parse_postgresql_text(text)
        assert len(result.nodes) == 1
        assert result.nodes[0].scan_type == ScanType.INDEX_SCAN

    def test_planning_time(self):
        text = """Seq Scan on t  (cost=0.00..10.00 rows=100 width=4)
Planning Time: 0.123 ms
Execution Time: 1.456 ms"""
        result = parse_postgresql_text(text)
        assert result.planning_time == 0.123
        assert result.execution_time == 1.456

    def test_actual_time(self):
        text = """Seq Scan on users  (cost=0.00..100.00 rows=5000 width=100)
  actual time=0.010..1.234 rows=5000 loops=1"""
        result = parse_postgresql_text(text)
        assert result.nodes[0].actual_time == 1.234
        assert result.nodes[0].actual_rows == 5000
        assert result.nodes[0].loops == 1

    def test_filter(self):
        text = """Seq Scan on users  (cost=0.00..100.00 rows=5000 width=100)
  Filter: (status = 'active')"""
        result = parse_postgresql_text(text)
        assert result.nodes[0].filter == "(status = 'active')"

    def test_empty(self):
        result = parse_postgresql_text("")
        assert len(result.nodes) == 0

    def test_total_cost(self):
        text = """Seq Scan on a  (cost=0.00..50.00 rows=100 width=4)
Seq Scan on b  (cost=0.00..100.00 rows=200 width=4)"""
        result = parse_postgresql_text(text)
        assert result.total_cost == 100.0


class TestPostgresqlJsonParser:
    def test_basic_plan(self):
        data = [{
            "Plan": {
                "Node Type": "Seq Scan",
                "Relation Name": "users",
                "Plan Rows": 1000,
                "Total Cost": 50.0,
                "Plan Width": 100,
            }
        }]
        result = parse_postgresql_json(json.dumps(data))
        assert len(result.nodes) == 1
        assert result.nodes[0].scan_type == ScanType.SEQ_SCAN
        assert result.nodes[0].table == "users"

    def test_nested_plans(self):
        data = [{
            "Plan": {
                "Node Type": "Hash Join",
                "Total Cost": 200.0,
                "Plan Rows": 100,
                "Plan Width": 50,
                "Plans": [
                    {
                        "Node Type": "Seq Scan",
                        "Relation Name": "users",
                        "Total Cost": 50.0,
                        "Plan Rows": 1000,
                        "Plan Width": 100,
                    },
                    {
                        "Node Type": "Index Scan",
                        "Relation Name": "orders",
                        "Index Name": "orders_user_id_idx",
                        "Total Cost": 100.0,
                        "Plan Rows": 500,
                        "Plan Width": 50,
                    },
                ],
            }
        }]
        result = parse_postgresql_json(json.dumps(data))
        assert len(result.nodes) == 3
        assert result.nodes[1].table == "users"
        assert result.nodes[2].index == "orders_user_id_idx"

    def test_with_timing(self):
        data = [{
            "Plan": {"Node Type": "Seq Scan", "Relation Name": "t", "Total Cost": 10.0, "Plan Rows": 1, "Plan Width": 4},
            "Planning Time": 0.5,
            "Execution Time": 1.2,
        }]
        result = parse_postgresql_json(json.dumps(data))
        assert result.planning_time == 0.5
        assert result.execution_time == 1.2

    def test_dict_format(self):
        data = {
            "Plan": {"Node Type": "Seq Scan", "Relation Name": "t", "Total Cost": 10.0, "Plan Rows": 1, "Plan Width": 4},
        }
        result = parse_postgresql_json(json.dumps(data))
        assert len(result.nodes) == 1


class TestMysqlTabularParser:
    def test_basic(self):
        text = """| id | select_type | table | type | possible_keys | key | rows | Extra |
| 1 | SIMPLE | users | ALL | NULL | NULL | 1000 | |"""
        result = parse_mysql_tabular(text)
        assert len(result.nodes) == 1
        assert result.nodes[0].scan_type == ScanType.FULL_TABLE_SCAN
        assert result.nodes[0].table == "users"

    def test_index_scan(self):
        text = """| id | select_type | table | type | possible_keys | key | rows | Extra |
| 1 | SIMPLE | users | ref | idx_name | idx_name | 10 | |"""
        result = parse_mysql_tabular(text)
        assert result.nodes[0].scan_type == ScanType.INDEX_SCAN

    def test_empty(self):
        result = parse_mysql_tabular("")
        assert len(result.nodes) == 0


class TestMysqlJsonParser:
    def test_basic(self):
        data = {
            "query_block": {
                "select_id": 1,
                "table": {
                    "table_name": "users",
                    "access_type": "ALL",
                    "rows_examined_per_scan": 1000,
                },
            }
        }
        result = parse_mysql_json(json.dumps(data))
        assert len(result.nodes) == 1
        assert result.nodes[0].table == "users"

    def test_with_index(self):
        data = {
            "query_block": {
                "select_id": 1,
                "table": {
                    "table_name": "users",
                    "access_type": "ref",
                    "key": "idx_status",
                    "rows_examined_per_scan": 10,
                },
            }
        }
        result = parse_mysql_json(json.dumps(data))
        assert result.nodes[0].scan_type == ScanType.INDEX_SCAN
        assert result.nodes[0].index == "idx_status"


class TestParseExplain:
    def test_auto_detect_postgresql(self):
        text = "Seq Scan on users  (cost=0.00..100.00 rows=1000 width=100)"
        result = parse_explain(text)
        assert result.dialect == "postgresql"
        assert len(result.nodes) == 1

    def test_auto_detect_postgresql_json(self):
        data = [{"Plan": {"Node Type": "Seq Scan", "Relation Name": "t", "Total Cost": 10.0, "Plan Rows": 1, "Plan Width": 4}}]
        result = parse_explain(json.dumps(data))
        assert result.dialect == "postgresql"

    def test_empty_string(self):
        result = parse_explain("")
        assert len(result.nodes) == 0

    def test_unknown_text(self):
        result = parse_explain("some random text that is not explain output")
        assert result.dialect in ("unknown", "postgresql", "mysql")
