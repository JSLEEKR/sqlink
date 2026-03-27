<div align="center">

# 🔍 sqlink

### Type-safe SQL query builder for Python

[![Stars](https://img.shields.io/github/stars/JSLEEKR/sqlink?style=for-the-badge)](https://github.com/JSLEEKR/sqlink)
[![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-652-brightgreen?style=for-the-badge)](tests/)
[![Zero Deps](https://img.shields.io/badge/dependencies-zero-orange?style=for-the-badge)](#installation)

<br/>

**Build SQL queries programmatically with a fluent chain API, full type safety, parameterized queries, and multi-dialect support for PostgreSQL, MySQL, and SQLite.**

</div>

---

## Why This Exists

Writing raw SQL strings is fragile: forgotten quotes, manual parameter escaping, and dialect differences between PostgreSQL, MySQL, and SQLite. ORMs solve these problems but add heavyweight abstractions, opaque query generation, and performance overhead.

**sqlink** sits in the sweet spot — a lightweight, zero-dependency query builder that gives you:

- **Full SQL control** — every clause, join, CTE, window function, and DDL operation
- **Zero injection risk** — all values are parameterized automatically
- **Dialect portability** — same query code targets PostgreSQL, MySQL, or SQLite
- **Type safety** — full annotations, `py.typed` marker, mypy-compatible
- **Composability** — scopes, templates, paginators, and batch builders

No magic, no hidden N+1s, no fighting the ORM. Just clean SQL.

---

## Features

| Category | Capabilities |
|---|---|
| **Query Types** | SELECT, INSERT, UPDATE, DELETE, INSERT FROM SELECT |
| **Expressions** | F(), And/Or/Not, Between, In/NotIn, Like/ILike, IsNull, Case, Exists |
| **Joins** | INNER, LEFT, RIGHT, FULL, CROSS, raw JOIN |
| **Advanced SQL** | CTEs (WITH / WITH RECURSIVE), UNION / UNION ALL / INTERSECT / EXCEPT |
| **Window Functions** | ROW_NUMBER, RANK, DENSE_RANK, SUM OVER, partition/order/frame |
| **Aggregates** | COUNT, SUM, AVG, MAX, MIN, COALESCE, GREATEST, LEAST, CONCAT, CAST |
| **Date/Time** | DateTrunc, Extract, DateAdd/Sub, Age, Year/Month/Day/Hour/Minute |
| **JSON/JSONB** | ->, ->>, @>, <@, ?, ?|, ?& (PostgreSQL) |
| **Schema** | CREATE TABLE, DROP TABLE, Column types, ForeignKey, constraints |
| **DDL** | CREATE/DROP INDEX, TRUNCATE, CREATE/DROP VIEW |
| **Migrations** | AlterTable: add/drop/rename column, alter type, constraints, indexes |
| **Transactions** | BEGIN/COMMIT/ROLLBACK, SAVEPOINTs, isolation levels |
| **Composition** | Scope, QueryTemplate, Paginator, ConditionalBuilder, BatchInsert |
| **Dialects** | PostgreSQL ($1), MySQL (%s / backticks), SQLite (?), Generic |
| **Debug Tools** | interpolate_params, explain_query, format_sql |
| **Rendering** | to_dict, to_json, to_prepared, to_raw_sql, to_all_dialects |
| **Safety** | SQL injection detection, identifier validation, order direction sanitization |
| **Type Hints** | Full annotations, py.typed marker, mypy-clean |

---

## Installation

```bash
pip install sqlink
```

Zero external dependencies. Requires Python 3.10+.

---

## Quick Start

```python
from sqlink import Query, F

sql, params = (
    Query("users")
    .select("id", "name", "email")
    .where(F("age") > 18, F("active") == True)
    .order_by(F("name").asc())
    .limit(10)
    .build()
)

# sql:    SELECT "id", "name", "email" FROM "users"
#         WHERE "age" > ? AND "active" = ? ORDER BY "name" ASC LIMIT 10
# params: [18, True]
```

---

## Usage

### SELECT Queries

```python
from sqlink import Query, F, Table, Raw, Func

# Basic SELECT
Query("users").select("id", "name").build()

# SELECT *
Query("users").select_all().build()

# SELECT DISTINCT
Query("users").select("email").distinct().build()

# With table alias
Query("users", alias="u").select("u.id", "u.name").build()

# Pagination (1-indexed)
Query("users").select("*").paginate(page=2, per_page=25).build()

# SELECT with LIMIT/OFFSET
Query("users").select("id").limit(10).offset(20).build()

# FOR UPDATE lock
Query("users").select("*").where(F("id") == 1).for_update().build()
```

### WHERE Conditions

```python
# Comparison operators
F("age") > 18               # "age" > ?
F("age") >= 21              # "age" >= ?
F("status") == "active"     # "status" = ?
F("name") != "admin"        # "name" != ?

# NULL checks
F("deleted_at") == None     # "deleted_at" IS NULL
F("email") != None          # "email" IS NOT NULL
F("token").is_null()        # "token" IS NULL
F("token").is_not_null()    # "token" IS NOT NULL

# IN / NOT IN
F("role").is_in(["admin", "mod"])      # "role" IN (?, ?)
F("id").not_in([1, 2, 3])             # "id" NOT IN (?, ?, ?)

# BETWEEN / LIKE / ILIKE
F("age").between(18, 65)              # "age" BETWEEN ? AND ?
F("name").like("%john%")              # "name" LIKE ?
F("name").ilike("%john%")             # "name" ILIKE ? (PostgreSQL)

# Logical operators (Python operators)
(F("a") > 1) & (F("b") < 10)         # ("a" > ? AND "b" < ?)
(F("x") == 1) | (F("y") == 2)        # ("x" = ? OR "y" = ?)
~(F("active") == True)                # NOT ("active" = ?)

# Compound conditions
(F("role") == "admin") | ((F("age") > 18) & (F("verified") == True))

# Raw WHERE clause
Query("users").where_raw('"email" ILIKE %s', ['%@example.com']).build()
```

### INSERT

```python
# Single row (dict auto-detects columns)
Query("users").insert("name", "email").values(
    {"name": "John", "email": "john@example.com"}
).build()

# Multiple rows in one INSERT
Query("users").insert("name", "email").values(
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob",   "email": "bob@example.com"},
).build()

# Upsert — ON CONFLICT DO UPDATE
Query("users").insert("email", "name").values(
    {"email": "john@example.com", "name": "John"}
).on_conflict(["email"]).build()

# ON CONFLICT DO NOTHING
Query("users").insert("email").values(
    {"email": "dup@example.com"}
).on_conflict_do_nothing(["email"]).build()

# INSERT ... RETURNING
Query("users").insert("name").values(
    {"name": "John"}
).returning("id", "created_at").build()

# INSERT FROM SELECT
select_q = Query("temp_users").select("name", "email").where(F("valid") == True)
Query("users").insert("name", "email").from_select(select_q).build()
```

### UPDATE

```python
# Keyword args shorthand
Query("users").update(name="New Name", age=31).where(F("id") == 1).build()

# Chained .set()
Query("users").update().set("name", "John").set("age", 30).where(F("id") == 1).build()

# Raw expression (increment counter without fetching)
Query("users").update().set("login_count", Raw('"login_count" + 1')).where(F("id") == 1).build()

# UPDATE with RETURNING
Query("users").update(status="suspended").where(F("id") == 42).returning("id", "status").build()
```

### DELETE

```python
# Basic delete
Query("users").delete().where(F("id") == 1).build()

# Delete with RETURNING
Query("users").delete().where(F("active") == False).returning("id").build()

# Delete with subquery condition
subq = Query("banned_emails").select("email")
Query("users").delete().where(F("email").is_in(subq)).build()
```

### JOINs

```python
# INNER JOIN
Query("users").select("users.id", "orders.total").join(
    "orders", F("users.id") == F("orders.user_id")
).build()

# LEFT JOIN
Query("users").select("users.id", "orders.total").left_join(
    "orders", Raw('"users"."id" = "orders"."user_id"')
).build()

# RIGHT JOIN
Query("orders").select("*").right_join("users", Raw('"orders"."user_id" = "users"."id"')).build()

# FULL OUTER JOIN
Query("a").select("*").full_join("b", Raw('"a"."id" = "b"."a_id"')).build()

# CROSS JOIN
Query("products").select("*").cross_join("colors").build()

# Multiple JOINs
(
    Query("orders")
    .select("orders.id", "users.name", "products.title")
    .join("users",    Raw('"orders"."user_id" = "users"."id"'))
    .join("products", Raw('"orders"."product_id" = "products"."id"'))
    .where(F("orders.status") == "shipped")
    .build()
)

# JOIN with table alias
Query("users", alias="u").select("u.id").join(
    "orders", Raw('"u"."id" = "o"."user_id"'), alias="o"
).build()
```

### GROUP BY / HAVING

```python
from sqlink import Count, Sum, Avg

# Basic aggregation
(
    Query("orders")
    .select("status", Count("id").as_("total"))
    .group_by("status")
    .build()
)

# HAVING filter
(
    Query("orders")
    .select("user_id", Sum("amount").as_("total"))
    .group_by("user_id")
    .having(Sum("amount") > 1000)
    .build()
)
```

### CTEs (WITH)

```python
# Simple CTE
active = Query("users").select("id", "name").where(F("active") == True)
sql, params = (
    Query()
    .with_cte("active_users", active)
    .select("*")
    .from_table("active_users")
    .build()
)
# -> WITH "active_users" AS (SELECT ...) SELECT * FROM "active_users"

# Chained CTEs
q = (
    Query()
    .with_cte("active", Query("users").select("*").where(F("active") == True))
    .with_cte("recent", Query("active").select("*").where(F("created_at") > "2024-01-01"))
    .select("*")
    .from_table("recent")
    .build()
)

# Recursive CTE
(
    Query()
    .with_cte("tree", Query("nodes").select("id", "parent_id"), recursive=True)
    .select("*")
    .from_table("tree")
    .build()
)
```

### UNION / INTERSECT / EXCEPT

```python
q1 = Query("users").select("id", "name")
q2 = Query("admins").select("id", "name")

q1.union(q2).build()         # UNION (deduplicates)
q1.union_all(q2).build()     # UNION ALL (keeps duplicates)
q1.intersect(q2).build()     # INTERSECT
q1.except_(q2).build()       # EXCEPT
```

### Subqueries

```python
from sqlink.expressions import Subquery, Exists

# Subquery in WHERE
subq = Query("orders").select("user_id").where(F("total") > 100)
Query("users").select("*").where(F("id").is_in(subq)).build()

# EXISTS
Query("users").select("id").where(
    Exists(Query("orders").select("1").where(F("user_id") == F("users.id")))
).build()

# FROM subquery
inner = Query("orders").select("user_id", Sum("total").as_("sum")).group_by("user_id")
Query().from_subquery(inner, alias="totals").select("*").where(F("sum") > 500).build()
```

### Window Functions

```python
from sqlink.expressions import Window, Func, F

# ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC)
win = Window(Func("ROW_NUMBER")).partition_by("dept").order_by("salary", "DESC")
Query("employees").select(win.as_("row_num"), "name", "salary").build()

# Running total with frame spec
running_sum = (
    Window(Func("SUM", F("amount")))
    .partition_by("user_id")
    .order_by("created_at")
    .frame("ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW")
)
Query("payments").select("id", running_sum.as_("running_total")).build()

# RANK, DENSE_RANK, NTILE
rank   = Window(Func("RANK")).partition_by("dept").order_by("score", "DESC")
ntile4 = Window(Func("NTILE", 4)).order_by("salary")
Query("employees").select(rank.as_("rank"), ntile4.as_("quartile")).build()

# LAG / LEAD
lag = Window(Func("LAG", F("value"), 1)).partition_by("series_id").order_by("ts")
Query("series").select(lag.as_("prev_value")).build()
```

### Aggregate Functions

```python
from sqlink import Count, Sum, Avg, Max, Min, Coalesce, Greatest, Least
from sqlink import Concat, Lower, Upper, Trim, Length, Now, Round, Abs

# Aggregates
Count("id")                    # COUNT("id")
Count("id", distinct=True)     # COUNT(DISTINCT id)
Sum("revenue")                 # SUM("revenue")
Avg("score")                   # AVG("score")
Max("created_at")              # MAX("created_at")
Min("price")                   # MIN("price")

# Scalar functions
Coalesce("preferred_name", "name")    # COALESCE("preferred_name", "name")
Greatest("a", "b", "c")              # GREATEST("a", "b", "c")
Least("low", "mid")                  # LEAST("low", "mid")
Round("price", 2)                    # ROUND("price", 2)
Abs("balance")                       # ABS("balance")

# String functions
Lower("email")                       # LOWER("email")
Upper("code")                        # UPPER("code")
Concat("first_name", "last_name")    # CONCAT("first_name", "last_name")
Trim("name")                         # TRIM("name")
Length("description")                # LENGTH("description")

# Datetime
Now()                                # NOW()
CurrentTimestamp()                   # CURRENT_TIMESTAMP

# Use in query
Query("products").select(
    "name",
    Coalesce("sale_price", "price").as_("final_price"),
    Round("rating", 1).as_("rating"),
).where(F("active") == True).build()
```

### Date/Time Operations

```python
from sqlink.date_ops import DateTrunc, Extract, DateAdd, DateSub, Age
from sqlink.date_ops import Year, Month, Day, Hour, CurrentDate

# DATE_TRUNC
DateTrunc("month", "created_at")       # DATE_TRUNC('month', "created_at")
DateTrunc("week", "event_time")        # DATE_TRUNC('week', "event_time")

# EXTRACT
Extract("year", "created_at")          # EXTRACT(YEAR FROM "created_at")
Year("created_at")                     # shorthand
Month("created_at")                    # EXTRACT(MONTH FROM "created_at")
Day("created_at")                      # EXTRACT(DAY FROM "created_at")
Hour("created_at")                     # EXTRACT(HOUR FROM "created_at")

# Interval arithmetic
DateAdd("created_at", 7, "DAY")        # "created_at" + INTERVAL '7 DAY'
DateSub("expires_at", 1, "MONTH")      # "expires_at" - INTERVAL '1 MONTH'

# PostgreSQL AGE
Age("birth_date")                      # AGE("birth_date")
Age("birth_date", "reference_date")    # AGE("reference_date", "birth_date")

# In query
Query("users").select(
    "id",
    Year("created_at").as_("join_year"),
    DateAdd("subscription_end", 30, "DAY").as_("grace_period"),
).where(F("active") == True).build()
```

### JSON/JSONB Operators (PostgreSQL)

```python
from sqlink.json_ops import JsonField

# Path traversal
JsonField("data", "name")              # data->>'name'
JsonField("data", "address.city")      # data->'address'->>'city'

# Manual chain
JsonField("data").arrow("config").text("timeout")   # data->'config'->>'timeout'

# Array index
JsonField("tags").arrow_index(0)       # tags->0

# Containment
JsonField("metadata").contains({"role": "admin"})   # metadata @> ?
JsonField("flags").has_key("beta")                  # flags ? ?
JsonField("perms").has_any_keys(["read", "write"])  # perms ?| ?
JsonField("perms").has_all_keys(["read", "write"])  # perms ?& ?

# In WHERE clause
Query("users").select("*").where(
    JsonField("profile", "city") == "Seoul"
).build()
```

### Dialect Support

```python
from sqlink import PostgreSQLDialect, MySQLDialect, SQLiteDialect

q = Query("users").select("*").where(F("id") == 1)

# PostgreSQL — $1-style placeholders, double-quote identifiers, ILIKE, RETURNING
sql_pg, params_pg = q.build(PostgreSQLDialect())
# SELECT * FROM "users" WHERE "id" = $1   params: [1]

# MySQL — %s placeholders, backtick identifiers, ON DUPLICATE KEY UPDATE
sql_my, params_my = q.build(MySQLDialect())
# SELECT * FROM `users` WHERE `id` = %s   params: [1]

# SQLite — ? placeholders, double-quote identifiers
sql_sq, params_sq = q.build(SQLiteDialect())
# SELECT * FROM "users" WHERE "id" = ?   params: [1]

# Set dialect at Query level (applies to all .build() calls)
q = Query("users").select("*").dialect(PostgreSQLDialect())
sql, params = q.build()
```

### Schema Builder

```python
from sqlink import Schema, Column, ForeignKey
from sqlink.types import ColumnType

# CREATE TABLE
schema = Schema("users", if_not_exists=True)
schema.add_column(Column("id",         ColumnType.SERIAL,   primary_key=True))
schema.add_column(Column("name",       ColumnType.VARCHAR,  nullable=False, max_length=255))
schema.add_column(Column("email",      ColumnType.VARCHAR,  unique=True,    max_length=255))
schema.add_column(Column("created_at", ColumnType.TIMESTAMP, default="NOW()"))
schema.add_column(Column("active",     ColumnType.BOOLEAN,  default=True))

print(schema.create_table_sql())
# CREATE TABLE IF NOT EXISTS "users" (
#   "id" SERIAL PRIMARY KEY,
#   "name" VARCHAR(255) NOT NULL,
#   "email" VARCHAR(255) UNIQUE,
#   "created_at" TIMESTAMP DEFAULT NOW(),
#   "active" BOOLEAN DEFAULT TRUE
# )

# Foreign keys
schema.add_column(
    Column("org_id", ColumnType.INTEGER).with_fk(
        ForeignKey(references_table="organizations", references_column="id", on_delete="CASCADE")
    )
)

# DROP TABLE
schema.drop_table_sql()             # DROP TABLE "users"
schema.drop_table_sql(cascade=True) # DROP TABLE "users" CASCADE
```

### DDL Operations

```python
from sqlink.ddl import CreateIndex, DropIndex, Truncate, CreateView, DropView

# CREATE INDEX
CreateIndex("idx_users_email", "users", ["email"]).build()
CreateIndex("idx_orders_user", "orders", ["user_id", "created_at"], unique=True).build()
CreateIndex("idx_search", "products", ["name"], if_not_exists=True).build()

# DROP INDEX
DropIndex("idx_users_email").build()
DropIndex("idx_users_email", if_exists=True).build()

# TRUNCATE
Truncate("users").build()
Truncate("users", cascade=True, restart_identity=True).build()

# CREATE VIEW
view_q = Query("orders").select("user_id", Sum("total").as_("total")).group_by("user_id")
CreateView("user_totals", view_q).build()
CreateView("active_users", Query("users").select("*").where(F("active") == True),
           or_replace=True).build()

# DROP VIEW
DropView("user_totals").build()
DropView("user_totals", if_exists=True, cascade=True).build()
```

### Migration Builder

```python
from sqlink.migration import AlterTable
from sqlink.schema import Column, ForeignKey
from sqlink.types import ColumnType

alter = AlterTable("users")

# Add / drop / rename columns
alter.add_column(Column("phone", ColumnType.VARCHAR, max_length=20))
alter.drop_column("legacy_field")
alter.rename_column("fname", "first_name")

# Change type
alter.alter_column_type("score", "FLOAT")

# Constraints
alter.set_not_null("email")
alter.drop_not_null("middle_name")
alter.add_unique("email", name="uq_users_email")
alter.drop_constraint("uq_old_email")

# Default values
alter.set_default("active", True)
alter.drop_default("score")

# Indexes
alter.add_index("email", name="idx_users_email")
alter.add_index("user_id", "created_at", unique=True, name="idx_orders_uc")
alter.drop_index("idx_old")

# Foreign keys
alter.add_foreign_key(
    ForeignKey(references_table="orgs", references_column="id", on_delete="SET NULL"),
    name="fk_users_org"
)

# Rename table
alter.rename_table("members")

statements = alter.build()
# Returns list of SQL strings — one per operation
```

### Transaction Builder

```python
from sqlink.transaction import Transaction

# Basic transaction
tx = Transaction()
tx.add(Query("accounts").update(balance=Raw('"balance" - ?', [100])).where(F("id") == 1))
tx.add(Query("accounts").update(balance=Raw('"balance" + ?', [100])).where(F("id") == 2))
tx.add(Query("transfers").insert("from_id", "to_id", "amount").values(
    {"from_id": 1, "to_id": 2, "amount": 100}
))
statements = tx.build()
# -> [("BEGIN", []), ("UPDATE ...", [...]), ("UPDATE ...", [...]), ("INSERT ...", [...]), ("COMMIT", [])]

# With isolation level
tx = Transaction(isolation_level="SERIALIZABLE")

# SAVEPOINTs
tx = Transaction()
tx.add(Query("orders").insert("status").values({"status": "pending"}))
tx.savepoint("sp1")
tx.add(Query("payments").insert("amount").values({"amount": 50}))
tx.rollback_to("sp1")   # undo payment
tx.release_savepoint("sp1")
```

### Query Composition

```python
from sqlink.compose import Scope, QueryTemplate, Paginator, ConditionalBuilder, BatchInsert

# Scope — reusable filter fragment
active = Scope(lambda q: q.where(F("active") == True))
recent = Scope(lambda q: q.where(F("created_at") > "2024-01-01"))
combined = active & recent   # compose scopes

base = Query("users").select("*")
filtered = combined(base)

# QueryTemplate — parameterized query factory
by_user = QueryTemplate(
    lambda user_id: Query("orders").select("*").where(F("user_id") == user_id)
)
sql, params = by_user.build(user_id=42)

# Paginator — stateful pagination over base query
base = Query("users").select("*").where(F("active") == True).order_by(F("name").asc())
pager = Paginator(base, per_page=25)
page1_sql, page1_params = pager.page(1)
page2_sql, page2_params = pager.page(2)
count_sql, count_params = pager.count_query()   # COUNT(*) version

# ConditionalBuilder — apply clauses conditionally
name = request.get("name")
min_age = request.get("min_age")

sql, params = (
    ConditionalBuilder(Query("users").select("*"))
    .when(name is not None,  lambda q: q.where(F("name").like(f"%{name}%")))
    .when(min_age is not None, lambda q: q.where(F("age") >= min_age))
    .build()
)

# BatchInsert — chunked multi-row inserts
batch = BatchInsert("events", ["type", "user_id", "data"], chunk_size=500)
for event in events:
    batch.add(event)

for sql, params in batch.build_chunks():
    db.execute(sql, params)
```

### Rendering Utilities

```python
from sqlink.renderer import to_dict, to_json, to_prepared, to_raw_sql, to_all_dialects

q = Query("users").select("id", "name").where(F("active") == True)

# Structured dict
to_dict(q)
# {sql: ..., params: [...], type: "SELECT", dialect: "generic", complexity: "simple"}

# JSON string
print(to_json(q, indent=2))

# Prepared statement format (compatible with psycopg2, asyncpg)
to_prepared(q, PostgreSQLDialect())
# {"text": "SELECT ...", "values": [True]}

# All dialects at once
to_all_dialects(q)
# {"postgresql": {sql: ..., params: [...]}, "mysql": ..., "sqlite": ..., "generic": ...}

# Raw SQL for debugging (NEVER use in production)
print(to_raw_sql(q))
# SELECT "id", "name" FROM "users" WHERE "active" = TRUE
```

### Debug Tools

```python
from sqlink.debug import interpolate_params, explain_query, format_sql

sql = 'SELECT * FROM "users" WHERE "age" > ? AND "active" = ?'
params = [18, True]

# Inline interpolation — for logging only
print(interpolate_params(sql, params))
# SELECT * FROM "users" WHERE "age" > 18 AND "active" = TRUE

# Query analysis
info = explain_query(sql, params)
# {type: "SELECT", param_count: 2, clauses: {WHERE: 1, JOIN: 0, ...}, complexity: "simple"}

# Pretty print SQL
q = Query("orders").select("*").join("users", Raw('"orders"."user_id" = "users"."id"')).where(F("total") > 100)
print(format_sql(q.sql()))
# SELECT *
#   FROM "orders"
#   INNER JOIN "users" ON "orders"."user_id" = "users"."id"
#   WHERE "total" > ?
```

### SQL Injection Protection

```python
from sqlink.validation import validate_identifier, check_dangerous_value, sanitize_order_direction

# Identifier validation (used internally by all builders)
validate_identifier("users")           # True
validate_identifier("users; DROP TABLE users")  # raises ValidationError

# Value scanning (secondary defense — parameterized queries are primary)
check_dangerous_value("normal string")         # False
check_dangerous_value("'; DROP TABLE users")   # True

# ORDER BY direction sanitization
sanitize_order_direction("ASC")   # "ASC"
sanitize_order_direction("asc")   # "ASC"
sanitize_order_direction("DROP")  # raises ValidationError
```

### Query Labels and Comments

```python
# Add a /* label */ for APM tracing and slow query logs
sql, params = (
    Query("users")
    .select("*")
    .label("user-list-page")
    .where(F("active") == True)
    .build()
)
# /* user-list-page */ SELECT * FROM "users" WHERE "active" = ?

# Inline SQL comment
Query("orders").select("*").comment("nightly batch export").build()
# /* nightly batch export */ SELECT * FROM "orders"
```

### Table Helper

```python
from sqlink import Table

users = Table("users")

# All operations available via Query, scoped to this table
users.select("id", "name").where(F("active") == True).build()
users.select_all().order_by(F("created_at").desc()).build()
users.insert("name", "email").values({"name": "John", "email": "j@example.com"}).build()
users.update(active=False).where(F("id") == 1).build()
users.delete().where(F("id") == 1).build()

# With dialect
pg_users = Table("users", dialect=PostgreSQLDialect())
pg_users.select("*").where(F("id") == 1).build()  # uses $1 placeholder
```

### DISTINCT ON (PostgreSQL)

```python
# DISTINCT ON — return first row per partition
Query("logs").select("user_id", "action", "created_at").distinct_on("user_id").order_by(
    F("user_id").asc(), F("created_at").desc()
).build()
# SELECT DISTINCT ON ("user_id") "user_id", "action", "created_at"
# FROM "logs" ORDER BY "user_id" ASC, "created_at" DESC
```

### CASE Expressions

```python
from sqlink.expressions import Case

status_label = (
    Case()
    .when(F("score") >= 90, "excellent")
    .when(F("score") >= 70, "good")
    .when(F("score") >= 50, "average")
    .else_("poor")
)

Query("students").select("name", status_label.as_("grade")).build()
```

---

## Architecture

```
src/sqlink/
  __init__.py       Public API re-exports
  builder.py        Core Query/Table builder — fluent chain API, all SQL types
  expressions.py    F(), Condition, And, Or, Not, In, Between, Case, Window, Alias, Subquery, Exists
  dialect.py        PostgreSQLDialect, MySQLDialect, SQLiteDialect, base Dialect
  types.py          JoinType, OrderDirection, ColumnType enums
  schema.py         Schema, Column, ForeignKey — CREATE/DROP TABLE
  aggregates.py     Count, Sum, Avg, Max, Min, Coalesce, Concat, Lower, Upper, Round, ...
  compose.py        Scope, QueryTemplate, Paginator, ConditionalBuilder, BatchInsert
  transaction.py    Transaction builder — BEGIN/COMMIT/ROLLBACK, SAVEPOINTs, isolation levels
  migration.py      AlterTable — add/drop/rename columns, indexes, constraints
  ddl.py            CreateIndex, DropIndex, Truncate, CreateView, DropView
  json_ops.py       JsonField, JsonContains, JsonHasKey, JsonHasAnyKey, ... (PostgreSQL)
  date_ops.py       DateTrunc, Extract, DateAdd, DateSub, Age, Year, Month, Day, Hour, Minute
  validation.py     validate_identifier, check_dangerous_value, sanitize_order_direction
  debug.py          interpolate_params, explain_query, format_sql
  renderer.py       to_dict, to_json, to_prepared, to_raw_sql, to_all_dialects
  py.typed          PEP 561 marker — mypy and pyright support
```

### Design Principles

**1. Parameters first** — every value passed to `F()`, `.values()`, `.update()`, etc. becomes a bound parameter. Raw SQL is opt-in via `Raw()`.

**2. Composable by design** — `Query` objects are mutable builders. Use `.clone()` to branch:
```python
base = Query("users").select("*").where(F("active") == True)
admin_q = base.clone().where(F("role") == "admin").limit(100)
staff_q = base.clone().where(F("role") == "staff")
```

**3. Dialect as a build-time argument** — dialect affects only placeholder format and identifier quoting. The same query object builds correctly for all dialects.

**4. Zero magic** — no metaclasses, no descriptors, no monkey-patching. Every class has a clear `to_sql()` → `(str, list)` contract.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=sqlink --cov-report=term-missing

# Specific module
pytest tests/test_window.py tests/test_json_ops.py -v
```

**652 tests** across 28 test files covering:

- All SQL query types (SELECT, INSERT, UPDATE, DELETE)
- All expression types and operator combinations
- All three dialects with cross-dialect consistency checks
- CTEs, UNION, subqueries, EXISTS
- Window functions with frame specs
- Aggregate and scalar functions
- Date/time expressions
- JSON/JSONB operators
- Schema and DDL builders
- AlterTable migrations
- Transaction builder with SAVEPOINTs
- Query composition (Scope, Template, Paginator, BatchInsert)
- Rendering utilities (dict, JSON, prepared, raw, all-dialects)
- Validation and SQL injection protection
- Debug tools (interpolate, explain, format)
- Type safety and py.typed compliance
- Edge cases: empty IN lists, NULL handling, empty identifiers
- Real-world integration scenarios (e-commerce, analytics, auth)
- Stress tests (1000-row batch inserts, 20-CTE chains, deeply nested conditions)

---

## Comparison

| Feature | sqlink | SQLAlchemy Core | Peewee | Raw SQL |
|---|---|---|---|---|
| Type hints | Full | Partial | Partial | N/A |
| Dependencies | Zero | Many | Zero | N/A |
| Multi-dialect | Yes | Yes | Yes | Manual |
| Parameterized | Auto | Auto | Auto | Manual |
| Window functions | Yes | Yes | No | Yes |
| JSON operators | Yes (PG) | Yes | No | Yes |
| Migration DSL | Yes | Via Alembic | Yes | Manual |
| Query tracing labels | Yes | No | No | Manual |
| Learning curve | Low | High | Medium | None |

---

## License

MIT — see [LICENSE](LICENSE)
