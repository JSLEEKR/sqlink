"""Rule definitions for SQL anti-pattern detection."""

from __future__ import annotations

from dataclasses import dataclass

from sqlink.models import Severity


@dataclass
class Rule:
    """A rule for detecting SQL anti-patterns."""

    id: str
    title: str
    description: str
    severity: Severity
    suggestion: str
    category: str


# All built-in rules
RULES: dict[str, Rule] = {}


def _register(rule: Rule) -> Rule:
    RULES[rule.id] = rule
    return rule


# === Query Structure Rules ===

SELECT_STAR = _register(Rule(
    id="SQ001",
    title="SELECT * detected",
    description="Using SELECT * fetches all columns, which wastes bandwidth and prevents covering index optimization.",
    severity=Severity.WARNING,
    suggestion="List only the columns you need: SELECT col1, col2 FROM ...",
    category="query_structure",
))

MISSING_WHERE = _register(Rule(
    id="SQ002",
    title="Missing WHERE clause",
    description="Query modifies or reads all rows without filtering. This can be extremely slow on large tables.",
    severity=Severity.ERROR,
    suggestion="Add a WHERE clause to limit the scope of the operation.",
    category="query_structure",
))

SELECT_DISTINCT_SMELL = _register(Rule(
    id="SQ003",
    title="DISTINCT may indicate a join issue",
    description="DISTINCT is sometimes used to mask duplicate rows caused by incorrect joins.",
    severity=Severity.INFO,
    suggestion="Verify that your joins are correct and DISTINCT is truly necessary.",
    category="query_structure",
))

OFFSET_PAGINATION = _register(Rule(
    id="SQ004",
    title="OFFSET-based pagination detected",
    description="OFFSET pagination becomes slower as offset grows because the database must scan and discard rows.",
    severity=Severity.WARNING,
    suggestion="Use keyset/cursor pagination: WHERE id > :last_seen_id ORDER BY id LIMIT :page_size",
    category="query_structure",
))

IMPLICIT_CROSS_JOIN = _register(Rule(
    id="SQ005",
    title="Implicit cross join (comma join)",
    description="Multiple tables in FROM without explicit JOIN creates a cross join, producing a cartesian product.",
    severity=Severity.ERROR,
    suggestion="Use explicit JOIN syntax with ON conditions.",
    category="query_structure",
))

TOO_MANY_JOINS = _register(Rule(
    id="SQ006",
    title="Too many joins",
    description="Queries with many joins are hard to optimize and may indicate denormalization opportunities.",
    severity=Severity.WARNING,
    suggestion="Consider denormalizing, using materialized views, or breaking into multiple queries.",
    category="query_structure",
))

UNION_WITHOUT_ALL = _register(Rule(
    id="SQ007",
    title="UNION without ALL",
    description="UNION (without ALL) requires sorting and deduplication. Use UNION ALL if duplicates are acceptable.",
    severity=Severity.INFO,
    suggestion="Use UNION ALL if you don't need duplicate elimination.",
    category="query_structure",
))

# === WHERE Clause Rules ===

FUNCTION_ON_INDEXED_COLUMN = _register(Rule(
    id="WH001",
    title="Function applied to column in WHERE",
    description="Applying a function to a column in WHERE prevents index usage (non-sargable predicate).",
    severity=Severity.ERROR,
    suggestion="Rewrite to apply the function to the value instead: WHERE col >= '2024-01-01' instead of WHERE DATE(col) = '2024-01-01'",
    category="where_clause",
))

LEADING_WILDCARD = _register(Rule(
    id="WH002",
    title="LIKE with leading wildcard",
    description="LIKE '%pattern' or LIKE '%pattern%' prevents index usage and causes full table scan.",
    severity=Severity.ERROR,
    suggestion="Use full-text search, trigram indexes, or restructure to avoid leading wildcards.",
    category="where_clause",
))

OR_CONDITIONS = _register(Rule(
    id="WH003",
    title="OR conditions may prevent index usage",
    description="OR conditions on different columns can prevent the optimizer from using indexes effectively.",
    severity=Severity.WARNING,
    suggestion="Consider using UNION ALL to combine separate indexed queries, or create a composite index.",
    category="where_clause",
))

NOT_EQUAL_FILTER = _register(Rule(
    id="WH004",
    title="NOT EQUAL (!= / <>) may cause full scan",
    description="Inequality filters typically cannot use indexes effectively and may scan the entire table.",
    severity=Severity.INFO,
    suggestion="If possible, rewrite as a positive condition or use a different filtering strategy.",
    category="where_clause",
))

