"""Parser for EXPLAIN output (PostgreSQL and MySQL formats)."""

from __future__ import annotations

import json
import re

from sqlink.models import ExplainNode, ExplainResult, ScanType


def detect_dialect(explain_text: str) -> str:
    """Detect whether EXPLAIN output is PostgreSQL or MySQL format."""
    text = explain_text.strip()

    # JSON format (PostgreSQL EXPLAIN (FORMAT JSON))
    if text.startswith("[") or text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, list) and data and "Plan" in data[0]:
                return "postgresql"
            if isinstance(data, dict) and "query_block" in data:
                return "mysql"
        except json.JSONDecodeError:
            pass

    # PostgreSQL text format markers
    if re.search(r"(Seq Scan|Index Scan|Bitmap Heap Scan|Hash Join|Merge Join|Nested Loop)\s+on\b", text):
        return "postgresql"
    if re.search(r"->", text) and re.search(r"\bcost=[\d.]+\.\.[\d.]+\b", text):
        return "postgresql"

    # MySQL EXPLAIN markers
    if re.search(r"\b(type|possible_keys|key|rows|Extra)\b", text) and re.search(r"\b(ALL|ref|range|index|const|eq_ref)\b", text):
        return "mysql"
    if "select_type" in text or "table" in text.split("\n")[0]:
        return "mysql"

    return "unknown"


def _parse_scan_type(type_str: str) -> ScanType:
    """Map a string to a ScanType."""
    type_map = {
        "seq scan": ScanType.SEQ_SCAN,
        "index scan": ScanType.INDEX_SCAN,
        "index only scan": ScanType.INDEX_ONLY_SCAN,
        "bitmap heap scan": ScanType.BITMAP_SCAN,
        "bitmap index scan": ScanType.BITMAP_INDEX_SCAN,
        "nested loop": ScanType.NESTED_LOOP,
        "hash join": ScanType.HASH_JOIN,
        "merge join": ScanType.MERGE_JOIN,
        "sort": ScanType.SORT,
        "hash": ScanType.HASH,
        "aggregate": ScanType.AGGREGATE,
        "materialize": ScanType.MATERIALIZE,
        "subquery scan": ScanType.SUBQUERY_SCAN,
        # MySQL types
        "all": ScanType.FULL_TABLE_SCAN,
    }
    lower = type_str.strip().lower()
    return type_map.get(lower, ScanType.UNKNOWN)


def parse_postgresql_text(text: str) -> ExplainResult:
    """Parse PostgreSQL text-format EXPLAIN output."""
    lines = text.strip().split("\n")
    nodes: list[ExplainNode] = []
    planning_time = None
    execution_time = None

    for line in lines:
        stripped = line.strip()

        # Planning/Execution time
        pt_match = re.match(r"Planning\s+[Tt]ime:\s+([\d.]+)\s*ms", stripped)
        if pt_match:
            planning_time = float(pt_match.group(1))
            continue

        et_match = re.match(r"Execution\s+[Tt]ime:\s+([\d.]+)\s*ms", stripped)
        if et_match:
            execution_time = float(et_match.group(1))
            continue

        # Parse node line
        node_match = re.match(
            r"(?:->)?\s*(.+?)\s+on\s+(\S+)(?:\s+(\S+))?\s*"
            r"\(cost=([\d.]+)\.\.([\d.]+)\s+rows=(\d+)\s+width=(\d+)\)",
            stripped,
        )
        if node_match:
            scan_type = _parse_scan_type(node_match.group(1))
            table = node_match.group(2)
            index_or_alias = node_match.group(3)
            cost = float(node_match.group(5))
            rows = int(node_match.group(6))
            width = int(node_match.group(7))

            node = ExplainNode(
                scan_type=scan_type,
                table=table,
                cost=cost,
                rows=rows,
                width=width,
            )
            if index_or_alias and scan_type in (ScanType.INDEX_SCAN, ScanType.INDEX_ONLY_SCAN, ScanType.BITMAP_INDEX_SCAN):
                node.index = index_or_alias
            nodes.append(node)
            continue

        # Simpler node pattern without table
        simple_match = re.match(
            r"(?:->)?\s*(.+?)\s*\(cost=([\d.]+)\.\.([\d.]+)\s+rows=(\d+)\s+width=(\d+)\)",
            stripped,
        )
        if simple_match:
            scan_type = _parse_scan_type(simple_match.group(1))
            if scan_type != ScanType.UNKNOWN:
                cost = float(simple_match.group(3))
                rows = int(simple_match.group(4))
                width = int(simple_match.group(5))
                node = ExplainNode(scan_type=scan_type, cost=cost, rows=rows, width=width)
                nodes.append(node)
                continue

        # Actual time line
        actual_match = re.search(
            r"actual time=([\d.]+)\.\.([\d.]+)\s+rows=(\d+)\s+loops=(\d+)",
            stripped,
        )
        if actual_match and nodes:
            nodes[-1].actual_time = float(actual_match.group(2))
            nodes[-1].actual_rows = int(actual_match.group(3))
            nodes[-1].loops = int(actual_match.group(4))

        # Filter line
        filter_match = re.match(r"Filter:\s+(.+)", stripped)
        if filter_match and nodes:
            nodes[-1].filter = filter_match.group(1)

    total_cost = max((n.cost or 0) for n in nodes) if nodes else None

    return ExplainResult(
        raw=text,
        nodes=nodes,
        total_cost=total_cost,
        planning_time=planning_time,
        execution_time=execution_time,
        dialect="postgresql",
    )


