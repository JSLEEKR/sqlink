"""Tests for SQL analyzer."""

import pytest
from sqlink.analyzer import QueryAnalyzer
from sqlink.models import Severity


@pytest.fixture
def analyzer():
    return QueryAnalyzer()


class TestSelectStar:
    def test_detects_select_star(self, analyzer):
        r = analyzer.analyze("SELECT * FROM users")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ001" in rule_ids

    def test_no_star_no_finding(self, analyzer):
        r = analyzer.analyze("SELECT id, name FROM users")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ001" not in rule_ids


class TestMissingWhere:
    def test_update_without_where(self, analyzer):
        r = analyzer.analyze("UPDATE users SET status = 'inactive'")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ002" in rule_ids

    def test_delete_without_where(self, analyzer):
        r = analyzer.analyze("DELETE FROM users")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ002" in rule_ids

    def test_update_with_where_ok(self, analyzer):
        r = analyzer.analyze("UPDATE users SET status = 'inactive' WHERE id = 1")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ002" not in rule_ids

    def test_select_without_where_no_sq002(self, analyzer):
        r = analyzer.analyze("SELECT * FROM users")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ002" not in rule_ids


class TestDistinctSmell:
    def test_distinct_with_join(self, analyzer):
        r = analyzer.analyze("SELECT DISTINCT u.name FROM users u JOIN orders o ON u.id = o.user_id")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ003" in rule_ids

    def test_distinct_without_join_no_finding(self, analyzer):
        r = analyzer.analyze("SELECT DISTINCT name FROM users")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ003" not in rule_ids


class TestOffsetPagination:
    def test_detects_offset(self, analyzer):
        r = analyzer.analyze("SELECT * FROM users LIMIT 10 OFFSET 100")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ004" in rule_ids


class TestImplicitCrossJoin:
    def test_detects_cross_join(self, analyzer):
        r = analyzer.analyze("SELECT * FROM users, orders")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ005" in rule_ids

    def test_single_table_no_cross_join(self, analyzer):
        r = analyzer.analyze("SELECT * FROM users")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ005" not in rule_ids


class TestTooManyJoins:
    def test_too_many_joins(self):
        analyzer = QueryAnalyzer(max_joins=2)
        sql = "SELECT * FROM a JOIN b ON a.id=b.id JOIN c ON b.id=c.id JOIN d ON c.id=d.id"
        r = analyzer.analyze(sql)
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ006" in rule_ids


class TestUnionWithoutAll:
    def test_detects_union(self, analyzer):
        r = analyzer.analyze("SELECT id FROM a UNION SELECT id FROM b")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ007" in rule_ids

    def test_union_all_ok(self, analyzer):
        r = analyzer.analyze("SELECT id FROM a UNION ALL SELECT id FROM b")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ007" not in rule_ids


class TestWhereClauseRules:
    def test_function_on_column(self, analyzer):
        r = analyzer.analyze("SELECT * FROM t WHERE UPPER(name) = 'X'")
        rule_ids = [f.rule_id for f in r.findings]
        assert "WH001" in rule_ids

    def test_leading_wildcard(self, analyzer):
        r = analyzer.analyze("SELECT * FROM t WHERE name LIKE '%test'")
        rule_ids = [f.rule_id for f in r.findings]
        assert "WH002" in rule_ids

    def test_or_conditions(self, analyzer):
        r = analyzer.analyze("SELECT * FROM t WHERE a = 1 OR b = 2")
        rule_ids = [f.rule_id for f in r.findings]
        assert "WH003" in rule_ids

    def test_not_equal(self, analyzer):
        r = analyzer.analyze("SELECT * FROM t WHERE status != 'active'")
        rule_ids = [f.rule_id for f in r.findings]
        assert "WH004" in rule_ids

    def test_is_null(self, analyzer):
        r = analyzer.analyze("SELECT * FROM t WHERE deleted_at IS NULL")
        rule_ids = [f.rule_id for f in r.findings]
        assert "WH005" in rule_ids

    def test_in_subquery(self, analyzer):
        r = analyzer.analyze("SELECT * FROM t WHERE id IN (SELECT id FROM t2)")
        rule_ids = [f.rule_id for f in r.findings]
        assert "WH006" in rule_ids


