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
    analyze.add_argument("--suggest-indexes", action="store_true", help="Show index suggestions")
    analyze.add_argument("--suggest-rewrites", action="store_true", help="Show rewrite suggestions")
    analyze.add_argument("--complexity", action="store_true", help="Show complexity score")
    analyze.add_argument("--patterns", action="store_true", help="Check against pattern library")

    # rules command
    subparsers.add_parser("rules", help="List all available rules")

    # batch command
    batch = subparsers.add_parser("batch", help="Analyze multiple queries from file with N+1 detection")
    batch.add_argument("file", help="File containing SQL queries")
    batch.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    batch.add_argument("--no-color", action="store_true", help="Disable colored output")
    batch.add_argument("--disable-rules", nargs="*", default=[], help="Rule IDs to disable")

    # fingerprint command
    fp = subparsers.add_parser("fingerprint", help="Fingerprint queries to find duplicates")
    fp.add_argument("file", help="File containing SQL queries")
    fp.add_argument("--min-count", type=int, default=2, help="Minimum count to report (default: 2)")
    fp.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # patterns command
    subparsers.add_parser("patterns", help="List all known patterns")

    return parser


def _read_queries_from_file(filepath: str) -> list[str]:
    """Read SQL queries from a file."""
    from sqlink.file_analyzer import split_sql_file

    with open(filepath) as f:
        content = f.read()
    return split_sql_file(content)


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
        import json
        output: dict = result.to_dict()

        if args.suggest_indexes:
            from sqlink.index_advisor import suggest_indexes
            from sqlink.parser import parse_query
            parsed = parse_query(sql)
            output["index_suggestions"] = [s.to_dict() for s in suggest_indexes(parsed)]

        if args.suggest_rewrites:
            from sqlink.rewriter import suggest_rewrites
            from sqlink.parser import parse_query
            parsed = parse_query(sql)
            output["rewrites"] = [r.to_dict() for r in suggest_rewrites(parsed)]

        if args.complexity:
            from sqlink.complexity import calculate_complexity
            from sqlink.parser import parse_query
            parsed = parse_query(sql)
            output["complexity"] = calculate_complexity(parsed).to_dict()

        if args.patterns:
            from sqlink.patterns import match_patterns
            matches = match_patterns(sql)
            output["patterns"] = [{"id": m.id, "name": m.name, "type": m.pattern_type.value} for m in matches]

        print(json.dumps(output, indent=2))
    else:
        print(format_text(result, color=use_color))

        if args.suggest_indexes:
            from sqlink.index_advisor import suggest_indexes
            from sqlink.parser import parse_query
            parsed = parse_query(sql)
            indexes = suggest_indexes(parsed)
            if indexes:
                print("\nIndex Suggestions:")
                for s in indexes:
                    print(f"  {s.create_sql}")
                    print(f"    Reason: {s.reason}")

        if args.suggest_rewrites:
            from sqlink.rewriter import suggest_rewrites
            from sqlink.parser import parse_query
            parsed = parse_query(sql)
            rewrites = suggest_rewrites(parsed)
            if rewrites:
                print("\nSuggested Rewrites:")
                for r in rewrites:
                    print(f"  [{r.rule_id}] {r.description}")
                    print(f"    {r.rewritten[:200]}")

        if args.complexity:
            from sqlink.complexity import calculate_complexity
            from sqlink.parser import parse_query
            parsed = parse_query(sql)
            comp = calculate_complexity(parsed)
            print(f"\nComplexity: {comp.total} ({comp.level})")
            for detail in comp.details:
                print(f"  {detail}")

        if args.patterns:
            from sqlink.patterns import match_patterns
            matches = match_patterns(sql)
            if matches:
                print("\nPattern Matches:")
                for m in matches:
                    print(f"  [{m.pattern_type.value}] {m.name}")
                    print(f"    {m.description}")

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


def cmd_fingerprint(args: argparse.Namespace) -> int:
    """Handle fingerprint command."""
    from sqlink.fingerprint import find_duplicates

    queries = _read_queries_from_file(args.file)
    if not queries:
        print("Error: no queries found in file", file=sys.stderr)
        return 1

    dups = find_duplicates(queries, min_count=args.min_count)

    if args.format == "json":
        import json
        print(json.dumps(dups, indent=2))
    else:
        if not dups:
            print("No duplicate query patterns found.")
        else:
            print(f"Found {len(dups)} duplicate pattern(s):\n")
            for d in dups:
                print(f"  Pattern (x{d['count']}): {d['normalized'][:100]}")
                print(f"    Fingerprint: {d['fingerprint']}")
                for ex in d["examples"]:
                    print(f"    Example: {ex[:100]}")
                print()

    return 0


def cmd_patterns(_args: argparse.Namespace) -> int:
    """Handle patterns command."""
    from sqlink.patterns import PATTERNS, PatternType

    print("\nAnti-Patterns:")
    print("-" * 40)
    for p in PATTERNS.values():
        if p.pattern_type == PatternType.ANTI_PATTERN:
            print(f"  {p.id}: {p.name}")
            print(f"    {p.description}")
            if p.example_bad:
                print(f"    Bad:  {p.example_bad}")
            if p.example_good:
                print(f"    Good: {p.example_good}")
            print()

    print("\nBest Practices:")
    print("-" * 40)
    for p in PATTERNS.values():
        if p.pattern_type == PatternType.BEST_PRACTICE:
            print(f"  {p.id}: {p.name}")
            print(f"    {p.description}")
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
        "fingerprint": cmd_fingerprint,
        "patterns": cmd_patterns,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
