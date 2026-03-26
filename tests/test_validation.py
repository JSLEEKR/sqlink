"""Tests for SQL injection protection and validation."""

import pytest
from sqlink.validation import (
    ValidationError,
    validate_identifier,
    validate_table_name,
    validate_column_name,
    check_dangerous_value,
    sanitize_order_direction,
    validate_limit,
    validate_offset,
)


class TestValidateIdentifier:
    def test_valid_simple(self):
        assert validate_identifier("users") is True

    def test_valid_underscore(self):
        assert validate_identifier("user_name") is True

    def test_valid_qualified(self):
        assert validate_identifier("schema.table") is True

    def test_valid_starts_underscore(self):
        assert validate_identifier("_private") is True

    def test_empty_raises(self):
        with pytest.raises(ValidationError, match="Empty"):
            validate_identifier("")

    def test_drop_injection(self):
        with pytest.raises(ValidationError):
            validate_identifier("users; DROP TABLE users")

    def test_comment_injection(self):
        with pytest.raises(ValidationError):
            validate_identifier("users--comment")

    def test_block_comment_injection(self):
        with pytest.raises(ValidationError):
            validate_identifier("users/*comment*/")

    def test_starts_with_number(self):
        with pytest.raises(ValidationError):
            validate_identifier("123abc")

    def test_special_chars(self):
        with pytest.raises(ValidationError):
            validate_identifier("user@name")

    def test_semicolon_delete(self):
        with pytest.raises(ValidationError):
            validate_identifier("t; DELETE FROM users")

    def test_xp_cmdshell(self):
        with pytest.raises(ValidationError):
            validate_identifier("xp_cmdshell")

    def test_waitfor_delay(self):
        with pytest.raises(ValidationError):
            validate_identifier("x; WAITFOR DELAY '0:0:5'")

    def test_benchmark(self):
        with pytest.raises(ValidationError):
            validate_identifier("x; BENCHMARK(1000, SHA1('test'))")

    def test_sleep(self):
        with pytest.raises(ValidationError):
            validate_identifier("x; SLEEP(5)")


class TestValidateTableName:
    def test_valid(self):
        assert validate_table_name("orders") is True

    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_table_name("")

    def test_injection(self):
        with pytest.raises(ValidationError):
            validate_table_name("orders; DROP TABLE orders")


class TestValidateColumnName:
    def test_valid(self):
        assert validate_column_name("email") is True

    def test_star(self):
        assert validate_column_name("*") is True

    def test_qualified(self):
        assert validate_column_name("users.email") is True

    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_column_name("")

    def test_injection(self):
        with pytest.raises(ValidationError):
            validate_column_name("email; DROP TABLE users")


class TestCheckDangerousValue:
    def test_safe_string(self):
        assert check_dangerous_value("hello") is False

    def test_safe_number(self):
        assert check_dangerous_value(42) is False

    def test_drop_table(self):
        assert check_dangerous_value("'; DROP TABLE users--") is True

    def test_delete(self):
        assert check_dangerous_value("x'; DELETE FROM users--") is True

    def test_comment(self):
        assert check_dangerous_value("admin'--") is True

    def test_safe_none(self):
        assert check_dangerous_value(None) is False

    def test_safe_bool(self):
        assert check_dangerous_value(True) is False

    def test_benchmark_attack(self):
        assert check_dangerous_value("1; BENCHMARK(5000000, SHA1('test'))") is True

    def test_sleep_attack(self):
        assert check_dangerous_value("1; SLEEP(5)") is True


class TestSanitizeOrderDirection:
    def test_asc(self):
        assert sanitize_order_direction("ASC") == "ASC"

    def test_desc(self):
        assert sanitize_order_direction("DESC") == "DESC"

    def test_lowercase(self):
        assert sanitize_order_direction("asc") == "ASC"

    def test_with_spaces(self):
        assert sanitize_order_direction("  desc  ") == "DESC"

    def test_invalid(self):
        with pytest.raises(ValidationError):
            sanitize_order_direction("RANDOM")

    def test_injection(self):
        with pytest.raises(ValidationError):
            sanitize_order_direction("ASC; DROP TABLE users")


class TestValidateLimit:
    def test_valid(self):
        assert validate_limit(10) == 10

    def test_zero(self):
        assert validate_limit(0) == 0

    def test_negative(self):
        with pytest.raises(ValidationError):
            validate_limit(-1)

    def test_not_int(self):
        with pytest.raises(ValidationError):
            validate_limit("10")


class TestValidateOffset:
    def test_valid(self):
        assert validate_offset(20) == 20

    def test_zero(self):
        assert validate_offset(0) == 0

    def test_negative(self):
        with pytest.raises(ValidationError):
            validate_offset(-5)

    def test_not_int(self):
        with pytest.raises(ValidationError):
            validate_offset(3.14)
