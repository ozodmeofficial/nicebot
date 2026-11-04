"""Handlers and routers. A ``Router`` groups handlers; ``Nicebot`` is a Router too.

Example::

    router = Router()

    @router.command("start")
    async def start(ctx: Context):
        await ctx.reply("Hi!")

    bot.include(router)
"""
from __future__ import annotations

import asyncio
import contextlib
import re
import time
from typing import TYPE_CHECKING, Any, Callable, Iterable, TypedDict, TypeVar

from .filters import Filter, as_filter
from .keyboards import CallbackTemplate
from .utils import TTLCache, parse_duration

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from .context import Context

Handler_T = Callable[..., Any]
F = TypeVar("F", bound=Callable[..., Any])

CONTENT_TYPES = (
    "text", "photo", "video", "document", "audio", "voice", "video_note", "sticker", "animation", "contact", "location",
    "venue", "poll", "dice", "game", "invoice", "successful_payment", "web_app_data", "new_chat_members", "left_chat_member",
    "pinned_message", "story", "giveaway", "users_shared", "chat_shared", "paid_media", "checklist",
)

_CHAT_ALIASES = {"private": ("private",), "group": ("group", "supergroup"), "supergroup": ("supergroup",), "channel": ("channel",)}


class Handler:
    """One registered handler: the function plus everything that decides whether it runs. Created by the decorators.

    Example::

        h = bot.all_handlers()[0]
        print(h.event, h.name, h.commands)
    """

    __slots__ = (
        "event", "func", "filters", "commands", "exact", "regex", "contains", "startswith", "ignore_case", "template", "content",
        "states", "chat_types", "admin", "users", "throttle", "throttle_cache", "typing", "payload", "description", "router",
        "block", "name", "match_command_any",
    )

    def __init__(self, event: str, func: Handler_T, *, filters: Iterable[Any] = (), commands: Iterable[str] = (), exact: Iterable[str] = (),
                 regex: Any = None, contains: Iterable[str] = (), startswith: Iterable[str] = (), ignore_case: bool = True, template: str | None = None,
                 content: Iterable[str] = (), state: Any = ..., chat: Any = None, admin: bool = False, users: Iterable[int] | None = None,
                 throttle: Any = None, typing: Any = None, payload: Any = None, description: Any = None, block: bool = True):
        self.event = event
        self.func = func
        self.filters = [as_filter(f) for f in filters]
        self.commands = {c.lower().lstrip("/") for c in commands}
        self.ignore_case = ignore_case
        self.exact = {e.lower() if ignore_case else e for e in exact}
        self.regex = re.compile(regex, re.I if ignore_case else 0) if isinstance(regex, str) else regex
        self.contains = [c.lower() if ignore_case else c for c in contains]
        self.startswith = [c.lower() if ignore_case else c for c in startswith]
        self.template = CallbackTemplate(template) if template else None
        self.content = set(content)
        if state is ...:
            self.states = None
        elif isinstance(state, (list, tuple, set)):
            self.states = set(state)
        else:
            self.states = {state}
        if chat is None:
            self.chat_types = None
        else:
            kinds = [chat] if isinstance(chat, str) else list(chat)
            self.chat_types = {t for k in kinds for t in _CHAT_ALIASES.get(k, (k,))}
        self.admin = admin
        self.users = set(users) if users else None
        self.throttle = parse_duration(throttle)
        self.throttle_cache = TTLCache(maxsize=100_000, ttl=self.throttle) if self.throttle else None
        self.typing = "typing" if typing is True else typing
        self.payload = re.compile(payload) if isinstance(payload, str) else payload
        self.description = description
        self.block = block
        self.router: Router | None = None
        self.name = getattr(func, "__name__", "handler")

    def __repr__(self) -> str:
        return f"<Handler {self.event}:{self.name}>"

    # ---------------------------------------------------------------- matching
    async def check(self, ctx: "Context") -> bool:
        """``True`` if this handler should run for ``ctx`` (fills ``ctx.params``/``ctx.match``).

        Example::

            if await handler.check(ctx):
                await handler.run(ctx)
        """
        if self.chat_types is not None and (ctx.chat is None or ctx.chat.type not in self.chat_types):
            return False
        if self.admin and not ctx.is_admin:
            return False
        if self.users is not None and ctx.user_id not in self.users:
            return False
        msg = ctx.event if ctx.event_name in ("message", "edited_message", "channel_post", "edited_channel_post", "business_message", "edited_business_message") else None

        if self.commands:
            cmd = ctx.command
            if cmd is None or cmd not in self.commands:
                return False
            if self.payload is not None:
                m = self.payload.fullmatch(ctx.payload) if hasattr(self.payload, "fullmatch") else None
                if not m:
                    return False
                ctx.params.update(m.groupdict())
        if self.content:
            if msg is None:
                return False
            if "any" not in self.content and not any(getattr(msg, c, None) for c in self.content):
                return False
        text = ctx.text
        if self.exact or self.contains or self.startswith or self.regex is not None:
            if self.event == "callback_query":
                text = ctx.data
            if text is None:
                return False
            t = text.lower() if self.ignore_case else text
            if self.exact and t.strip() not in self.exact:
                return False
            if self.contains and not any(c in t for c in self.contains):
                return False
            if self.startswith and not any(t.startswith(s) for s in self.startswith):
                return False
            if self.regex is not None:
                m = self.regex.search(text)
                if not m:
                    return False
                ctx.match = m
                ctx.params.update({k: v for k, v in m.groupdict().items() if v is not None})
        if self.template is not None:
            data = ctx.data
            if data is None:
                return False
            params = self.template.match(data)
            if params is None:
                return False
            ctx.params.update(params)
        if self.states is not None:
            if (await ctx.get_state()) not in self.states:
                return False
        for f in self.filters:
            if not await f(ctx):
                return False
        return True

    # ---------------------------------------------------------------- running
    async def run(self, ctx: "Context") -> Any:
        """Call the function (with throttling, the "typing…" status and dependency injection).

        Example::

            await handler.run(ctx)
        """
        from .di import call_handler

        if self.throttle_cache is not None and ctx.user_id is not None:
            key = ctx.user_id
            last = self.throttle_cache.get(key)
            if last is not None:
                if last == "warned":
                    return None
                self.throttle_cache.set(key, "warned", ttl=max(self.throttle - (time.monotonic() - last), 0.1))
                if ctx.is_callback:
                    await ctx.answer(ctx.t("nb.throttled"))
                else:
                    await ctx.reply(ctx.t("nb.throttled"))
                return None
            self.throttle_cache.set(key, time.monotonic())
        if self.typing and ctx.chat_id is not None:
            async with _keep_action(ctx, self.typing):
                return await call_handler(self.func, ctx)
        return await call_handler(self.func, ctx)


