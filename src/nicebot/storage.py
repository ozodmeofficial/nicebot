"""Key–value storage for states, buttons, caches and counters.

Backends: ``DBStorage`` (default, your ORM database), ``MemoryStorage`` and ``RedisStorage`` (``redis://``).
Values must be JSON-serialisable.

Example::

    await bot.storage.set("maintenance_note", "back at 18:00", ttl=3600)
    note = await bot.storage.get("maintenance_note")
"""
from __future__ import annotations

import time
from typing import Any

import msgspec

_enc = msgspec.json.Encoder()
_dec = msgspec.json.Decoder()


class Storage:
    """Interface of a key–value store (all methods are async). Subclass it to plug in your own backend.

    Example::

        await bot.storage.set("promo:active", True, ttl=3600)
        if await bot.storage.get("promo:active"):
            ...
    """

    async def get(self, key: str, default: Any = None) -> Any:
        """Read a value (``default`` if missing or expired).

        Example::

            count = await bot.storage.get("visits", 0)
        """
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a JSON-serialisable value; ``ttl`` in seconds.

        Example::

            await bot.storage.set("otp:42", "1234", ttl=300)
        """
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        """Delete a key; returns ``True`` if it existed.

        Example::

            await bot.storage.delete("otp:42")
        """
        raise NotImplementedError

    async def pop(self, key: str, default: Any = None) -> Any:
        """Get and delete in one step.

        Example::

            code = await bot.storage.pop("otp:42")
        """
        value = await self.get(key, default)
        await self.delete(key)
        return value

    async def incr(self, key: str, amount: int = 1, ttl: float | None = None) -> int:
        """Add ``amount`` to a counter and return the new value.

        Example::

            n = await bot.storage.incr(f"clicks:{ctx.user_id}", ttl=86400)
        """
        value = int(await self.get(key, 0) or 0) + amount
        await self.set(key, value, ttl)
        return value

    async def exists(self, key: str) -> bool:
        """Is the key present?

        Example::

            if await bot.storage.exists("lock"):
                return
        """
        sentinel = "__nb_missing__"
        return (await self.get(key, sentinel)) != sentinel

    async def close(self) -> None:
        """Release connections (called on shutdown).

        Example::

            await storage.close()
        """
        return None


class MemoryStorage(Storage):
    """Fast in-process storage; lost on restart. Good for tests and tiny bots.

    Example::

        bot = Nicebot(token="...", storage="memory")
    """

    def __init__(self) -> None:
        self._d: dict[str, tuple[float | None, Any]] = {}
        self._ops = 0

    def _alive(self, key: str) -> tuple[bool, Any]:
        item = self._d.get(key)
        if item is None:
            return False, None
        exp, val = item
        if exp is not None and exp < time.time():
            del self._d[key]
            return False, None
        return True, val

    def _gc(self) -> None:
        self._ops += 1
        if self._ops % 5000 == 0:
            now = time.time()
            for k in [k for k, (e, _) in self._d.items() if e is not None and e < now]:
                self._d.pop(k, None)

    async def get(self, key: str, default: Any = None) -> Any:
        """Read a value (``default`` if missing or expired).

        Example::

            count = await bot.storage.get("visits", 0)
        """
        ok, val = self._alive(key)
        return val if ok else default

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a JSON-serialisable value; ``ttl`` in seconds.

        Example::

            await bot.storage.set("otp:42", "1234", ttl=300)
        """
        self._gc()
        self._d[key] = (time.time() + ttl if ttl else None, value)

    async def delete(self, key: str) -> bool:
        """Delete a key; returns ``True`` if it existed.

        Example::

            await bot.storage.delete("otp:42")
        """
        return self._d.pop(key, None) is not None

    async def pop(self, key: str, default: Any = None) -> Any:
        """Get and delete in one step.

        Example::

            code = await bot.storage.pop("otp:42")
        """
        ok, val = self._alive(key)
        self._d.pop(key, None)
        return val if ok else default

    async def incr(self, key: str, amount: int = 1, ttl: float | None = None) -> int:
        """Add ``amount`` to a counter and return the new value.

        Example::

            n = await bot.storage.incr(f"clicks:{ctx.user_id}", ttl=86400)
        """
        ok, val = self._alive(key)
        exp = self._d[key][0] if ok else (time.time() + ttl if ttl else None)
        value = (int(val) if ok else 0) + amount
        self._d[key] = (exp, value)
        return value


