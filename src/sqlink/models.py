"""Data models for sqlink."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Severity(enum.Enum):
    """Severity levels for findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        order = [Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.CRITICAL]
        return order.index(self) < order.index(other)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self == other or self < other


class QueryType(enum.Enum):
    """Type of SQL query."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    UNKNOWN = "UNKNOWN"


class JoinType(enum.Enum):
    """Type of SQL join."""

    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL"
    CROSS = "CROSS"
    NATURAL = "NATURAL"


class ScanType(enum.Enum):
    """Type of scan in EXPLAIN output."""

    SEQ_SCAN = "Seq Scan"
    INDEX_SCAN = "Index Scan"
    INDEX_ONLY_SCAN = "Index Only Scan"
    BITMAP_SCAN = "Bitmap Heap Scan"
    BITMAP_INDEX_SCAN = "Bitmap Index Scan"
    NESTED_LOOP = "Nested Loop"
    HASH_JOIN = "Hash Join"
    MERGE_JOIN = "Merge Join"
    SORT = "Sort"
    HASH = "Hash"
    AGGREGATE = "Aggregate"
    MATERIALIZE = "Materialize"
    SUBQUERY_SCAN = "Subquery Scan"
    FULL_TABLE_SCAN = "ALL"  # MySQL
    UNKNOWN = "Unknown"


@dataclass
class TableReference:
    """A reference to a table in a query."""

    name: str
    alias: str | None = None
    schema: str | None = None

    @property
    def full_name(self) -> str:
        if self.schema:
            return f"{self.schema}.{self.name}"
        return self.name

    @property
    def effective_name(self) -> str:
        return self.alias or self.name


@dataclass
class ColumnReference:
    """A reference to a column in a query."""

    name: str
    table: str | None = None

    @property
    def full_name(self) -> str:
        if self.table:
            return f"{self.table}.{self.name}"
        return self.name


@dataclass
class JoinClause:
    """A JOIN clause in a query."""

    join_type: JoinType
    table: TableReference
    condition: str | None = None


@dataclass
class WhereCondition:
    """A condition in a WHERE clause."""

    raw: str
    columns: list[ColumnReference] = field(default_factory=list)
    has_function: bool = False
    has_or: bool = False
    has_like_wildcard_prefix: bool = False
    has_not_equal: bool = False
    has_is_null: bool = False
    has_in_subquery: bool = False


@dataclass
class SubQuery:
    """A subquery within a query."""

    raw: str
    location: str = ""  # WHERE, FROM, SELECT, etc.


@dataclass
class ParsedQuery:
    """Result of parsing a SQL query."""

    raw: str
    query_type: QueryType = QueryType.UNKNOWN
    tables: list[TableReference] = field(default_factory=list)
    columns: list[ColumnReference] = field(default_factory=list)
    joins: list[JoinClause] = field(default_factory=list)
    where_conditions: list[WhereCondition] = field(default_factory=list)
    has_select_star: bool = False
    has_distinct: bool = False
    has_group_by: bool = False
    has_order_by: bool = False
    has_limit: bool = False
    has_offset: bool = False
    has_having: bool = False
    has_union: bool = False
    subqueries: list[SubQuery] = field(default_factory=list)
    group_by_columns: list[ColumnReference] = field(default_factory=list)
    order_by_columns: list[ColumnReference] = field(default_factory=list)


@dataclass
class ExplainNode:
    """A node in an EXPLAIN output tree."""

    scan_type: ScanType
    table: str | None = None
    index: str | None = None
    rows: int | None = None
    cost: float | None = None
    actual_time: float | None = None
    actual_rows: int | None = None
    loops: int | None = None
    filter: str | None = None
    width: int | None = None
    children: list[ExplainNode] = field(default_factory=list)
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class ExplainResult:
    """Parsed EXPLAIN output."""

    raw: str
    nodes: list[ExplainNode] = field(default_factory=list)
    total_cost: float | None = None
    planning_time: float | None = None
    execution_time: float | None = None
    dialect: str = "unknown"  # postgresql, mysql


@dataclass
class Finding:
    """A finding from the analysis."""

    rule_id: str
    title: str
    description: str
    severity: Severity
    suggestion: str
    location: str = ""
    context: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "suggestion": self.suggestion,
            "location": self.location,
            "context": self.context,
            "metadata": self.metadata,
        }


@dataclass
class AnalysisResult:
    """Complete analysis result."""

    query: str
    findings: list[Finding] = field(default_factory=list)
    parsed_query: ParsedQuery | None = None
    explain_result: ExplainResult | None = None
    score: int = 100  # 0-100, lower = worse

    @property
    def has_issues(self) -> bool:
        return len(self.findings) > 0

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.INFO)

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "score": self.score,
            "findings": [f.to_dict() for f in self.findings],
            "summary": {
                "critical": self.critical_count,
                "error": self.error_count,
                "warning": self.warning_count,
                "info": self.info_count,
                "total": len(self.findings),
            },
        }