class TestMissingLimit:
    def test_select_without_limit(self, analyzer):
        r = analyzer.analyze("SELECT id FROM users")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SD001" in rule_ids

    def test_select_with_limit_ok(self, analyzer):
        r = analyzer.analyze("SELECT id FROM users LIMIT 10")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SD001" not in rule_ids


class TestOrderWithoutLimit:
    def test_order_without_limit(self, analyzer):
        r = analyzer.analyze("SELECT id FROM users ORDER BY name")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SD002" in rule_ids

    def test_order_with_limit_ok(self, analyzer):
        r = analyzer.analyze("SELECT id FROM users ORDER BY name LIMIT 10")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SD002" not in rule_ids


class TestHavingWithoutGroup:
    def test_having_no_group(self, analyzer):
        r = analyzer.analyze("SELECT COUNT(*) FROM t HAVING COUNT(*) > 1")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SD003" in rule_ids


class TestExplainAnalysis:
    def test_full_table_scan(self, analyzer):
        explain = """
        Seq Scan on users  (cost=0.00..100.00 rows=5000 width=100)
        """
        r = analyzer.analyze("SELECT * FROM users", explain_text=explain)
        rule_ids = [f.rule_id for f in r.findings]
        assert "EX001" in rule_ids

    def test_high_cost(self, analyzer):
        explain = """
        Seq Scan on users  (cost=0.00..5000.00 rows=100 width=100)
        """
        r = analyzer.analyze("SELECT * FROM users", explain_text=explain)
        rule_ids = [f.rule_id for f in r.findings]
        assert "EX002" in rule_ids

    def test_large_rows(self, analyzer):
        explain = """
        Seq Scan on users  (cost=0.00..100.00 rows=50000 width=100)
        """
        r = analyzer.analyze("SELECT * FROM users", explain_text=explain)
        rule_ids = [f.rule_id for f in r.findings]
        assert "EX003" in rule_ids


class TestNPlusOne:
    def test_detects_n_plus_one(self, analyzer):
        queries = [
            "SELECT * FROM orders WHERE user_id = 1",
            "SELECT * FROM orders WHERE user_id = 2",
            "SELECT * FROM orders WHERE user_id = 3",
            "SELECT * FROM orders WHERE user_id = 4",
        ]
        results = analyzer.analyze_batch(queries)
        all_rules = []
        for r in results:
            all_rules.extend(f.rule_id for f in r.findings)
        assert "NP001" in all_rules

    def test_detects_repeated_query(self, analyzer):
        queries = [
            "SELECT * FROM config",
            "SELECT * FROM config",
            "SELECT * FROM config",
        ]
        results = analyzer.analyze_batch(queries)
        all_rules = []
        for r in results:
            all_rules.extend(f.rule_id for f in r.findings)
        assert "NP002" in all_rules

    def test_no_n_plus_one_for_different_queries(self, analyzer):
        queries = [
            "SELECT * FROM users",
            "SELECT * FROM orders",
        ]
        results = analyzer.analyze_batch(queries)
        all_rules = []
        for r in results:
            all_rules.extend(f.rule_id for f in r.findings)
        assert "NP001" not in all_rules


class TestDisabledRules:
    def test_disable_rule(self):
        analyzer = QueryAnalyzer(disabled_rules={"SQ001"})
        r = analyzer.analyze("SELECT * FROM users")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ001" not in rule_ids

    def test_disable_multiple_rules(self):
        analyzer = QueryAnalyzer(disabled_rules={"SQ001", "SD001"})
        r = analyzer.analyze("SELECT * FROM users")
        rule_ids = [f.rule_id for f in r.findings]
        assert "SQ001" not in rule_ids
        assert "SD001" not in rule_ids


class TestScoring:
    def test_perfect_score(self, analyzer):
        r = analyzer.analyze("SELECT id FROM users WHERE id = 1 LIMIT 1")
        # Should have no findings (or only info), score should be high
        assert r.score >= 80

    def test_low_score_many_issues(self, analyzer):
        r = analyzer.analyze("DELETE FROM users")
        assert r.score < 100

    def test_score_never_negative(self, analyzer):
        # Create a query that triggers many rules
        sql = "SELECT * FROM a, b WHERE UPPER(name) LIKE '%x' AND status != 'a' AND deleted_at IS NULL AND id IN (SELECT id FROM c) AND a = 1 OR b = 2"
        r = analyzer.analyze(sql)
        assert r.score >= 0
