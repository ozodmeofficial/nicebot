"""Key–value storage used for state, buttons, caches, counters.

Backends: ``MemoryStorage`` (default), ``RedisStorage`` (``redis://``), ``DBStorage`` (your ORM database).
Values must be JSON-serialisable.
"""
from __future__ import annotations

import time
from typing import Any

import msgspec

_enc = msgspec.json.Encoder()
_dec = msgspec.json.Decoder()


class Storage:
    """Interface. All methods are async."""

    async def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        raise NotImplementedError

    async def pop(self, key: str, default: Any = None) -> Any:
        """Get and delete atomically (as far as the backend allows)."""
        value = await self.get(key, default)
        await self.delete(key)
        return value

    async def incr(self, key: str, amount: int = 1, ttl: float | None = None) -> int:
        value = int(await self.get(key, 0) or 0) + amount
        await self.set(key, value, ttl)
        return value

    async def exists(self, key: str) -> bool:
        sentinel = "__nb_missing__"
        return (await self.get(key, sentinel)) != sentinel

    async def close(self) -> None:
        return None


class MemoryStorage(Storage):
    """Fast in-process storage. Lost on restart — use Redis or DB for persistence."""

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
        ok, val = self._alive(key)
        return val if ok else default

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        self._gc()
        self._d[key] = (time.time() + ttl if ttl else None, value)

    async def delete(self, key: str) -> bool:
        return self._d.pop(key, None) is not None

    async def pop(self, key: str, default: Any = None) -> Any:
        ok, val = self._alive(key)
        self._d.pop(key, None)
        return val if ok else default

    async def incr(self, key: str, amount: int = 1, ttl: float | None = None) -> int:
        ok, val = self._alive(key)
        exp = self._d[key][0] if ok else (time.time() + ttl if ttl else None)
        value = (int(val) if ok else 0) + amount
        self._d[key] = (exp, value)
        return value


class RedisStorage(Storage):
    """``pip install nicebot[redis]`` — persistent and shared between processes."""

    def __init__(self, url: str = "redis://localhost:6379/0", prefix: str = "nb:"):
        try:
            import redis.asyncio as aioredis
        except ImportError as e:  # pragma: no cover
            raise ImportError("Redis uchun: pip install 'nicebot[redis]'") from e
        self.r = aioredis.from_url(url)
        self.prefix = prefix

    async def get(self, key: str, default: Any = None) -> Any:
        raw = await self.r.get(self.prefix + key)
        return default if raw is None else _dec.decode(raw)

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        await self.r.set(self.prefix + key, _enc.encode(value), px=int(ttl * 1000) if ttl else None)

    async def delete(self, key: str) -> bool:
        return bool(await self.r.delete(self.prefix + key))

    async def pop(self, key: str, default: Any = None) -> Any:
        raw = await self.r.getdel(self.prefix + key)
        return default if raw is None else _dec.decode(raw)

    async def incr(self, key: str, amount: int = 1, ttl: float | None = None) -> int:
        k = self.prefix + key
        value = int(await self.r.incrby(k, amount))
        if ttl and value == amount:
            await self.r.pexpire(k, int(ttl * 1000))
        return value

    async def close(self) -> None:
        await self.r.aclose()


class DBStorage(Storage):
    """Stores keys in your ORM database (table ``nb_kv``). Persistent, no extra service."""

    def __init__(self) -> None:
        from .orm.builtin import KV

        self.KV = KV

    async def get(self, key: str, default: Any = None) -> Any:
        row = await self.KV.get_or_none(key=key)
        if row is None:
            return default
        if row.expires_at is not None and row.expires_at < time.time():
            await self.KV.filter(key=key).delete()
            return default
        return _dec.decode(row.value.encode())

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        exp = time.time() + ttl if ttl else None
        raw = _enc.encode(value).decode()
        n = await self.KV.filter(key=key).update(value=raw, expires_at=exp)
        if not n:
            try:
                await self.KV.create(key=key, value=raw, expires_at=exp)
            except Exception:
                await self.KV.filter(key=key).update(value=raw, expires_at=exp)

    async def delete(self, key: str) -> bool:
        return bool(await self.KV.filter(key=key).delete())


def make_storage(spec: Any) -> Storage:
    """``None``/``"memory"`` → Memory, ``"redis://..."`` → Redis, ``"db"`` → DBStorage, or a Storage instance."""
    if spec is None or spec == "memory":
        return MemoryStorage()
    if isinstance(spec, Storage):
        return spec
    if isinstance(spec, str) and spec.startswith(("redis://", "rediss://", "unix://")):
        return RedisStorage(spec)
    if spec == "db":
        return DBStorage()
    raise ValueError(f"Noma'lum storage: {spec!r}")
