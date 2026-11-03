"""Database: pick a backend from a URL, connect, auto-migrate."""
from __future__ import annotations

import logging
from typing import Any, Iterable

log = logging.getLogger("nicebot.orm")

_CURRENT: "Database | None" = None


def current_database() -> "Database":
    if _CURRENT is None:
        raise RuntimeError(
            "Baza ulanmagan. Nicebot(db='sqlite:///bot.db') bering yoki `await Database(url).connect()` chaqiring."
        )
    return _CURRENT


def backend_for(url: str, **options: Any) -> Any:
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
    raise ValueError(f"Noma'lum baza turi: {scheme!r}. Mavjud: sqlite, postgres, mysql, mongodb")


class Database:
    """``db = Database("postgres://user:pass@host/db"); await db.connect()``

    URL examples::

        sqlite:///bot.db            sqlite:///:memory:
        postgres://user:pass@localhost:5432/mybot
        mysql://user:pass@localhost:3306/mybot
        mongodb://localhost:27017/mybot
    """

    def __init__(self, url: str, **options: Any):
        self.url = url
        self.backend = backend_for(url, **options)
        self.connected = False

    @property
    def dialect(self) -> str:
        return self.backend.dialect

    async def connect(self, models: Iterable[type] | None = None, *, migrate: bool = True, default: bool = True) -> "Database":
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
        """``async with db.transaction(): ...`` — all-or-nothing (SQL databases)."""
        return self.backend.transaction()

    async def execute(self, sql: str, *params: Any) -> int:
        """Raw SQL escape hatch (SQL backends only)."""
        return await self.backend.execute(sql, list(params))

    async def fetch(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        return await self.backend.fetch(sql, list(params))

    async def close(self) -> None:
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
