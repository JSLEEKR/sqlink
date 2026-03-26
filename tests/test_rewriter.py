"""Tests for query rewriter."""

import pytest
from sqlink.rewriter import Rewrite, suggest_rewrites
from sqlink.parser import parse_query


class TestRewrite:
    def test_to_dict(self):
        r = Rewrite(original="SELECT *", rewritten="SELECT id", rule_id="SQ001", description="Fix")
        d = r.to_dict()
        assert d["original"] == "SELECT *"
        assert d["rewritten"] == "SELECT id"
        assert d["rule_id"] == "SQ001"


class TestSelectStarRewrite:
    def test_suggests_rewrite(self):
        q = parse_query("SELECT * FROM users")
        rewrites = suggest_rewrites(q)
        sq001 = [r for r in rewrites if r.rule_id == "SQ001"]
        assert len(sq001) >= 1
        assert "TODO" in sq001[0].rewritten

    def test_no_rewrite_for_explicit_columns(self):
        q = parse_query("SELECT id, name FROM users")
        rewrites = suggest_rewrites(q)
        sq001 = [r for r in rewrites if r.rule_id == "SQ001"]
        assert len(sq001) == 0


class TestOffsetRewrite:
    def test_suggests_keyset(self):
        q = parse_query("SELECT id FROM users ORDER BY id LIMIT 10 OFFSET 100")
        rewrites = suggest_rewrites(q)
        sq004 = [r for r in rewrites if r.rule_id == "SQ004"]
        assert len(sq004) >= 1
        assert "last_seen_id" in sq004[0].rewritten

    def test_no_rewrite_without_offset(self):
        q = parse_query("SELECT id FROM users LIMIT 10")
        rewrites = suggest_rewrites(q)
        sq004 = [r for r in rewrites if r.rule_id == "SQ004"]
        assert len(sq004) == 0


class TestUnionRewrite:
    def test_suggests_union_all(self):
        q = parse_query("SELECT id FROM a UNION SELECT id FROM b")
        rewrites = suggest_rewrites(q)
        sq007 = [r for r in rewrites if r.rule_id == "SQ007"]
        assert len(sq007) >= 1
        assert "UNION ALL" in sq007[0].rewritten

    def test_no_rewrite_for_union_all(self):
        q = parse_query("SELECT id FROM a UNION ALL SELECT id FROM b")
        rewrites = suggest_rewrites(q)
        sq007 = [r for r in rewrites if r.rule_id == "SQ007"]
        assert len(sq007) == 0


class TestInSubqueryRewrite:
    def test_suggests_exists(self):
        q = parse_query("SELECT * FROM t WHERE id IN (SELECT user_id FROM t2)")
        rewrites = suggest_rewrites(q)
        wh006 = [r for r in rewrites if r.rule_id == "WH006"]
        assert len(wh006) >= 1
        assert "EXISTS" in wh006[0].rewritten

    def test_no_rewrite_without_subquery(self):
        q = parse_query("SELECT * FROM t WHERE id IN (1, 2, 3)")
        rewrites = suggest_rewrites(q)
        wh006 = [r for r in rewrites if r.rule_id == "WH006"]
        assert len(wh006) == 0


class TestAddLimitRewrite:
    def test_suggests_limit(self):
        q = parse_query("SELECT id FROM users WHERE status = 'active'")
        rewrites = suggest_rewrites(q)
        sd001 = [r for r in rewrites if r.rule_id == "SD001"]
        assert len(sd001) >= 1
        assert "LIMIT" in sd001[0].rewritten

    def test_no_rewrite_with_limit(self):
        q = parse_query("SELECT id FROM users LIMIT 10")
        rewrites = suggest_rewrites(q)
        sd001 = [r for r in rewrites if r.rule_id == "SD001"]
        assert len(sd001) == 0

    def test_no_rewrite_for_aggregation(self):
        q = parse_query("SELECT status, COUNT(*) FROM users GROUP BY status")
        rewrites = suggest_rewrites(q)
        sd001 = [r for r in rewrites if r.rule_id == "SD001"]
        assert len(sd001) == 0

    def test_no_rewrite_for_non_select(self):
        q = parse_query("UPDATE users SET name = 'x' WHERE id = 1")
        rewrites = suggest_rewrites(q)
        sd001 = [r for r in rewrites if r.rule_id == "SD001"]
        assert len(sd001) == 0
