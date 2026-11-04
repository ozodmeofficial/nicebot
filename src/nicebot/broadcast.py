"""Mass messaging with Telegram's limits respected, blocked users marked, and resume support.

Example::

    result = await bot.broadcast("📢 New products in the shop!", id="june-news")
    print(result)   # {"total": 1200, "sent": 1180, "failed": 20, "blocked": 18}
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Iterable

from .errors import BadRequest, Forbidden, RetryAfter, TelegramError
from .keyboards import build_inline
from .utils import maybe_await

if TYPE_CHECKING:
    from .bot import Nicebot

log = logging.getLogger("nicebot.broadcast")


async def broadcast(bot: "Nicebot", content: Any, *, users: Iterable[int] | None = None, buttons: Any = None, copy_from: tuple[int, int] | None = None,
                    rate: float = 25, id: str | None = None, on_progress: Callable[..., Any] | None = None, progress_every: float = 3.0, **kw: Any) -> dict[str, int]:
    """Send ``content`` (text, or ``callable(user_id) -> text``) to all users that did not block the bot (or to ``users``).

    * ``rate`` — messages per second (Telegram allows about 30/s)
    * ``copy_from=(chat_id, message_id)`` — copy any message (photo, video, buttons…)
    * ``id="newyear"`` — remembers progress; calling again with the same id continues where it stopped
    * ``on_progress`` — ``func(stats)`` called every ``progress_every`` seconds
    * returns ``{"total", "sent", "failed", "blocked"}``

    Example::

        stats = await bot.broadcast("🎉 Happy New Year!", id="ny-2027", buttons=[Button("🎁 Gift", url=GIFT_URL)])
        stats = await bot.broadcast(None, copy_from=(ctx.chat_id, ctx.message.reply_to_message.message_id))
        stats = await bot.broadcast(lambda uid: f"Your id is {uid}", users=[111, 222])
    """
    if users is None:
        users = await bot.User.filter(is_blocked=False).order_by("id").values_list("id")
    ids = list(users)
    key = f"bc:{id}" if id else None
    state = (await bot.storage.get(key) if key else None) or {"pos": 0, "sent": 0, "failed": 0, "blocked": 0}
    stats = {"total": len(ids), "sent": state["sent"], "failed": state["failed"], "blocked": state["blocked"]}
    markup = await build_inline(bot, buttons) if buttons is not None else None
    interval = 1.0 / max(rate, 0.1)
    last_report = 0.0
    start = int(state["pos"])
    for pos in range(start, len(ids)):
        uid = ids[pos]
        t0 = time.monotonic()
        while True:
            try:
                if copy_from is not None:
                    await bot.copy_message(uid, copy_from[0], copy_from[1], reply_markup=markup, **kw)
                else:
                    text = await maybe_await(content(uid)) if callable(content) else content
                    await bot._call_with_parse_fallback("send_message", chat_id=uid, text=str(text), parse_mode=bot.parse_mode, reply_markup=markup, **kw)
                stats["sent"] += 1
                break
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 0.5)
            except Forbidden:
                stats["failed"] += 1
                stats["blocked"] += 1
                try:
                    await bot.User.filter(id=uid).update(is_blocked=True)
                except Exception:  # noqa: BLE001
                    pass
                break
            except (BadRequest, TelegramError) as e:
                stats["failed"] += 1
                log.debug("broadcast %s: %s", uid, e)
                break
        if key and (pos % 20 == 0 or pos == len(ids) - 1):
            await bot.storage.set(key, {"pos": pos + 1, "sent": stats["sent"], "failed": stats["failed"], "blocked": stats["blocked"]}, ttl=7 * 86400)
        if on_progress and time.monotonic() - last_report >= progress_every:
            last_report = time.monotonic()
            await maybe_await(on_progress(dict(stats)))
        spent = time.monotonic() - t0
        if spent < interval:
            await asyncio.sleep(interval - spent)
    if key:
        await bot.storage.delete(key)
    if on_progress:
        await maybe_await(on_progress(dict(stats)))
    return stats