def parse_postgresql_json(text: str) -> ExplainResult:
    """Parse PostgreSQL JSON-format EXPLAIN output."""
    data = json.loads(text)
    if isinstance(data, list):
        plan_data = data[0]
    else:
        plan_data = data

    planning_time = plan_data.get("Planning Time")
    execution_time = plan_data.get("Execution Time")

    nodes: list[ExplainNode] = []

    def _walk_plan(plan: dict) -> None:
        node_type = plan.get("Node Type", "Unknown")
        scan_type = _parse_scan_type(node_type)

        node = ExplainNode(
            scan_type=scan_type,
            table=plan.get("Relation Name"),
            index=plan.get("Index Name"),
            rows=plan.get("Plan Rows"),
            cost=plan.get("Total Cost"),
            actual_time=plan.get("Actual Total Time"),
            actual_rows=plan.get("Actual Rows"),
            loops=plan.get("Actual Loops"),
            filter=plan.get("Filter"),
            width=plan.get("Plan Width"),
        )
        nodes.append(node)

        for child in plan.get("Plans", []):
            _walk_plan(child)

    if "Plan" in plan_data:
        _walk_plan(plan_data["Plan"])

    total_cost = max((n.cost or 0) for n in nodes) if nodes else None

    return ExplainResult(
        raw=text,
        nodes=nodes,
        total_cost=total_cost,
        planning_time=planning_time,
        execution_time=execution_time,
        dialect="postgresql",
    )


def parse_mysql_tabular(text: str) -> ExplainResult:
    """Parse MySQL tabular EXPLAIN output."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip() and not l.strip().startswith("+")]

    if not lines:
        return ExplainResult(raw=text, dialect="mysql")

    # Find header — split by | and strip
    header_line = lines[0].strip("|")
    headers = [h.strip().lower() for h in header_line.split("|") if h.strip()]

    if not headers:
        return ExplainResult(raw=text, dialect="mysql")

    nodes: list[ExplainNode] = []
    for line in lines[1:]:
        line_stripped = line.strip("|")
        values = [v.strip() for v in line_stripped.split("|")]
        # Pad with empty strings if trailing fields are empty
        while len(values) < len(headers):
            values.append("")
        if not any(values):
            continue

        row = dict(zip(headers, values))

        type_val = row.get("type", "ALL")
        scan_type = _parse_scan_type(type_val)
        if type_val.lower() == "ref":
            scan_type = ScanType.INDEX_SCAN
        elif type_val.lower() == "range":
            scan_type = ScanType.INDEX_SCAN
        elif type_val.lower() in ("const", "eq_ref"):
            scan_type = ScanType.INDEX_SCAN

        rows_val = row.get("rows")
        try:
            rows = int(rows_val) if rows_val and rows_val != "NULL" else None
        except ValueError:
            rows = None

        node = ExplainNode(
            scan_type=scan_type,
            table=row.get("table"),
            index=row.get("key"),
            rows=rows,
            extra={"raw_type": type_val, "extra": row.get("extra", "")},
        )
        nodes.append(node)

    return ExplainResult(raw=text, nodes=nodes, dialect="mysql")


def parse_mysql_json(text: str) -> ExplainResult:
    """Parse MySQL JSON-format EXPLAIN output."""
    data = json.loads(text)
    nodes: list[ExplainNode] = []

    def _walk_block(block: dict) -> None:
        table = block.get("table", {})
        if isinstance(table, dict):
            access_type = table.get("access_type", "ALL")
            scan_type = _parse_scan_type(access_type)
            if access_type in ("ref", "range", "const", "eq_ref"):
                scan_type = ScanType.INDEX_SCAN

            rows = table.get("rows_examined_per_scan") or table.get("rows_produced_per_join")
            node = ExplainNode(
                scan_type=scan_type,
                table=table.get("table_name"),
                index=table.get("key"),
                rows=rows,
            )
            nodes.append(node)

        # Nested blocks
        for nested in block.get("nested_loop", []):
            _walk_block(nested)

        # Ordering operations
        if "ordering_operation" in block:
            _walk_block(block["ordering_operation"])

    if "query_block" in data:
        _walk_block(data["query_block"])

    return ExplainResult(raw=text, nodes=nodes, dialect="mysql")


def parse_explain(text: str) -> ExplainResult:
    """Parse EXPLAIN output, auto-detecting format and dialect."""
    text = text.strip()
    if not text:
        return ExplainResult(raw=text)

    dialect = detect_dialect(text)

    # Try JSON first
    if text.startswith("[") or text.startswith("{"):
        try:
            if dialect == "mysql":
                return parse_mysql_json(text)
            return parse_postgresql_json(text)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    if dialect == "postgresql":
        return parse_postgresql_text(text)

    if dialect == "mysql":
        return parse_mysql_tabular(text)

    # Fallback: try PostgreSQL text format
    result = parse_postgresql_text(text)
    if result.nodes:
        return result

    # Try MySQL tabular
    result = parse_mysql_tabular(text)
    if result.nodes:
        return result

    return ExplainResult(raw=text, dialect="unknown")
