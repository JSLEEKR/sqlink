"""Tests for pattern library."""

import pytest
from sqlink.patterns import (
    Pattern,
    PatternType,
    PATTERNS,
    match_anti_patterns,
    match_best_practices,
    match_patterns,
    get_pattern,
    get_all_patterns,
)


class TestPattern:
    def test_matches(self):
        p = Pattern(id="T1", name="Test", description="D", pattern_type=PatternType.ANTI_PATTERN, regex=r"\bSELECT\s+\*")
        assert p.matches("SELECT * FROM t")
        assert not p.matches("SELECT id FROM t")

    def test_case_insensitive(self):
        p = Pattern(id="T1", name="Test", description="D", pattern_type=PatternType.ANTI_PATTERN, regex=r"\bselect\b")
        assert p.matches("SELECT 1")


class TestBuiltInPatterns:
    def test_patterns_not_empty(self):
        assert len(PATTERNS) > 0

    def test_all_have_required_fields(self):
        for pid, p in PATTERNS.items():
            assert p.id == pid
            assert p.name
            assert p.description
            assert p.regex

    def test_count_star_existence(self):
        p = get_pattern("AP001")
        assert p is not None
        assert p.matches("SELECT COUNT(*) FROM users WHERE email = 'x'")
        assert not p.matches("SELECT COUNT(id) FROM users")

    def test_order_by_rand(self):
        p = get_pattern("AP002")
        assert p.matches("SELECT * FROM t ORDER BY RAND() LIMIT 10")
        assert not p.matches("SELECT * FROM t ORDER BY id")

    def test_for_update_without_where(self):
        p = get_pattern("AP003")
        assert p.matches("SELECT * FROM accounts FOR UPDATE")
        assert not p.matches("SELECT * FROM accounts WHERE id = 1 FOR UPDATE")

    def test_not_in_subquery(self):
        p = get_pattern("AP005")
        assert p.matches("SELECT * FROM t WHERE id NOT IN (SELECT col FROM t2)")
        assert not p.matches("SELECT * FROM t WHERE id NOT IN (1, 2, 3)")

    def test_exists_best_practice(self):
        p = get_pattern("BP001")
        assert p.matches("SELECT EXISTS (SELECT 1 FROM users WHERE id = 1)")

    def test_insert_with_columns(self):
        p = get_pattern("BP002")
        assert p.matches("INSERT INTO users (name, email) VALUES ('x', 'y')")
        assert not p.matches("INSERT INTO users VALUES ('x', 'y')")

    def test_coalesce(self):
        p = get_pattern("BP003")
        assert p.matches("SELECT COALESCE(name, 'unknown') FROM users")


class TestMatchFunctions:
    def test_match_patterns(self):
        sql = "SELECT COUNT(*) FROM users WHERE email = 'x'"
        matches = match_patterns(sql)
        assert len(matches) >= 1
        assert any(m.id == "AP001" for m in matches)

    def test_match_anti_patterns(self):
        sql = "SELECT * FROM t ORDER BY RAND() LIMIT 10"
        matches = match_anti_patterns(sql)
        assert len(matches) >= 1
        assert all(m.pattern_type == PatternType.ANTI_PATTERN for m in matches)

    def test_match_best_practices(self):
        sql = "SELECT EXISTS (SELECT 1 FROM users WHERE id = 1)"
        matches = match_best_practices(sql)
        assert len(matches) >= 1
        assert all(m.pattern_type == PatternType.BEST_PRACTICE for m in matches)

    def test_no_matches(self):
        sql = "SELECT id FROM users WHERE id = 1 LIMIT 1"
        anti = match_anti_patterns(sql)
        # This clean query should have minimal anti-pattern matches
        assert all(m.id != "AP002" for m in anti)  # No ORDER BY RAND

    def test_get_all_patterns(self):
        all_p = get_all_patterns()
        assert len(all_p) == len(PATTERNS)

    def test_get_pattern_not_found(self):
        assert get_pattern("NONEXISTENT") is None

    def test_correlated_subquery(self):
        sql = "SELECT u.name, (SELECT COUNT(*) FROM orders WHERE user_id = u.id) FROM users u"
        matches = match_anti_patterns(sql)
        assert any(m.id == "AP004" for m in matches)

    def test_implicit_type_conversion(self):
        sql = "SELECT * FROM users WHERE phone = 1234567890"
        matches = match_anti_patterns(sql)
        assert any(m.id == "AP006" for m in matches)
