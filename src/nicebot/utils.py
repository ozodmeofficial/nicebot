"""Small helpers: durations, safe HTML formatting, misc."""
from __future__ import annotations

import asyncio
import functools
import html as _html
import inspect
import re
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")

# ----------------------------------------------------------------- durations
_DUR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h|d|w)", re.I)
_UNITS = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_duration(value: float | int | str | None) -> float | None:
    """``"1h30m"`` → ``5400.0``; numbers are seconds; ``None`` stays ``None``.

    Units: ``ms s m h d w``.  ``"90"`` → 90 seconds.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    total, pos = 0.0, 0
    for m in _DUR_RE.finditer(s):
        if s[pos:m.start()].strip():
            raise ValueError(f"Noto'g'ri davomiylik: {value!r}")
        total += float(m.group(1)) * _UNITS[m.group(2).lower()]
        pos = m.end()
    if pos == 0 or s[pos:].strip():
        raise ValueError(f"Noto'g'ri davomiylik: {value!r} (misol: '30s', '5m', '1h30m', '2d')")
    return total


def human_duration(seconds: float) -> str:
    seconds = int(seconds)
    parts = []
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        if seconds >= size:
            parts.append(f"{seconds // size}{unit}")
            seconds %= size
    return "".join(parts) or "0s"


# ----------------------------------------------------------------- HTML
def escape(text: Any) -> str:
    """Escape a value for Telegram HTML parse mode."""
    return _html.escape(str(text), quote=False)


class Html(str):
    """A string already safe for HTML parse mode (won't be escaped again)."""

    __slots__ = ()


def html(template: str, *args: Any, **kwargs: Any) -> Html:
    """Safe formatting: values are escaped, the template is trusted.

    >>> html("<b>Salom, {}!</b>", "<script>")
    '<b>Salom, &lt;script&gt;!</b>'
    """
    esc = lambda v: v if isinstance(v, Html) else escape(v)  # noqa: E731
    return Html(template.format(*[esc(a) for a in args], **{k: esc(v) for k, v in kwargs.items()}))


def bold(text: Any) -> Html:
    return Html(f"<b>{_e(text)}</b>")


def italic(text: Any) -> Html:
    return Html(f"<i>{_e(text)}</i>")


def underline(text: Any) -> Html:
    return Html(f"<u>{_e(text)}</u>")


def strike(text: Any) -> Html:
    return Html(f"<s>{_e(text)}</s>")


def spoiler(text: Any) -> Html:
    return Html(f"<tg-spoiler>{_e(text)}</tg-spoiler>")


def code(text: Any) -> Html:
    return Html(f"<code>{_e(text)}</code>")


def pre(text: Any, language: str | None = None) -> Html:
    if language:
        return Html(f'<pre><code class="language-{escape(language)}">{_e(text)}</code></pre>')
    return Html(f"<pre>{_e(text)}</pre>")


def link(text: Any, url: str) -> Html:
    return Html(f'<a href="{_html.escape(url, quote=True)}">{_e(text)}</a>')


def mention(name: Any, user_id: int) -> Html:
    return Html(f'<a href="tg://user?id={int(user_id)}">{_e(name)}</a>')


def quote(text: Any, expandable: bool = False) -> Html:
    tag = "blockquote expandable" if expandable else "blockquote"
    return Html(f"<{tag}>{_e(text)}</blockquote>")


def _e(v: Any) -> str:
    return v if isinstance(v, Html) else escape(v)


# ----------------------------------------------------------------- async helpers
async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def ensure_async(func: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    if inspect.iscoroutinefunction(func):
        return func

    @functools.wraps(func)
    async def wrapper(*a: Any, **kw: Any) -> Any:
        return await maybe_await(func(*a, **kw))

    return wrapper


class TTLCache:
    """Tiny in-memory LRU cache with per-item expiry."""

    def __init__(self, maxsize: int = 10_000, ttl: float | None = None):
        self.maxsize, self.ttl = maxsize, ttl
        self._d: OrderedDict[Any, tuple[float | None, Any]] = OrderedDict()

    def get(self, key: Any, default: Any = None) -> Any:
        item = self._d.get(key)
        if item is None:
            return default
        exp, val = item
        if exp is not None and exp < time.monotonic():
            self._d.pop(key, None)
            return default
        self._d.move_to_end(key)
        return val

    def set(self, key: Any, value: Any, ttl: float | None = None) -> None:
        ttl = self.ttl if ttl is None else ttl
        self._d[key] = (time.monotonic() + ttl if ttl else None, value)
        self._d.move_to_end(key)
        while len(self._d) > self.maxsize:
            self._d.popitem(last=False)

    def pop(self, key: Any, default: Any = None) -> Any:
        item = self._d.pop(key, None)
        return default if item is None else item[1]

    def __contains__(self, key: Any) -> bool:
        sentinel = object()
        return self.get(key, sentinel) is not sentinel

    def clear(self) -> None:
        self._d.clear()

    def __len__(self) -> int:
        return len(self._d)


def cache(ttl: float | str | None = "5m", maxsize: int = 1024) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Memoize an async (or sync) function for ``ttl``.

    >>> @cache("10m")
    ... async def kurs(): ...
    """
    seconds = parse_duration(ttl)

    def deco(func: Callable[..., Any]) -> Callable[..., Any]:
        store = TTLCache(maxsize=maxsize, ttl=seconds)
        locks: dict[Any, asyncio.Lock] = {}
        afunc = ensure_async(func)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                key = (args, tuple(sorted(kwargs.items())))
                hash(key)
            except TypeError:
                key = repr((args, sorted(kwargs.items())))
            sentinel = object()
            hit = store.get(key, sentinel)
            if hit is not sentinel:
                return hit
            lock = locks.setdefault(key, asyncio.Lock())
            async with lock:
                hit = store.get(key, sentinel)
                if hit is not sentinel:
                    return hit
                value = await afunc(*args, **kwargs)
                store.set(key, value)
                locks.pop(key, None)
                return value

        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        return wrapper

    return deco


def chunks(items: list[T], size: int) -> list[list[T]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def short_id(n: int = 8) -> str:
    import secrets

    return secrets.token_urlsafe(n)[:n]
