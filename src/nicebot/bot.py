"""``Nicebot`` — the one object you need."""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import signal
import sys
import time
import traceback
from typing import Any, Awaitable, Callable, Iterable

import msgspec

from . import types as T
from .api import BotAPI
from .client import Client
from .config import Config, load_env
from .context import MESSAGE_EVENTS, Context
from .errors import BadRequest, Conflict, FlowSignal, Forbidden, SkipHandler, StopHandling, TelegramError, Unauthorized
from .i18n import I18n
from .router import Handler, Router
from .storage import Storage, make_storage
from .utils import TTLCache, escape, maybe_await, parse_duration

log = logging.getLogger("nicebot")

_UPDATE_FIELDS = [f for f in T.Update.__struct_fields__ if f != "update_id"]
_UPDATE_DECODER = msgspec.json.Decoder(T.Update)
_LOOSE = msgspec.json.Decoder()

Middleware = Callable[[Context, Callable[[], Awaitable[Any]]], Awaitable[Any]]


def detect_event(update: T.Update) -> tuple[str | None, Any]:
    for name in _UPDATE_FIELDS:
        v = getattr(update, name, None)
        if v is not None:
            return name, v
    return None, None


class Nicebot(Router, BotAPI):
    """Create once, decorate handlers, call ``bot.start()``.

    >>> bot = Nicebot(token="123:ABC", db="sqlite:///bot.db", admins=[123456789])
    >>> @bot.command("start")
    ... async def start(ctx):
    ...     await ctx.reply(f"Salom, {ctx.name}!")
    >>> bot.start()

    Main options:
        token            – from @BotFather (or env ``BOT_TOKEN``)
        db               – ``sqlite:///bot.db`` · ``postgres://…`` · ``mysql://…`` · ``mongodb://…`` (default: in-memory SQLite)
        storage          – ``"db"`` (default) · ``"memory"`` · ``"redis://…"``
        admins           – Telegram ids allowed to use admin features
        lang / locales   – default language and folder with ``uz.json``, ``ru.json``…
        parse_mode       – ``"HTML"`` (default), ``"MarkdownV2"`` or ``None``
        required_channels – users must join these channels first
        support_chat     – forward unmatched private messages here, reply to answer
        captcha          – ``True`` or ``"2m"``: new group members must press a button
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        db: str | Any = None,
        storage: Any = "db",
        admins: Iterable[int] | int = (),
        lang: str = "uz",
        locales: str | None = "locales",
        parse_mode: str | None = "HTML",
        user_model: type | None = None,
        track_users: bool = True,
        analytics: bool = True,
        admin_panel: bool = True,
        required_channels: Iterable[int | str] = (),
        support_chat: int | str | None = None,
        captcha: bool | str = False,
        error_message: bool | str = True,
        notify_errors: bool = True,
        max_concurrency: int = 256,
        ask_timeout: Any = "10m",
        state_ttl: Any = "30d",
        tz: str | None = None,
        api_url: str = "https://api.telegram.org",
        flood_wait_max: Any = "2m",
        config: dict[str, Any] | None = None,
        name: str = "nicebot",
    ):
        super().__init__(name)
        token = token or os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
        if not token:
            raise ValueError("Token kerak: Nicebot(token='...') yoki BOT_TOKEN muhit o'zgaruvchisi")
        self.token = token
        self.client = Client(token, api_url=api_url, flood_wait_max=parse_duration(flood_wait_max) or 120)
        self.admins: set[int] = {admins} if isinstance(admins, int) else {int(a) for a in admins}
        self.parse_mode = parse_mode
        self.i18n = I18n(locales, default=lang)
        self.track_users = track_users
        self.analytics = analytics
        self.admin_panel = admin_panel
        self.required_channels = list(required_channels)
        self.support_chat = support_chat
        self.captcha = parse_duration("2m") if captcha is True else parse_duration(captcha) if captcha else None
        self.error_message = error_message
        self.notify_errors = notify_errors
        self.ask_timeout = ask_timeout
        self.state_ttl = parse_duration(state_ttl)
        self.tz = tz
        self.config = Config(config or {})

        from .orm import Database

        self._db_url = db
        if isinstance(db, Database):
            self.db: Any = db
        else:
            if db is None:
                log.info("db berilmadi: xotiradagi SQLite ishlatiladi (restartda ma'lumot o'chadi). Saqlash uchun db='sqlite:///bot.db'.")
            self.db = Database(db or "sqlite:///:memory:")
        self.storage: Storage = make_storage(storage)
        self.client.file_cache = self.storage
        self.user_model = user_model

        self.me: T.User | None = None
        self.username: str | None = None
        self.middlewares: list[Middleware] = []
        self._providers: dict[Any, Any] = {}
        self._waiters: dict[Any, tuple[asyncio.Future, int | None]] = {}
        self._sem = asyncio.Semaphore(max_concurrency)
        self._tasks: set[asyncio.Task] = set()
        self._startup: list[Callable[..., Any]] = []
        self._shutdown: list[Callable[..., Any]] = []
        self._new_user_hooks: list[Callable[..., Any]] = []
        self._referral_hooks: list[Callable[..., Any]] = []
        self._jobs: list[Any] = []
        self._api_routes: list[tuple[str, str, Callable[..., Any]]] = []
        self._static: list[tuple[str, str]] = []
        self._albums: dict[str, list[T.Message]] = {}
        self._album_timers: dict[str, asyncio.TimerHandle] = {}
        self._stats: dict[tuple[str, str], int] = {}
        self._error_seen = TTLCache(maxsize=1000, ttl=600)
        self._sub_cache = TTLCache(maxsize=100_000, ttl=60)
        self._maintenance: str | None = None
        self._stop: asyncio.Event | None = None
        self._ready = False
        self._index: dict[str, list[Handler]] = {}
        self._errors: list[tuple[type[BaseException], Callable[..., Any]]] = []
        self.started_at: float | None = None

    # ===================================================================== construction helpers
    @classmethod
    def from_env(cls, path: str = ".env", **overrides: Any) -> "Nicebot":
        """Read ``.env``: BOT_TOKEN, DATABASE_URL, ADMINS, REDIS_URL, LANG, SUPPORT_CHAT, REQUIRED_CHANNELS, TZ."""
        env = load_env(path)
        g = os.environ.get
        kw: dict[str, Any] = {"token": g("BOT_TOKEN")}
        if g("DATABASE_URL") or g("DB_URL"):
            kw["db"] = g("DATABASE_URL") or g("DB_URL")
        if g("ADMINS"):
            kw["admins"] = [int(x) for x in g("ADMINS", "").replace(" ", "").split(",") if x]
        if g("REDIS_URL"):
            kw["storage"] = g("REDIS_URL")
        if g("BOT_LANG"):
            kw["lang"] = g("BOT_LANG")
        if g("SUPPORT_CHAT"):
            kw["support_chat"] = int(g("SUPPORT_CHAT"))  # type: ignore[arg-type]
        if g("REQUIRED_CHANNELS"):
            kw["required_channels"] = [c.strip() for c in g("REQUIRED_CHANNELS", "").split(",") if c.strip()]
        if g("TZ"):
            kw["tz"] = g("TZ")
        kw["config"] = {**env, **{k: v for k, v in os.environ.items() if k in env}}
        kw.update(overrides)
        return cls(**kw)

    def provide(self, key: Any, value: Any) -> None:
        """Inject a value (or ``factory(ctx)``) into handlers that type-hint ``key``."""
        self._providers[key] = value

    def middleware(self, func: Middleware) -> Middleware:
        """``@bot.middleware async def mw(ctx, next): ...; await next()``"""
        self.middlewares.append(func)
        return func

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._startup.append(func)
        return func

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._shutdown.append(func)
        return func

    def on_new_user(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Called once when a user writes to the bot for the first time: ``async def h(ctx, user)``."""
        self._new_user_hooks.append(func)
        return func

    def on_referral(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """A new user came via someone's link: ``async def h(ctx, referrer)``."""
        self._referral_hooks.append(func)
        return func

    # ===================================================================== API plumbing
    async def request(self, method: str, params: dict[str, Any], returns: Any = "Any") -> Any:
        return await self.client.request(method, {k: v for k, v in params.items() if v is not None}, returns)

    async def _call_with_parse_fallback(self, method: str, **params: Any) -> Any:
        fn = getattr(self, method)
        try:
            return await fn(**params)
        except BadRequest as e:
            if "can't parse entities" in e.description.lower() and params.get("parse_mode"):
                log.warning("HTML/Markdown xato (%s) — matn formatlashsiz yuborildi. Foydalanuvchi matni uchun html() ishlating.", e.description)
                params["parse_mode"] = None
                return await fn(**params)
            raise

    async def safe_delete(self, chat_id: int | str, message_id: int) -> bool:
        try:
            return bool(await self.delete_message(chat_id, message_id))
        except TelegramError:
            return False

    def _track(self, task: asyncio.Task) -> asyncio.Task:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def later(self, delay: Any, coro: Awaitable[Any]) -> asyncio.Task:
        """Run ``coro`` after ``delay`` (``"30s"``, ``"5m"``…)."""
        seconds = parse_duration(delay) or 0

        async def runner() -> None:
            try:
                await asyncio.sleep(seconds)
            except asyncio.CancelledError:
                if hasattr(coro, "close"):
                    coro.close()  # type: ignore[union-attr]
                raise
            try:
                await coro
            except Exception:  # noqa: BLE001
                log.exception("later() vazifasida xato")

        task = asyncio.create_task(runner())
        task._nb_later = True  # type: ignore[attr-defined]
        return self._track(task)

    def background(self, func: Callable[..., Awaitable[Any]], *args: Any, retries: int = 3, delay: Any = "2s", **kwargs: Any) -> asyncio.Task:
        """Fire-and-forget with retries + exponential backoff. Awaited on graceful shutdown."""
        base = parse_duration(delay) or 1

        async def runner() -> Any:
            for attempt in range(retries + 1):
                try:
                    return await maybe_await(func(*args, **kwargs))
                except Exception:  # noqa: BLE001
                    if attempt >= retries:
                        log.exception("Fon vazifasi %s %d urinishdan keyin ham bajarilmadi", getattr(func, "__name__", func), retries + 1)
                        return None
                    await asyncio.sleep(base * (2 ** attempt))
            return None

        return self._track(asyncio.create_task(runner()))

    async def notify_admins(self, text: Any, **kw: Any) -> None:
        for admin in self.admins:
            try:
                await self._call_with_parse_fallback("send_message", chat_id=admin, text=str(text), parse_mode=self.parse_mode, **kw)
            except TelegramError:
                pass

    def ref_link(self, user_id: int) -> str:
        """``https://t.me/<bot>?start=ref_<id>`` — new users who open it get ``referrer_id``."""
        return f"https://t.me/{self.username or 'bot'}?start=ref_{int(user_id)}"

    def deep_link(self, payload: str, group: bool = False) -> str:
        return f"https://t.me/{self.username or 'bot'}?{'startgroup' if group else 'start'}={payload}"

    async def get_setting(self, user_id: int, key: str, default: Any = False) -> Any:
        return await self.storage.get(f"set:{user_id}:{key}", default)

    async def set_setting(self, user_id: int, key: str, value: Any) -> None:
        await self.storage.set(f"set:{user_id}:{key}", value)

    @property
    def User(self) -> Any:
        """The ORM model used for ``ctx.user`` (``nicebot.User`` or your subclass)."""
        if self.user_model is not None:
            return self.user_model
        from .orm.model import registry

        return registry()["nb_users"]

    # ===================================================================== maintenance & broadcast
    async def maintenance(self, on: bool = True, text: str | None = None) -> None:
        """Only admins can use the bot while maintenance is on."""
        self._maintenance = (text or "") if on else None
        await self.storage.set("nb:maintenance", self._maintenance)

    async def broadcast(self, content: Any, *, users: Iterable[int] | None = None, buttons: Any = None, copy_from: tuple[int, int] | None = None,
                        rate: float = 25, id: str | None = None, on_progress: Callable[..., Any] | None = None, **kw: Any) -> dict[str, int]:
        """Send to many users with the rate limit respected; resumable with ``id=``. See ``nicebot.broadcast``."""
        from .broadcast import broadcast

        return await broadcast(self, content, users=users, buttons=buttons, copy_from=copy_from, rate=rate, id=id, on_progress=on_progress, **kw)

    async def stats(self) -> dict[str, Any]:
        from .features import compute_stats

        return await compute_stats(self)

    # ===================================================================== scheduler & mini app
    def every(self, interval: Any, *, first: Any = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """``@bot.every("1h")`` — run periodically while the bot is up."""
        from .scheduler import Job

        def deco(func: Callable[..., Any]) -> Callable[..., Any]:
            self._jobs.append(Job(func, every=parse_duration(interval), first=parse_duration(first)))
            return func

        return deco

    def at(self, time_of_day: str, *, days: Iterable[int | str] | None = None, tz: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """``@bot.at("09:00")`` daily; ``days=["mon","fri"]``; ``tz="Asia/Tashkent"``."""
        from .scheduler import Job

        def deco(func: Callable[..., Any]) -> Callable[..., Any]:
            self._jobs.append(Job(func, at=time_of_day, days=days, tz=tz or self.tz))
            return func

        return deco

    def api(self, path: str, methods: Iterable[str] = ("POST",), *, auth: bool = True) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Mini App backend endpoint; Telegram ``initData`` is verified for you (``auth=True``).

        >>> @bot.api("/score")
        ... async def score(req):
        ...     return {"user": req.user["id"], "body": req.json}
        """

        def deco(func: Callable[..., Any]) -> Callable[..., Any]:
            func._nb_auth = auth  # type: ignore[attr-defined]
            for m in methods:
                self._api_routes.append((m.upper(), path, func))
            return func

        return deco

    def webapp(self, folder: str, path: str = "/") -> None:
        """Serve a Mini App's static files (``index.html``…) from ``folder`` at ``path``."""
        self._static.append((path, folder))

    # ===================================================================== dispatch
    def _build_index(self) -> None:
        from .features import builtin_router

        handlers = self.all_handlers() + builtin_router(self).all_handlers()
        self._index = {}
        for h in handlers:
            self._index.setdefault(h.event, []).append(h)
        self._errors = self.all_error_handlers()

    @property
    def allowed_updates(self) -> list[str]:
        events = set(self._index) - {"album", "fallback"}
        events |= {"message", "callback_query", "my_chat_member"}
        if self.captcha:
            events.add("chat_member")
        if "edited_message" in events:
            events.add("edited_message")
        return sorted(e for e in events if e in _UPDATE_FIELDS)

    async def feed(self, update: T.Update | dict[str, Any] | bytes) -> None:
        """Process one update (webhook servers, tests, custom transports)."""
        if isinstance(update, (bytes, bytearray, str)):
            raw = update.encode() if isinstance(update, str) else bytes(update)
            try:
                update = _UPDATE_DECODER.decode(raw)
            except msgspec.ValidationError as e:
                log.warning("Update'ni o'qib bo'lmadi (%s) — o'tkazib yuborildi", e)
                return
        elif isinstance(update, dict):
            try:
                update = msgspec.convert(update, T.Update)
            except msgspec.ValidationError as e:
                log.warning("Update'ni o'qib bo'lmadi (%s) — o'tkazib yuborildi", e)
                return
        await self.process_update(update)

    async def process_update(self, update: T.Update) -> None:
        if not self._index:
            self._build_index()
        event_name, event = detect_event(update)
        if event_name is None:
            return
        ctx = Context(self, update, event_name, event)
        if self._resolve_waiter(ctx):
            return
        if event_name == "callback_query" and (event.data or "").startswith("~c"):
            await ctx.answer(ctx.t("nb.expired"))
            return
        msg = event if event_name == "message" else None
        if msg is not None and msg.media_group_id and "album" in self._index:
            self._buffer_album(msg)
            return
        async with self._sem:
            await self._dispatch(ctx)

    async def _dispatch(self, ctx: Context) -> None:
        try:
            chain = self._builtin_middlewares() + self.middlewares

            async def call(i: int) -> Any:
                if i < len(chain):
                    return await chain[i](ctx, lambda: call(i + 1))
                return await self._route(ctx)

            await call(0)
        except (FlowSignal, asyncio.CancelledError) as e:
            if isinstance(e, asyncio.CancelledError):
                raise
        except Exception as e:  # noqa: BLE001
            await self._handle_error(ctx, e)
        finally:
            if ctx.is_callback and not ctx._answered:
                try:
                    await ctx.answer()
                except Exception:  # noqa: BLE001
                    pass

    def _resolve_waiter(self, ctx: Context) -> bool:
        if not self._waiters:
            return False
        if ctx.event_name == "message":
            w = self._waiters.get((ctx.chat_id, ctx.user_id))
            if w and not w[0].done():
                w[0].set_result(ctx)
                return True
        elif ctx.event_name == "callback_query":
            data = ctx.data or ""
            if data.startswith("~c"):
                token = data[2:].split(":", 1)[0]
                w = self._waiters.get(token)
                if w and not w[0].done():
                    if w[1] is not None and ctx.user_id != w[1]:
                        self._track(asyncio.create_task(ctx.answer(ctx.t("nb.not_yours"))))
                        return True
                    w[0].set_result(ctx)
                    return True
        return False

    def _buffer_album(self, msg: T.Message) -> None:
        gid = msg.media_group_id
        self._albums.setdefault(gid, []).append(msg)
        timer = self._album_timers.pop(gid, None)
        if timer:
            timer.cancel()
        loop = asyncio.get_running_loop()
        self._album_timers[gid] = loop.call_later(0.8, lambda: self._track(asyncio.create_task(self._flush_album(gid))))

    async def _flush_album(self, gid: str) -> None:
        self._album_timers.pop(gid, None)
        msgs = sorted(self._albums.pop(gid, []), key=lambda m: m.message_id)
        if not msgs:
            return
        ctx = Context(self, T.Update(update_id=0, message=msgs[0]), "message", msgs[0])
        ctx.album = msgs
        ctx.extra["route"] = "album"
        async with self._sem:
            await self._dispatch(ctx)

    async def _route(self, ctx: Context) -> bool:
        from .features import handle_internal_callback, support_relay

        if ctx.is_callback and (ctx.data or "").startswith("~"):
            handled = await handle_internal_callback(ctx)
            if handled:
                return True
        if ctx.event_name == "message" and await support_relay(ctx, phase="before"):
            return True
        event = ctx.extra.get("route", ctx.event_name)
        if self.analytics:
            self._count(f"cmd:{ctx.command}" if ctx.command else f"ev:{event}")
        for h in self._index.get(event, ()):
            ctx.params = {}
            ctx.match = None
            if not await h.check(ctx):
                continue
            try:
                await h.run(ctx)
            except SkipHandler:
                continue
            return True
        if event == "message":
            if await support_relay(ctx, phase="after"):
                return True
            for h in self._index.get("fallback", ()):
                if await h.check(ctx):
                    await h.run(ctx)
                    return True
        if event == "pre_checkout_query":
            await self.answer_pre_checkout_query(ctx.event.id, True)
            return True
        return False

    def _builtin_middlewares(self) -> list[Middleware]:
        from .features import maintenance_mw, subscription_mw, user_mw

        out: list[Middleware] = []
        if self.track_users:
            out.append(user_mw)
        if self._maintenance is not None:
            out.append(maintenance_mw)
        if self.required_channels:
            out.append(subscription_mw)
        return out

    def _count(self, name: str, n: int = 1) -> None:
        day = dt.date.today().isoformat()
        key = (day, name[:128])
        self._stats[key] = self._stats.get(key, 0) + n

    async def flush_stats(self) -> None:
        if not self._stats or not self.db.connected:
            return
        from .orm.builtin import Stat
        from .orm.query import F

        stats, self._stats = self._stats, {}
        for (day, name), n in stats.items():
            try:
                if not await Stat.filter(day=day, name=name).update(count=F("count") + n):
                    try:
                        await Stat.create(day=day, name=name, count=n)
                    except Exception:  # noqa: BLE001 - created concurrently
                        await Stat.filter(day=day, name=name).update(count=F("count") + n)
            except Exception:  # noqa: BLE001
                log.debug("Statistikani yozib bo'lmadi", exc_info=True)

    async def _handle_error(self, ctx: Context, exc: BaseException) -> None:
        for exc_type, func in self._errors:
            if isinstance(exc, exc_type):
                from .di import call_handler

                ctx.extra["error"] = exc
                ctx.extra["exc"] = exc
                try:
                    result = await call_handler(func, ctx)
                except Exception:  # noqa: BLE001
                    log.exception("Error handler'ning o'zida xato")
                    break
                if result is not False:
                    return
        if isinstance(exc, Forbidden) and ctx.is_private and ctx.user is not None:
            await ctx.user.update(is_blocked=True)
            return
        log.error("Handler xatosi (%s): %s", ctx, exc, exc_info=exc)
        if self.error_message and ctx.chat_id and ctx.event_name in ("message", "callback_query"):
            text = self.error_message if isinstance(self.error_message, str) else ctx.t("nb.error")
            try:
                if ctx.is_callback:
                    await ctx.answer(text, alert=True)
                else:
                    await ctx.reply(text)
            except Exception:  # noqa: BLE001
                pass
        if self.notify_errors and self.admins:
            sig = f"{type(exc).__name__}:{exc}"[:200]
            if sig in self._error_seen:
                return
            self._error_seen.set(sig, True)
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-3000:]
            who = f"{ctx.user_id} ({escape(ctx.name)})" if ctx.user_id else "-"
            text = (
                f"🚨 <b>Xatolik</b>\n<b>Update:</b> {ctx.event_name}\n<b>Foydalanuvchi:</b> {who}\n"
                f"<b>Matn:</b> {escape((ctx.text or ctx.data or '')[:200])}\n\n<pre>{escape(tb)}</pre>"
            )
            await self.notify_admins(text)

    # ===================================================================== lifecycle
    async def setup(self) -> None:
        """Connect the database, read bot info, register commands. Called by ``start``/``run`` and tests."""
        if self._ready:
            return
        from .features import register_commands
        from .orm.builtin import KV, Stat  # noqa: F401 - ensure registration

        if not self.db.connected:
            await self.db.connect()
        if self.me is None:
            self.me = await self.get_me()
            self.username = self.me.username
        self._maintenance = await self.storage.get("nb:maintenance")
        self._build_index()
        await register_commands(self)
        for f in self._startup:
            await maybe_await(f(self) if _takes_arg(f) else f())
        self._ready = True
        self.started_at = time.time()

    async def close(self) -> None:
        for f in self._shutdown:
            try:
                await maybe_await(f(self) if _takes_arg(f) else f())
            except Exception:  # noqa: BLE001
                log.exception("on_shutdown xatosi")
        for t in list(self._tasks):
            if getattr(t, "_nb_later", False):
                t.cancel()
        if self._tasks:
            await asyncio.wait(list(self._tasks), timeout=10)
        await self.flush_stats()
        await self.storage.close()
        await self.db.close()
        await self.client.close()
        self._ready = False

    async def run(self, *, webhook: str | None = None, port: int | None = None, host: str = "0.0.0.0", drop_pending: bool = False,
                  handle_signals: bool = True, stop: asyncio.Event | None = None) -> None:
        """Async entry point. Polling by default; ``webhook="https://domain/path"`` to use webhooks."""
        self._stop = stop or asyncio.Event()
        if handle_signals:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, self._stop.set)
                except (NotImplementedError, RuntimeError):  # Windows
                    pass
        await self.setup()
        from .scheduler import run_jobs
        from .server import run_server

        jobs = self._track(asyncio.create_task(run_jobs(self, self._jobs)))
        flusher = self._track(asyncio.create_task(self._flush_loop()))
        server = None
        try:
            if webhook or self._api_routes or self._static:
                server = await run_server(self, webhook=webhook, host=host, port=port or int(os.environ.get("PORT", 8080)))
            if webhook:
                log.info("✅ @%s webhook rejimida ishga tushdi: %s", self.username, webhook)
                await self._stop.wait()
            else:
                await self.delete_webhook(drop_pending_updates=drop_pending)
                log.info("✅ @%s ishga tushdi (polling). To'xtatish: Ctrl+C", self.username)
                await self._polling()
        finally:
            jobs.cancel()
            flusher.cancel()
            if server is not None:
                await server.cleanup()
            await self.close()
            log.info("👋 @%s to'xtatildi", self.username)

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            await self.flush_stats()

    async def _polling(self) -> None:
        assert self._stop is not None
        offset: int | None = None
        backoff = 1.0
        allowed = self.allowed_updates
        stop_task = asyncio.ensure_future(self._stop.wait())
        try:
            while not self._stop.is_set():
                fetch = asyncio.ensure_future(self.client.request("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": allowed}, "list[Raw]", timeout=35))
                done, _ = await asyncio.wait({fetch, stop_task}, return_when=asyncio.FIRST_COMPLETED)
                if stop_task in done:
                    fetch.cancel()
                    break
                try:
                    raws = fetch.result()
                    backoff = 1.0
                except Unauthorized:
                    log.critical("Token noto'g'ri yoki bekor qilingan (401). @BotFather'dan yangisini oling.")
                    raise
                except Conflict:
                    log.error("Boshqa joyda shu token bilan bot ishlayapti (409). 5 soniyadan keyin qayta urinaman...")
                    await asyncio.sleep(5)
                    continue
                except Exception as e:  # noqa: BLE001
                    log.warning("getUpdates xatosi: %s — %.0fs kutib qayta urinaman", e, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue
                for raw in raws:
                    try:
                        upd = _UPDATE_DECODER.decode(raw)
                    except msgspec.ValidationError as e:
                        loose = _LOOSE.decode(raw)
                        offset = int(loose.get("update_id", offset or 0)) + 1
                        log.warning("Noma'lum update turi o'tkazib yuborildi (%s)", e)
                        continue
                    offset = upd.update_id + 1
                    self._track(asyncio.create_task(self.process_update(upd)))
        finally:
            stop_task.cancel()
            pending = [t for t in self._tasks if not t.done() and t.get_coro().__name__ == "process_update"]  # type: ignore[union-attr]
            if pending:
                log.info("Ishlayotgan %d ta handler tugashini kutyapman...", len(pending))
                await asyncio.wait(pending, timeout=15)
            if offset is not None:
                try:  # confirm processed updates so they are not delivered again
                    await self.client.request("getUpdates", {"offset": offset, "timeout": 0, "limit": 1}, "list[Raw]", timeout=5)
                except Exception:  # noqa: BLE001
                    pass

    def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()

    def start(self, *, reload: bool = False, webhook: str | None = None, port: int | None = None, host: str = "0.0.0.0", drop_pending: bool = False,
              log_level: str | int = "INFO") -> None:
        """Blocking entry point. ``reload=True`` restarts the bot when your code changes."""
        from .logs import setup_logging

        setup_logging(log_level)
        if reload:
            from .reload import supervise

            if supervise():
                return
        if sys.platform == "win32":  # pragma: no cover
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
        try:
            asyncio.run(self.run(webhook=webhook, port=port, host=host, drop_pending=drop_pending))
        except KeyboardInterrupt:
            pass

    @staticmethod
    def run_all(*bots: "Nicebot", log_level: str | int = "INFO") -> None:
        """Run several bots in one process: ``Nicebot.run_all(shop_bot, support_bot)``."""
        from .logs import setup_logging

        setup_logging(log_level)

        async def main() -> None:
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, stop.set)
                except (NotImplementedError, RuntimeError):
                    pass
            await asyncio.gather(*(b.run(handle_signals=False, stop=stop) for b in bots))

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass

    def test(self, **kw: Any) -> Any:
        """``async with bot.test() as t: user = t.user(); await user.send("/start")`` — no Telegram needed."""
        from .testing import TestSession

        return TestSession(self, **kw)

    def __repr__(self) -> str:
        return f"<Nicebot @{self.username or '?'} handlers={len(self.all_handlers())}>"


def _takes_arg(func: Callable[..., Any]) -> bool:
    import inspect

    try:
        return len(inspect.signature(func).parameters) >= 1
    except (TypeError, ValueError):
        return False
