# Changelog

All notable changes to sqlink are documented in this file.

Format: `[version] YYYY-MM-DD — description`

---

## [1.0.0] 2026-03-27 — Production release

### Added — Core Builder
- `Query` class: fluent chain API for SELECT, INSERT, UPDATE, DELETE
- `Table` helper: table-scoped query factory with optional dialect binding
- `.clone()` for safe query branching via deep copy
- `__repr__` / `__str__` on `Query` and `Expr` — build-time introspection
- `.comment()` and `.label()` for `/* ... */` SQL comments and APM tracing tags

### Added — Expressions
- `F()` field reference with full operator overloading (`==`, `!=`, `>`, `>=`, `<`, `<=`)
- `And`, `Or`, `Not` via Python `&`, `|`, `~` operators
- `Between`, `In`, `NotIn`, `Like`, `ILike`, `IsNull`, `IsNotNull`
- `Case` WHEN/THEN/ELSE expression builder
- `Exists` for correlated subquery conditions
- `Subquery` wrapper for FROM/IN subqueries
- `Alias` via `.as_()` on any `Expr`
- `Raw` for opt-in raw SQL fragments with optional params
- `Func` for arbitrary SQL function calls
- `Window` for window functions with `PARTITION BY`, `ORDER BY`, and frame specs
- `OrderExpr` with `.asc()` / `.desc()` on `F()`

### Added — SQL Clauses
- `.select()`, `.select_all()`, `.add_select()`, `.distinct()`, `.distinct_on()`
- `.from_table()`, `.from_subquery()`
- `.where()`, `.where_raw()`
- `.join()`, `.left_join()`, `.right_join()`, `.full_join()`, `.cross_join()`, `.join_raw()`
- `.group_by()`, `.having()`
- `.order_by()`, `.order_by_asc()`, `.order_by_desc()`
- `.limit()`, `.offset()`, `.paginate()`
- `.insert()`, `.values()`, `.from_select()`
- `.on_conflict()`, `.on_conflict_do_nothing()`
- `.update()`, `.set()`
- `.delete()`
- `.returning()`
- `.with_cte()` (including recursive CTEs)
- `.union()`, `.union_all()`, `.intersect()`, `.except_()`
- `.for_update()`, `.for_share()` row-level locking

### Added — Dialects
- `Dialect` base: `?` placeholders, double-quote identifiers
- `PostgreSQLDialect`: `$1`-style numbered placeholders, ILIKE, RETURNING, ON CONFLICT
- `MySQLDialect`: `%s` placeholders, backtick identifiers, ON DUPLICATE KEY UPDATE
- `SQLiteDialect`: `?` placeholders, RETURNING (3.35+), ON CONFLICT

### Added — Aggregates & Functions
- `Count`, `Sum`, `Avg`, `Max`, `Min` with optional `distinct=True`
- `Coalesce`, `Greatest`, `Least`, `Concat`, `Cast`
- `Lower`, `Upper`, `Trim`, `Length`, `Round`, `Abs`
- `Now`, `CurrentTimestamp`

### Added — Date/Time (date_ops.py)
- `DateTrunc(precision, column)` — DATE_TRUNC
- `Extract(part, column)` — EXTRACT(PART FROM column)
- `DateAdd(column, value, unit)` — column + INTERVAL 'N unit'
- `DateSub(column, value, unit)` — column - INTERVAL 'N unit'
- `DateDiff(col1, col2)` — col1 - col2
- `Age(column, reference?)` — PostgreSQL AGE()
- Convenience: `Year`, `Month`, `Day`, `Hour`, `Minute`, `CurrentDate`, `CurrentTime`

### Added — JSON/JSONB (json_ops.py)
- `JsonField` with path traversal via `.arrow()`, `.text()`, `.arrow_index()`
- `JsonContains` (`@>`), `JsonContainedBy` (`<@`)
- `JsonHasKey` (`?`), `JsonHasAnyKey` (`?|`), `JsonHasAllKeys` (`?&`)
- Comparison operators on `JsonField` for WHERE conditions

### Added — Schema Builder (schema.py)
- `Schema` with `CREATE TABLE IF NOT EXISTS` and `DROP TABLE [CASCADE]`
- `Column` with type, nullable, default, primary_key, unique, max_length
- `ForeignKey` with ON DELETE / ON UPDATE actions

### Added — DDL (ddl.py)
- `CreateIndex` / `DropIndex` with UNIQUE and IF [NOT] EXISTS
- `Truncate` with CASCADE and RESTART IDENTITY
- `CreateView` / `DropView` with OR REPLACE, IF EXISTS, CASCADE

### Added — Migration Builder (migration.py)
- `AlterTable`: add/drop/rename column, alter column type
- SET/DROP NOT NULL, SET/DROP DEFAULT
- ADD/DROP UNIQUE constraint, DROP CONSTRAINT
- ADD/DROP INDEX (with CREATE INDEX SQL)
- ADD FOREIGN KEY
- RENAME TABLE

### Added — Transaction Builder (transaction.py)
- `Transaction` with BEGIN / COMMIT / ROLLBACK
- Configurable isolation level (`SERIALIZABLE`, `READ COMMITTED`, etc.)
- SAVEPOINT, ROLLBACK TO SAVEPOINT, RELEASE SAVEPOINT

### Added — Query Composition (compose.py)
- `Scope`: reusable query modifier with `&` combinator
- `QueryTemplate`: parameterized query factory
- `Paginator`: stateful pagination with `.page(n)` and `.count_query()`
- `ConditionalBuilder`: `.when()` / `.unless()` conditional clause application
- `BatchInsert`: chunked multi-row inserts with configurable `chunk_size`

### Added — Debug Tools (debug.py)
- `interpolate_params()`: inline param substitution for logging
- `explain_query()`: clause detection, complexity scoring, param counting
- `format_sql()`: keyword-based SQL pretty-printing with indentation

### Added — Rendering Utilities (renderer.py)
- `to_dict()`: query metadata as structured dict
- `to_json()`: JSON serialization with indent
- `to_prepared()`: `{text, values}` format for DB drivers
- `to_raw_sql()`: debug-only interpolated SQL
- `to_all_dialects()`: build same query in all four dialects
- `render_migration()`: join AlterTable statements into a migration script

### Added — Validation (validation.py)
- `validate_identifier()`: safe identifier check with SQL injection pattern detection
- `validate_table_name()`, `validate_column_name()`
- `check_dangerous_value()`: secondary defense scan on string values
- `sanitize_order_direction()`: restrict to ASC / DESC
- `validate_limit()`, `validate_offset()`

### Added — Type Safety
- Full type annotations on all public APIs
- `py.typed` PEP 561 marker for mypy / pyright support
- `__all__` exports in `__init__.py`

### Tests
- 652 tests across 28 test files
- Coverage: builder, expressions, all dialects, CTEs, UNION, subqueries
- Window functions, aggregates, date/time, JSON/JSONB
- Schema, DDL, migration, transaction, composition
- Rendering, validation, debug tools
- Type safety, repr/str, error handling
- Real-world integration scenarios (e-commerce, analytics, auth flows)
- Stress tests: 1000-row batch inserts, 20-CTE chains, deeply nested conditions
