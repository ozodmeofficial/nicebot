"""Small helpers: durations, safe HTML formatting, caching.

Example::

    from nicebot import bold, cache, html, mention, parse_duration

    await ctx.reply(html("Hi <b>{}</b>!", ctx.text))      # user text is escaped
    parse_duration("1h30m")                                # 5400.0
"""
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
    """Turn a duration into seconds: ``"1h30m"`` → ``5400.0``. Numbers are seconds, ``None`` stays ``None``.

    Units: ``ms s m h d w``.

    Example::

        parse_duration("30s")    # 30.0
        parse_duration("1h30m")  # 5400.0
        parse_duration(90)       # 90.0
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
            raise ValueError(f"Invalid duration: {value!r}")
        total += float(m.group(1)) * _UNITS[m.group(2).lower()]
        pos = m.end()
    if pos == 0 or s[pos:].strip():
        raise ValueError(f"Invalid duration: {value!r} (examples: '30s', '5m', '1h30m', '2d')")
    return total


def human_duration(seconds: float) -> str:
    """Format seconds as a short duration.

    Example::

        human_duration(5400)   # "1h30m"
    """
    seconds = int(seconds)
    parts = []
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        if seconds >= size:
            parts.append(f"{seconds // size}{unit}")
            seconds %= size
    return "".join(parts) or "0s"


# ----------------------------------------------------------------- HTML
def escape(text: Any) -> str:
    """Escape a value for Telegram HTML (``<``, ``>``, ``&``). Use it for any text that came from users.

    Example::

        await ctx.reply(f"You wrote: <i>{escape(ctx.text)}</i>")
    """
    return _html.escape(str(text), quote=False)


class Html(str):
    """A string that is already safe HTML (it is not escaped again by ``html()``).

    Example::

        title = Html("<b>Shop</b>")
        await ctx.reply(html("{} — {}", title, user_text))
    """

    __slots__ = ()


def html(template: str, *args: Any, **kwargs: Any) -> Html:
    """Safe formatting: values are escaped, the template is trusted.

    Example::

        html("<b>Hello, {}!</b>", "<script>")   # '<b>Hello, &lt;script&gt;!</b>'
        await ctx.reply(html("Your name: <b>{}</b>", ctx.text))
    """
    esc = lambda v: v if isinstance(v, Html) else escape(v)  # noqa: E731
    return Html(template.format(*[esc(a) for a in args], **{k: esc(v) for k, v in kwargs.items()}))


def bold(text: Any) -> Html:
    """Bold text (the value is escaped).

    Example::

        await ctx.reply(f"Total: {bold(total)}")
    """
    return Html(f"<b>{_e(text)}</b>")


def italic(text: Any) -> Html:
    """Italic text.

    Example::

        await ctx.reply(italic("coming soon"))
    """
    return Html(f"<i>{_e(text)}</i>")


def underline(text: Any) -> Html:
    """Underlined text.

    Example::

        await ctx.reply(underline("important"))
    """
    return Html(f"<u>{_e(text)}</u>")


def strike(text: Any) -> Html:
    """Strikethrough text.

    Example::

        await ctx.reply(f"{strike('100 000')} 80 000 so'm")
    """
    return Html(f"<s>{_e(text)}</s>")


def spoiler(text: Any) -> Html:
    """Hidden text revealed on tap.

    Example::

        await ctx.reply(f"Answer: {spoiler('42')}")
    """
    return Html(f"<tg-spoiler>{_e(text)}</tg-spoiler>")


def code(text: Any) -> Html:
    """Inline monospace text.

    Example::

        await ctx.reply(f"Your code: {code('NICE2026')}")
    """
    return Html(f"<code>{_e(text)}</code>")


def pre(text: Any, language: str | None = None) -> Html:
    """A monospace block, optionally with a language for highlighting.

    Example::

        await ctx.reply(pre("print('hi')", "python"))
    """
    if language:
        return Html(f'<pre><code class="language-{escape(language)}">{_e(text)}</code></pre>')
    return Html(f"<pre>{_e(text)}</pre>")


def link(text: Any, url: str) -> Html:
    """A link with custom text.

    Example::

        await ctx.reply(link("Our website", "https://example.com"))
    """
    return Html(f'<a href="{_html.escape(url, quote=True)}">{_e(text)}</a>')


def mention(name: Any, user_id: int) -> Html:
    """A clickable mention of a user by id (works without a username).

    Example::

        await ctx.reply(f"New order from {mention(user.first_name, user.id)}")
    """
    return Html(f'<a href="tg://user?id={int(user_id)}">{_e(name)}</a>')


def quote(text: Any, expandable: bool = False) -> Html:
    """A block quote (``expandable=True`` collapses long quotes).

    Example::

        await ctx.reply(quote("Great service!") + "\n— a happy customer")
    """
    tag = "blockquote expandable" if expandable else "blockquote"
    return Html(f"<{tag}>{_e(text)}</blockquote>")


def _e(v: Any) -> str:
    return v if isinstance(v, Html) else escape(v)


# ----------------------------------------------------------------- async helpers
async def maybe_await(value: Any) -> Any:
    """Await the value if it is awaitable, otherwise return it (lets users pass sync or async functions).

    Example::

        result = await maybe_await(func(ctx))
    """
    if inspect.isawaitable(value):
        return await value
    return value


def ensure_async(func: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    """Wrap a sync function so it can be awaited.

    Example::

        f = ensure_async(len)
        await f([1, 2])   # 2
    """
    if inspect.iscoroutinefunction(func):
        return func

    @functools.wraps(func)
    async def wrapper(*a: Any, **kw: Any) -> Any:
        return await maybe_await(func(*a, **kw))

    return wrapper


class TTLCache:
    """Tiny in-memory LRU cache with per-item expiry.

    Example::

        c = TTLCache(maxsize=1000, ttl=60)
        c.set("rate", 12500)
        c.get("rate")   # 12500 (None after 60 s)
    """

    def __init__(self, maxsize: int = 10_000, ttl: float | None = None):
        self.maxsize, self.ttl = maxsize, ttl
        self._d: OrderedDict[Any, tuple[float | None, Any]] = OrderedDict()

    def get(self, key: Any, default: Any = None) -> Any:
        """The value, or ``default`` if missing/expired.

        Example::

            cache.get("key", 0)
        """
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
        """Store a value (``ttl`` overrides the default expiry).

        Example::

            cache.set("key", 1, ttl=10)
        """
        ttl = self.ttl if ttl is None else ttl
        self._d[key] = (time.monotonic() + ttl if ttl else None, value)
        self._d.move_to_end(key)
        while len(self._d) > self.maxsize:
            self._d.popitem(last=False)

    def pop(self, key: Any, default: Any = None) -> Any:
        """Remove and return a value.

        Example::

            cache.pop("key")
        """
        item = self._d.pop(key, None)
        return default if item is None else item[1]

    def __contains__(self, key: Any) -> bool:
        sentinel = object()
        return self.get(key, sentinel) is not sentinel

    def clear(self) -> None:
        """Remove everything.

        Example::

            cache.clear()
        """
        self._d.clear()

    def __len__(self) -> int:
        return len(self._d)


def cache(ttl: float | str | None = "5m", maxsize: int = 1024) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator: remember the result of an async (or sync) function for ``ttl`` (per arguments).

    Example::

        @cache("10m")
        async def usd_rate() -> float:
            return await fetch_rate()
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
    """Split a list into pieces of ``size``.

    Example::

        chunks([1, 2, 3, 4, 5], 2)   # [[1, 2], [3, 4], [5]]
    """
    return [items[i:i + size] for i in range(0, len(items), size)]


def short_id(n: int = 8) -> str:
    """A random URL-safe id.

    Example::

        short_id()    # "f3K9aZ1q"
    """
    import secrets

    return secrets.token_urlsafe(n)[:n]
