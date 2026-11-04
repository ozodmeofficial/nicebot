"""Database connection: ``Database(url)`` for SQLite, PostgreSQL, MySQL/MariaDB and MongoDB.

Example::

    bot = Nicebot(token="...", db="postgresql://user:pass@localhost/shop")    # connected on start
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

log = logging.getLogger("nicebot.orm")

_CURRENT: "Database | None" = None


def current_database() -> "Database":
    """The database the models use (the one connected last with ``default=True``).

    Example::

        db = current_database()
    """
    if _CURRENT is None:
        raise RuntimeError(
            "No database is connected. Pass Nicebot(db='sqlite:///bot.db') or call `await Database(url).connect()`."
        )
    return _CURRENT


def backend_for(url: str, **options: Any) -> Any:
    """Create the backend for a URL: ``sqlite://``, ``postgres://``/``postgresql://``, ``mysql://``/``mariadb://`` or ``mongodb://``.

    Example::

        backend = backend_for("sqlite:///bot.db")
    """
    scheme = url.split("://", 1)[0].lower()
    if scheme in ("sqlite", "sqlite3"):
        from .sql import SQLiteBackend

        return SQLiteBackend(url, **options)
    if scheme in ("postgres", "postgresql", "pg"):
        from .sql import PostgresBackend

        return PostgresBackend(url.replace("pg://", "postgresql://", 1), **options)
    if scheme in ("mysql", "mariadb"):
        from .sql import MySQLBackend

        return MySQLBackend(url, **options)
    if scheme in ("mongodb", "mongodb+srv", "mongo"):
        from .mongo import MongoBackend

        return MongoBackend(url.replace("mongo://", "mongodb://", 1), **options)
    raise ValueError(f"Unknown database type {scheme!r}. Supported: sqlite, postgres, mysql, mongodb")


class Database:
    """A database connection used by your models. ``Nicebot(db=...)`` creates and connects it for you.

    Example::

        db = await Database("postgresql://user:pass@localhost/shop").connect()
        async with db.transaction():
            await Order.create(user_id=1, product="Book")
        rows = await db.fetch("SELECT COUNT(*) AS n FROM orders")
        await db.close()
    """

    def __init__(self, url: str, **options: Any):
        self.url = url
        self.backend = backend_for(url, **options)
        self.connected = False

    @property
    def dialect(self) -> str:
        """``"sqlite"``, ``"postgres"``, ``"mysql"`` or ``"mongodb"``.

        Example::

            if bot.db.dialect == "sqlite": ...
        """
        return self.backend.dialect

    async def connect(self, models: Iterable[type] | None = None, *, migrate: bool = True, default: bool = True) -> "Database":
        """Open the connection and (with ``migrate=True``) create missing tables and columns. Returns the database.

        Example::

            db = await Database("sqlite:///bot.db").connect()
        """
        global _CURRENT
        await self.backend.connect()
        self.connected = True
        if default or _CURRENT is None:
            _CURRENT = self
        if models is not None:
            for m in models:
                m._meta.database = self
        if migrate:
            await self.migrate(models)
        return self

    async def migrate(self, models: Iterable[type] | None = None) -> None:
        """Create missing tables/columns/indexes for the models (data is never deleted).

        Example::

            await db.migrate([Product, Order])
        """
        from .model import registry

        todo = list(models) if models is not None else [m for m in registry().values() if not m._meta.abstract]
        # parents (FK targets) first
        ordered: list[type] = []

        def visit(m: type, stack: tuple = ()) -> None:
            if m in ordered or m in stack:
                return
            from .fields import ForeignKey

            for f in m._meta.fields.values():
                if isinstance(f, ForeignKey):
                    t = f.target()
                    if t is not m:
                        visit(t, stack + (m,))
            ordered.append(m)

        for m in todo:
            visit(m)
        for m in ordered:
            if m._meta.database not in (None, self) and models is None:
                continue
            await self.backend.sync_schema(m)
            m._meta.synced = True

    def transaction(self) -> Any:
        """``async with db.transaction():`` — all-or-nothing (SQL databases; a no-op on MongoDB without replica set).

        Example::

            async with bot.db.transaction():
                await buyer.increment("balance", -price)
                await seller.increment("balance", price)
        """
        return self.backend.transaction()

    async def execute(self, sql: str, *params: Any) -> int:
        """Run raw SQL and return the number of affected rows (SQL backends only).

        Example::

            await bot.db.execute("UPDATE products SET price = price * 1.1")
        """
        return await self.backend.execute(sql, list(params))

    async def fetch(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        """Run a raw SQL query and return rows as dicts (SQL backends only).

        Example::

            rows = await bot.db.fetch("SELECT city, COUNT(*) AS n FROM customers GROUP BY city")
        """
        return await self.backend.fetch(sql, list(params))

    async def close(self) -> None:
        """Close the connection.

        Example::

            await db.close()
        """
        global _CURRENT
        await self.backend.close()
        self.connected = False
        if _CURRENT is self:
            _CURRENT = None

    async def __aenter__(self) -> "Database":
        if not self.connected:
            await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"<Database {self.dialect}>"
