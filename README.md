# sqlink

SQL query analyzer that detects anti-patterns, parses EXPLAIN output, and suggests optimizations.

## Features

- **Query Analysis**: Detect SELECT *, missing WHERE, implicit cross joins, and more
- **WHERE Clause Analysis**: Find non-sargable predicates, leading wildcards, OR conditions
- **EXPLAIN Parser**: Parse PostgreSQL and MySQL EXPLAIN output (text and JSON formats)
- **N+1 Detection**: Batch analysis to find N+1 query patterns
- **Scoring**: 0-100 score based on detected issues
- **Multiple Formats**: Text (with color) and JSON output

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Analyze a single query
sqlink analyze "SELECT * FROM users WHERE UPPER(name) = 'JOHN'"

# Analyze with EXPLAIN output
sqlink analyze "SELECT * FROM users" --explain explain_output.txt

# Batch analysis with N+1 detection
sqlink batch queries.sql

# JSON output
sqlink analyze --format json "SELECT * FROM users"

# List all rules
sqlink rules

# Disable specific rules
sqlink analyze --disable-rules SQ001 SD001 "SELECT * FROM users"
```

## Rules

### Query Structure (SQ001-SQ007)
- SELECT * detection
- Missing WHERE on UPDATE/DELETE
- DISTINCT with JOIN smell
- OFFSET pagination
- Implicit cross joins
- Too many joins
- UNION without ALL

### WHERE Clause (WH001-WH006)
- Function on indexed column (non-sargable)
- Leading wildcard LIKE
- OR conditions
- NOT EQUAL filters
- IS NULL checks
- IN with subquery

### EXPLAIN Analysis (EX001-EX006)
- Full table scan
- High cost operations
- Large row estimates
- Nested loop on large data
- Sort without index
- Row estimate mismatch

### N+1 Detection (NP001-NP002)
- N+1 query patterns
- Repeated identical queries

### Schema Design (SD001-SD003)
- SELECT without LIMIT
- ORDER BY without LIMIT
- HAVING without GROUP BY

## License

MIT
