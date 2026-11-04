"""``Nicebot`` — the one object you need.

Example::

    from nicebot import Context, Nicebot

    bot = Nicebot(token="123456:ABC...", db="sqlite:///bot.db", admins=[123456789])

    @bot.command("start")
    async def start(ctx: Context):
        await ctx.reply(f"Hello, {ctx.name}!")

    bot.start()
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterable, Sequence

import msgspec

from . import types as T
from .api import BotAPI
from .client import Client
from .config import Config, load_env
from .context import MESSAGE_EVENTS, Context
from .errors import BadRequest, Conflict, FileTooBig, FlowSignal, Forbidden, SkipHandler, TelegramError, Unauthorized
from .i18n import I18n
from .media import DOWNLOAD_LIMIT, Media
from .router import Handler, Router
from .storage import Storage, make_storage
from .utils import TTLCache, escape, maybe_await, parse_duration

if TYPE_CHECKING:
    from .orm.builtin import User
    from .testing import TestSession

log = logging.getLogger("nicebot")

_UPDATE_FIELDS = [f for f in T.Update.__struct_fields__ if f != "update_id"]
_UPDATE_DECODER = msgspec.json.Decoder(T.Update)
_LOOSE = msgspec.json.Decoder()

Middleware = Callable[[Context, Callable[[], Awaitable[Any]]], Awaitable[Any]]


def detect_event(update: T.Update) -> tuple[str | None, Any]:
    """Return ``(event_name, payload)`` of an update, e.g. ``("message", Message(...))``.

    Example::

        name, payload = detect_event(update)
        if name == "callback_query":
            print(payload.data)
    """
    for name in _UPDATE_FIELDS:
        v = getattr(update, name, None)
        if v is not None:
            return name, v
    return None, None


class Nicebot(Router, BotAPI):
    """Create it once, decorate your handlers, call ``bot.start()``.

    Every Bot API method is available on the bot in snake_case (``await bot.send_message(...)``).

    Main options:
        token             – from @BotFather (or the ``BOT_TOKEN`` environment variable)
        db                – ``sqlite:///bot.db`` · ``postgresql://…`` · ``mysql://…`` · ``mongodb://…`` (default: in-memory SQLite)
        storage           – ``"db"`` (default) · ``"memory"`` · ``"redis://…"`` — where states, buttons and caches live
        admins            – Telegram ids allowed to use admin commands
        lang / locales    – default language and folder with ``uz.json``, ``ru.json``, ``en.json``…
        parse_mode        – ``"HTML"`` (default), ``"MarkdownV2"`` or ``None``
        required_channels – users must join these channels before using the bot
        support_chat      – unmatched private messages go to this group; reply there to answer
        captcha           – ``True`` or ``"2m"``: new group members must press a button
        public_url        – your HTTPS address for Mini Apps and webhooks (``tunnel=True`` sets it for you)
        test_server       – use Telegram's test environment (Mini Apps may use plain HTTP there)
        cors              – origins allowed to call ``@bot.api`` from another site: ``["https://me.github.io"]`` or ``"*"``
        debug             – lets you open the Mini App in a normal browser at ``http://localhost:<port>`` with a fake user

    Example::

        bot = Nicebot(
            token="123456:ABC...",
            db="sqlite:///shop.db",
            admins=[123456789],
            lang="en",
            required_channels=["@my_channel"],
        )

        @bot.command("start", description="Start the bot")
        async def start(ctx: Context):
            await ctx.reply("Welcome!")

        bot.start(reload=True)
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
        test_server: bool = False,
        public_url: str | None = None,
        cors: Iterable[str] | str | None = None,
        debug: bool = False,
        dev_user: dict[str, Any] | None = None,
        flood_wait_max: Any = "2m",
        config: dict[str, Any] | None = None,
        name: str = "nicebot",
    ):
        super().__init__(name)
        token = token or os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
        if not token:
            raise ValueError("A bot token is required: Nicebot(token='...') or the BOT_TOKEN environment variable. Get one from @BotFather.")
        self.token = token
        self.client = Client(token, api_url=api_url, test_server=test_server, flood_wait_max=parse_duration(flood_wait_max) or 120)
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
        #: Telegram test environment (``Nicebot(test_server=True)``).
        self.test_server = test_server
        #: Public HTTPS address of the built-in web server (Mini Apps, webhooks). ``tunnel=True`` fills it in.
        self.public_url: str | None = (public_url or os.environ.get("PUBLIC_URL") or "").rstrip("/") or None
        #: Origins allowed to call ``@bot.api`` routes from the browser.
        self.cors: list[str] = [cors] if isinstance(cors, str) else list(cors or [])
        #: Browser testing mode for Mini Apps (see ``dev_user``).
        self.debug = debug
        #: The fake Telegram user used by the browser testing mode.
        self.dev_user: dict[str, Any] = dev_user or {"id": next(iter(self.admins), 1), "first_name": "Dev", "username": "dev_user", "language_code": lang}

        from .orm import Database

        self._db_url = db
        if isinstance(db, Database):
            self.db: Any = db
        else:
            if db is None:
                log.info("No db= given: using in-memory SQLite (data is lost on restart). Use db='sqlite:///bot.db' to keep it.")
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
        self._menu_app: tuple[str, str] | None = None
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
        self._drop_pending = False
        self.started_at: float | None = None

    # ===================================================================== construction helpers
    @classmethod
    def from_env(cls, path: str = ".env", **overrides: Any) -> "Nicebot":
        """Create the bot from a ``.env`` file / environment variables.

        Reads ``BOT_TOKEN``, ``DATABASE_URL``, ``ADMINS`` (comma separated), ``REDIS_URL``, ``BOT_LANG``,
        ``SUPPORT_CHAT``, ``REQUIRED_CHANNELS``, ``TZ`` and ``PUBLIC_URL``. Every other variable is in ``bot.config``.

        Example::

            # .env
            # BOT_TOKEN=123456:ABC...
            # ADMINS=111,222
            # SHOP_NAME=Tezbaraka
            bot = Nicebot.from_env()
            print(bot.config.SHOP_NAME)
        """
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
        """Make a value available to handlers that ask for it by type hint (dependency injection).

        ``value`` may be an object or a ``factory(ctx)`` (sync or async) called for every update.

        Example::

            bot.provide(Settings, Settings(price=50_000))

            @bot.command("price")
            async def price(ctx: Context, settings: Settings):
                await ctx.reply(f"{settings.price} so'm")
        """
        self._providers[key] = value

    def middleware(self, func: Middleware) -> Middleware:
        """Register code that runs around every update. Call ``await next()`` to continue.

        Example::

            @bot.middleware
            async def timing(ctx: Context, next):
                start = time.monotonic()
                await next()
                log.info("%s took %.3fs", ctx, time.monotonic() - start)
        """
        self.middlewares.append(func)
        return func

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Run a function once the bot is connected (``func()`` or ``func(bot)``).

        Example::

            @bot.on_startup
            async def ready(bot: Nicebot):
                await bot.notify_admins("✅ Bot started")
        """
        self._startup.append(func)
        return func

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Run a function when the bot stops (Ctrl+C, SIGTERM).

        Example::

            @bot.on_shutdown
            async def bye(bot: Nicebot):
                await bot.notify_admins("👋 Bot stopped")
        """
        self._shutdown.append(func)
        return func

    def on_new_user(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Called once when somebody writes to the bot for the first time: ``async def h(ctx, user)``.

        Example::

            @bot.on_new_user
            async def welcome(ctx: Context, user: User):
                await ctx.notify_admins(f"🆕 New user: {user.mention}")
        """
        self._new_user_hooks.append(func)
        return func

    def on_referral(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Called when a new user came through somebody's referral link: ``async def h(ctx, referrer)``.

        Example::

            @bot.on_referral
            async def bonus(ctx: Context, referrer: User):
                await referrer.update(data={**referrer.data, "bonus": referrer.data.get("bonus", 0) + 1})
        """
        self._referral_hooks.append(func)
        return func

    # ===================================================================== API plumbing
    async def request(self, method: str, params: dict[str, Any], returns: Any = "Any") -> Any:
        """Call any Bot API method by its Telegram name (``None`` values are dropped).

        Example::

            me = await bot.request("getMe", {})
        """
        return await self.client.request(method, {k: v for k, v in params.items() if v is not None}, returns)

    async def _call_with_parse_fallback(self, method: str, **params: Any) -> Any:
        fn = getattr(self, method)
        try:
            return await fn(**params)
        except BadRequest as e:
            if "can't parse entities" in e.description.lower() and params.get("parse_mode"):
                log.warning("Bad HTML/Markdown (%s) — the message was sent without formatting. Use html() for user-provided text.", e.description)
                params["parse_mode"] = None
                return await fn(**params)
            raise

    async def safe_delete(self, chat_id: int | str, message_id: int) -> bool:
        """Delete a message and return ``False`` instead of raising when it is impossible.

        Example::

            await bot.safe_delete(chat_id, msg.message_id)
        """
        try:
            return bool(await self.delete_message(chat_id, message_id))
        except TelegramError:
            return False

    def _track(self, task: asyncio.Task) -> asyncio.Task:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def later(self, delay: Any, coro: Awaitable[Any]) -> asyncio.Task:
        """Run a coroutine after ``delay`` (``"30s"``, ``"5m"``, seconds) without blocking the handler.

        Example::

            msg = await ctx.reply("This offer ends in 1 minute")
            bot.later("1m", bot.safe_delete(msg.chat.id, msg.message_id))
        """
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
                log.exception("Error in a later() task")

        task = asyncio.create_task(runner())
        task._nb_later = True  # type: ignore[attr-defined]
        return self._track(task)

    def background(self, func: Callable[..., Awaitable[Any]], *args: Any, retries: int = 3, delay: Any = "2s", **kwargs: Any) -> asyncio.Task:
        """Fire-and-forget with retries and exponential backoff; awaited on graceful shutdown.

        Example::

            bot.background(send_invoice_email, order.id, retries=5)
        """
        base = parse_duration(delay) or 1

        async def runner() -> Any:
            for attempt in range(retries + 1):
                try:
                    return await maybe_await(func(*args, **kwargs))
                except Exception:  # noqa: BLE001
                    if attempt >= retries:
                        log.exception("Background task %s failed after %d attempts", getattr(func, "__name__", func), retries + 1)
                        return None
                    await asyncio.sleep(base * (2 ** attempt))
            return None

        return self._track(asyncio.create_task(runner()))

    async def notify_admins(self, text: Any, **kw: Any) -> None:
        """Send a message to every admin (errors such as "blocked" are ignored).

        Example::

            await bot.notify_admins("📈 1000 users today!")
        """
        for admin in self.admins:
            try:
                await self._call_with_parse_fallback("send_message", chat_id=admin, text=str(text), parse_mode=self.parse_mode, **kw)
            except TelegramError:
                pass

    def ref_link(self, user_id: int) -> str:
        """Referral link of a user: ``https://t.me/<bot>?start=ref_<id>``. New users who open it get ``referrer_id``.

        Example::

            await ctx.reply(f"Your link: {bot.ref_link(ctx.user_id)}")
        """
        return f"https://t.me/{self.username or 'bot'}?start=ref_{int(user_id)}"

    def start_link(self, payload: str, group: bool = False) -> str:
        """A ``t.me`` link that opens the bot with ``/start <payload>`` (``group=True`` adds the bot to a group).

        Example::

            bot.start_link("promo_2026")      # https://t.me/your_bot?start=promo_2026
        """
        return f"https://t.me/{self.username or 'bot'}?{'startgroup' if group else 'start'}={payload}"

    def deep_link(self, payload: Any, **opts: Any) -> Any:
        """Decorator: handle ``/start <payload>`` links (``payload`` is a regex, named groups become parameters).

        For backwards compatibility the returned value is also the link itself (a ``str``), but prefer
        ``bot.start_link(payload)`` to build links.

        Example::

            @bot.deep_link(r"promo_(?P<code>\\w+)")
            async def promo(ctx: Context, code: str):
                await ctx.reply(f"Promo code: {code}")
        """
        deco = Router.deep_link(self, payload, **opts)
        if isinstance(payload, str):
            return _LinkDecorator(self.start_link(payload), deco)
        return deco

    def app_link(self, short_name: str | None = None, startapp: str | None = None) -> str:
        """A direct link that opens your Mini App: ``https://t.me/<bot>/<short_name>?startapp=<param>``.

        Without ``short_name`` it opens the bot's main Mini App (set up in @BotFather → Bot Settings → Configure Mini App).

        Example::

            bot.app_link("shop", startapp="promo")   # https://t.me/your_bot/shop?startapp=promo
            bot.app_link()                           # https://t.me/your_bot?startapp
        """
        base = f"https://t.me/{self.username or 'bot'}"
        if short_name:
            return f"{base}/{short_name}" + (f"?startapp={startapp}" if startapp else "")
        return f"{base}?startapp" + (f"={startapp}" if startapp else "")

    async def get_setting(self, user_id: int, key: str, default: Any = False) -> Any:
        """Read a per-user setting (``Toggle`` values, ``ctx.set_setting``).

        Example::

            notify = await bot.get_setting(user.id, "notify", default=True)
        """
        return await self.storage.get(f"set:{user_id}:{key}", default)

    async def set_setting(self, user_id: int, key: str, value: Any) -> None:
        """Save a per-user setting.

        Example::

            await bot.set_setting(user.id, "notify", False)
        """
        await self.storage.set(f"set:{user_id}:{key}", value)

    @property
    def User(self) -> "type[User]":
        """The ORM model behind ``ctx.user`` (``nicebot.User`` or the subclass you passed as ``user_model``).

        Example::

            active = await bot.User.filter(is_blocked=False).count()
        """
        if self.user_model is not None:
            return self.user_model  # type: ignore[return-value]
        from .orm.model import registry

        return registry()["nb_users"]  # type: ignore[return-value]

    # ===================================================================== files
    async def download_file(self, file: Any) -> bytes:
        """Download a Telegram file into memory.

        ``file`` may be a ``file_id``, a ``Media``, a Telegram media object (``PhotoSize``, ``Document``…),
        a list of photo sizes or a ``Message``. Raises ``FileTooBig`` above 20 MB on the cloud Bot API.

        Example::

            data = await bot.download_file(message.document)
        """
        file_id, size = self._file_ref(file)
        path = await self._file_path(file_id, size)
        return await self.client.download(path)

    async def save_file(self, file: Any, path: str | os.PathLike[str] | None = None, *, folder: str | os.PathLike[str] = "downloads") -> str:
        """Download a Telegram file straight to disk (streamed) and return the path.

        Example::

            await bot.save_file(user_photo_id, "avatars/42.jpg")
        """
        media = file if isinstance(file, Media) else Media.of(file, self) if isinstance(file, T.Message) else None
        file_id, size = self._file_ref(file)
        name = media.filename if media else None
        tg_path = await self._file_path(file_id, size)
        if name is None:
            name = Path(tg_path).name or file_id
        dest = Path(folder) / name if path is None else Path(path)
        if path is not None and (str(path).endswith(("/", "\\")) or dest.is_dir()):
            dest = dest / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        await self.client.download_to(tg_path, dest)
        return str(dest)

    def _file_ref(self, file: Any) -> tuple[str, int | None]:
        if isinstance(file, str):
            return file, None
        if isinstance(file, Media):
            return file.file_id, file.size
        if isinstance(file, T.Message):
            m = Media.of(file, self)
            if m is None:
                raise ValueError("This message has no file")
            return m.file_id, m.size
        if isinstance(file, (list, tuple)) and file:
            file = max(file, key=lambda p: (getattr(p, "width", 0) or 0) * (getattr(p, "height", 0) or 0))
        file_id = getattr(file, "file_id", None)
        if not file_id:
            raise TypeError(f"Cannot download {type(file).__name__}: pass a file_id, Media, Message or a Telegram media object")
        return file_id, getattr(file, "file_size", None)

    async def _file_path(self, file_id: str, size: int | None) -> str:
        if size is not None and size > DOWNLOAD_LIMIT and self.client.is_cloud:
            raise FileTooBig(size)
        try:
            info = await self.get_file(file_id)
        except BadRequest as e:
            if "too big" in e.description.lower():
                raise FileTooBig(size) from e
            raise
        if not info.file_path:
            raise FileTooBig(size)
        return info.file_path

    # ===================================================================== maintenance & broadcast
    async def maintenance(self, on: bool = True, text: str | None = None) -> None:
        """Turn maintenance mode on/off: only admins can use the bot while it is on (survives restarts).

        Example::

            await bot.maintenance(True, "🛠 Back in 10 minutes")
        """
        self._maintenance = (text or "") if on else None
        await self.storage.set("nb:maintenance", self._maintenance)

    async def broadcast(self, content: Any, *, users: Iterable[int] | None = None, buttons: Any = None, copy_from: tuple[int, int] | None = None,
                        rate: float = 25, id: str | None = None, on_progress: Callable[..., Any] | None = None, **kw: Any) -> dict[str, int]:
        """Send a message to many users, respecting Telegram limits; resumable with ``id=``.

        Returns ``{"sent": …, "failed": …, "blocked": …, "total": …}``.

        Example::

            result = await bot.broadcast("🎉 New collection!", buttons=[Button("🛍 Open", url=SHOP)], id="june-sale")
            await ctx.reply(f"Sent to {result['sent']} users")
        """
        from .broadcast import broadcast

        return await broadcast(self, content, users=users, buttons=buttons, copy_from=copy_from, rate=rate, id=id, on_progress=on_progress, **kw)

    async def stats(self) -> dict[str, Any]:
        """Usage statistics: users, DAU/WAU/MAU, retention and top commands.

        Example::

            s = await bot.stats()
            await ctx.reply(f"Users: {s['users']}, today: {s['dau']}")
        """
        from .features import compute_stats

        return await compute_stats(self)

    # ===================================================================== scheduler
    def every(self, interval: Any, *, first: Any = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator: run a function periodically while the bot is running.

        Example::

            @bot.every("1h")
            async def sync_prices(bot: Nicebot):
                await Product.refresh_prices()
        """
        from .scheduler import Job

        def deco(func: Callable[..., Any]) -> Callable[..., Any]:
            self._jobs.append(Job(func, every=parse_duration(interval), first=parse_duration(first)))
            return func

        return deco

    def at(self, time_of_day: str, *, days: Iterable[int | str] | None = None, tz: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator: run a function every day at ``"HH:MM"`` (optionally only on some ``days``).

        Example::

            @bot.at("09:00", days=["mon", "fri"], tz="Asia/Tashkent")
            async def report(bot: Nicebot):
                await bot.notify_admins(str(await bot.stats()))
        """
        from .scheduler import Job

        def deco(func: Callable[..., Any]) -> Callable[..., Any]:
            self._jobs.append(Job(func, at=time_of_day, days=days, tz=tz or self.tz))
            return func

        return deco

    # ===================================================================== mini apps
    def api(self, path: str, methods: Iterable[str] = ("POST",), *, auth: bool = True) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator: a backend endpoint for your Mini App. Telegram ``initData`` is verified for you (``auth=True``).

        The handler gets a ``WebAppRequest`` and returns a dict (JSON), a string or an aiohttp response.
        Raise ``PermissionError`` → 403, ``ValueError``/``KeyError`` → 400.

        Example::

            @bot.api("/api/score")
            async def score(req: WebAppRequest):
                user = await req.db_user()
                await user.update(data={**user.data, "score": int(req.json["score"])})
                return {"ok": True}

            @bot.api("/api/products", methods=["GET"], auth=False)
            async def products(req: WebAppRequest):
                return [p.to_dict() for p in await Product.all()]
        """

        def deco(func: Callable[..., Any]) -> Callable[..., Any]:
            func._nb_auth = auth  # type: ignore[attr-defined]
            for m in methods:
                self._api_routes.append((m.upper(), path, func))
            return func

        return deco

    def webapp(self, folder: str | os.PathLike[str], path: str = "/") -> None:
        """Serve your Mini App's static files (``index.html``, JS, CSS, images) from ``folder`` at ``path``.

        Unknown routes fall back to ``index.html`` so single-page apps (React, Vue…) work.

        Example::

            bot.webapp("webapp")            # webapp/index.html → https://<public_url>/
            bot.webapp("admin", "/admin")   # admin/index.html → https://<public_url>/admin
        """
        self._static.append((path, str(folder)))

    def menu_app(self, text: str, path: str = "/") -> None:
        """Show a Mini App button next to the message field (the "menu button") for every user.

        Applied when the bot starts, once the public HTTPS address is known.

        Example::

            bot.webapp("webapp")
            bot.menu_app("🛍 Shop")      # opens https://<public_url>/
            bot.start(tunnel=True)
        """
        self._menu_app = (text, path)

    def webapp_url(self, path: str = "/") -> str:
        """Turn a path like ``"/shop"`` into the full public URL of your Mini App.

        Telegram opens Mini Apps only over HTTPS (plain HTTP is allowed on the test server).

        Example::

            bot.webapp_url("/shop?item=5")   # "https://red-cat.trycloudflare.com/shop?item=5"
        """
        if path.startswith(("https://", "http://")):
            url = path
        else:
            if not self.public_url:
                raise ValueError(
                    f"The Mini App path {path!r} needs a public HTTPS address. Run bot.start(tunnel=True) while developing, "
                    "or set Nicebot(public_url='https://your-domain') / the PUBLIC_URL variable."
                )
            url = self.public_url + "/" + path.lstrip("/")
        if url.startswith("http://") and not self.test_server:
            raise ValueError(
                f"Telegram opens Mini Apps only over HTTPS, got {url!r}. Use bot.start(tunnel=True), deploy behind HTTPS, "
                "or use Telegram's test server (Nicebot(test_server=True)) where HTTP is allowed."
            )
        return url

    async def set_menu_app(self, text: str, url: str = "/", *, chat_id: int | None = None) -> bool:
        """Set the menu button to open a Mini App now (for everyone, or for one ``chat_id``).

        Example::

            await bot.set_menu_app("🎮 Play", "/game", chat_id=ctx.chat_id)
        """
        button = T.MenuButtonWebApp(text=text, web_app=T.WebAppInfo(url=self.webapp_url(url)))
        return await self.set_chat_menu_button(chat_id=chat_id, menu_button=button)

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
        """Update types requested from Telegram (computed from your handlers).

        Example::

            print(bot.allowed_updates)   # ['callback_query', 'message', 'my_chat_member']
        """
        if not self._index:
            self._build_index()
        events = set(self._index) - {"album", "fallback"}
        events |= {"message", "callback_query", "my_chat_member"}
        if self.captcha:
            events.add("chat_member")
        return sorted(e for e in events if e in _UPDATE_FIELDS)

    async def feed(self, update: T.Update | dict[str, Any] | bytes) -> None:
        """Process one update (from a webhook, a test or a custom transport).

        Example::

            await bot.feed({"update_id": 1, "message": {...}})
        """
        if isinstance(update, (bytes, bytearray, str)):
            raw = update.encode() if isinstance(update, str) else bytes(update)
            try:
                update = _UPDATE_DECODER.decode(raw)
            except msgspec.ValidationError as e:
                log.warning("Could not decode an update (%s) — skipped", e)
                return
        elif isinstance(update, dict):
            try:
                update = msgspec.convert(update, T.Update)
            except msgspec.ValidationError as e:
                log.warning("Could not decode an update (%s) — skipped", e)
                return
        await self.process_update(update)

    async def process_update(self, update: T.Update) -> None:
        """Route a decoded ``Update`` to the matching handler (used by polling and webhooks).

        Example::

            await bot.process_update(T.Update(update_id=1, message=msg))
        """
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
            w = self._waiters.get((ctx._chat_id_or_none(), ctx.user_id))
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
        gid = msg.media_group_id or ""
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
        """Write the in-memory usage counters to the database (done every 30 s and on shutdown).

        Example::

            await bot.flush_stats()
        """
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
                log.debug("Could not save statistics", exc_info=True)

    async def _handle_error(self, ctx: Context, exc: BaseException) -> None:
        for exc_type, func in self._errors:
            if isinstance(exc, exc_type):
                from .di import call_handler

                ctx.extra["error"] = exc
                ctx.extra["exc"] = exc
                try:
                    result = await call_handler(func, ctx)
                except Exception:  # noqa: BLE001
                    log.exception("The error handler itself failed")
                    break
                if result is not False:
                    return
        if isinstance(exc, Forbidden) and ctx.is_private and ctx.user is not None:
            await ctx.user.update(is_blocked=True)
            return
        log.error("Handler error (%s): %s", ctx, exc, exc_info=exc)
        if self.error_message and ctx._chat_id_or_none() and ctx.event_name in ("message", "callback_query"):
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
                f"🚨 <b>{escape(ctx.t('nb.admin.error_title'))}</b>\n<b>Update:</b> {ctx.event_name}\n<b>{escape(ctx.t('nb.admin.user'))}:</b> {who}\n"
                f"<b>{escape(ctx.t('nb.admin.text'))}:</b> {escape((ctx.text or ctx.data or '')[:200])}\n\n<pre>{escape(tb)}</pre>"
            )
            await self.notify_admins(text)

    # ===================================================================== lifecycle
    async def setup(self) -> None:
        """Connect the database, read the bot's info and register commands. Called by ``start``/``run`` and tests.

        Example::

            await bot.setup()
            print(bot.username)
        """
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

    async def shutdown(self) -> None:
        """Stop gracefully: run ``on_shutdown`` hooks, wait for tasks, close the database and HTTP sessions.

        Example::

            try:
                await bot.run()
            finally:
                await bot.shutdown()     # run() already does this for you
        """
        for f in self._shutdown:
            try:
                await maybe_await(f(self) if _takes_arg(f) else f())
            except Exception:  # noqa: BLE001
                log.exception("on_shutdown hook failed")
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

    async def close(self) -> None:  # type: ignore[override]
        """Same as ``shutdown()`` (kept for compatibility).

        Telegram's own ``close`` method (moving a bot between local Bot API servers) is ``bot.close_bot_instance()``.

        Example::

            await bot.close()
        """
        await self.shutdown()

    async def close_bot_instance(self) -> bool:
        """Telegram's ``close`` method: close the bot instance before moving it to another local Bot API server.

        Example::

            await bot.close_bot_instance()
        """
        return await BotAPI.close(self)

    async def run(self, *, webhook: str | bool | None = None, port: int | None = None, host: str = "0.0.0.0", drop_pending: bool = False,
                  handle_signals: bool = True, stop: asyncio.Event | None = None, tunnel: "bool | str | Sequence[str]" = False) -> None:
        """Async entry point (``bot.start()`` calls it). Polling by default.

        * ``webhook="https://domain/path"`` — receive updates by webhook (``True`` uses ``public_url``/the tunnel)
        * ``port`` — web server port for Mini Apps/webhooks (default ``$PORT`` or 8080)
        * ``tunnel=True`` — free public HTTPS address for development
        * ``drop_pending=True`` — skip updates that arrived while the bot was off

        Example::

            async def main():
                await bot.run(tunnel=True)

            asyncio.run(main())
        """
        self._stop = stop or asyncio.Event()
        self._drop_pending = drop_pending
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
        tun = None
        port = port or int(os.environ.get("PORT", 8080))
        try:
            needs_server = bool(webhook or self._api_routes or self._static or tunnel or self.debug)
            if tunnel:
                from .tunnel import Tunnel

                tun = await Tunnel.open(port, tunnel)
                self.public_url = tun.url
            if webhook is True:
                if not self.public_url:
                    raise ValueError("webhook=True needs a public HTTPS address: pass tunnel=True or Nicebot(public_url=...)")
                webhook = self.public_url + "/nicebot/webhook"
            if needs_server:
                server = await run_server(self, webhook=webhook or None, host=host, port=port)
                if self._static:
                    log.info("📱 Mini App: %s  (browser: http://localhost:%d%s)", self.public_url or "set public_url or use tunnel=True",
                             port, "" if self.debug else " — add debug=True to test without Telegram")
            if self._menu_app and self.public_url:
                try:
                    await self.set_menu_app(*self._menu_app)
                except (ValueError, TelegramError) as e:
                    log.warning("Could not set the Mini App menu button: %s", e)
            if webhook:
                log.info("✅ @%s is running (webhook): %s", self.username, webhook)
                await self._stop.wait()
            else:
                await self.delete_webhook(drop_pending_updates=drop_pending)
                log.info("✅ @%s is running (polling). Stop with Ctrl+C", self.username)
                await self._polling()
        finally:
            jobs.cancel()
            flusher.cancel()
            if server is not None:
                await server.cleanup()
            if tun is not None:
                await tun.close()
            await self.shutdown()
            log.info("👋 @%s stopped", self.username)

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
                    log.critical("The token is wrong or revoked (401). Get a new one from @BotFather.")
                    raise
                except Conflict:
                    log.error("Another process is running with this token (409). Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    continue
                except Exception as e:  # noqa: BLE001
                    log.warning("getUpdates failed: %s — retrying in %.0fs", e, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue
                for raw in raws:
                    try:
                        upd = _UPDATE_DECODER.decode(raw)
                    except msgspec.ValidationError as e:
                        loose = _LOOSE.decode(raw)
                        offset = int(loose.get("update_id", offset or 0)) + 1
                        log.warning("Skipped an unknown update type (%s)", e)
                        continue
                    offset = upd.update_id + 1
                    self._track(asyncio.create_task(self.process_update(upd)))
        finally:
            stop_task.cancel()
            pending = [t for t in self._tasks if not t.done() and t.get_coro().__name__ == "process_update"]  # type: ignore[union-attr]
            if pending:
                log.info("Waiting for %d running handlers to finish...", len(pending))
                await asyncio.wait(pending, timeout=15)
            if offset is not None:
                try:  # confirm processed updates so they are not delivered again
                    await self.client.request("getUpdates", {"offset": offset, "timeout": 0, "limit": 1}, "list[Raw]", timeout=5)
                except Exception:  # noqa: BLE001
                    pass

    def stop(self) -> None:
        """Ask a running bot to stop (same as Ctrl+C).

        Example::

            @bot.command("shutdown", admin=True)
            async def shutdown(ctx: Context):
                ctx.bot.stop()
        """
        if self._stop is not None:
            self._stop.set()

    def start(self, *, reload: bool = False, webhook: str | bool | None = None, port: int | None = None, host: str = "0.0.0.0", drop_pending: bool = False,
              tunnel: "bool | str | Sequence[str]" = False, log_level: str | int = "INFO") -> None:
        """Run the bot until Ctrl+C (blocking).

        * ``reload=True`` — restart automatically when your code changes
        * ``tunnel=True`` — free HTTPS address for Mini Apps/webhooks while developing
        * ``webhook=`` — ``"https://domain/path"`` or ``True`` (uses ``public_url``/the tunnel)
        * ``port`` — web server port (default ``$PORT`` or 8080)

        Example::

            bot.start()                     # polling
            bot.start(reload=True)          # development
            bot.start(tunnel=True)          # Mini App development, no domain needed
            bot.start(webhook="https://bot.example.com/tg", port=8080)
        """
        from .logs import setup_logging

        setup_logging(log_level)
        if reload:
            from .reload import supervise

            if supervise():
                return
        if sys.platform == "win32":  # pragma: no cover
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
        try:
            asyncio.run(self.run(webhook=webhook, port=port, host=host, drop_pending=drop_pending, tunnel=tunnel))
        except KeyboardInterrupt:
            pass

    @staticmethod
    def run_all(*bots: "Nicebot", log_level: str | int = "INFO") -> None:
        """Run several bots in one process.

        Example::

            Nicebot.run_all(shop_bot, support_bot)
        """
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

    def test(self, **kw: Any) -> "TestSession":
        """Test the bot without Telegram: fake users send messages and press buttons.

        Example::

            async def test_start():
                async with bot.test() as t:
                    ali = t.user(first_name="Ali")
                    await ali.send("/start")
                    assert t.last.text == "Hello, Ali!"
        """
        from .testing import TestSession

        return TestSession(self, **kw)

    def __repr__(self) -> str:
        return f"<Nicebot @{self.username or '?'} handlers={len(self.all_handlers())}>"


class _LinkDecorator(str):
    """A ``str`` (the t.me link) that also works as the ``@bot.deep_link(...)`` decorator."""

    _deco: Callable[[Callable[..., Any]], Callable[..., Any]]

    def __new__(cls, link: str, deco: Callable[[Callable[..., Any]], Callable[..., Any]]) -> "_LinkDecorator":
        obj = super().__new__(cls, link)
        obj._deco = deco
        return obj

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        return self._deco(func)


def _takes_arg(func: Callable[..., Any]) -> bool:
    import inspect

    try:
        return len(inspect.signature(func).parameters) >= 1
    except (TypeError, ValueError):
        return False
