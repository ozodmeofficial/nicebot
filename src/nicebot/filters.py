"""Composable filters: ``F.text & ~F.command``, ``F.photo | F.document``, or any ``lambda ctx: ...``."""
from __future__ import annotations

import inspect
import re
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Union

if TYPE_CHECKING:
    from .context import Context

FilterFunc = Callable[["Context"], Union[bool, Awaitable[bool]]]


class Filter:
    """Wraps a predicate; combine with ``&`` ``|`` ``~``."""

    __slots__ = ("func", "name")

    def __init__(self, func: FilterFunc, name: str = "filter"):
        self.func = func
        self.name = name

    async def __call__(self, ctx: "Context") -> bool:
        r = self.func(ctx)
        if inspect.isawaitable(r):
            r = await r
        return bool(r)

    def __and__(self, other: Any) -> "Filter":
        a, b = self, as_filter(other)

        async def both(ctx: "Context") -> bool:
            return await a(ctx) and await b(ctx)

        return Filter(both, f"({a.name} & {b.name})")

    def __or__(self, other: Any) -> "Filter":
        a, b = self, as_filter(other)

        async def either(ctx: "Context") -> bool:
            return await a(ctx) or await b(ctx)

        return Filter(either, f"({a.name} | {b.name})")

    def __invert__(self) -> "Filter":
        a = self

        async def negate(ctx: "Context") -> bool:
            return not await a(ctx)

        return Filter(negate, f"~{a.name}")

    def __repr__(self) -> str:
        return f"<Filter {self.name}>"


def as_filter(obj: Any) -> Filter:
    if isinstance(obj, Filter):
        return obj
    if callable(obj):
        return Filter(obj, getattr(obj, "__name__", "filter"))
    raise TypeError(f"Filter bo'lishi kerak: {obj!r}")


def _has(attr: str) -> Filter:
    return Filter(lambda ctx: ctx.message is not None and getattr(ctx.message, attr, None) is not None, attr)


class _F:
    """Ready-made filters. ``from nicebot import F``."""

    text = _has("text")
    photo = _has("photo")
    video = _has("video")
    document = _has("document")
    audio = _has("audio")
    voice = _has("voice")
    video_note = _has("video_note")
    sticker = _has("sticker")
    animation = _has("animation")
    contact = _has("contact")
    location = _has("location")
    venue = _has("venue")
    poll = _has("poll")
    dice = _has("dice")
    web_app_data = _has("web_app_data")
    successful_payment = _has("successful_payment")
    reply = _has("reply_to_message")
    forwarded = _has("forward_origin")
    media = Filter(lambda ctx: ctx.message is not None and any(getattr(ctx.message, a, None) for a in ("photo", "video", "document", "audio", "voice", "animation", "video_note")), "media")
    command = Filter(lambda ctx: bool(ctx.command), "command")
    private = Filter(lambda ctx: ctx.chat is not None and ctx.chat.type == "private", "private")
    group = Filter(lambda ctx: ctx.chat is not None and ctx.chat.type in ("group", "supergroup"), "group")
    channel = Filter(lambda ctx: ctx.chat is not None and ctx.chat.type == "channel", "channel")
    admin = Filter(lambda ctx: ctx.is_admin, "admin")
    premium = Filter(lambda ctx: bool(ctx.from_user and ctx.from_user.is_premium), "premium")
    any = Filter(lambda ctx: True, "any")

    @staticmethod
    def regex(pattern: str | re.Pattern, flags: int = 0) -> Filter:
        rx = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
        return Filter(lambda ctx: bool(ctx.text and rx.search(ctx.text)), f"regex({rx.pattern})")

    @staticmethod
    def contains(*words: str, ignore_case: bool = True) -> Filter:
        ws = [w.lower() for w in words] if ignore_case else list(words)

        def check(ctx: "Context") -> bool:
            t = ctx.text or ""
            t = t.lower() if ignore_case else t
            return any(w in t for w in ws)

        return Filter(check, f"contains{words}")

    @staticmethod
    def user(*ids: int) -> Filter:
        s = set(ids)
        return Filter(lambda ctx: ctx.user_id in s, "user")

    @staticmethod
    def chat(*ids: int) -> Filter:
        s = set(ids)
        return Filter(lambda ctx: ctx.chat_id in s, "chat")

    @staticmethod
    def lang(*codes: str) -> Filter:
        s = set(codes)
        return Filter(lambda ctx: ctx.lang in s, "lang")

    @staticmethod
    def state(*names: str | None) -> Filter:
        s = set(names)

        async def check(ctx: "Context") -> bool:
            return (await ctx.get_state()) in s

        return Filter(check, f"state{names}")


F = _F()
