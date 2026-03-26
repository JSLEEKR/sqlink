<div align="center">

# 🔍 sqlink

### SQL query analyzer for smarter databases

[![GitHub Stars](https://img.shields.io/github/stars/JSLEEKR/sqlink?style=for-the-badge&logo=github&color=yellow)](https://github.com/JSLEEKR/sqlink/stargazers)
[![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-503%20passing-brightgreen?style=for-the-badge)](#)

<br/>

**Detect SQL anti-patterns, parse EXPLAIN output, and get optimization suggestions**

Static Analysis + Cost Estimation + Auto-Fix Suggestions

[Quick Start](#-quick-start) | [Features](#features) | [CLI Commands](#-cli-commands) | [Rules](#-rules)

</div>

---

## Why This Exists

Every production database has that one query someone wrote at 2 AM that now scans 10 million rows. You find it in the slow query log weeks later, buried under hundreds of similar queries. DBAs know the patterns, but developers keep repeating the same mistakes -- SELECT *, missing indexes, N+1 loops, OFFSET pagination on million-row tables.

sqlink catches these problems before they hit production. Point it at a query, a SQL file, or a slow query log and get a scored analysis with specific fixes. No database connection required -- it works entirely through static analysis with optional schema context for accurate cost estimation.

- **24 built-in rules** -- covering query structure, WHERE clause anti-patterns, EXPLAIN analysis, N+1 detection, and schema design
- **10 pattern detectors** -- ORDER BY RAND(), COUNT(*) for existence, correlated subqueries, NOT IN with NULLs, implicit type conversion
- **Auto-fix suggestions** -- rewrites for SELECT *, keyset pagination, UNION ALL, EXISTS conversion, missing LIMIT
- **Cost estimation** -- PostgreSQL-inspired planner model with schema-aware index/scan cost modeling
- **Query fingerprinting** -- normalize and group queries to find duplicates across thousands of statements
- **Slow query log parsing** -- feed PostgreSQL and MySQL logs directly into the analyzer

Stop guessing at SQL performance. Let sqlink show you exactly what to fix.

---

## Features

### Analysis Engine

- **Anti-Pattern Detection** -- 24 rules across 5 categories catch common SQL mistakes
- **0-100 Scoring** -- severity-weighted score tells you how problematic a query is at a glance
- **EXPLAIN Parser** -- parse PostgreSQL and MySQL EXPLAIN output (text and JSON) to find full table scans, high costs, and row estimate mismatches
- **N+1 Detection** -- batch analysis identifies repeated query patterns that signal N+1 problems

### Optimization Tools

- **Index Advisor** -- suggests indexes for WHERE, JOIN, ORDER BY, and GROUP BY columns with composite index support and priority ranking
- **Query Rewriter** -- generates improved query versions: SELECT * to explicit columns, OFFSET to keyset pagination, IN subquery to EXISTS, UNION to UNION ALL
- **Complexity Scorer** -- breaks down query complexity by joins, subqueries, conditions, aggregation, and modifiers with level classification (low/medium/high/very high)
- **Cost Estimator** -- estimates query cost without a database connection using PostgreSQL-inspired planner constants, optionally enhanced with schema context and table statistics

### Developer Utilities

- **SQL Formatter** -- pretty-prints SQL with keyword uppercasing and clause-level indentation
- **Query Sanitizer** -- strips sensitive data (emails, credit cards, SSNs, IPs, passwords) for safe logging
- **Query Diff** -- structural comparison showing added/removed tables, joins, conditions, and columns between two queries
- **Query Fingerprinting** -- normalizes literals and groups queries by structure to find duplicates across large sets
- **Pattern Library** -- 7 anti-patterns and 3 best practices with bad/good examples
- **Slow Query Log Parser** -- auto-detects and parses PostgreSQL duration logs and MySQL slow query logs
- **Config File** -- `.sqlink.json` with directory hierarchy search and config merging

---

## 🚀 Quick Start

### Installation

```bash
pip install -e .
```

### Analyze Your First Query

```bash
# Single query analysis
sqlink analyze "SELECT * FROM users WHERE UPPER(name) = 'JOHN'"

# See what's wrong in JSON
sqlink analyze --format json "SELECT * FROM users"
```

### Get Fix Suggestions

```bash
# Index suggestions + query rewrites + complexity score
sqlink analyze --suggest-indexes --suggest-rewrites --complexity \
  "SELECT * FROM users WHERE email = 'test@test.com'"

# Check against pattern library
sqlink analyze --patterns "SELECT COUNT(*) FROM users WHERE email = 'x'"
```

### Batch Analysis

```bash
# Analyze a SQL file with N+1 detection
sqlink batch queries.sql

# Find duplicate query patterns
sqlink fingerprint queries.sql --min-count 2
```

---

## 📦 CLI Commands

| Command | Description |
|---------|-------------|
| `sqlink analyze <query>` | Analyze a single SQL query |
| `sqlink analyze -f <file>` | Analyze first query from a SQL file |
| `sqlink batch <file>` | Batch analyze all queries with N+1 detection |
| `sqlink fingerprint <file>` | Find duplicate query patterns |
| `sqlink rules` | List all available rules |
| `sqlink patterns` | List all known anti-patterns and best practices |

### Analyze Options

| Flag | Description |
|------|-------------|
| `--format json/text` | Output format (default: text) |
| `--suggest-indexes` | Show index suggestions |
| `--suggest-rewrites` | Show rewrite suggestions |
| `--complexity` | Show complexity breakdown |
| `--patterns` | Check against pattern library |
| `--explain <file>` | Include EXPLAIN output for deeper analysis |
| `--disable-rules SQ001 ...` | Skip specific rules |
| `--max-joins N` | Set join count threshold (default: 5) |
| `--no-color` | Disable colored output |

---

## 📋 Rules

### Query Structure (SQ001-SQ007)

| Rule | Severity | Description |
|------|----------|-------------|
| SQ001 | Warning | SELECT * -- list columns explicitly |
| SQ002 | Critical | Missing WHERE on UPDATE/DELETE |
| SQ003 | Warning | DISTINCT with JOIN -- possible join issue |
| SQ004 | Warning | OFFSET pagination -- use keyset pagination |
| SQ005 | Error | Implicit cross join |
| SQ006 | Warning | Too many JOINs (configurable threshold) |
| SQ007 | Info | UNION without ALL -- unnecessary deduplication |

### WHERE Clause (WH001-WH006)

| Rule | Severity | Description |
|------|----------|-------------|
| WH001 | Warning | Function on indexed column (non-sargable) |
| WH002 | Warning | Leading wildcard LIKE |
| WH003 | Info | OR conditions -- consider UNION |
| WH004 | Info | NOT EQUAL filter -- poor index utilization |
| WH005 | Info | IS NULL check -- consider default values |
| WH006 | Warning | IN with subquery -- consider EXISTS |

### EXPLAIN Analysis (EX001-EX006)

| Rule | Severity | Description |
|------|----------|-------------|
| EX001 | Error | Full table scan detected |
| EX002 | Warning | High cost operation |
| EX003 | Warning | Large row estimate |
| EX004 | Error | Nested loop on large dataset |
| EX005 | Warning | Sort without index |
| EX006 | Warning | Row estimate mismatch (actual vs planned) |

### N+1 Detection (NP001-NP002)

| Rule | Severity | Description |
|------|----------|-------------|
| NP001 | Error | N+1 query pattern detected |
| NP002 | Warning | Repeated identical queries |

### Schema Design (SD001-SD003)

| Rule | Severity | Description |
|------|----------|-------------|
| SD001 | Info | SELECT without LIMIT |
| SD002 | Info | ORDER BY without LIMIT |
| SD003 | Warning | HAVING without GROUP BY |

---

## 🧩 Pattern Library

### Anti-Patterns (AP001-AP007)

| ID | Pattern | Fix |
|----|---------|-----|
| AP001 | COUNT(*) for existence check | Use EXISTS (SELECT 1 ...) |
| AP002 | ORDER BY RAND() | Use random ID selection |
| AP003 | SELECT FOR UPDATE without WHERE | Add WHERE to avoid table lock |
| AP004 | Correlated subquery in SELECT | Rewrite as JOIN |
| AP005 | NOT IN with NULLs risk | Use NOT EXISTS |
| AP006 | Implicit type conversion | Match column types |
| AP007 | Multiple COUNT(CASE ...) | Use GROUP BY |

### Best Practices (BP001-BP003)

| ID | Pattern |
|----|---------|
| BP001 | EXISTS for existence check |
| BP002 | Explicit column list in INSERT |
| BP003 | COALESCE for default values |

---

## 🔧 Configuration

Create a `.sqlink.json` in your project root:

```json
{
  "disabled_rules": ["SD001"],
  "max_joins": 5,
  "high_cost_threshold": 1000.0,
  "output_format": "text",
  "color": true,
  "severity_threshold": "info"
}
```

sqlink searches up the directory tree for config files and merges them.

---

## 🏗️ Architecture

```
src/sqlink/
├── analyzer.py        # Core analysis engine with scoring
├── parser.py          # SQL tokenizer and parser
├── rules.py           # 24 rule definitions
├── patterns.py        # Anti-pattern and best practice library
├── explain_parser.py  # PostgreSQL/MySQL EXPLAIN parser
├── index_advisor.py   # Index suggestion engine
├── rewriter.py        # Query rewrite generator
├── complexity.py      # Complexity scoring
├── cost_estimator.py  # Cost estimation with schema context
├── fingerprint.py     # Query normalization and grouping
├── sanitizer.py       # Sensitive data removal
├── formatter.py       # SQL pretty-printer
├── diff.py            # Structural query comparison
├── log_parser.py      # Slow query log parser
├── file_analyzer.py   # SQL file splitting and batch analysis
├── statistics.py      # Table and column statistics
├── config.py          # Configuration management
├── reporter.py        # Text and JSON output formatting
├── models.py          # Data models
└── cli.py             # CLI interface
```

---

## 🧪 Testing

```bash
# Run all 503 tests
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_stress.py     # Performance stress tests
python -m pytest tests/test_integration.py # Cross-module integration tests
```

---

## License

MIT