class RedisStorage(Storage):
    """Redis storage (``pip install "nicebot[redis]"``): persistent and shared between processes.

    Example::

        bot = Nicebot(token="...", storage="redis://localhost:6379/0")
    """

    def __init__(self, url: str = "redis://localhost:6379/0", prefix: str = "nb:"):
        try:
            import redis.asyncio as aioredis
        except ImportError as e:  # pragma: no cover
            raise ImportError("Redis needs an extra package: pip install 'nicebot[redis]'") from e
        self.r = aioredis.from_url(url)
        self.prefix = prefix

    async def get(self, key: str, default: Any = None) -> Any:
        """Read a value (``default`` if missing or expired).

        Example::

            count = await bot.storage.get("visits", 0)
        """
        raw = await self.r.get(self.prefix + key)
        return default if raw is None else _dec.decode(raw)

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a JSON-serialisable value; ``ttl`` in seconds.

        Example::

            await bot.storage.set("otp:42", "1234", ttl=300)
        """
        await self.r.set(self.prefix + key, _enc.encode(value), px=int(ttl * 1000) if ttl else None)

    async def delete(self, key: str) -> bool:
        """Delete a key; returns ``True`` if it existed.

        Example::

            await bot.storage.delete("otp:42")
        """
        return bool(await self.r.delete(self.prefix + key))

    async def pop(self, key: str, default: Any = None) -> Any:
        """Get and delete in one step.

        Example::

            code = await bot.storage.pop("otp:42")
        """
        raw = await self.r.getdel(self.prefix + key)
        return default if raw is None else _dec.decode(raw)

    async def incr(self, key: str, amount: int = 1, ttl: float | None = None) -> int:
        """Add ``amount`` to a counter and return the new value.

        Example::

            n = await bot.storage.incr(f"clicks:{ctx.user_id}", ttl=86400)
        """
        k = self.prefix + key
        value = int(await self.r.incrby(k, amount))
        if ttl and value == amount:
            await self.r.pexpire(k, int(ttl * 1000))
        return value

    async def close(self) -> None:
        """Release connections (called on shutdown).

        Example::

            await storage.close()
        """
        await self.r.aclose()


class DBStorage(Storage):
    """Keeps keys in your ORM database (table ``nb_kv``). The default: persistent, no extra service.

    Example::

        bot = Nicebot(token="...", db="sqlite:///bot.db")   # storage="db" is the default
    """

    def __init__(self) -> None:
        from .orm.builtin import KV

        self.KV = KV

    async def get(self, key: str, default: Any = None) -> Any:
        """Read a value (``default`` if missing or expired).

        Example::

            count = await bot.storage.get("visits", 0)
        """
        row = await self.KV.get_or_none(key=key)
        if row is None:
            return default
        if row.expires_at is not None and row.expires_at < time.time():
            await self.KV.filter(key=key).delete()
            return default
        return _dec.decode(row.value.encode())

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a JSON-serialisable value; ``ttl`` in seconds.

        Example::

            await bot.storage.set("otp:42", "1234", ttl=300)
        """
        exp = time.time() + ttl if ttl else None
        raw = _enc.encode(value).decode()
        n = await self.KV.filter(key=key).update(value=raw, expires_at=exp)
        if not n:
            try:
                await self.KV.create(key=key, value=raw, expires_at=exp)
            except Exception:
                await self.KV.filter(key=key).update(value=raw, expires_at=exp)

    async def delete(self, key: str) -> bool:
        """Delete a key; returns ``True`` if it existed.

        Example::

            await bot.storage.delete("otp:42")
        """
        return bool(await self.KV.filter(key=key).delete())


def make_storage(spec: Any) -> Storage:
    """Create a storage from a spec: ``"db"``, ``"memory"``/``None``, ``"redis://…"`` or a ``Storage`` instance.

    Example::

        storage = make_storage("redis://localhost:6379/0")
    """
    if spec is None or spec == "memory":
        return MemoryStorage()
    if isinstance(spec, Storage):
        return spec
    if isinstance(spec, str) and spec.startswith(("redis://", "rediss://", "unix://")):
        return RedisStorage(spec)
    if spec == "db":
        return DBStorage()
    raise ValueError(f"Unknown storage {spec!r}: use 'db', 'memory', 'redis://...' or a Storage object")