IS_NULL_CHECK = _register(Rule(
    id="WH005",
    title="IS NULL check detected",
    description="IS NULL checks can be inefficient if the column is not indexed for NULL values.",
    severity=Severity.INFO,
    suggestion="Consider using a default value instead of NULL, or ensure partial index covers NULL.",
    category="where_clause",
))

IN_SUBQUERY = _register(Rule(
    id="WH006",
    title="IN with subquery detected",
    description="IN (SELECT ...) can be less efficient than EXISTS or a JOIN in some databases.",
    severity=Severity.WARNING,
    suggestion="Consider rewriting as EXISTS or a JOIN for better performance.",
    category="where_clause",
))

# === EXPLAIN Analysis Rules ===

FULL_TABLE_SCAN = _register(Rule(
    id="EX001",
    title="Full table scan detected",
    description="Sequential/full table scan reads every row. This is slow on large tables.",
    severity=Severity.ERROR,
    suggestion="Add an index on the filtered/joined columns, or review the WHERE clause.",
    category="explain",
))

HIGH_COST = _register(Rule(
    id="EX002",
    title="High estimated cost",
    description="The query optimizer estimates a high cost for this operation.",
    severity=Severity.WARNING,
    suggestion="Review the query plan and consider adding indexes or restructuring the query.",
    category="explain",
))

LARGE_ROW_ESTIMATE = _register(Rule(
    id="EX003",
    title="Large row estimate",
    description="The query is estimated to process a large number of rows.",
    severity=Severity.WARNING,
    suggestion="Add more selective filters or indexes to reduce the number of rows processed.",
    category="explain",
))

NESTED_LOOP_LARGE = _register(Rule(
    id="EX004",
    title="Nested loop on large dataset",
    description="Nested loop joins are O(n*m) and become very slow with large datasets.",
    severity=Severity.ERROR,
    suggestion="Ensure join columns are indexed, or consider hash/merge join strategies.",
    category="explain",
))

SORT_WITHOUT_INDEX = _register(Rule(
    id="EX005",
    title="Sort operation detected",
    description="Explicit sort operation found. This can be expensive for large result sets.",
    severity=Severity.INFO,
    suggestion="Add an index that covers the ORDER BY columns to avoid the sort step.",
    category="explain",
))

ACTUAL_VS_ESTIMATED_MISMATCH = _register(Rule(
    id="EX006",
    title="Row estimate mismatch",
    description="Large difference between estimated and actual rows indicates stale statistics.",
    severity=Severity.WARNING,
    suggestion="Run ANALYZE on the table to update statistics.",
    category="explain",
))

# === N+1 Detection Rules ===

N_PLUS_ONE = _register(Rule(
    id="NP001",
    title="Potential N+1 query pattern",
    description="Multiple similar queries with different parameters suggest an N+1 problem.",
    severity=Severity.CRITICAL,
    suggestion="Use a JOIN, eager loading, or batch the queries with IN clause.",
    category="n_plus_one",
))

REPEATED_QUERY = _register(Rule(
    id="NP002",
    title="Repeated identical query",
    description="The same query is executed multiple times, wasting database resources.",
    severity=Severity.WARNING,
    suggestion="Cache the result or restructure to execute once.",
    category="n_plus_one",
))

# === Schema / Design Rules ===

MISSING_LIMIT = _register(Rule(
    id="SD001",
    title="SELECT without LIMIT",
    description="Unbounded SELECT may return millions of rows, consuming memory and bandwidth.",
    severity=Severity.WARNING,
    suggestion="Add LIMIT to cap result size, especially for user-facing queries.",
    category="schema_design",
))

ORDER_WITHOUT_LIMIT = _register(Rule(
    id="SD002",
    title="ORDER BY without LIMIT",
    description="Sorting all rows without limiting is wasteful if you only need the top N.",
    severity=Severity.INFO,
    suggestion="Add LIMIT if you don't need all sorted results.",
    category="schema_design",
))

HAVING_WITHOUT_GROUP = _register(Rule(
    id="SD003",
    title="HAVING without GROUP BY",
    description="HAVING without GROUP BY applies to the entire result as one group — likely a mistake.",
    severity=Severity.ERROR,
    suggestion="Use WHERE for row-level filtering, or add GROUP BY.",
    category="schema_design",
))


def get_rule(rule_id: str) -> Rule | None:
    """Get a rule by ID."""
    return RULES.get(rule_id)


def get_rules_by_category(category: str) -> list[Rule]:
    """Get all rules in a category."""
    return [r for r in RULES.values() if r.category == category]


def get_all_categories() -> list[str]:
    """Get all rule categories."""
    return sorted(set(r.category for r in RULES.values()))
