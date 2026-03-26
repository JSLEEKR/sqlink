"""Query pattern library — common SQL patterns and anti-patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class PatternType(Enum):
    """Type of pattern."""
    ANTI_PATTERN = "anti_pattern"
    BEST_PRACTICE = "best_practice"


@dataclass
class Pattern:
    """A SQL pattern or anti-pattern."""

    id: str
    name: str
    description: str
    pattern_type: PatternType
    regex: str  # regex to match against normalized SQL
    example_bad: str = ""
    example_good: str = ""
    tags: list[str] = field(default_factory=list)

    def matches(self, sql: str) -> bool:
        """Check if the SQL matches this pattern."""
        return bool(re.search(self.regex, sql, re.IGNORECASE))


# Built-in patterns
PATTERNS: dict[str, Pattern] = {}


def _register(p: Pattern) -> Pattern:
    PATTERNS[p.id] = p
    return p


# Anti-patterns

_register(Pattern(
    id="AP001",
    name="SELECT COUNT(*) for existence check",
    description="Using COUNT(*) just to check if rows exist is wasteful. Use EXISTS instead.",
    pattern_type=PatternType.ANTI_PATTERN,
    regex=r"\bSELECT\s+COUNT\s*\(\s*\*\s*\)\s+FROM\b",
    example_bad="SELECT COUNT(*) FROM users WHERE email = 'x'",
    example_good="SELECT EXISTS (SELECT 1 FROM users WHERE email = 'x')",
    tags=["performance", "existence"],
))

_register(Pattern(
    id="AP002",
    name="ORDER BY RAND()",
    description="ORDER BY RAND() is extremely slow on large tables. It generates a random value for every row.",
    pattern_type=PatternType.ANTI_PATTERN,
    regex=r"\bORDER\s+BY\s+RAND\s*\(\s*\)",
    example_bad="SELECT * FROM products ORDER BY RAND() LIMIT 10",
    example_good="SELECT * FROM products WHERE id >= (SELECT FLOOR(RAND() * MAX(id)) FROM products) LIMIT 10",
    tags=["performance", "random"],
))

_register(Pattern(
    id="AP003",
    name="SELECT for UPDATE without WHERE",
    description="SELECT ... FOR UPDATE without WHERE locks the entire table.",
    pattern_type=PatternType.ANTI_PATTERN,
    regex=r"\bSELECT\b(?!.*\bWHERE\b).+\bFOR\s+UPDATE\b",
    example_bad="SELECT * FROM accounts FOR UPDATE",
    example_good="SELECT * FROM accounts WHERE id = 1 FOR UPDATE",
    tags=["locking", "concurrency"],
))

_register(Pattern(
    id="AP004",
    name="Correlated subquery in SELECT",
    description="Correlated subqueries in SELECT execute once per row, causing N+1 behavior.",
    pattern_type=PatternType.ANTI_PATTERN,
    regex=r"\bSELECT\b[^;]*,\s*\(\s*SELECT\b",
    example_bad="SELECT u.name, (SELECT COUNT(*) FROM orders WHERE user_id = u.id) FROM users u",
    example_good="SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.name",
    tags=["performance", "n+1"],
))

_register(Pattern(
    id="AP005",
    name="NOT IN with NULLs risk",
    description="NOT IN with a subquery that may return NULL gives unexpected results (no rows match).",
    pattern_type=PatternType.ANTI_PATTERN,
    regex=r"\bNOT\s+IN\s*\(\s*SELECT\b",
    example_bad="SELECT * FROM t WHERE id NOT IN (SELECT nullable_col FROM t2)",
    example_good="SELECT * FROM t WHERE NOT EXISTS (SELECT 1 FROM t2 WHERE t2.id = t.id)",
    tags=["correctness", "null"],
))

_register(Pattern(
    id="AP006",
    name="Implicit type conversion",
    description="Comparing string column with number causes implicit conversion, preventing index use.",
    pattern_type=PatternType.ANTI_PATTERN,
    regex=r"\bWHERE\b[^;]*\w+\s*=\s*\d+\b",
    example_bad="SELECT * FROM users WHERE phone = 1234567890",
    example_good="SELECT * FROM users WHERE phone = '1234567890'",
    tags=["performance", "type"],
))

_register(Pattern(
    id="AP007",
    name="Multiple COUNT with CASE",
    description="Using multiple COUNT(CASE WHEN ...) can often be replaced with a single filtered aggregation.",
    pattern_type=PatternType.ANTI_PATTERN,
    regex=r"\bCOUNT\s*\(\s*CASE\b.*\bCOUNT\s*\(\s*CASE\b",
    example_bad="SELECT COUNT(CASE WHEN status='a' THEN 1 END), COUNT(CASE WHEN status='b' THEN 1 END) FROM t",
    example_good="SELECT status, COUNT(*) FROM t GROUP BY status",
    tags=["readability"],
))

# Best practices

_register(Pattern(
    id="BP001",
    name="EXISTS for existence check",
    description="Using EXISTS is the optimal way to check if matching rows exist.",
    pattern_type=PatternType.BEST_PRACTICE,
    regex=r"\bEXISTS\s*\(\s*SELECT\s+1\b",
    tags=["performance", "existence"],
))

_register(Pattern(
    id="BP002",
    name="Explicit column list in INSERT",
    description="Always list column names in INSERT statements for clarity and safety.",
    pattern_type=PatternType.BEST_PRACTICE,
    regex=r"\bINSERT\s+INTO\s+\w+\s*\([^)]+\)\s*VALUES\b",
    tags=["readability", "safety"],
))

_register(Pattern(
    id="BP003",
    name="COALESCE for default values",
    description="Using COALESCE to provide default values for nullable columns.",
    pattern_type=PatternType.BEST_PRACTICE,
    regex=r"\bCOALESCE\s*\(",
    tags=["null-handling"],
))


def match_patterns(sql: str) -> list[Pattern]:
    """Find all patterns that match the given SQL."""
    return [p for p in PATTERNS.values() if p.matches(sql)]


def match_anti_patterns(sql: str) -> list[Pattern]:
    """Find all anti-patterns in the SQL."""
    return [p for p in PATTERNS.values() if p.pattern_type == PatternType.ANTI_PATTERN and p.matches(sql)]


def match_best_practices(sql: str) -> list[Pattern]:
    """Find all best practices followed in the SQL."""
    return [p for p in PATTERNS.values() if p.pattern_type == PatternType.BEST_PRACTICE and p.matches(sql)]


def get_pattern(pattern_id: str) -> Pattern | None:
    """Get a pattern by ID."""
    return PATTERNS.get(pattern_id)


def get_all_patterns() -> list[Pattern]:
    """Get all patterns."""
    return list(PATTERNS.values())
