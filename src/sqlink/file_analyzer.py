"""File-based SQL analysis — read .sql files and analyze all queries."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlink.analyzer import QueryAnalyzer
from sqlink.models import AnalysisResult


def split_sql_file(content: str) -> list[str]:
    """Split a SQL file into individual queries.

    Handles:
    - Semicolon-separated queries
    - Single-line comments (--)
    - Multi-line comments (/* ... */)
    - String literals (won't split inside strings)
    """
    queries: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    i = 0

    while i < len(content):
        char = content[i]
        next_char = content[i + 1] if i + 1 < len(content) else ""

        # Handle line comments
        if not in_single_quote and not in_double_quote and not in_block_comment:
            if char == "-" and next_char == "-":
                in_line_comment = True
                i += 2
                continue

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                current.append(" ")
            i += 1
            continue

        # Handle block comments
        if not in_single_quote and not in_double_quote:
            if char == "/" and next_char == "*" and not in_block_comment:
                in_block_comment = True
                i += 2
                continue
            if char == "*" and next_char == "/" and in_block_comment:
                in_block_comment = False
                i += 2
                current.append(" ")
                continue

        if in_block_comment:
            i += 1
            continue

        # Handle string literals
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

        # Handle semicolons (query separator)
        if char == ";" and not in_single_quote and not in_double_quote:
            query = "".join(current).strip()
            if query:
                queries.append(query)
            current = []
            i += 1
            continue

        current.append(char)
        i += 1

    # Don't forget the last query (without trailing semicolon)
    query = "".join(current).strip()
    if query:
        queries.append(query)

    return queries


def analyze_file(
    filepath: str | Path,
    *,
    analyzer: QueryAnalyzer | None = None,
) -> list[AnalysisResult]:
    """Analyze all SQL queries in a file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if not path.is_file():
        raise ValueError(f"Not a file: {filepath}")

    content = path.read_text(encoding="utf-8")
    return analyze_sql_content(content, analyzer=analyzer)


def analyze_sql_content(
    content: str,
    *,
    analyzer: QueryAnalyzer | None = None,
) -> list[AnalysisResult]:
    """Analyze all SQL queries in a string."""
    if analyzer is None:
        analyzer = QueryAnalyzer()

    queries = split_sql_file(content)
    if not queries:
        return []

    return analyzer.analyze_batch(queries)


def analyze_stdin(*, analyzer: QueryAnalyzer | None = None) -> list[AnalysisResult]:
    """Read SQL from stdin and analyze."""
    content = sys.stdin.read()
    return analyze_sql_content(content, analyzer=analyzer)
