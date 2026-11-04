"""Built-in behaviour: user tracking, referrals, maintenance, forced subscription, captcha,
support relay, toggles, internal buttons, admin panel and statistics.

You do not import this module: the features switch on through ``Nicebot`` options.

Example::

    bot = Nicebot(
        token="...",
        admins=[123456789],                 # /stats /broadcast /maintenance /backup
        required_channels=["@my_channel"],  # forced subscription
        support_chat=-1001234567890,        # support relay
        captcha="2m",                       # captcha for new group members
    )
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import msgspec

from . import types as T
from .errors import BadRequest, Forbidden, TelegramError
from .keyboards import Button, func_by_id
from .router import Router
from .utils import escape, mention

if TYPE_CHECKING:
    from .bot import Nicebot
    from .context import Context

log = logging.getLogger("nicebot")

TRACK_EVENTS = {"message", "callback_query", "inline_query", "pre_checkout_query", "my_chat_member", "chat_join_request"}
Next = Callable[[], Awaitable[Any]]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ============================================================================ middlewares
async def user_mw(ctx: "Context", nxt: Next) -> Any:
    """Middleware: save every user to the database once and keep their profile fresh (``ctx.user``).

    Enabled by default (``Nicebot(track_users=False)`` turns it off).

    Example::

        @bot.command("me")
        async def me(ctx: Context):
            await ctx.reply(f"You joined on {ctx.user.created_at:%d.%m.%Y}")
    """
    bot = ctx.bot
    u = ctx.from_user
    if u is None or u.is_bot or ctx.event_name not in TRACK_EVENTS:
        return await nxt()
    from .di import call_handler

    Model = bot.User
    now = _now()
    user = await Model.get_or_none(id=u.id)
    referrer = None
    if user is None:
        ref_id = None
        if ctx.command == "start" and ctx.payload.startswith("ref_"):
            try:
                ref_id = int(ctx.payload[4:])
            except ValueError:
                ref_id = None
            if ref_id == u.id:
                ref_id = None
            if ref_id is not None:
                referrer = await Model.get_or_none(id=ref_id)
                if referrer is None:
                    ref_id = None
        user, created = await Model.get_or_create(
            id=u.id,
            defaults={
                "first_name": u.first_name or "",
                "last_name": u.last_name,
                "username": u.username,
                "is_premium": bool(u.is_premium),
                "referrer_id": ref_id,
                "last_seen": now,
            },
        )
        ctx.user = user
        if created:
            ctx.extra["new_user"] = True
            if bot.analytics:
                bot._count("new_users")
            for hook in bot._new_user_hooks:
                await call_handler(hook, ctx)
            if referrer is not None:
                ctx.extra["referrer"] = referrer
                for hook in bot._referral_hooks:
                    await call_handler(hook, ctx)
    else:
        changes: dict[str, Any] = {}
        if user.first_name != (u.first_name or ""):
            changes["first_name"] = u.first_name or ""
        if user.last_name != u.last_name:
            changes["last_name"] = u.last_name
        if user.username != u.username:
            changes["username"] = u.username
        if bool(user.is_premium) != bool(u.is_premium):
            changes["is_premium"] = bool(u.is_premium)
        if user.is_blocked and ctx.event_name != "my_chat_member":
            changes["is_blocked"] = False
        if user.last_seen is None or (now - user.last_seen).total_seconds() > 300:
            changes["last_seen"] = now
        if changes:
            await user.update(**changes)
        ctx.user = user
    if ctx.event_name == "my_chat_member" and ctx.chat is not None and ctx.chat.type == "private":
        status = ctx.event.new_chat_member.status
        blocked = status in ("kicked", "left")
        if user.is_blocked != blocked:
            await user.update(is_blocked=blocked)
    return await nxt()


async def maintenance_mw(ctx: "Context", nxt: Next) -> Any:
    """Middleware: while maintenance is on, everyone except admins gets the maintenance text.

    Example::

        await bot.maintenance(True)     # or the /maintenance admin command
    """
    bot = ctx.bot
    if bot._maintenance is None or ctx.is_admin or ctx.event_name not in ("message", "callback_query"):
        return await nxt()
    text = bot._maintenance or ctx.t("nb.maintenance")
    if ctx.is_callback:
        await ctx.answer(text, alert=True)
    elif ctx.is_private:
        await ctx.reply(text)
    return None


async def _channel_link(bot: "Nicebot", ch: Any) -> tuple[Any, str]:
    if isinstance(ch, (tuple, list)):
        return ch[0], ch[1]
    if isinstance(ch, str) and ch.startswith("@"):
        return ch, f"https://t.me/{ch[1:]}"
    cache = bot.__dict__.setdefault("_invite_links", {})
    if ch not in cache:
        try:
            chat = await bot.get_chat(ch)
            link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
            if link is None:
                link = await bot.export_chat_invite_link(ch)
        except TelegramError:
            link = "https://t.me/"
        cache[ch] = link
    return ch, cache[ch]


async def missing_channels(ctx: "Context") -> list[tuple[Any, str]]:
    """Channels from ``required_channels`` the user has not joined yet, as ``(chat, link)`` pairs.

    Example::

        if await missing_channels(ctx):
            await ctx.reply("Please join our channels")
    """
    bot = ctx.bot
    missing = []
    for ch in bot.required_channels:
        chat_id, link = await _channel_link(bot, ch)
        key = (ctx.user_id, str(chat_id))
        if bot._sub_cache.get(key):
            continue
        if await ctx.is_member(chat_id):
            bot._sub_cache.set(key, True)
        else:
            missing.append((chat_id, link))
    return missing


async def _subscription_prompt(ctx: "Context", missing: list[tuple[Any, str]]) -> None:
    buttons: list[list[Button]] = []
    for i, (chat_id, link) in enumerate(missing, 1):
        title = chat_id if isinstance(chat_id, str) and chat_id.startswith("@") else ctx.t("nb.admin.channel", n=i)
        buttons.append([Button(str(title), url=link)])
    buttons.append([Button(ctx.t("nb.check"), data="~s")])
    await ctx.reply(ctx.t("nb.subscribe"), buttons=buttons)


async def subscription_mw(ctx: "Context", nxt: Next) -> Any:
    """Middleware: users must join ``required_channels`` before the bot answers them.

    Example::

        bot = Nicebot(token="...", required_channels=["@my_channel"])
    """
    if ctx.is_admin or not ctx.is_private or ctx.event_name not in ("message", "callback_query"):
        return await nxt()
    if ctx.is_callback and ctx.data == "~s":
        return await nxt()
    missing = await missing_channels(ctx)
    if not missing:
        return await nxt()
    if ctx.is_callback:
        await ctx.answer(ctx.t("nb.not_subscribed"), alert=True)
    else:
        await _subscription_prompt(ctx, missing)
    return None


async def captcha_mw(ctx: "Context", nxt: Next) -> Any:
    """Middleware: new group members are muted until they press "I'm not a robot".

    Example::

        bot = Nicebot(token="...", captcha="2m")   # kick if not confirmed in 2 minutes
    """
    bot = ctx.bot
    m = ctx.message if ctx.event_name == "message" else None
    if not bot.captcha or m is None or not m.new_chat_members or not ctx.is_group:
        return await nxt()
    seconds = int(bot.captcha)
    for member in m.new_chat_members:
        if member.is_bot:
            continue
        try:
            await bot.restrict_chat_member(ctx.chat_id, member.id, T.ChatPermissions(can_send_messages=False))
        except TelegramError as e:
            log.warning("Captcha: could not restrict the member (%s). The bot must be a group admin.", e)
            continue
        who = mention(member.first_name, member.id)
        msg = await ctx.reply(ctx.t("nb.captcha", mention=who, seconds=seconds), buttons=[Button(ctx.t("nb.captcha_button"), data=f"~a{member.id}")])
        key = f"cap:{ctx.chat_id}:{member.id}"
        await bot.storage.set(key, msg.message_id, ttl=seconds + 60)
        bot.later(seconds, _captcha_timeout(bot, ctx.chat_id, member.id, key))
    return await nxt()


async def _captcha_timeout(bot: "Nicebot", chat_id: int, user_id: int, key: str) -> None:
    msg_id = await bot.storage.pop(key)
    if msg_id is None:
        return
    try:
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
    except TelegramError:
        pass
    await bot.safe_delete(chat_id, msg_id)


# ============================================================================ internal callbacks
async def handle_internal_callback(ctx: "Context") -> bool:
    """Handle nicebot's own buttons (``~…`` callback data: on_click, toggles, menus, pages, captcha). Internal.

    Example::

        handled = await handle_internal_callback(ctx)
    """
    from .di import call_handler

    bot = ctx.bot
    data = ctx.data or ""
    if data == "~x":
        await ctx.answer()
        return True
    if data == "~s":
        missing = await missing_channels(ctx)
        if missing:
            await ctx.answer(ctx.t("nb.not_subscribed"), alert=True)
        else:
            await ctx.answer("✅")
            await ctx.delete()
            start = next((h for h in bot._index.get("message", ()) if "start" in h.commands), None)
            if start is not None:
                ctx.extra["route"] = "message"
                await start.run(ctx)
        return True
    if data.startswith("~k"):
        rec = await bot.storage.get(f"cb:{data[2:]}")
        if rec is None:
            await ctx.answer(ctx.t("nb.expired"), alert=True)
            return True
        import time

        if rec.get("exp") and rec["exp"] < time.time():
            await ctx.answer(ctx.t("nb.expired"), alert=True)
            return True
        if rec.get("only") and ctx.user_id not in rec["only"]:
            await ctx.answer(ctx.t("nb.not_yours"), alert=True)
            return True
        if rec.get("once"):
            if await bot.storage.incr(f"cbu:{data[2:]}", 1, ttl=30 * 86400) > 1:
                await ctx.answer(ctx.t("nb.used"), alert=True)
                return True
        ctx.event.data = rec["d"]
        if rec["d"].startswith("~"):
            return await handle_internal_callback(ctx)
        return False
    if data.startswith("~f"):
        fid, _, raw = data[2:].partition("|")
        func = func_by_id(fid)
        if func is None:
            await ctx.answer(ctx.t("nb.expired"), alert=True)
            return True
        params = json.loads(raw) if raw else {}
        ctx.params = dict(params)
        ctx.value = next(iter(params.values())) if len(params) == 1 else (params or None)
        await call_handler(func, ctx)
        return True
    if data.startswith("~t"):
        await _toggle(ctx, data)
        return True
    if data.startswith("~p"):
        from .pagination import handle_page

        await handle_page(ctx, data)
        return True
    if data.startswith("~m"):
        from .menu import handle_menu

        await handle_menu(ctx, data)
        return True
    if data.startswith("~a"):
        uid = int(data[2:])
        if ctx.user_id != uid:
            await ctx.answer(ctx.t("nb.not_yours"), alert=True)
            return True
        await bot.storage.delete(f"cap:{ctx.chat_id}:{uid}")
        try:
            await ctx.unmute(uid)
        except TelegramError:
            pass
        await ctx.answer(ctx.t("nb.captcha_ok"))
        await ctx.delete()
        return True
    return False


async def _toggle(ctx: "Context", data: str) -> None:
    from .di import call_handler

    bot = ctx.bot
    key, fid, default = (data[2:].split("|") + ["", "0"])[:3]
    current = await bot.get_setting(ctx.user_id or 0, key, bool(int(default or 0)))
    new = not current
    await bot.set_setting(ctx.user_id or 0, key, new)
    markup = ctx.message.reply_markup if ctx.message is not None else None
    if markup is not None:
        rows = []
        for row in markup.inline_keyboard:
            new_row = []
            for b in row:
                if b.callback_data and b.callback_data.startswith(f"~t{key}|"):
                    label = b.text.split(" ", 1)[1] if " " in b.text else b.text
                    b = msgspec.structs.replace(b, text=f"{'✅' if new else '⬜️'} {label}")
                new_row.append(b)
            rows.append(new_row)
        try:
            await bot.edit_message_reply_markup(chat_id=ctx.chat_id, message_id=ctx.message.message_id, reply_markup=T.InlineKeyboardMarkup(inline_keyboard=rows))
        except BadRequest:
            pass
    if fid:
        func = func_by_id(fid)
        if func is not None:
            ctx.value = new
            ctx.params = {"value": new, "key": key}
            await call_handler(func, ctx)
    await ctx.answer()


# ============================================================================ support relay
async def support_relay(ctx: "Context", phase: str) -> bool:
    """Support mode: forward unmatched private messages to ``support_chat``; replies there go back to the user.

    Example::

        bot = Nicebot(token="...", support_chat=-1001234567890)
    """
    bot = ctx.bot
    if bot.support_chat is None or ctx.message is None:
        return False
    m = ctx.message
    if phase == "before":
        if str(ctx.chat_id) != str(bot.support_chat) or m.reply_to_message is None:
            return False
        uid = await bot.storage.get(f"sup:{m.reply_to_message.message_id}")
        if uid is None:
            return False
        try:
            await bot.copy_message(uid, m.chat.id, m.message_id)
            await ctx.react("👍")
        except Forbidden:
            await ctx.reply(ctx.t("nb.admin.user_blocked"))
        return True
    if not ctx.is_private or ctx.is_admin or ctx.command:
        return False
    u = ctx.from_user
    name = escape(" ".join(p for p in (u.first_name, u.last_name) if p))
    header = f"📩 {mention(name or u.id, u.id)} · <code>{u.id}</code>" + (f" · @{escape(u.username)}" if u.username else "")
    head = await bot._call_with_parse_fallback("send_message", chat_id=bot.support_chat, text=header, parse_mode="HTML")
    copied = await bot.copy_message(bot.support_chat, m.chat.id, m.message_id, reply_parameters=T.ReplyParameters(message_id=head.message_id))
    for mid in (head.message_id, copied.message_id):
        await bot.storage.set(f"sup:{mid}", u.id, ttl=90 * 86400)
    if await bot.storage.get(f"supack:{u.id}") is None:
        await bot.storage.set(f"supack:{u.id}", 1, ttl=600)
        await ctx.reply(ctx.t("nb.support_sent"))
    return True


# ============================================================================ commands menu
async def register_commands(bot: "Nicebot") -> None:
    """Publish commands that have ``description=`` in Telegram's menu (and admin commands for admins).

    Example::

        @bot.command("help", description={"uz": "Yordam", "en": "Help"})
        async def help(ctx: Context): ...
    """
    default: list[T.BotCommand] = []
    per_lang: dict[str, list[T.BotCommand]] = {}
    for h in bot.all_handlers():
        if not h.commands or not h.description or h.admin:
            continue
        name = sorted(h.commands)[0] if "start" not in h.commands else "start"
        desc = h.description
        if isinstance(desc, dict):
            for lang, text in desc.items():
                per_lang.setdefault(lang, []).append(T.BotCommand(command=name, description=str(text)[:256]))
            text = desc.get(bot.i18n.default) or next(iter(desc.values()))
        else:
            text = str(desc)
        default.append(T.BotCommand(command=name, description=text[:256]))
    try:
        if default:
            await bot.set_my_commands(default)
        for lang, cmds in per_lang.items():
            await bot.set_my_commands(cmds, language_code=lang)
        if bot.admin_panel and bot.admins:
            lang = bot.i18n.default
            admin_cmds = default + [T.BotCommand(command=c, description=bot.i18n.t(f"nb.cmd.{c}", lang)) for c in ("stats", "broadcast", "maintenance", "backup")]
            for admin in bot.admins:
                try:
                    await bot.set_my_commands(admin_cmds, scope=T.BotCommandScopeChat(chat_id=admin))
                except TelegramError:
                    pass
    except TelegramError as e:
        log.warning("Could not set the commands menu: %s", e)


# ============================================================================ statistics
async def compute_stats(bot: "Nicebot") -> dict[str, Any]:
    """Users, new users, DAU/WAU/MAU, blocked, premium, referrals, 7-day retention and top commands.

    Example::

        s = await compute_stats(bot)      # same as await bot.stats()
        print(s["dau"], s["top_commands"])
    """
    await bot.flush_stats()
    from .orm.builtin import Stat

    U = bot.User
    now = _now()
    day = dt.timedelta(days=1)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total = await U.count()
    cohort = U.filter(created_at__between=(now - 14 * day, now - 7 * day))
    cohort_n = await cohort.count()
    retained = await cohort.filter(last_seen__gte=now - 7 * day).count() if cohort_n else 0
    since = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    commands: dict[str, int] = {}
    for s in await Stat.filter(day__gte=since, name__startswith="cmd:"):
        commands[s.name[4:]] = commands.get(s.name[4:], 0) + int(s.count)
    return {
        "users": total,
        "new_today": await U.filter(created_at__gte=midnight).count(),
        "new_week": await U.filter(created_at__gte=now - 7 * day).count(),
        "dau": await U.filter(last_seen__gte=now - day).count(),
        "wau": await U.filter(last_seen__gte=now - 7 * day).count(),
        "mau": await U.filter(last_seen__gte=now - 30 * day).count(),
        "blocked": await U.filter(is_blocked=True).count(),
        "premium": await U.filter(is_premium=True).count(),
        "referred": await U.filter(referrer_id__isnull=False).count(),
        "retention_d7": round(100 * retained / cohort_n, 1) if cohort_n else None,
        "top_commands": sorted(commands.items(), key=lambda kv: -kv[1])[:10],
    }


def format_stats(s: dict[str, Any], t: Callable[..., str] | None = None) -> str:
    """Render ``bot.stats()`` as an HTML message (``t`` is a translator such as ``ctx.t``).

    Example::

        await ctx.reply(format_stats(await bot.stats(), ctx.t))
    """
    if t is None:
        from .i18n import I18n

        _i18n = I18n(None, default="en")
        t = lambda key, **kw: _i18n.t(key, "en", **kw)  # noqa: E731
    lines = [
        t("nb.admin.stats_title"),
        "",
        t("nb.admin.stats_total", users=s["users"]),
        t("nb.admin.stats_new", today=s["new_today"], week=s["new_week"]),
        t("nb.admin.stats_active", dau=s["dau"], wau=s["wau"], mau=s["mau"]),
        t("nb.admin.stats_blocked", blocked=s["blocked"], premium=s["premium"]),
        t("nb.admin.stats_referred", referred=s["referred"]),
        t("nb.admin.stats_retention", retention=s["retention_d7"] if s["retention_d7"] is not None else "—"),
    ]
    if s["top_commands"]:
        lines += ["", t("nb.admin.stats_top")] + [f"/{escape(c)} — {n}" for c, n in s["top_commands"]]
    return "\n".join(lines)


# ============================================================================ admin panel
def builtin_router(bot: "Nicebot") -> Router:
    """The router with the admin commands (/stats, /maintenance, /backup, /broadcast). Built once per bot.

    Example::

        router = builtin_router(bot)
        print([h.commands for h in router.all_handlers()])
    """
    cached = bot.__dict__.get("_builtin_router")
    if cached is not None:
        return cached
    r = Router("nicebot.builtin")
    bot.__dict__["_builtin_router"] = r
    if bot.captcha:
        bot.middlewares.insert(0, captcha_mw)
    if not (bot.admin_panel and bot.admins):
        return r

    @r.command("stats", admin=True)
    async def _stats(ctx: "Context") -> None:
        await ctx.reply(format_stats(await bot.stats(), ctx.t))

    @r.command("maintenance", admin=True)
    async def _maintenance(ctx: "Context") -> None:
        arg = ctx.arg.strip().lower()
        on = arg in ("on", "yoq", "вкл", "1", "true", "") if arg else bot._maintenance is None
        if arg in ("off", "o'chir", "ochir", "выкл", "0", "false"):
            on = False
        await bot.maintenance(on)
        await ctx.reply(ctx.t("nb.admin.maintenance_on") if on else ctx.t("nb.admin.maintenance_off"))

    @r.command("backup", admin=True)
    async def _backup(ctx: "Context") -> None:
        if bot.db.dialect != "sqlite" or getattr(bot.db.backend, "path", ":memory:") == ":memory:":
            await ctx.reply(ctx.t("nb.admin.backup_unsupported"))
            return
        import os
        import tempfile

        tmp = os.path.join(tempfile.mkdtemp(), "backup.db")
        await bot.db.backend.conn.execute("VACUUM INTO ?", [tmp])
        from ._base import InputFile

        await ctx.document(InputFile(tmp, filename=f"backup-{dt.date.today().isoformat()}.db"), caption=ctx.t("nb.admin.backup_caption"))

    @r.command("broadcast", admin=True)
    async def _broadcast(ctx: "Context") -> None:
        m = ctx.message
        source = m.reply_to_message if m is not None else None
        if source is None and not ctx.arg:
            await ctx.reply(ctx.t("nb.admin.broadcast_usage"))
            return
        n = await bot.User.filter(is_blocked=False).count()
        if not await ctx.confirm(ctx.t("nb.admin.broadcast_confirm", count=n)):
            return
        progress = await ctx.reply(ctx.t("nb.admin.broadcast_sending"))

        async def on_progress(stats: dict[str, int]) -> None:
            try:
                await bot.edit_message_text(f"⏳ {stats['sent'] + stats['failed']}/{stats['total']} · ✅ {stats['sent']} · ⛔️ {stats['blocked']}", chat_id=progress.chat.id, message_id=progress.message_id)
            except TelegramError:
                pass

        async def run() -> None:
            if source is not None:
                result = await bot.broadcast(None, copy_from=(source.chat.id, source.message_id), on_progress=on_progress)
            else:
                result = await bot.broadcast(ctx.arg, on_progress=on_progress)
            await bot.edit_message_text(
                ctx.t("nb.admin.broadcast_done", sent=result["sent"], blocked=result["blocked"], failed=result["failed"] - result["blocked"]),
                chat_id=progress.chat.id, message_id=progress.message_id, parse_mode="HTML",
            )

        ctx.background(run, retries=0)

    return r
