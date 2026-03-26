"""Query fingerprinting — normalize queries for grouping and comparison."""

from __future__ import annotations

import hashlib
import re


def fingerprint(sql: str) -> str:
    """Generate a fingerprint for a SQL query.

    Normalizes the query by:
    - Replacing numeric literals with ?
    - Replacing string literals with ?
    - Collapsing whitespace
    - Uppercasing
    - Replacing IN (...) lists with IN (?)
    - Replacing BETWEEN x AND y with BETWEEN ? AND ?

    Returns a hex hash string.
    """
    normalized = normalize_for_fingerprint(sql)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def normalize_for_fingerprint(sql: str) -> str:
    """Normalize a SQL query for fingerprinting (returns the normalized string)."""
    result = sql.strip().rstrip(";")

    # Replace string literals
    result = re.sub(r"'[^']*'", "?", result)
    result = re.sub(r'"[^"]*"', "?", result)

    # Replace numeric literals (integers and floats)
    result = re.sub(r"\b\d+(?:\.\d+)?\b", "?", result)

    # Collapse IN lists: IN (?, ?, ?) -> IN (?)
    result = re.sub(r"\bIN\s*\(\s*\?(?:\s*,\s*\?)*\s*\)", "IN (?)", result, flags=re.IGNORECASE)

    # Normalize whitespace
    result = re.sub(r"\s+", " ", result).strip()

    # Uppercase
    result = result.upper()

    return result


def group_by_fingerprint(queries: list[str]) -> dict[str, list[str]]:
    """Group queries by their fingerprint.

    Returns a dict mapping fingerprint -> list of original queries.
    """
    groups: dict[str, list[str]] = {}
    for query in queries:
        fp = fingerprint(query)
        groups.setdefault(fp, []).append(query)
    return groups


def find_duplicates(queries: list[str], *, min_count: int = 2) -> list[dict[str, object]]:
    """Find duplicate query patterns.

    Returns a list of dicts with:
    - fingerprint: the fingerprint hash
    - normalized: the normalized form
    - count: number of occurrences
    - examples: list of original queries (up to 3)
    """
    groups = group_by_fingerprint(queries)
    duplicates = []

    for fp, group in groups.items():
        if len(group) >= min_count:
            duplicates.append({
                "fingerprint": fp,
                "normalized": normalize_for_fingerprint(group[0]),
                "count": len(group),
                "examples": group[:3],
            })

    duplicates.sort(key=lambda d: -d["count"])
    return duplicates
