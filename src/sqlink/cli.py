"""CLI interface for sqlink."""

from __future__ import annotations

import argparse
import sys

from sqlink import __version__
from sqlink.analyzer import QueryAnalyzer
from sqlink.reporter import format_batch_json, format_batch_text, format_json, format_text


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="sqlink",
        description="SQL query analyzer — detect anti-patterns and suggest optimizations",
    )
    parser.add_argument("--version", action="version", version=f"sqlink {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze = subparsers.add_parser("analyze", help="Analyze SQL query(ies)")
    analyze.add_argument("query", nargs="?", help="SQL query to analyze (or use --file)")
    analyze.add_argument("-f", "--file", help="File containing SQL queries (one per line or semicolon-separated)")
    analyze.add_argument("-e", "--explain", help="File containing EXPLAIN output")
    analyze.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    analyze.add_argument("--no-color", action="store_true", help="Disable colored output")
    analyze.add_argument("--max-joins", type=int, default=5, help="Max joins before warning (default: 5)")
    analyze.add_argument("--disable-rules", nargs="*", default=[], help="Rule IDs to disable")

    # rules command
    subparsers.add_parser("rules", help="List all available rules")

    # batch command
    batch = subparsers.add_parser("batch", help="Analyze multiple queries from file with N+1 detection")
    batch.add_argument("file", help="File containing SQL queries")
    batch.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    batch.add_argument("--no-color", action="store_true", help="Disable colored output")
    batch.add_argument("--disable-rules", nargs="*", default=[], help="Rule IDs to disable")

    return parser


def _read_queries_from_file(filepath: str) -> list[str]:
    """Read SQL queries from a file."""
    with open(filepath) as f:
        content = f.read()

    # Split by semicolon or double newline
    if ";" in content:
        queries = [q.strip() for q in content.split(";") if q.strip()]
    else:
        queries = [q.strip() for q in content.split("\n\n") if q.strip()]

    return queries


def cmd_analyze(args: argparse.Namespace) -> int:
    """Handle analyze command."""
    sql = args.query
    if not sql and args.file:
        queries = _read_queries_from_file(args.file)
        sql = queries[0] if queries else None

    if not sql:
        print("Error: provide a SQL query as argument or use --file", file=sys.stderr)
        return 1

    explain_text = None
    if args.explain:
        with open(args.explain) as f:
            explain_text = f.read()

    analyzer = QueryAnalyzer(
        max_joins=args.max_joins,
        disabled_rules=set(args.disable_rules),
    )
    result = analyzer.analyze(sql, explain_text=explain_text)

    use_color = not args.no_color and sys.stdout.isatty()

    if args.format == "json":
        print(format_json(result))
    else:
        print(format_text(result, color=use_color))

    return 0 if result.score >= 50 else 1


def cmd_batch(args: argparse.Namespace) -> int:
    """Handle batch command."""
    queries = _read_queries_from_file(args.file)
    if not queries:
        print("Error: no queries found in file", file=sys.stderr)
        return 1

    analyzer = QueryAnalyzer(disabled_rules=set(args.disable_rules))
    results = analyzer.analyze_batch(queries)

    use_color = not args.no_color and sys.stdout.isatty()

    if args.format == "json":
        print(format_batch_json(results))
    else:
        print(format_batch_text(results, color=use_color))

    avg_score = sum(r.score for r in results) // len(results) if results else 0
    return 0 if avg_score >= 50 else 1


def cmd_rules(_args: argparse.Namespace) -> int:
    """Handle rules command."""
    from sqlink.rules import RULES, get_all_categories

    for category in get_all_categories():
        print(f"\n{category.upper().replace('_', ' ')}:")
        print("-" * 40)
        for rule in RULES.values():
            if rule.category == category:
                print(f"  {rule.id}: {rule.title} [{rule.severity.value}]")
                print(f"    {rule.description}")
                print()

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "analyze": cmd_analyze,
        "batch": cmd_batch,
        "rules": cmd_rules,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
