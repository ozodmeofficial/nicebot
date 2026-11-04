"""``ctx.paginate`` — long lists split into pages with ◀️ 2/5 ▶️ navigation.

Example::

    users = await bot.User.all().order_by("-created_at")
    await ctx.paginate(users, per_page=20, title="👥 Users", render=lambda u, i: f"{i}. {u.mention}")
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, Sequence

import msgspec

from . import types as T
from .keyboards import Button, _normalize, build_inline
from .utils import Html, escape, parse_duration, short_id

if TYPE_CHECKING:
    from .context import Context

NOOP = "~x"


def _nav(pid: str, page: int, pages: int, ctx: "Context") -> list[T.InlineKeyboardButton]:
    if pages <= 1:
        return []
    row = []
    row.append(T.InlineKeyboardButton(text=ctx.t("nb.prev") if page > 1 else " ", callback_data=f"~p{pid}:{page - 1}" if page > 1 else NOOP))
    row.append(T.InlineKeyboardButton(text=f"{page}/{pages}", callback_data=NOOP))
    row.append(T.InlineKeyboardButton(text=ctx.t("nb.next") if page < pages else " ", callback_data=f"~p{pid}:{page + 1}" if page < pages else NOOP))
    return row


def _render_page(ctx: "Context", rec: dict[str, Any], pid: str, page: int) -> tuple[str, T.InlineKeyboardMarkup | None]:
    per = rec["per"]
    total = rec["n"]
    pages = max(1, math.ceil(total / per))
    page = min(max(page, 1), pages)
    start = (page - 1) * per
    title = rec.get("title") or ""
    rows: list[list[T.InlineKeyboardButton]] = []
    if rec["kind"] == "text":
        lines = rec["items"][start:start + per]
        body = "\n".join(lines)
        text = f"{title}\n\n{body}" if title else body
    else:
        raw = rec["items"][start:start + per]
        btns = [msgspec.convert(b, T.InlineKeyboardButton) for b in raw]
        cols = rec.get("cols") or 1
        rows = [btns[i:i + cols] for i in range(0, len(btns), cols)]
        text = title or ctx.t("nb.page", page=page, pages=pages)
    nav = _nav(pid, page, pages, ctx)
    if nav:
        rows.append(nav)
    return text, (T.InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)


async def start_pagination(ctx: "Context", items: Sequence[Any], *, per_page: int, title: Any, render: Callable[[Any, int], Any] | None,
                           columns: Any, numbered: bool, ttl: Any, empty: Any, edit: bool) -> Any:
    """Send the first page of a paginated list (used by ``ctx.paginate``).

    Example::

        await start_pagination(ctx, items, per_page=10, title="Products", render=None, columns=1, numbered=True, ttl="7d", empty=None, edit=False)
    """
    items = list(items)
    if not items:
        return await (ctx.respond if edit else ctx.reply)(empty or ctx.t("nb.empty"))
    is_buttons = all(isinstance(i, (Button, T.InlineKeyboardButton)) for i in items)
    if is_buttons:
        built = []
        for b in items:
            ib = b if isinstance(b, T.InlineKeyboardButton) else await b.build(ctx.bot)
            built.append(msgspec.to_builtins(ib))
        rec = {"kind": "buttons", "items": built, "cols": int(columns) if isinstance(columns, int) else 1}
    else:
        lines = []
        for i, it in enumerate(items):
            line = render(it, i) if render else it
            line = line if isinstance(line, Html) else escape(line) if ctx.bot.parse_mode == "HTML" else str(line)
            lines.append(f"{i + 1}. {line}" if numbered and not render else str(line))
        rec = {"kind": "text", "items": lines}
    rec.update(per=per_page, n=len(items), title=str(title) if title else "")
    pid = short_id(8)
    await ctx.bot.storage.set(f"pg:{pid}", rec, ttl=parse_duration(ttl))
    text, markup = _render_page(ctx, rec, pid, 1)
    if edit and ctx.is_callback:
        return await ctx.bot._call_with_parse_fallback("edit_message_text", chat_id=ctx.chat_id, message_id=ctx.message.message_id, text=text, parse_mode=ctx.bot.parse_mode, reply_markup=markup)
    return await ctx.bot._call_with_parse_fallback("send_message", chat_id=ctx.chat_id, text=text, parse_mode=ctx.bot.parse_mode, reply_markup=markup)


async def handle_page(ctx: "Context", data: str) -> None:
    """Handle ◀️/▶️ presses (internal ``~p…`` callback data).

    Example::

        await handle_page(ctx, ctx.data)
    """
    pid, _, page = data[2:].partition(":")
    rec = await ctx.bot.storage.get(f"pg:{pid}")
    if rec is None:
        await ctx.answer(ctx.t("nb.expired"), alert=True)
        return
    await ctx.answer()
    text, markup = _render_page(ctx, rec, pid, int(page or 1))
    from .errors import BadRequest

    try:
        await ctx.bot._call_with_parse_fallback("edit_message_text", chat_id=ctx.chat_id, message_id=ctx.message.message_id, text=text, parse_mode=ctx.bot.parse_mode, reply_markup=markup)
    except BadRequest as e:
        if not e.not_modified:
            raise


__all__ = ["start_pagination", "handle_page", "build_inline", "_normalize"]
