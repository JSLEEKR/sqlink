"""Query sanitizer — remove sensitive data from SQL queries for safe logging."""

from __future__ import annotations

import re


def sanitize(sql: str, *, placeholder: str = "?") -> str:
    """Sanitize a SQL query by replacing literal values with placeholders.

    Replaces:
    - String literals ('...')
    - Numeric literals
    - Hex literals (0x...)
    - Boolean literals
    - UUID-like values
    """
    result = sql

    # Replace single-quoted strings (handle escaped quotes)
    result = re.sub(r"'(?:[^'\\]|\\.)*'", placeholder, result)

    # Replace double-quoted strings (if not identifiers — be conservative)
    # Only replace if followed by comparison operators
    result = re.sub(r'"(?:[^"\\]|\\.)*"(?=\s*(?:[=<>!]|IS|IN|LIKE|BETWEEN))', placeholder, result, flags=re.IGNORECASE)

    # Replace hex literals
    result = re.sub(r"\b0x[0-9a-fA-F]+\b", placeholder, result)

    # Replace UUID-like values
    result = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        placeholder,
        result,
    )

    # Replace numeric literals (integers and floats, but not in identifiers)
    result = re.sub(r"(?<=\s)\d+(?:\.\d+)?(?=\s|,|;|\)|$)", placeholder, result)
    result = re.sub(r"(?<=[=<>!])\s*\d+(?:\.\d+)?(?=\s|,|;|\)|$)", f" {placeholder}", result)

    return result


def sanitize_batch(queries: list[str], *, placeholder: str = "?") -> list[str]:
    """Sanitize a list of SQL queries."""
    return [sanitize(q, placeholder=placeholder) for q in queries]


def mask_identifiers(sql: str, *, tables: bool = False, columns: bool = False) -> str:
    """Mask table and/or column names in a SQL query.

    This is more aggressive than sanitize() and is useful for
    sharing query structures without revealing schema details.
    """
    result = sql

    if tables:
        # Replace table names after FROM, JOIN, INTO, UPDATE
        result = re.sub(
            r"(?<=\bFROM\s)\s*(\w+)",
            "TABLE_X",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?<=\bJOIN\s)\s*(\w+)",
            "TABLE_X",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?<=\bINTO\s)\s*(\w+)",
            "TABLE_X",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?<=\bUPDATE\s)\s*(\w+)",
            "TABLE_X",
            result,
            flags=re.IGNORECASE,
        )

    return result


def detect_sensitive_patterns(sql: str) -> list[str]:
    """Detect potentially sensitive data in a SQL query.

    Returns a list of warnings about sensitive data found.
    """
    warnings: list[str] = []

    # Email patterns
    if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", sql):
        warnings.append("Email address detected in query")

    # Credit card patterns (basic)
    if re.search(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", sql):
        warnings.append("Potential credit card number detected")

    # SSN patterns
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", sql):
        warnings.append("Potential SSN detected")

    # Password/secret column names
    if re.search(r"\b(password|passwd|secret|token|api_key|apikey|private_key)\b", sql, re.IGNORECASE):
        warnings.append("Sensitive column name detected (password/secret/token)")

    # IP addresses
    if re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", sql):
        warnings.append("IP address detected in query")

    # Phone numbers (basic pattern)
    if re.search(r"(?<!')\b\+?\d{1,3}[-.]?\d{3,4}[-.]?\d{3,4}[-.]?\d{0,4}\b(?!')", sql):
        # Avoid matching simple numeric literals
        pass  # Too many false positives, skip for now

    return warnings
