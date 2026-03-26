# sqlink

SQL query analyzer that detects anti-patterns, parses EXPLAIN output, and suggests optimizations.

## Features

- **Query Analysis**: Detect SELECT *, missing WHERE, implicit cross joins, and more
- **WHERE Clause Analysis**: Find non-sargable predicates, leading wildcards, OR conditions
- **EXPLAIN Parser**: Parse PostgreSQL and MySQL EXPLAIN output (text and JSON formats)
- **N+1 Detection**: Batch analysis to find N+1 query patterns
- **Scoring**: 0-100 score based on detected issues
- **Index Advisor**: Suggest indexes for WHERE, JOIN, ORDER BY, GROUP BY columns
- **Query Rewriter**: Suggest improved query rewrites (SELECT * fix, keyset pagination, etc.)
- **Complexity Scoring**: Score query complexity with breakdown (joins, subqueries, conditions)
- **Pattern Library**: 10 built-in anti-patterns and best practices detection
- **Query Fingerprinting**: Normalize and group queries for duplicate detection
- **Cost Estimator**: Estimate query cost with optional schema context
- **SQL Formatter**: Pretty-print SQL with keyword uppercasing and clause indentation
- **Query Sanitizer**: Remove sensitive data (emails, IPs, credentials) for safe logging
- **Query Diff**: Structural comparison of two SQL queries
- **Slow Query Log Parser**: Parse PostgreSQL and MySQL slow query logs
- **Config File Support**: `.sqlink.json` config with hierarchy search and merge
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

# With index suggestions and rewrites
sqlink analyze --suggest-indexes --suggest-rewrites "SELECT * FROM users WHERE email = 'test@test.com'"

# With complexity scoring and pattern matching
sqlink analyze --complexity --patterns "SELECT COUNT(*) FROM users WHERE email = 'x'"

# Batch analysis with N+1 detection
sqlink batch queries.sql

# JSON output
sqlink analyze --format json "SELECT * FROM users"

# Fingerprint queries to find duplicates
sqlink fingerprint queries.sql --min-count 2

# List all rules
sqlink rules

# List all known patterns
sqlink patterns

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

### Pattern Library (AP001-AP007, BP001-BP003)
- COUNT(*) for existence check
- ORDER BY RAND()
- SELECT FOR UPDATE without WHERE
- Correlated subquery in SELECT
- NOT IN with NULLs risk
- Implicit type conversion
- Multiple COUNT with CASE
- EXISTS best practice
- Explicit column list in INSERT
- COALESCE for default values

## License

MIT
