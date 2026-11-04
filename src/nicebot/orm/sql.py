"""SQL backends: SQLite (aiosqlite), PostgreSQL (asyncpg), MySQL/MariaDB (aiomysql).

One compiler, three dialects. Auto-migration: missing tables are created and missing
columns/indexes are added on connect — your data is never dropped.
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
from typing import Any, AsyncIterator

from ..errors import IntegrityError
from .fields import Bool, Date, DateTime, Field, Float, ForeignKey, Int, JSON, Str, Text, BigInt, _MISSING
from .query import F, Q

log = logging.getLogger("nicebot.orm")


def _like_escape(v: str) -> str:
    return str(v).replace("!", "!!").replace("%", "!%").replace("_", "!_")


class SQLBackend:
    """Shared SQL implementation of the ORM (dialects subclass it). Internal: use ``Database``.

    Example::

        db = await Database("sqlite:///bot.db").connect()
    """
    dialect = "sql"
    q = '"'

    def __init__(self, url: str, **options: Any):
        self.url = url
        self.options = options

    # ------------------------------------------------------------- dialect bits
    def quote(self, name: str) -> str:
        """Quote a table/column name for this SQL dialect.

        Example::

            backend.quote("order")   # '"order"'
        """
        return f"{self.q}{name}{self.q}"

    def ph(self, i: int) -> str:
        """The parameter placeholder for position ``i`` (``?``, ``$1`` or ``%s``).

        Example::

            backend.ph(1)
        """
        return "?"

    def column_type(self, f: Field) -> str:
        """SQL column type for a field.

        Example::

            backend.column_type(fields.Str(50))   # "VARCHAR(50)"
        """
        raise NotImplementedError

    def pk_definition(self, f: Field) -> str:
        """SQL for the auto-increment primary key column.

        Example::

            backend.pk_definition()
        """
        raise NotImplementedError

    def limit_clause(self, limit: int | None, offset: int | None) -> str:
        """SQL ``LIMIT/OFFSET`` clause.

        Example::

            backend.limit_clause(10, 20)
        """
        sql = ""
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        if offset:
            if limit is None:
                sql += " LIMIT -1"
            sql += f" OFFSET {int(offset)}"
        return sql

    # ------------------------------------------------------------- driver api
    async def connect(self) -> None:
        """Open the connection or pool.

        Example::

            await backend.connect()
        """
        raise NotImplementedError

    async def close(self) -> None:
        """Close the connection or pool.

        Example::

            await backend.close()
        """
        raise NotImplementedError

    async def execute(self, sql: str, params: list[Any] | tuple = ()) -> int:
        """Run SQL; returns affected rows.

        Example::

            await backend.execute("DELETE FROM t WHERE id = ?", [1])
        """
        raise NotImplementedError

    async def fetch(self, sql: str, params: list[Any] | tuple = ()) -> list[dict[str, Any]]:
        """Run a query; returns rows as dicts.

        Example::

            rows = await backend.fetch("SELECT * FROM t", [])
        """
        raise NotImplementedError

    async def fetchval(self, sql: str, params: list[Any] | tuple = ()) -> Any:
        """Run a query and return the first column of the first row.

        Example::

            n = await backend.fetchval("SELECT COUNT(*) FROM t", [])
        """
        rows = await self.fetch(sql, params)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    async def insert_returning(self, sql: str, params: list[Any], pk: str) -> Any:
        """Insert a row and return its new primary key.

        Example::

            pk = await backend.insert_returning("INSERT ...", params, "id")
        """
        raise NotImplementedError

    async def existing_columns(self, table: str) -> set[str] | None:
        """Column names that already exist in a table (for auto-migration).

        Example::

            await backend.existing_columns("products")
        """
        raise NotImplementedError

    async def create_index(self, table: str, name: str, cols: list[str], unique: bool) -> None:
        """Create an index if it does not exist.

        Example::

            await backend.create_index("products", ["price"], unique=False)
        """
        u = "UNIQUE " if unique else ""
        cols_sql = ", ".join(self.quote(c) for c in cols)
        await self.execute(f"CREATE {u}INDEX IF NOT EXISTS {self.quote(name)} ON {self.quote(table)} ({cols_sql})")

    def transaction(self) -> Any:
        """Async context manager for a transaction.

        Example::

            async with backend.transaction(): ...
        """
        raise NotImplementedError

    def wrap_error(self, e: Exception) -> Exception:
        """Translate driver errors (unique violations…) into ``IntegrityError``.

        Example::

            raise backend.wrap_error(e)
        """
        name = type(e).__name__.lower()
        if "integrity" in name or "unique" in name or "foreignkey" in name or "notnull" in name:
            return IntegrityError(str(e))
        return e

    # ------------------------------------------------------------- schema
    def _literal(self, v: Any) -> str:
        if isinstance(v, bool):
            return ("TRUE" if v else "FALSE") if self.dialect == "postgres" else str(int(v))
        if isinstance(v, (int, float)):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"

    def column_sql(self, f: Field, for_alter: bool = False) -> str:
        """SQL definition of one column.

        Example::

            backend.column_sql(field)   # '"price" INTEGER NOT NULL DEFAULT 0'
        """
        if f.pk:
            return self.pk_definition(f)
        parts = [self.quote(f.column), self.column_type(f)]
        default = f.default
        simple_default = default is not _MISSING and not callable(default) and default is not None and not isinstance(f, (JSON, Text))
        if simple_default:
            parts.append(f"DEFAULT {self._literal(f.to_db(default, self.dialect))}")
        if not f.null and (not for_alter or simple_default):
            parts.append("NOT NULL")
        if f.unique and not for_alter:
            parts.append("UNIQUE")
        if isinstance(f, ForeignKey) and not for_alter:
            target = f.target()
            parts.append(f"REFERENCES {self.quote(target._meta.table)}({self.quote(target._meta.pk.column)}) ON DELETE {f.on_delete}")
        return " ".join(parts)

    def create_table_sql(self, model: Any) -> str:
        """``CREATE TABLE`` statement for a model.

        Example::

            backend.create_table_sql(Product._meta)
        """
        meta = model._meta
        cols = [self.column_sql(f) for f in meta.fields.values()]
        return f"CREATE TABLE IF NOT EXISTS {self.quote(meta.table)} ({', '.join(cols)}){self.table_suffix()}"

    def table_suffix(self) -> str:
        """Extra SQL after ``CREATE TABLE (...)`` (MySQL engine/charset).

        Example::

            backend.table_suffix()
        """
        return ""

    async def sync_schema(self, model: Any) -> None:
        """Create missing tables, columns and indexes for a model (never drops data).

        Example::

            await backend.sync_schema(Product._meta)
        """
        meta = model._meta
        existing = await self.existing_columns(meta.table)
        if existing is None:
            await self.execute(self.create_table_sql(model))
            log.info("Jadval yaratildi: %s", meta.table)
        else:
            for f in meta.fields.values():
                if f.column not in existing:
                    await self.execute(f"ALTER TABLE {self.quote(meta.table)} ADD COLUMN {self.column_sql(f, for_alter=True)}")
                    log.info("Column added: %s.%s", meta.table, f.column)
                    if f.unique and not f.pk:
                        await self.create_index(meta.table, f"uq_{meta.table}_{f.column}", [f.column], True)
        for f in meta.fields.values():
            if f.index and not f.unique:
                await self.create_index(meta.table, f"ix_{meta.table}_{f.column}", [f.column], False)
        for cols in meta.indexes:
            columns = [meta.field(c).column for c in cols]
            await self.create_index(meta.table, f"ix_{meta.table}_{'_'.join(columns)}", columns, False)
        for cols in meta.unique_together:
            columns = [meta.field(c).column for c in cols]
            await self.create_index(meta.table, f"uq_{meta.table}_{'_'.join(columns)}", columns, True)

    # ------------------------------------------------------------- compiler
    def compile_q(self, q: Q, model: Any, params: list[Any]) -> str:
        """Compile a ``Q`` tree into a WHERE fragment / query document.

        Example::

            where, params = backend.compile_q(meta, Q(price__lt=5))
        """
        parts: list[str] = []
        for child in q.children:
            if isinstance(child, Q):
                if not child.children:
                    continue
                parts.append(self.compile_q(child, model, params))
            else:
                parts.append(self.compile_leaf(child, model, params))
        if not parts:
            sql = "1=1"
        else:
            sql = f" {q.op} ".join(parts)
            if len(parts) > 1:
                sql = f"({sql})"
        return f"NOT ({sql})" if q.negated else sql

    def compile_leaf(self, leaf: tuple[str, str, Any], model: Any, params: list[Any]) -> str:
        """Compile one ``field__lookup=value`` condition.

        Example::

            backend.compile_leaf(meta, "price", "lt", 5, params)
        """
        name, op, value = leaf
        f = model._meta.field(name)
        col = self.quote(f.column)
        d = self.dialect

        def p(v: Any, convert: bool = True) -> str:
            params.append(f.to_db(v, d) if convert else v)
            return self.ph(len(params))

        if op == "exact":
            return f"{col} IS NULL" if value is None else f"{col} = {p(value)}"
        if op == "ne":
            return f"{col} IS NOT NULL" if value is None else f"({col} <> {p(value)} OR {col} IS NULL)"
        if op in ("gt", "gte", "lt", "lte"):
            sym = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
            return f"{col} {sym} {p(value)}"
        if op == "in":
            values = list(value)
            if not values:
                return "1=0"
            return f"{col} IN ({', '.join(p(v) for v in values)})"
        if op == "not_in":
            values = list(value)
            if not values:
                return "1=1"
            return f"({col} NOT IN ({', '.join(p(v) for v in values)}) OR {col} IS NULL)"
        if op == "isnull":
            return f"{col} IS NULL" if value else f"{col} IS NOT NULL"
        if op == "between":
            lo, hi = value
            return f"{col} BETWEEN {p(lo)} AND {p(hi)}"
        if op in ("contains", "icontains", "startswith", "istartswith", "endswith", "iendswith"):
            v = _like_escape(value)
            base = op[1:] if op.startswith("i") else op
            pattern = {"contains": f"%{v}%", "startswith": f"{v}%", "endswith": f"%{v}"}[base]
            if op.startswith("i"):
                return f"LOWER({col}) LIKE LOWER({p(pattern, False)}) ESCAPE '!'"
            return f"{col} LIKE {p(pattern, False)} ESCAPE '!'"
        raise ValueError(f"Unsupported lookup: {op}")

    def where_sql(self, q: Q, model: Any, params: list[Any]) -> str:
        """Full WHERE clause for a QuerySet.

        Example::

            backend.where_sql(qs, params)
        """
        if not q or not q.children:
            return ""
        return " WHERE " + self.compile_q(q, model, params)

    def order_sql(self, model: Any, ordering: list[str]) -> str:
        """ORDER BY clause for a QuerySet.

        Example::

            backend.order_sql(qs)
        """
        if not ordering:
            return ""
        parts = []
        for o in ordering:
            desc = o.startswith("-")
            f = model._meta.field(o.lstrip("-"))
            parts.append(f"{self.quote(f.column)} {'DESC' if desc else 'ASC'}")
        return " ORDER BY " + ", ".join(parts)

    # ------------------------------------------------------------- operations
    async def _guard(self, coro: Any) -> Any:
        try:
            return await coro
        except Exception as e:  # noqa: BLE001
            err = self.wrap_error(e)
            if err is e:
                raise
            raise err from e

    async def insert(self, model: Any, row: dict[str, Any]) -> Any:
        """Insert one row; returns the primary key.

        Example::

            await backend.insert(meta, {"title": "Book"})
        """
        meta = model._meta
        cols = list(row)
        params = list(row.values())
        if cols:
            sql = f"INSERT INTO {self.quote(meta.table)} ({', '.join(self.quote(c) for c in cols)}) VALUES ({', '.join(self.ph(i + 1) for i in range(len(cols)))})"
        else:
            sql = self.empty_insert_sql(meta.table)
        pk = await self._guard(self.insert_returning(sql, params, meta.pk.column))
        return row.get(meta.pk.column, pk) if pk is None else pk

    def empty_insert_sql(self, table: str) -> str:
        """SQL to insert a row with only default values.

        Example::

            backend.empty_insert_sql("t")
        """
        return f"INSERT INTO {self.quote(table)} DEFAULT VALUES"

    async def bulk_insert(self, model: Any, rows: list[dict[str, Any]]) -> list[Any]:
        """Insert many rows at once.

        Example::

            await backend.bulk_insert(meta, rows)
        """
        ids = []
        async with self.transaction():
            for row in rows:
                ids.append(await self.insert(model, row))
        return ids

    async def select(self, model: Any, qs: Any) -> list[dict[str, Any]]:
        """Run a QuerySet and return rows.

        Example::

            rows = await backend.select(qs)
        """
        meta = model._meta
        params: list[Any] = []
        if qs._values is not None:
            cols = ", ".join(self.quote(meta.field(v).column) for v in qs._values)
        else:
            cols = ", ".join(self.quote(f.column) for f in meta.fields.values())
        sql = f"SELECT {cols} FROM {self.quote(meta.table)}"
        sql += self.where_sql(qs.where, model, params)
        sql += self.order_sql(model, qs.ordering)
        sql += self.limit_clause(qs._limit, qs._offset)
        return await self.fetch(sql, params)

    async def count(self, model: Any, where: Q) -> int:
        """Count rows of a QuerySet.

        Example::

            n = await backend.count(qs)
        """
        params: list[Any] = []
        sql = f"SELECT COUNT(*) AS n FROM {self.quote(model._meta.table)}" + self.where_sql(where, model, params)
        return int(await self.fetchval(sql, params) or 0)

    async def aggregate(self, model: Any, where: Q, func: str, f: Field) -> Any:
        """SUM/AVG/MIN/MAX of a field.

        Example::

            await backend.aggregate(qs, "SUM", "price")
        """
        params: list[Any] = []
        sql = f"SELECT {func}({self.quote(f.column)}) AS v FROM {self.quote(model._meta.table)}" + self.where_sql(where, model, params)
        v = await self.fetchval(sql, params)
        if v is None:
            return None
        if func in ("MAX", "MIN"):
            return f.from_db(v, self.dialect)
        if func == "SUM" and isinstance(f, Int) and not isinstance(f, Float):
            return int(v)
        return float(v)

    def _set_expr(self, f: Field, value: Any, model: Any, params: list[Any]) -> str:
        if isinstance(value, F):
            expr = self.quote(model._meta.field(value.field).column)
            for op, operand in value.ops:
                params.append(operand)
                expr = f"({expr} {op} {self.ph(len(params))})"
            return expr
        params.append(f.to_db(value, self.dialect))
        return self.ph(len(params))

    async def update(self, model: Any, where: Q, data: dict[Field, Any]) -> int:
        """Update rows of a QuerySet; returns how many changed.

        Example::

            await backend.update(qs, {field: 5})
        """
        if not data:
            return 0
        params: list[Any] = []
        sets = ", ".join(f"{self.quote(f.column)} = {self._set_expr(f, v, model, params)}" for f, v in data.items())
        sql = f"UPDATE {self.quote(model._meta.table)} SET {sets}" + self.where_sql(where, model, params)
        return await self._guard(self.execute(sql, params))

    async def delete(self, model: Any, where: Q) -> int:
        """Delete rows of a QuerySet; returns how many.

        Example::

            await backend.delete(qs)
        """
        params: list[Any] = []
        sql = f"DELETE FROM {self.quote(model._meta.table)}" + self.where_sql(where, model, params)
        return await self._guard(self.execute(sql, params))


# =========================================================================== SQLite
class SQLiteBackend(SQLBackend):
    """SQLite via aiosqlite (``sqlite:///file.db``, ``sqlite:///:memory:``).

    Example::

        Nicebot(token="...", db="sqlite:///bot.db")
    """
    dialect = "sqlite"

    def __init__(self, url: str, **options: Any):
        super().__init__(url, **options)
        path = url.split("://", 1)[1]
        if path.startswith("/"):
            path = path[1:]
        self.path = path or ":memory:"
        self.conn: Any = None
        self._tx_lock = asyncio.Lock()
        self._in_tx: contextvars.ContextVar[bool] = contextvars.ContextVar("nb_sqlite_tx", default=False)

    def column_type(self, f: Field) -> str:
        """SQL column type for a field.

        Example::

            backend.column_type(fields.Str(50))   # "VARCHAR(50)"
        """
        if isinstance(f, (Int, Bool)):
            return "INTEGER"
        if isinstance(f, Float):
            return "REAL"
        return "TEXT"

    def pk_definition(self, f: Field) -> str:
        """SQL for the auto-increment primary key column.

        Example::

            backend.pk_definition()
        """
        if f.generated:
            return f"{self.quote(f.column)} INTEGER PRIMARY KEY AUTOINCREMENT"
        return f"{self.quote(f.column)} {self.column_type(f)} PRIMARY KEY"

    async def connect(self) -> None:
        """Open the connection or pool.

        Example::

            await backend.connect()
        """
        try:
            import aiosqlite
        except ImportError as e:  # pragma: no cover
            raise ImportError("SQLite needs aiosqlite, which comes with nicebot: pip install nicebot") from e
        self.conn = await aiosqlite.connect(self.path, isolation_level=None)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            await self.conn.execute("PRAGMA journal_mode = WAL")
            await self.conn.execute("PRAGMA synchronous = NORMAL")
        await self.conn.execute("PRAGMA busy_timeout = 5000")

    async def close(self) -> None:
        """Close the connection or pool.

        Example::

            await backend.close()
        """
        if self.conn is not None:
            await self.conn.close()
            self.conn = None

    async def _wait_tx(self) -> None:
        # statements outside a running transaction wait for it to finish
        if self._tx_lock.locked() and not self._in_tx.get():
            async with self._tx_lock:
                pass

    async def execute(self, sql: str, params: list[Any] | tuple = ()) -> int:
        """Run SQL; returns affected rows.

        Example::

            await backend.execute("DELETE FROM t WHERE id = ?", [1])
        """
        await self._wait_tx()
        cur = await self.conn.execute(sql, list(params))
        n = cur.rowcount
        await cur.close()
        return n

    async def fetch(self, sql: str, params: list[Any] | tuple = ()) -> list[dict[str, Any]]:
        """Run a query; returns rows as dicts.

        Example::

            rows = await backend.fetch("SELECT * FROM t", [])
        """
        await self._wait_tx()
        cur = await self.conn.execute(sql, list(params))
        rows = await cur.fetchall()
        await cur.close()
        return [dict(r) for r in rows]

    async def insert_returning(self, sql: str, params: list[Any], pk: str) -> Any:
        """Insert a row and return its new primary key.

        Example::

            pk = await backend.insert_returning("INSERT ...", params, "id")
        """
        await self._wait_tx()
        cur = await self.conn.execute(sql, params)
        rid = cur.lastrowid
        await cur.close()
        return rid

    async def existing_columns(self, table: str) -> set[str] | None:
        """Column names that already exist in a table (for auto-migration).

        Example::

            await backend.existing_columns("products")
        """
        rows = await self.fetch(f"PRAGMA table_info({self.quote(table)})")
        return {r["name"] for r in rows} if rows else None

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Async context manager for a transaction.

        Example::

            async with backend.transaction(): ...
        """
        if self._in_tx.get():
            yield
            return
        async with self._tx_lock:
            token = self._in_tx.set(True)
            await self.conn.execute("BEGIN")
            try:
                yield
            except BaseException:
                await self.conn.execute("ROLLBACK")
                raise
            else:
                await self.conn.execute("COMMIT")
            finally:
                self._in_tx.reset(token)


# =========================================================================== PostgreSQL
class PostgresBackend(SQLBackend):
    """PostgreSQL via asyncpg (``pip install "nicebot[postgres]"``).

    Example::

        Nicebot(token="...", db="postgresql://user:pass@localhost/shop")
    """
    dialect = "postgres"

    def __init__(self, url: str, **options: Any):
        super().__init__(url.replace("postgres://", "postgresql://", 1), **options)
        self.pool: Any = None
        self._conn: contextvars.ContextVar[Any] = contextvars.ContextVar("nb_pg_conn", default=None)

    def ph(self, i: int) -> str:
        """The parameter placeholder for position ``i`` (``?``, ``$1`` or ``%s``).

        Example::

            backend.ph(1)
        """
        return f"${i}"

    def column_type(self, f: Field) -> str:
        """SQL column type for a field.

        Example::

            backend.column_type(fields.Str(50))   # "VARCHAR(50)"
        """
        if isinstance(f, Bool):
            return "BOOLEAN"
        if isinstance(f, BigInt):
            return "BIGINT"
        if isinstance(f, Int):
            return "INTEGER"
        if isinstance(f, Float):
            return "DOUBLE PRECISION"
        if isinstance(f, Str):
            return f"VARCHAR({f.max_length})"
        if isinstance(f, DateTime):
            return "TIMESTAMPTZ"
        if isinstance(f, Date):
            return "DATE"
        if isinstance(f, JSON):
            return "JSONB"
        return "TEXT"

    def pk_definition(self, f: Field) -> str:
        """SQL for the auto-increment primary key column.

        Example::

            backend.pk_definition()
        """
        if f.generated:
            kind = "BIGSERIAL" if isinstance(f, BigInt) else "SERIAL"
            return f"{self.quote(f.column)} {kind} PRIMARY KEY"
        return f"{self.quote(f.column)} {self.column_type(f)} PRIMARY KEY"

    def limit_clause(self, limit: int | None, offset: int | None) -> str:
        """SQL ``LIMIT/OFFSET`` clause.

        Example::

            backend.limit_clause(10, 20)
        """
        sql = ""
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        if offset:
            sql += f" OFFSET {int(offset)}"
        return sql

    async def connect(self) -> None:
        """Open the connection or pool.

        Example::

            await backend.connect()
        """
        try:
            import asyncpg
        except ImportError as e:  # pragma: no cover
            raise ImportError("PostgreSQL needs an extra package: pip install 'nicebot[postgres]'") from e
        self.pool = await asyncpg.create_pool(self.url, min_size=self.options.get("min_size", 1), max_size=self.options.get("max_size", 10))

    async def close(self) -> None:
        """Close the connection or pool.

        Example::

            await backend.close()
        """
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    @contextlib.asynccontextmanager
    async def _acquire(self) -> AsyncIterator[Any]:
        conn = self._conn.get()
        if conn is not None:
            yield conn
            return
        async with self.pool.acquire() as conn:
            yield conn

    async def execute(self, sql: str, params: list[Any] | tuple = ()) -> int:
        """Run SQL; returns affected rows.

        Example::

            await backend.execute("DELETE FROM t WHERE id = ?", [1])
        """
        async with self._acquire() as c:
            status = await c.execute(sql, *params)
        try:
            return int(status.rsplit(" ", 1)[-1])
        except (ValueError, AttributeError):
            return 0

    async def fetch(self, sql: str, params: list[Any] | tuple = ()) -> list[dict[str, Any]]:
        """Run a query; returns rows as dicts.

        Example::

            rows = await backend.fetch("SELECT * FROM t", [])
        """
        async with self._acquire() as c:
            rows = await c.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def insert_returning(self, sql: str, params: list[Any], pk: str) -> Any:
        """Insert a row and return its new primary key.

        Example::

            pk = await backend.insert_returning("INSERT ...", params, "id")
        """
        async with self._acquire() as c:
            return await c.fetchval(sql + f" RETURNING {self.quote(pk)}", *params)

    async def existing_columns(self, table: str) -> set[str] | None:
        """Column names that already exist in a table (for auto-migration).

        Example::

            await backend.existing_columns("products")
        """
        rows = await self.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = $1",
            [table],
        )
        return {r["column_name"] for r in rows} if rows else None

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Async context manager for a transaction.

        Example::

            async with backend.transaction(): ...
        """
        if self._conn.get() is not None:
            async with self._conn.get().transaction():
                yield
            return
        async with self.pool.acquire() as conn:
            token = self._conn.set(conn)
            try:
                async with conn.transaction():
                    yield
            finally:
                self._conn.reset(token)


# =========================================================================== MySQL / MariaDB
class MySQLBackend(SQLBackend):
    """MySQL/MariaDB via aiomysql (``pip install "nicebot[mysql]"``).

    Example::

        Nicebot(token="...", db="mysql://user:pass@localhost/shop")
    """
    dialect = "mysql"
    q = "`"

    def __init__(self, url: str, **options: Any):
        super().__init__(url, **options)
        self.pool: Any = None
        self._conn: contextvars.ContextVar[Any] = contextvars.ContextVar("nb_my_conn", default=None)

    def ph(self, i: int) -> str:
        """The parameter placeholder for position ``i`` (``?``, ``$1`` or ``%s``).

        Example::

            backend.ph(1)
        """
        return "%s"

    def column_type(self, f: Field) -> str:
        """SQL column type for a field.

        Example::

            backend.column_type(fields.Str(50))   # "VARCHAR(50)"
        """
        if isinstance(f, Bool):
            return "TINYINT(1)"
        if isinstance(f, BigInt):
            return "BIGINT"
        if isinstance(f, Int):
            return "INT"
        if isinstance(f, Float):
            return "DOUBLE"
        if isinstance(f, Str):
            return f"VARCHAR({f.max_length})"
        if isinstance(f, DateTime):
            return "DATETIME(6)"
        if isinstance(f, Date):
            return "DATE"
        return "LONGTEXT"

    def pk_definition(self, f: Field) -> str:
        """SQL for the auto-increment primary key column.

        Example::

            backend.pk_definition()
        """
        if f.generated:
            return f"{self.quote(f.column)} BIGINT AUTO_INCREMENT PRIMARY KEY"
        return f"{self.quote(f.column)} {self.column_type(f)} PRIMARY KEY"

    def table_suffix(self) -> str:
        """Extra SQL after ``CREATE TABLE (...)`` (MySQL engine/charset).

        Example::

            backend.table_suffix()
        """
        return " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"

    def limit_clause(self, limit: int | None, offset: int | None) -> str:
        """SQL ``LIMIT/OFFSET`` clause.

        Example::

            backend.limit_clause(10, 20)
        """
        sql = ""
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        if offset:
            if limit is None:
                sql += " LIMIT 18446744073709551615"
            sql += f" OFFSET {int(offset)}"
        return sql

    def empty_insert_sql(self, table: str) -> str:
        """SQL to insert a row with only default values.

        Example::

            backend.empty_insert_sql("t")
        """
        return f"INSERT INTO {self.quote(table)} () VALUES ()"

    async def connect(self) -> None:
        """Open the connection or pool.

        Example::

            await backend.connect()
        """
        try:
            import aiomysql
        except ImportError as e:  # pragma: no cover
            raise ImportError("MySQL needs an extra package: pip install 'nicebot[mysql]'") from e
        from urllib.parse import unquote, urlparse

        u = urlparse(self.url)
        self.pool = await aiomysql.create_pool(
            host=u.hostname or "localhost",
            port=u.port or 3306,
            user=unquote(u.username or "root"),
            password=unquote(u.password or ""),
            db=(u.path or "/").lstrip("/") or None,
            autocommit=True,
            charset="utf8mb4",
            minsize=self.options.get("min_size", 1),
            maxsize=self.options.get("max_size", 10),
        )

    async def close(self) -> None:
        """Close the connection or pool.

        Example::

            await backend.close()
        """
        if self.pool is not None:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None

    @contextlib.asynccontextmanager
    async def _cursor(self) -> AsyncIterator[Any]:
        import aiomysql

        conn = self._conn.get()
        if conn is not None:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                yield cur
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                yield cur

    async def execute(self, sql: str, params: list[Any] | tuple = ()) -> int:
        """Run SQL; returns affected rows.

        Example::

            await backend.execute("DELETE FROM t WHERE id = ?", [1])
        """
        async with self._cursor() as cur:
            return await cur.execute(sql, tuple(params))

    async def fetch(self, sql: str, params: list[Any] | tuple = ()) -> list[dict[str, Any]]:
        """Run a query; returns rows as dicts.

        Example::

            rows = await backend.fetch("SELECT * FROM t", [])
        """
        async with self._cursor() as cur:
            await cur.execute(sql, tuple(params))
            return list(await cur.fetchall())

    async def insert_returning(self, sql: str, params: list[Any], pk: str) -> Any:
        """Insert a row and return its new primary key.

        Example::

            pk = await backend.insert_returning("INSERT ...", params, "id")
        """
        async with self._cursor() as cur:
            await cur.execute(sql, tuple(params))
            return cur.lastrowid

    async def existing_columns(self, table: str) -> set[str] | None:
        """Column names that already exist in a table (for auto-migration).

        Example::

            await backend.existing_columns("products")
        """
        rows = await self.fetch(
            "SELECT COLUMN_NAME AS c FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = %s",
            [table],
        )
        return {r["c"] for r in rows} if rows else None

    async def create_index(self, table: str, name: str, cols: list[str], unique: bool) -> None:
        """Create an index if it does not exist.

        Example::

            await backend.create_index("products", ["price"], unique=False)
        """
        exists = await self.fetch(
            "SELECT 1 AS x FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s",
            [table, name],
        )
        if exists:
            return
        u = "UNIQUE " if unique else ""
        await self.execute(f"CREATE {u}INDEX {self.quote(name)} ON {self.quote(table)} ({', '.join(self.quote(c) for c in cols)})")

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Async context manager for a transaction.

        Example::

            async with backend.transaction(): ...
        """
        if self._conn.get() is not None:
            yield
            return
        async with self.pool.acquire() as conn:
            token = self._conn.set(conn)
            await conn.begin()
            try:
                yield
            except BaseException:
                await conn.rollback()
                raise
            else:
                await conn.commit()
            finally:
                self._conn.reset(token)
