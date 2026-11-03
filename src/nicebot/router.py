"""Handlers and routers. A ``Router`` groups handlers; ``Nicebot`` is a Router too."""
from __future__ import annotations

import asyncio
import contextlib
import re
import time
from typing import TYPE_CHECKING, Any, Callable, Iterable

from .filters import Filter, as_filter
from .keyboards import CallbackTemplate
from .utils import TTLCache, parse_duration

if TYPE_CHECKING:
    from .context import Context

Handler_T = Callable[..., Any]

CONTENT_TYPES = (
    "text", "photo", "video", "document", "audio", "voice", "video_note", "sticker", "animation", "contact", "location",
    "venue", "poll", "dice", "game", "invoice", "successful_payment", "web_app_data", "new_chat_members", "left_chat_member",
    "pinned_message", "story", "giveaway", "users_shared", "chat_shared", "paid_media", "checklist",
)

_CHAT_ALIASES = {"private": ("private",), "group": ("group", "supergroup"), "supergroup": ("supergroup",), "channel": ("channel",)}


class Handler:
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


class Router:
    """Group handlers in modules and plug them into the bot with ``bot.include(router)``.

    ``Router(admin=True)`` / ``Router(chat="private")`` apply those options to all its handlers.
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
        opts = {**self.defaults, **options}
        filters = list(opts.pop("filters", ()))
        h = Handler(event, func, filters=filters, **opts)
        h.router = self
        self.handlers.append(h)
        return h

    def _deco(self, event: str, **options: Any) -> Callable[[Handler_T], Handler_T]:
        def deco(func: Handler_T) -> Handler_T:
            h = self.add(event, func, **options)
            from .keyboards import func_id

            func_id(func)
            if h.template is not None:
                func._nb_template = h.template  # type: ignore[attr-defined]
            return func

        return deco

    def include(self, *routers: "Router | str") -> None:
        """``bot.include(shop_router)`` or ``bot.include("handlers")`` (imports every module in the package/folder)."""
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
        out = list(self.handlers)
        for r in self.routers:
            out.extend(r.all_handlers())
        return out

    def all_error_handlers(self) -> list[tuple[type[BaseException], Handler_T]]:
        out = list(self.error_handlers)
        for r in self.routers:
            out.extend(r.all_error_handlers())
        return out

    # ---------------------------------------------------------------- messages
    def command(self, *names: str, description: Any = None, payload: Any = None, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """``@bot.command("start")`` — also ``description=`` (shown in Telegram's menu; dict for languages)."""
        if not names:
            raise ValueError("Buyruq nomini bering: @bot.command('start')")
        return self._deco("message", commands=names, description=description, payload=payload, **opts)

    def deep_link(self, payload: Any, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """``/start`` with a payload matching ``payload`` (regex): ``@bot.deep_link(r"promo_(?P<code>\\w+)")``."""
        return self.command("start", payload=payload, **opts)

    def text(self, *exact: str, regex: Any = None, contains: Any = None, startswith: Any = None, ignore_case: bool = True, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """``@bot.text("salom")`` exact · ``regex=`` · ``contains=`` · ``startswith=`` · ``@bot.text()`` any non-command text."""
        filters = list(opts.pop("filters", ()))
        if not (exact or regex or contains or startswith):
            filters.append(Filter(lambda c: c.text is not None and not (c.text.startswith("/") and c.command is not None), "plain_text"))
        contains = [contains] if isinstance(contains, str) else (contains or [])
        startswith = [startswith] if isinstance(startswith, str) else (startswith or [])
        return self._deco("message", exact=exact, regex=regex, contains=contains, startswith=startswith, ignore_case=ignore_case, filters=filters, **opts)

    def message(self, *filters: Any, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("message", filters=filters, **opts)

    def on(self, *content: str, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """``@bot.on("photo")``, ``@bot.on("document", "video")``, ``@bot.on("contact")``, ``@bot.on("any")``."""
        for c in content:
            if c != "any" and c not in CONTENT_TYPES:
                raise ValueError(f"Noma'lum kontent turi: {c}. Mavjud: {', '.join(CONTENT_TYPES)}")
        return self._deco("message", content=content or ("any",), **opts)

    def edited(self, *filters: Any, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("edited_message", filters=filters, **opts)

    def channel(self, *filters: Any, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("channel_post", filters=filters, **opts)

    def join(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """Someone joined a group (service message)."""
        return self._deco("message", content=("new_chat_members",), **opts)

    def leave(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("message", content=("left_chat_member",), **opts)

    def webapp_data(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """Data sent from a Mini App with ``Telegram.WebApp.sendData``."""
        return self._deco("message", content=("web_app_data",), **opts)

    def paid(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """Successful payment (Telegram Stars or providers)."""
        return self._deco("message", content=("successful_payment",), **opts)

    # ---------------------------------------------------------------- others
    def callback(self, template: str | None = None, *, regex: Any = None, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """``@bot.callback("buy:{id:int}")`` → ``async def buy(ctx, id: int)``. ``@bot.callback()`` catches all."""
        if template is not None and "{" not in template and regex is None:
            return self._deco("callback_query", exact=(template,), ignore_case=False, **opts)
        return self._deco("callback_query", template=template, regex=regex, **opts)

    def inline(self, regex: Any = None, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("inline_query", regex=regex, **opts)

    def chosen_inline(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("chosen_inline_result", **opts)

    def pre_checkout(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("pre_checkout_query", **opts)

    def my_chat_member(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("my_chat_member", **opts)

    def chat_member(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("chat_member", **opts)

    def join_request(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("chat_join_request", **opts)

    def reaction(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("message_reaction", **opts)

    def poll_answer(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        return self._deco("poll_answer", **opts)

    def event(self, name: str, *filters: Any, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """Any update type by its Bot API name: ``@bot.event("chat_boost")``."""
        return self._deco(name, filters=filters, **opts)

    def album(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """Media groups arrive as ONE call: ``async def h(ctx, album: list[Message])``."""
        return self._deco("album", **opts)

    def fallback(self, **opts: Any) -> Callable[[Handler_T], Handler_T]:
        """Runs when nothing else matched a message."""
        return self._deco("fallback", **opts)

    def error(self, exc: type[BaseException] = Exception) -> Callable[[Handler_T], Handler_T]:
        """``@bot.error(ValueError) async def h(ctx, error): ...``"""

        def deco(func: Handler_T) -> Handler_T:
            self.error_handlers.append((exc, func))
            return func

        return deco


def discover(target: str) -> list[Router]:
    """Import every module of a package (``"handlers"``) or folder and collect their Router objects."""
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