@contextlib.asynccontextmanager
async def _keep_action(ctx: "Context", action: str):  # type: ignore[no-untyped-def]
    async def loop() -> None:
        while True:
            await ctx.action(action)
            await asyncio.sleep(4.5)

    task = asyncio.create_task(loop())
    try:
        yield
    finally:
        task.cancel()


class HandlerOptions(TypedDict, total=False):
    """Options every handler decorator accepts.

    Example::

        @bot.command("ban", admin=True, chat="supergroup", throttle="5s")
        async def ban(ctx: Context): ...
    """

    #: Only admins from ``Nicebot(admins=[...])``.
    admin: bool
    #: Chat types: ``"private"``, ``"group"`` (groups + supergroups), ``"supergroup"``, ``"channel"`` or a list.
    chat: Any
    #: Rate limit per user: ``"3s"``; extra presses get "⏳ Please wait".
    throttle: Any
    #: Show "typing…" (``True``) or another action (``"upload_photo"``) while the handler runs.
    typing: Any
    #: Run only when the user is in this state (``ctx.set_state``) — a name or a list.
    state: Any
    #: Only these user ids.
    users: Iterable[int]
    #: Extra filters (``F.photo``, functions…).
    filters: Iterable[Any]


class Router:
    """Group handlers in modules and plug them into the bot with ``bot.include(router)``.

    Options passed to ``Router(...)`` (``admin=True``, ``chat="private"``…) apply to all its handlers.
    ``Nicebot`` is a Router too, so every decorator below also works on ``bot``.

    Example::

        # handlers/admin.py
        from nicebot import Context, Router

        router = Router(admin=True)

        @router.command("ping")
        async def ping(ctx: Context):
            await ctx.reply("pong")

        # bot.py
        bot.include(router)          # or bot.include("handlers") to load every module
    """

    def __init__(self, name: str | None = None, **defaults: Any):
        self.name = name or "router"
        self.defaults = defaults
        self.handlers: list[Handler] = []
        self.error_handlers: list[tuple[type[BaseException], Handler_T]] = []
        self.routers: list[Router] = []
        self.parent: Router | None = None

    # ---------------------------------------------------------------- core
    def add(self, event: str, func: Handler_T, **options: Any) -> Handler:
        """Register ``func`` for an update type without a decorator.

        Example::

            router.add("message", echo, content=["text"])
        """
        opts = {**self.defaults, **options}
        filters = list(opts.pop("filters", ()))
        h = Handler(event, func, filters=filters, **opts)
        h.router = self
        self.handlers.append(h)
        return h

    def _deco(self, event: str, **options: Any) -> Callable[[F], F]:
        def deco(func: F) -> F:
            h = self.add(event, func, **options)
            from .keyboards import func_id

            func_id(func)
            if h.template is not None:
                func._nb_template = h.template  # type: ignore[attr-defined]
            return func

        return deco

    def include(self, *routers: "Router | str") -> None:
        """Add routers: objects, or a package/folder name whose modules are imported and scanned for Routers.

        Example::

            bot.include(shop_router, admin_router)
            bot.include("handlers")
        """
        for r in routers:
            if isinstance(r, str):
                for found in discover(r):
                    self.include(found)
                continue
            if r is self or r in self.routers:
                continue
            r.parent = self
            self.routers.append(r)

    def all_handlers(self) -> list[Handler]:
        """Every handler of this router and its children, in order.

        Example::

            print([h.name for h in bot.all_handlers()])
        """
        out = list(self.handlers)
        for r in self.routers:
            out.extend(r.all_handlers())
        return out

    def all_error_handlers(self) -> list[tuple[type[BaseException], Handler_T]]:
        """Every ``@error`` handler of this router and its children.

        Example::

            print(len(bot.all_error_handlers()))
        """
        out = list(self.error_handlers)
        for r in self.routers:
            out.extend(r.all_error_handlers())
        return out

    # ---------------------------------------------------------------- messages
    def command(self, *names: str, description: Any = None, payload: Any = None, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Handle ``/command`` messages (several names allowed).

        ``description`` puts the command into Telegram's menu (a dict gives one text per language).

        Example::

            @bot.command("start", description={"uz": "Boshlash", "en": "Start"})
            async def start(ctx: Context):
                await ctx.reply("Hi!")

            @bot.command("help", "h")
            async def help(ctx: Context): ...
        """
        if not names:
            raise ValueError("Give the command a name: @bot.command('start')")
        return self._deco("message", commands=names, description=description, payload=payload, **opts)

    def deep_link(self, payload: Any, **opts: "Unpack[HandlerOptions]") -> Any:
        """Handle ``/start <payload>`` deep links; ``payload`` is a regex and named groups become parameters.

        Example::

            @bot.deep_link(r"promo_(?P<code>\\w+)")      # t.me/your_bot?start=promo_SUMMER
            async def promo(ctx: Context, code: str):
                await ctx.reply(f"Code {code} activated")
        """
        return self.command("start", payload=payload, **opts)

    def text(self, *exact: str, regex: Any = None, contains: Any = None, startswith: Any = None, ignore_case: bool = True,
             **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Handle text messages: exact texts, ``regex=``, ``contains=``, ``startswith=``; ``@bot.text()`` catches any non-command text.

        Regex named groups become handler parameters.

        Example::

            @bot.text("hi", "hello")
            async def hi(ctx: Context): ...

            @bot.text(regex=r"order (?P<num>\\d+)")
            async def order(ctx: Context, num: str): ...

            @bot.text()
            async def echo(ctx: Context):
                await ctx.reply(ctx.text)
        """
        filters = list(opts.pop("filters", ()))  # type: ignore[misc]
        if not (exact or regex or contains or startswith):
            filters.append(Filter(lambda c: c.text is not None and not (c.text.startswith("/") and c.command is not None), "plain_text"))
        contains = [contains] if isinstance(contains, str) else (contains or [])
        startswith = [startswith] if isinstance(startswith, str) else (startswith or [])
        return self._deco("message", exact=exact, regex=regex, contains=contains, startswith=startswith, ignore_case=ignore_case, filters=filters, **opts)

    def message(self, *filters: Any, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Handle any message that passes the filters.

        Example::

            @bot.message(F.photo & F.caption)
            async def photo_with_caption(ctx: Context): ...
        """
        return self._deco("message", filters=filters, **opts)

    def on(self, *content: str, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Handle messages by content type: ``"photo"``, ``"video"``, ``"document"``, ``"voice"``, ``"contact"``, ``"location"``… or ``"any"``.

        Example::

            @bot.on("photo", "document")
            async def files(ctx: Context):
                await ctx.media.save()
        """
        for c in content:
            if c != "any" and c not in CONTENT_TYPES:
                raise ValueError(f"Unknown content type {c!r}. Available: {', '.join(CONTENT_TYPES)}")
        return self._deco("message", content=content or ("any",), **opts)

    def edited(self, *filters: Any, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Handle edited messages.

        Example::

            @bot.edited()
            async def edited(ctx: Context):
                await ctx.reply("You edited your message")
        """
        return self._deco("edited_message", filters=filters, **opts)

    def channel(self, *filters: Any, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Handle posts in channels where the bot is an admin.

        Example::

            @bot.channel()
            async def post(ctx: Context):
                await ctx.react("🔥")
        """
        return self._deco("channel_post", filters=filters, **opts)

    def join(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Somebody joined a group (service message).

        Example::

            @bot.join()
            async def welcome(ctx: Context):
                await ctx.reply(f"Welcome, {ctx.mention}!")
        """
        return self._deco("message", content=("new_chat_members",), **opts)

    def leave(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Somebody left a group.

        Example::

            @bot.leave()
            async def bye(ctx: Context):
                await ctx.delete()
        """
        return self._deco("message", content=("left_chat_member",), **opts)

    def webapp_data(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Data sent from a Mini App with ``Telegram.WebApp.sendData`` (reply-keyboard Mini Apps). Read it with ``ctx.web_app_data``.

        Example::

            @bot.webapp_data()
            async def order(ctx: Context):
                data = ctx.web_app_data          # dict if JSON was sent
                await ctx.reply(f"Order for {data['total']} so'm received")
        """
        return self._deco("message", content=("web_app_data",), **opts)

    def paid(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """A successful payment (Telegram Stars or a payment provider).

        Example::

            @bot.paid()
            async def paid(ctx: Context):
                p = ctx.message.successful_payment
                await ctx.reply(f"Thanks for {p.total_amount} ⭐")
        """
        return self._deco("message", content=("successful_payment",), **opts)

    # ---------------------------------------------------------------- others
    def callback(self, template: str | None = None, *, regex: Any = None, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Handle inline button presses by ``callback_data``: exact text, a template (``"buy:{id:int}"``) or ``regex=``.

        ``@bot.callback()`` catches every button not handled elsewhere. (With ``Button(on_click=...)`` you rarely need this.)

        Example::

            @bot.callback("buy:{id:int}")
            async def buy(ctx: Context, id: int):
                await ctx.edit(f"Product {id} added")

            Button("Buy", on_click=buy, id=5)      # fills the template: "buy:5"
        """
        if template is not None and "{" not in template and regex is None:
            return self._deco("callback_query", exact=(template,), ignore_case=False, **opts)
        return self._deco("callback_query", template=template, regex=regex, **opts)

    def inline(self, regex: Any = None, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Handle inline queries (``@your_bot text`` typed in any chat). Answer with ``ctx.answer_inline``.

        Example::

            @bot.inline()
            async def search(ctx: Context):
                await ctx.answer_inline([("Hello", "Hello from the bot!")])
        """
        return self._deco("inline_query", regex=regex, **opts)

    def chosen_inline(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """The user picked one of your inline results (enable "inline feedback" in @BotFather).

        Example::

            @bot.chosen_inline()
            async def chosen(ctx: Context):
                print(ctx.event.result_id)
        """
        return self._deco("chosen_inline_result", **opts)

    def pre_checkout(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Check an order before payment (by default nicebot approves every one).

        Example::

            @bot.pre_checkout()
            async def check(ctx: Context):
                await ctx.bot.answer_pre_checkout_query(ctx.event.id, ok=in_stock(ctx.event.invoice_payload))
        """
        return self._deco("pre_checkout_query", **opts)

    def my_chat_member(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """The bot's own status changed in a chat (added to a group, blocked by a user…).

        Example::

            @bot.my_chat_member()
            async def status(ctx: Context):
                print(ctx.event.new_chat_member.status)
        """
        return self._deco("my_chat_member", **opts)

    def chat_member(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """A member's status changed in a group where the bot is an admin.

        Example::

            @bot.chat_member()
            async def changed(ctx: Context):
                print(ctx.event.old_chat_member.status, "→", ctx.event.new_chat_member.status)
        """
        return self._deco("chat_member", **opts)

    def join_request(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Somebody asked to join a chat with join requests enabled.

        Example::

            @bot.join_request()
            async def approve(ctx: Context):
                await ctx.bot.approve_chat_join_request(ctx.event.chat.id, ctx.user_id)
        """
        return self._deco("chat_join_request", **opts)

    def reaction(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Somebody put or removed a reaction (the bot must be an admin).

        Example::

            @bot.reaction()
            async def reacted(ctx: Context):
                print(ctx.event.new_reaction)
        """
        return self._deco("message_reaction", **opts)

    def poll_answer(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """A user voted in a non-anonymous poll sent by the bot.

        Example::

            @bot.poll_answer()
            async def vote(ctx: Context):
                print(ctx.user_id, ctx.event.option_ids)
        """
        return self._deco("poll_answer", **opts)

    def event(self, name: str, *filters: Any, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Any update type by its Bot API name.

        Example::

            @bot.event("chat_boost")
            async def boost(ctx: Context):
                await ctx.bot.notify_admins("🚀 New boost!")
        """
        return self._deco(name, filters=filters, **opts)

    def album(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Albums (media groups) arrive as ONE call; files are in ``ctx.album_media`` (and raw messages in ``ctx.album``).

        Example::

            @bot.album()
            async def album(ctx: Context):
                for m in ctx.album_media:
                    await m.save("albums/")
                await ctx.reply(f"Saved {len(ctx.album_media)} files")
        """
        return self._deco("album", **opts)

    def fallback(self, **opts: "Unpack[HandlerOptions]") -> Callable[[F], F]:
        """Runs when no other handler matched a message.

        Example::

            @bot.fallback()
            async def unknown(ctx: Context):
                await ctx.reply("I don't understand. Try /help")
        """
        return self._deco("fallback", **opts)

    def error(self, exc: type[BaseException] = Exception) -> Callable[[F], F]:
        """Handle exceptions raised by handlers (``async def h(ctx, error)``). Return ``False`` to fall through.

        Example::

            @bot.error(DoesNotExist)
            async def not_found(ctx: Context, error: DoesNotExist):
                await ctx.reply("Not found 🤷")
        """

        def deco(func: F) -> F:
            self.error_handlers.append((exc, func))
            return func

        return deco


def discover(target: str) -> list[Router]:
    """Import every module of a package (``"handlers"``) or folder and collect their Router objects.

    Example::

        routers = discover("handlers")    # [Router('shop'), Router('admin')]
    """
    import importlib
    import importlib.util
    import pkgutil
    import sys
    from pathlib import Path

    found: list[Router] = []
    path = Path(target)
    if path.is_dir() and (path / "__init__.py").exists():
        parent = str(path.resolve().parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        package = path.name
    elif path.is_dir():
        found_mods = []
        for py in sorted(path.glob("*.py")):
            if py.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(f"nb_handlers_{path.name}_{py.stem}", py)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod  # type: ignore[union-attr]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            found_mods.append(mod)
        return [v for m in found_mods for v in vars(m).values() if isinstance(v, Router)]
    else:
        package = target.replace("/", ".").replace("\\", ".").strip(".")
    pkg = importlib.import_module(package)
    modules = [pkg]
    if hasattr(pkg, "__path__"):
        for info in sorted(pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."), key=lambda i: i.name):
            modules.append(importlib.import_module(info.name))
    from .bot import Nicebot

    for m in modules:
        for v in vars(m).values():
            if isinstance(v, Router) and not isinstance(v, Nicebot) and v not in found:
                found.append(v)
    return found
