<div align="center">

# :link: sqlink

### Fluent SQL query builder with chain API and dialect support

[![Stars](https://img.shields.io/github/stars/JSLEEKR/sqlink?style=for-the-badge)](https://github.com/JSLEEKR/sqlink)
[![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-188-green?style=for-the-badge)](tests/)

<br/>

**Build SQL queries programmatically with a fluent chain API, parameterized queries, and multi-dialect support.**

</div>

---

## Why This Exists

Writing raw SQL strings is error-prone: missing quotes, SQL injection vulnerabilities, and dialect differences between PostgreSQL, MySQL, and SQLite. ORMs solve this but add heavyweight abstractions. **sqlink** sits in the sweet spot -- a lightweight query builder that gives you full control over SQL while keeping your code clean, safe, and portable across databases.

## Features

- **Fluent Chain API** -- Build queries with readable method chaining
- **Parameterized Queries** -- All values are parameterized by default (no SQL injection)
- **Multi-Dialect** -- PostgreSQL (`$1`), MySQL (`%s`), SQLite (`?`) with correct quoting
- **Full CRUD** -- SELECT, INSERT, UPDATE, DELETE with all standard clauses
- **Advanced SQL** -- JOINs, CTEs, subqueries, UNION, CASE, window functions
- **Upsert Support** -- ON CONFLICT (PostgreSQL/SQLite) and ON DUPLICATE KEY (MySQL)
- **Schema Builder** -- CREATE TABLE with columns, constraints, and foreign keys
- **Expression System** -- Composable conditions with `F()`, `And`, `Or`, `Not`, `Between`, `In`
- **Zero Dependencies** -- Pure Python, no external packages required
- **Type Hints** -- Full type annotations for IDE support

## Installation

```bash
pip install sqlink
```

## Quick Start

```python
from sqlink import Query, F

# SELECT with conditions
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

## Usage

### SELECT Queries

```python
from sqlink import Query, F, Table, Raw, Func

# Basic select
Query("users").select("id", "name").build()

# SELECT DISTINCT
Query("users").select("email").distinct().build()

# With table alias
Query("users", alias="u").select("u.id", "u.name").build()

# Pagination
Query("users").select("*").paginate(page=2, per_page=25).build()
```

### WHERE Conditions

```python
# Comparison operators
F("age") > 18        # age > ?
F("status") == "active"   # status = ?
F("name") != "admin"      # name != ?

# NULL checks
F("deleted_at") == None   # deleted_at IS NULL
F("email") != None        # email IS NOT NULL

# IN / NOT IN
F("role").is_in(["admin", "mod"])     # role IN (?, ?)
F("id").not_in([1, 2, 3])            # id NOT IN (?, ?, ?)

# BETWEEN / LIKE
F("age").between(18, 65)       # age BETWEEN ? AND ?
F("name").like("%john%")       # name LIKE ?

# Logical operators
(F("a") > 1) & (F("b") < 10)  # (a > ? AND b < ?)
(F("x") == 1) | (F("y") == 2) # (x = ? OR y = ?)
~(F("active") == True)         # NOT (active = ?)
```

### INSERT

```python
# Single row
Query("users").insert("name", "email").values(
    {"name": "John", "email": "john@example.com"}
).build()

# Multiple rows
Query("users").insert("name", "email").values(
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com"},
).build()

# Upsert (ON CONFLICT)
Query("users").insert("email", "name").values(
    {"email": "john@example.com", "name": "John"}
).on_conflict(["email"]).build()

# INSERT ... RETURNING
Query("users").insert("name").values(
    {"name": "John"}
).returning("id").build()
```

### UPDATE

```python
# Update with kwargs
Query("users").update(name="New Name", age=31).where(F("id") == 1).build()

# Update with set()
Query("users").update().set("name", "John").set("age", 30).where(F("id") == 1).build()

# Update with raw expression
Query("users").update().set("login_count", Raw('"login_count" + 1')).where(F("id") == 1).build()
```

### DELETE

```python
Query("users").delete().where(F("id") == 1).build()
```

### JOINs

```python
Query("users").select("users.id", "orders.total").join(
    "orders", Raw('"users"."id" = "orders"."user_id"')
).build()

# LEFT JOIN
Query("users").select("*").left_join(
    "orders", Raw('"users"."id" = "orders"."user_id"')
).build()
```

### CTEs (WITH)

```python
active = Query("users").select("id", "name").where(F("active") == True)
Query().with_cte("active_users", active).select("*").from_table("active_users").build()
```

### UNION

```python
q1 = Query("users").select("id", "name")
q2 = Query("admins").select("id", "name")
q1.union(q2).build()
q1.union_all(q2).build()
```

### Dialect Support

```python
from sqlink import PostgreSQLDialect, MySQLDialect, SQLiteDialect

# PostgreSQL ($1, $2 placeholders, double-quote identifiers)
Query("users").select("*").where(F("id") == 1).build(PostgreSQLDialect())

# MySQL (%s placeholders, backtick identifiers)
Query("users").select("*").where(F("id") == 1).build(MySQLDialect())

# SQLite (? placeholders, double-quote identifiers)
Query("users").select("*").where(F("id") == 1).build(SQLiteDialect())
```

### Schema Builder

```python
from sqlink import Schema, Column, ForeignKey
from sqlink.types import ColumnType

schema = Schema("users", if_not_exists=True)
schema.add_column(Column("id", ColumnType.SERIAL, primary_key=True))
schema.add_column(Column("name", ColumnType.VARCHAR, nullable=False, max_length=255))
schema.add_column(Column("email", ColumnType.VARCHAR, unique=True, max_length=255))

print(schema.create_table_sql())
# CREATE TABLE IF NOT EXISTS "users" ("id" SERIAL PRIMARY KEY, "name" VARCHAR(255) NOT NULL, "email" VARCHAR(255) UNIQUE)
```

### Table Helper

```python
users = Table("users")
users.select("id", "name").where(F("active") == True).build()
users.insert("name").values({"name": "John"}).build()
users.update(active=False).where(F("id") == 1).build()
users.delete().where(F("id") == 1).build()
```

## Architecture

```
src/sqlink/
  __init__.py      # Public API exports
  builder.py       # Core Query builder with fluent chain API
  expressions.py   # F(), Condition, And, Or, Not, In, Between, Case, etc.
  dialect.py       # PostgreSQL, MySQL, SQLite dialect implementations
  schema.py        # CREATE TABLE / DROP TABLE schema builder
  types.py         # Enums and type definitions
```

## License

MIT
