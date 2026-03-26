"""Report generation for sqlink analysis results."""

from __future__ import annotations

import json

from sqlink.models import AnalysisResult, Severity


SEVERITY_ICONS = {
    Severity.CRITICAL: "[CRITICAL]",
    Severity.ERROR: "[ERROR]",
    Severity.WARNING: "[WARNING]",
    Severity.INFO: "[INFO]",
}

SEVERITY_COLORS = {
    Severity.CRITICAL: "\033[91m",  # bright red
    Severity.ERROR: "\033[31m",      # red
    Severity.WARNING: "\033[33m",    # yellow
    Severity.INFO: "\033[36m",       # cyan
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def format_text(result: AnalysisResult, *, color: bool = True) -> str:
    """Format analysis result as human-readable text."""
    lines: list[str] = []

    # Header
    score_color = ""
    if color:
        if result.score >= 80:
            score_color = "\033[32m"  # green
        elif result.score >= 50:
            score_color = "\033[33m"  # yellow
        else:
            score_color = "\033[31m"  # red

    if color:
        lines.append(f"{BOLD}sqlink Analysis Report{RESET}")
        lines.append(f"{DIM}{'=' * 60}{RESET}")
    else:
        lines.append("sqlink Analysis Report")
        lines.append("=" * 60)

    # Query preview
    query_preview = result.query[:100].replace("\n", " ")
    if len(result.query) > 100:
        query_preview += "..."
    lines.append(f"Query: {query_preview}")
    lines.append("")

    # Score
    if color:
        lines.append(f"Score: {score_color}{result.score}/100{RESET}")
    else:
        lines.append(f"Score: {result.score}/100")

    # Summary
    summary_parts = []
    if result.critical_count:
        summary_parts.append(f"{result.critical_count} critical")
    if result.error_count:
        summary_parts.append(f"{result.error_count} errors")
    if result.warning_count:
        summary_parts.append(f"{result.warning_count} warnings")
    if result.info_count:
        summary_parts.append(f"{result.info_count} info")

    if summary_parts:
        lines.append(f"Findings: {', '.join(summary_parts)}")
    else:
        lines.append("No issues found!")

    lines.append("")

    # Findings
    sorted_findings = sorted(result.findings, key=lambda f: f.severity, reverse=True)
    for f in sorted_findings:
        icon = SEVERITY_ICONS[f.severity]
        if color:
            c = SEVERITY_COLORS[f.severity]
            lines.append(f"{c}{icon}{RESET} {BOLD}{f.title}{RESET} ({f.rule_id})")
        else:
            lines.append(f"{icon} {f.title} ({f.rule_id})")

        lines.append(f"  {f.description}")
        if f.context:
            if color:
                lines.append(f"  {DIM}Context: {f.context}{RESET}")
            else:
                lines.append(f"  Context: {f.context}")
        lines.append(f"  Suggestion: {f.suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_json(result: AnalysisResult, *, indent: int = 2) -> str:
    """Format analysis result as JSON."""
    return json.dumps(result.to_dict(), indent=indent)


def format_batch_text(results: list[AnalysisResult], *, color: bool = True) -> str:
    """Format a batch of analysis results."""
    lines: list[str] = []

    if color:
        lines.append(f"{BOLD}sqlink Batch Analysis Report{RESET}")
        lines.append(f"{DIM}{'=' * 60}{RESET}")
    else:
        lines.append("sqlink Batch Analysis Report")
        lines.append("=" * 60)

    total_findings = sum(len(r.findings) for r in results)
    avg_score = sum(r.score for r in results) // len(results) if results else 0

    lines.append(f"Queries analyzed: {len(results)}")
    lines.append(f"Total findings: {total_findings}")
    lines.append(f"Average score: {avg_score}/100")
    lines.append("")

    for i, result in enumerate(results, 1):
        if color:
            lines.append(f"{BOLD}--- Query {i} ---{RESET}")
        else:
            lines.append(f"--- Query {i} ---")
        lines.append(format_text(result, color=color))

    return "\n".join(lines)


def format_batch_json(results: list[AnalysisResult], *, indent: int = 2) -> str:
    """Format a batch of analysis results as JSON."""
    data = {
        "query_count": len(results),
        "total_findings": sum(len(r.findings) for r in results),
        "average_score": sum(r.score for r in results) // len(results) if results else 0,
        "results": [r.to_dict() for r in results],
    }
    return json.dumps(data, indent=indent)


def format_summary(results: list[AnalysisResult], *, color: bool = True) -> str:
    """Format a compact summary of findings across all results."""
    lines: list[str] = []

    # Aggregate findings by rule
    rule_counts: dict[str, int] = {}
    for r in results:
        for f in r.findings:
            key = f"{f.rule_id}: {f.title}"
            rule_counts[key] = rule_counts.get(key, 0) + 1

    if color:
        lines.append(f"{BOLD}Finding Summary{RESET}")
    else:
        lines.append("Finding Summary")

    if not rule_counts:
        lines.append("No issues found across all queries.")
        return "\n".join(lines)

    for rule, count in sorted(rule_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {rule}: {count} occurrence(s)")

    return "\n".join(lines)
