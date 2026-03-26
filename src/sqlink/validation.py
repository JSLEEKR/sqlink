"""Query validation and SQL injection protection for sqlink."""

from __future__ import annotations

import re
from typing import Any


class ValidationError(Exception):
    """Raised when query validation fails."""
    pass


# Patterns that should never appear in identifiers
_DANGEROUS_PATTERNS = [
    r";\s*DROP\b",
    r";\s*DELETE\b",
    r";\s*INSERT\b",
    r";\s*UPDATE\b",
    r";\s*ALTER\b",
    r";\s*CREATE\b",
    r";\s*TRUNCATE\b",
    r";\s*EXEC\b",
    r"--",
    r"/\*",
    r"\*/",
    r"xp_",
    r"WAITFOR\s+DELAY",
    r"BENCHMARK\s*\(",
    r"SLEEP\s*\(",
]

_DANGEROUS_RE = re.compile("|".join(_DANGEROUS_PATTERNS), re.IGNORECASE)

# Valid identifier pattern (alphanumeric, underscore, dot for qualified names)
_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$")

# Star is also a valid column reference
_VALID_COLUMN = re.compile(r"^(\*|[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*(\.\*)?)$")


def validate_identifier(name: str) -> bool:
    """Check if a string is a safe SQL identifier.

    Returns True if safe, raises ValidationError if dangerous.
    """
    if not name:
        raise ValidationError("Empty identifier")

    if _DANGEROUS_RE.search(name):
        raise ValidationError(
            f"Potentially dangerous SQL detected in identifier: {name!r}"
        )

    if not _VALID_IDENTIFIER.match(name):
        # Allow * for select all
        if name != "*" and not _VALID_COLUMN.match(name):
            raise ValidationError(
                f"Invalid identifier: {name!r}. "
                "Identifiers must start with a letter or underscore "
                "and contain only alphanumeric characters, underscores, and dots."
            )

    return True


def validate_table_name(name: str) -> bool:
    """Validate a table name."""
    if not name:
        raise ValidationError("Empty table name")
    return validate_identifier(name)


def validate_column_name(name: str) -> bool:
    """Validate a column name."""
    if not name:
        raise ValidationError("Empty column name")
    if name == "*":
        return True
    return validate_identifier(name)


def check_dangerous_value(value: Any) -> bool:
    """Check if a value contains potential SQL injection patterns.

    Note: This is a secondary defense. Parameterized queries are the primary
    protection against SQL injection.
    """
    if isinstance(value, str) and _DANGEROUS_RE.search(value):
        return True  # Dangerous pattern found
    return False


def sanitize_order_direction(direction: str) -> str:
    """Sanitize ORDER BY direction to prevent injection."""
    upper = direction.upper().strip()
    if upper not in ("ASC", "DESC"):
        raise ValidationError(
            f"Invalid order direction: {direction!r}. Must be 'ASC' or 'DESC'."
        )
    return upper


def validate_limit(value: int) -> int:
    """Validate LIMIT value."""
    if not isinstance(value, int):
        raise ValidationError(f"LIMIT must be an integer, got {type(value).__name__}")
    if value < 0:
        raise ValidationError(f"LIMIT must be non-negative, got {value}")
    return value


def validate_offset(value: int) -> int:
    """Validate OFFSET value."""
    if not isinstance(value, int):
        raise ValidationError(f"OFFSET must be an integer, got {type(value).__name__}")
    if value < 0:
        raise ValidationError(f"OFFSET must be non-negative, got {value}")
    return value
