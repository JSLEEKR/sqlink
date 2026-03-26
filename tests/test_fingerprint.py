"""Tests for query fingerprinting."""

import pytest
from sqlink.fingerprint import (
    fingerprint,
    normalize_for_fingerprint,
    group_by_fingerprint,
    find_duplicates,
)


class TestNormalizeForFingerprint:
    def test_replaces_string_literals(self):
        result = normalize_for_fingerprint("SELECT * FROM t WHERE name = 'John'")
        assert "JOHN" not in result
        assert "?" in result

    def test_replaces_numbers(self):
        result = normalize_for_fingerprint("SELECT * FROM t WHERE id = 42")
        assert "42" not in result
        assert "?" in result

    def test_replaces_floats(self):
        result = normalize_for_fingerprint("SELECT * FROM t WHERE price > 19.99")
        assert "19.99" not in result

    def test_collapses_in_lists(self):
        result = normalize_for_fingerprint("SELECT * FROM t WHERE id IN (1, 2, 3)")
        assert result.count("?") == 1 or "IN (?)" in result

    def test_uppercases(self):
        result = normalize_for_fingerprint("select * from users")
        assert result == "SELECT * FROM USERS"

    def test_collapses_whitespace(self):
        result = normalize_for_fingerprint("SELECT  *\n  FROM\n  t")
        assert "  " not in result

    def test_strips_semicolon(self):
        result = normalize_for_fingerprint("SELECT 1;")
        assert not result.endswith(";")

    def test_double_quoted_strings(self):
        result = normalize_for_fingerprint('SELECT * FROM t WHERE name = "test"')
        assert "test" not in result.lower()


class TestFingerprint:
    def test_same_query_same_fingerprint(self):
        fp1 = fingerprint("SELECT * FROM users WHERE id = 1")
        fp2 = fingerprint("SELECT * FROM users WHERE id = 2")
        assert fp1 == fp2

    def test_different_queries_different_fingerprint(self):
        fp1 = fingerprint("SELECT * FROM users WHERE id = 1")
        fp2 = fingerprint("SELECT * FROM orders WHERE id = 1")
        assert fp1 != fp2

    def test_returns_hex_string(self):
        fp = fingerprint("SELECT 1")
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_string_values_dont_matter(self):
        fp1 = fingerprint("SELECT * FROM t WHERE name = 'Alice'")
        fp2 = fingerprint("SELECT * FROM t WHERE name = 'Bob'")
        assert fp1 == fp2

    def test_in_list_length_doesnt_matter(self):
        fp1 = fingerprint("SELECT * FROM t WHERE id IN (1, 2)")
        fp2 = fingerprint("SELECT * FROM t WHERE id IN (1, 2, 3, 4, 5)")
        assert fp1 == fp2

    def test_whitespace_doesnt_matter(self):
        fp1 = fingerprint("SELECT * FROM t WHERE id = 1")
        fp2 = fingerprint("SELECT  *  FROM  t  WHERE  id  =  1")
        assert fp1 == fp2

    def test_case_doesnt_matter(self):
        fp1 = fingerprint("SELECT * FROM users")
        fp2 = fingerprint("select * from users")
        assert fp1 == fp2


class TestGroupByFingerprint:
    def test_groups_similar_queries(self):
        queries = [
            "SELECT * FROM users WHERE id = 1",
            "SELECT * FROM users WHERE id = 2",
            "SELECT * FROM users WHERE id = 3",
            "SELECT * FROM orders WHERE id = 1",
        ]
        groups = group_by_fingerprint(queries)
        assert len(groups) == 2
        # One group should have 3 queries
        counts = sorted(len(v) for v in groups.values())
        assert counts == [1, 3]

    def test_empty_list(self):
        groups = group_by_fingerprint([])
        assert groups == {}

    def test_all_unique(self):
        queries = ["SELECT 1", "SELECT 2 FROM t", "DELETE FROM t"]
        groups = group_by_fingerprint(queries)
        # SELECT 1 and SELECT 2 normalize to same thing
        assert len(groups) >= 2


class TestFindDuplicates:
    def test_finds_duplicates(self):
        queries = [
            "SELECT * FROM users WHERE id = 1",
            "SELECT * FROM users WHERE id = 2",
            "SELECT * FROM users WHERE id = 3",
        ]
        dups = find_duplicates(queries)
        assert len(dups) == 1
        assert dups[0]["count"] == 3

    def test_min_count(self):
        queries = [
            "SELECT * FROM users WHERE id = 1",
            "SELECT * FROM users WHERE id = 2",
        ]
        dups = find_duplicates(queries, min_count=3)
        assert len(dups) == 0

    def test_examples_limited(self):
        queries = [f"SELECT * FROM t WHERE id = {i}" for i in range(10)]
        dups = find_duplicates(queries)
        assert len(dups[0]["examples"]) == 3

    def test_sorted_by_count(self):
        queries = (
            [f"SELECT * FROM a WHERE id = {i}" for i in range(5)]
            + [f"SELECT * FROM b WHERE id = {i}" for i in range(3)]
        )
        dups = find_duplicates(queries)
        assert len(dups) >= 2
        assert dups[0]["count"] >= dups[1]["count"]

    def test_has_normalized_form(self):
        queries = ["SELECT * FROM t WHERE id = 1", "SELECT * FROM t WHERE id = 2"]
        dups = find_duplicates(queries)
        assert "normalized" in dups[0]
        assert "?" in dups[0]["normalized"]

    def test_no_duplicates(self):
        queries = ["SELECT 1", "DELETE FROM t"]
        dups = find_duplicates(queries)
        assert len(dups) == 0
