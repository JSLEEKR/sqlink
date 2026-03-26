"""Query log parser — parse PostgreSQL and MySQL slow query logs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LogEntry:
    """A parsed log entry."""

    query: str
    duration_ms: float | None = None
    timestamp: str | None = None
    user: str | None = None
    database: str | None = None
    rows_examined: int | None = None
    rows_sent: int | None = None
    source: str = ""  # filename:line

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "user": self.user,
            "database": self.database,
            "rows_examined": self.rows_examined,
            "rows_sent": self.rows_sent,
            "source": self.source,
        }


@dataclass
class LogSummary:
    """Summary of parsed log entries."""

    total_entries: int = 0
    total_duration_ms: float = 0.0
    slowest_queries: list[LogEntry] = field(default_factory=list)
    most_frequent: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "total_entries": self.total_entries,
            "total_duration_ms": self.total_duration_ms,
            "avg_duration_ms": self.total_duration_ms / self.total_entries if self.total_entries else 0,
            "slowest_queries": [e.to_dict() for e in self.slowest_queries],
            "most_frequent": self.most_frequent,
        }


def parse_postgresql_log(content: str) -> list[LogEntry]:
    """Parse PostgreSQL log format.

    Expected format:
    2024-01-15 10:30:45.123 UTC [1234] user@db LOG:  duration: 123.456 ms  statement: SELECT ...
    """
    entries: list[LogEntry] = []

    pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[\d.]*)\s+"
        r"(?:\w+\s+)?"  # timezone
        r"(?:\[\d+\]\s+)?"  # PID
        r"(?:(\w+)@(\w+)\s+)?"  # user@db
        r"LOG:\s+duration:\s+([\d.]+)\s+ms\s+"
        r"(?:statement|execute[^:]*?):\s+(.+?)(?:\n(?!\d{4})|$)",
        re.DOTALL,
    )

    for match in pattern.finditer(content):
        entries.append(LogEntry(
            query=match.group(5).strip(),
            duration_ms=float(match.group(4)),
            timestamp=match.group(1),
            user=match.group(2),
            database=match.group(3),
        ))

    # Fallback: simpler format
    if not entries:
        simple_pattern = re.compile(
            r"duration:\s+([\d.]+)\s+ms\s+(?:statement|execute[^:]*?):\s+(.+?)(?:\n\n|\Z)",
            re.DOTALL,
        )
        for match in simple_pattern.finditer(content):
            entries.append(LogEntry(
                query=match.group(2).strip(),
                duration_ms=float(match.group(1)),
            ))

    return entries


def parse_mysql_slow_log(content: str) -> list[LogEntry]:
    """Parse MySQL slow query log format.

    Expected format:
    # Time: 2024-01-15T10:30:45.123456Z
    # User@Host: user[user] @ localhost []  Id:  1234
    # Query_time: 1.234567  Lock_time: 0.000123 Rows_sent: 100  Rows_examined: 50000
    SET timestamp=1705312245;
    SELECT ...;
    """
    entries: list[LogEntry] = []
    blocks = re.split(r"(?=# Time:)", content)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        time_match = re.search(r"# Time:\s+(.+)", block)
        user_match = re.search(r"# User@Host:\s+(\w+)", block)
        query_match = re.search(
            r"# Query_time:\s+([\d.]+)\s+Lock_time:\s+[\d.]+\s+"
            r"Rows_sent:\s+(\d+)\s+Rows_examined:\s+(\d+)",
            block,
        )

        # Extract the actual SQL (after SET timestamp or after the # lines)
        sql_match = re.search(r"(?:SET timestamp=\d+;\n)?([^#].+?)(?:;\s*$|\Z)", block, re.DOTALL)
        if not sql_match:
            continue

        query = sql_match.group(1).strip().rstrip(";")
        if not query or query.startswith("#"):
            continue

        entry = LogEntry(query=query)
        if time_match:
            entry.timestamp = time_match.group(1).strip()
        if user_match:
            entry.user = user_match.group(1)
        if query_match:
            entry.duration_ms = float(query_match.group(1)) * 1000  # convert seconds to ms
            entry.rows_sent = int(query_match.group(2))
            entry.rows_examined = int(query_match.group(3))

        entries.append(entry)

    return entries


def parse_log(content: str) -> list[LogEntry]:
    """Auto-detect log format and parse."""
    if "# Time:" in content or "# Query_time:" in content:
        return parse_mysql_slow_log(content)
    if "duration:" in content and ("statement:" in content or "execute" in content):
        return parse_postgresql_log(content)

    # Try both
    entries = parse_postgresql_log(content)
    if entries:
        return entries
    return parse_mysql_slow_log(content)


def summarize_log(entries: list[LogEntry], *, top_n: int = 10) -> LogSummary:
    """Create a summary of log entries."""
    summary = LogSummary(total_entries=len(entries))

    for entry in entries:
        if entry.duration_ms:
            summary.total_duration_ms += entry.duration_ms

    # Top N slowest
    sorted_by_time = sorted(
        [e for e in entries if e.duration_ms is not None],
        key=lambda e: e.duration_ms or 0,
        reverse=True,
    )
    summary.slowest_queries = sorted_by_time[:top_n]

    # Most frequent (by fingerprint)
    from sqlink.fingerprint import fingerprint, normalize_for_fingerprint

    freq: dict[str, dict[str, object]] = {}
    for entry in entries:
        fp = fingerprint(entry.query)
        if fp not in freq:
            freq[fp] = {
                "fingerprint": fp,
                "normalized": normalize_for_fingerprint(entry.query),
                "count": 0,
                "total_duration_ms": 0.0,
                "example": entry.query[:200],
            }
        freq[fp]["count"] += 1
        if entry.duration_ms:
            freq[fp]["total_duration_ms"] += entry.duration_ms

    sorted_freq = sorted(freq.values(), key=lambda x: -x["count"])
    summary.most_frequent = sorted_freq[:top_n]

    return summary
