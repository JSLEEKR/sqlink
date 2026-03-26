"""Tests for rules module."""

from sqlink.rules import RULES, get_all_categories, get_rule, get_rules_by_category
from sqlink.models import Severity


class TestRules:
    def test_rules_not_empty(self):
        assert len(RULES) > 0

    def test_all_rules_have_required_fields(self):
        for rule_id, rule in RULES.items():
            assert rule.id == rule_id
            assert rule.title
            assert rule.description
            assert isinstance(rule.severity, Severity)
            assert rule.suggestion
            assert rule.category

    def test_get_rule_exists(self):
        rule = get_rule("SQ001")
        assert rule is not None
        assert rule.id == "SQ001"

    def test_get_rule_not_exists(self):
        assert get_rule("NONEXISTENT") is None

    def test_get_rules_by_category(self):
        rules = get_rules_by_category("query_structure")
        assert len(rules) > 0
        for r in rules:
            assert r.category == "query_structure"

    def test_get_all_categories(self):
        cats = get_all_categories()
        assert len(cats) > 0
        assert "query_structure" in cats
        assert "where_clause" in cats
        assert "explain" in cats

    def test_unique_rule_ids(self):
        ids = [r.id for r in RULES.values()]
        assert len(ids) == len(set(ids))

    def test_rule_categories_exist(self):
        expected = {"query_structure", "where_clause", "explain", "n_plus_one", "schema_design"}
        actual = set(get_all_categories())
        assert expected.issubset(actual)
