"""Dependency injection: handlers ask for what they need by parameter name or type hint.

Names: ``bot``, ``message``, ``callback``, ``user``, ``chat``, ``text``, ``args``, ``arg``, ``payload``, ``data``,
``value``, ``album``, ``lang``, ``state``, ``config``, ``db``, ``storage``, plus callback/regex parameters.
Types: ``Context``, ``Nicebot``, ``User`` (your model), ``Message``… and anything registered with ``bot.provide``.

Example::

    @bot.callback("buy:{id:int}")
    async def buy(ctx: Context, id: int, user: User, config: Config):
        await ctx.reply(f"{user.first_name} bought #{id} in {config.SHOP_NAME}")
"""
from __future__ import annotations

import inspect
import typing
from typing import TYPE_CHECKING, Any, Callable

from . import types as T
from .utils import maybe_await

if TYPE_CHECKING:
    from .context import Context

_PLANS: dict[Any, list[tuple[str, str, Any, Any, bool]]] = {}
_EMPTY = inspect.Parameter.empty

_NAMED = {
    "bot": lambda c: c.bot,
    "message": lambda c: c.message,
    "msg": lambda c: c.message,
    "callback": lambda c: c.callback,
    "query": lambda c: c.inline_query,
    "user": lambda c: c.user if c.user is not None else c.from_user,
    "tg_user": lambda c: c.from_user,
    "chat": lambda c: c.chat,
    "chat_id": lambda c: c.chat_id,
    "user_id": lambda c: c.user_id,
    "text": lambda c: c.text,
    "args": lambda c: c.args,
    "arg": lambda c: c.arg,
    "payload": lambda c: c.payload,
    "data": lambda c: c.data,
    "value": lambda c: c.value,
    "album": lambda c: c.album,
    "lang": lambda c: c.lang,
    "match": lambda c: c.match,
    "update": lambda c: c.update,
    "config": lambda c: c.bot.config,
    "storage": lambda c: c.bot.storage,
    "db": lambda c: c.bot.db,
    "event": lambda c: c.event,
}


def _resolve_hints(func: Callable[..., Any]) -> dict[str, Any]:
    try:
        return typing.get_type_hints(func)
    except Exception:  # noqa: BLE001 - unresolved forward refs: fall back to raw annotations
        return {k: v for k, v in getattr(func, "__annotations__", {}).items() if not isinstance(v, str)}


def plan(func: Callable[..., Any]) -> list[tuple[str, str, Any, Any, bool]]:
    """Inspect a handler's parameters once: ``[(name, kind, annotation, default, keyword_only)]``.

    Example::

        plan(buy)   # [("ctx", "ctx", Context, ..., False), ("id", "param", int, ..., False)]
    """
    p = _PLANS.get(func)
    if p is not None:
        return p
    from .context import Context

    sig = inspect.signature(func)
    hints = _resolve_hints(func)
    out = []
    first = True
    for name, param in sig.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            out.append((name, "var", None, None, False))
            continue
        kwonly = param.kind == param.KEYWORD_ONLY
        ann = hints.get(name, _EMPTY)
        if ann is Context or name in ("ctx", "context", "c") or (first and ann is _EMPTY):
            out.append((name, "ctx", ann, param.default, kwonly))
        else:
            out.append((name, "auto", ann, param.default, kwonly))
        first = False
    _PLANS[func] = out
    return out


def _convert(value: Any, ann: Any) -> Any:
    if ann in (int, float, str) and value is not None and not isinstance(value, ann):
        try:
            return ann(value)
        except (TypeError, ValueError):
            return value
    return value


async def resolve(ctx: "Context", name: str, ann: Any, default: Any) -> Any:
    """Find the value for one handler parameter: callback/regex params, well-known names, type hints or ``bot.provide``.

    Example::

        value = await resolve(ctx, "user", User, inspect.Parameter.empty)
    """
    bot = ctx.bot
    if name in ctx.params:
        return _convert(ctx.params[name], ann)
    if ann is not _EMPTY and ann is not None:
        prov = bot._providers.get(ann)
        if prov is not None:
            return await maybe_await(prov(ctx)) if callable(prov) and not isinstance(prov, type) else prov
        if isinstance(ann, type):
            from .orm.model import Model
            from .bot import Nicebot

            if issubclass(ann, Nicebot):
                return bot
            if issubclass(ann, Model) and ctx.user is not None and isinstance(ctx.user, ann):
                return ctx.user
            if ann is T.Message:
                return ctx.message
            if ann is T.CallbackQuery:
                return ctx.callback
            if ann is T.User:
                return ctx.from_user
            if ann is T.Chat:
                return ctx.chat
            if ann is T.InlineQuery:
                return ctx.inline_query
    if name == "state":
        return await ctx.get_state()
    getter = _NAMED.get(name)
    if getter is not None:
        return getter(ctx)
    if name in ctx.extra:
        return ctx.extra[name]
    return None if default is _EMPTY else default


async def call_handler(func: Callable[..., Any], ctx: "Context") -> Any:
    """Call a handler, filling its parameters from ``ctx`` (dependency injection).

    Example::

        await call_handler(buy, ctx)     # buy(ctx, id=5, user=<User>)
    """
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    for name, kind, ann, default, kwonly in plan(func):
        if kind == "var":
            continue
        value = ctx if kind == "ctx" else await resolve(ctx, name, ann, default)
        if not kwonly:
            args.append(value)
        else:
            kwargs[name] = value
    return await maybe_await(func(*args, **kwargs))
