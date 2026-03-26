"""Tests for query sanitizer."""

import pytest
from sqlink.sanitizer import (
    sanitize,
    sanitize_batch,
    mask_identifiers,
    detect_sensitive_patterns,
)


class TestSanitize:
    def test_replaces_string_literals(self):
        result = sanitize("SELECT * FROM users WHERE name = 'John Doe'")
        assert "John Doe" not in result
        assert "?" in result

    def test_replaces_escaped_quotes(self):
        result = sanitize("SELECT * FROM t WHERE name = 'O\\'Brien'")
        assert "Brien" not in result

    def test_replaces_hex(self):
        result = sanitize("SELECT * FROM t WHERE token = 0xDEADBEEF")
        assert "DEADBEEF" not in result

    def test_replaces_uuid(self):
        result = sanitize("SELECT * FROM t WHERE id = '550e8400-e29b-41d4-a716-446655440000'")
        assert "550e8400" not in result

    def test_replaces_numbers_in_where(self):
        result = sanitize("SELECT * FROM t WHERE id = 42")
        assert "42" not in result

    def test_preserves_sql_structure(self):
        result = sanitize("SELECT * FROM users WHERE id = 1")
        assert "SELECT" in result
        assert "FROM" in result
        assert "WHERE" in result

    def test_custom_placeholder(self):
        result = sanitize("SELECT * FROM t WHERE name = 'x'", placeholder="$1")
        assert "$1" in result

    def test_multiple_values(self):
        result = sanitize("SELECT * FROM t WHERE a = 'x' AND b = 'y' AND c = 1")
        assert "x" not in result
        assert "y" not in result

    def test_in_list(self):
        result = sanitize("SELECT * FROM t WHERE id IN (1, 2, 3)")
        assert "?" in result

    def test_empty_string(self):
        result = sanitize("")
        assert result == ""


class TestSanitizeBatch:
    def test_batch(self):
        queries = ["SELECT * FROM t WHERE a = 'x'", "SELECT * FROM t WHERE b = 1"]
        results = sanitize_batch(queries)
        assert len(results) == 2
        assert "x" not in results[0]

    def test_empty_batch(self):
        assert sanitize_batch([]) == []


class TestMaskIdentifiers:
    def test_mask_tables_from(self):
        result = mask_identifiers("SELECT * FROM users", tables=True)
        assert "users" not in result
        assert "TABLE_X" in result

    def test_mask_tables_join(self):
        result = mask_identifiers("SELECT * FROM a JOIN orders ON a.id = orders.a_id", tables=True)
        # The JOIN target is masked, but column references remain
        assert "JOIN TABLE_X" in result

    def test_no_masking_by_default(self):
        result = mask_identifiers("SELECT * FROM users")
        assert "users" in result

    def test_mask_insert(self):
        result = mask_identifiers("INSERT INTO users (name) VALUES ('x')", tables=True)
        assert "users" not in result

    def test_mask_update(self):
        result = mask_identifiers("UPDATE users SET name = 'x'", tables=True)
        assert "users" not in result


class TestDetectSensitivePatterns:
    def test_email(self):
        warnings = detect_sensitive_patterns("SELECT * FROM t WHERE email = 'john@example.com'")
        assert any("Email" in w for w in warnings)

    def test_credit_card(self):
        warnings = detect_sensitive_patterns("SELECT * FROM t WHERE card = '4111-1111-1111-1111'")
        assert any("credit card" in w for w in warnings)

    def test_ssn(self):
        warnings = detect_sensitive_patterns("SELECT * FROM t WHERE ssn = '123-45-6789'")
        assert any("SSN" in w for w in warnings)

    def test_password_column(self):
        warnings = detect_sensitive_patterns("SELECT password FROM users")
        assert any("password" in w.lower() for w in warnings)

    def test_api_key_column(self):
        warnings = detect_sensitive_patterns("SELECT api_key FROM settings")
        assert any("password" in w.lower() or "secret" in w.lower() or "token" in w.lower() for w in warnings)

    def test_ip_address(self):
        warnings = detect_sensitive_patterns("SELECT * FROM t WHERE ip = '192.168.1.1'")
        assert any("IP" in w for w in warnings)

    def test_no_sensitive_data(self):
        warnings = detect_sensitive_patterns("SELECT id, name FROM users WHERE status = 'active'")
        assert len(warnings) == 0

    def test_token_column(self):
        warnings = detect_sensitive_patterns("SELECT token FROM sessions")
        assert len(warnings) >= 1
