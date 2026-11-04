"""Buttons and keyboards — inline and reply — with the least possible code.

Example::

    from nicebot import Button

    @bot.command("shop")
    async def shop(ctx: Context):
        await ctx.reply("Book — 50 000 so'm", buttons=[
            [Button("🛒 Buy", on_click=buy, product="book")],
            [Button("🌐 Website", url="https://example.com"), Button("📱 App", webapp="/")],
        ])
"""
from __future__ import annotations

import json
import re
import time
import zlib
from typing import TYPE_CHECKING, Any, Callable, Iterable, Sequence

from . import types as T
from .utils import parse_duration, short_id

if TYPE_CHECKING:
    from .bot import Nicebot

CB_MAX = 64

# ------------------------------------------------------------------ handler registry for on_click
_FUNCS: dict[str, Callable[..., Any]] = {}


_SCANNED = False


def _key(func: Callable[..., Any]) -> str:
    qual = getattr(func, "__qualname__", repr(func))
    if "<lambda>" in qual or "<locals>" in qual:
        code = getattr(func, "__code__", None)
        qual += f"@{code.co_firstlineno if code else 0}"
    return f"{getattr(func, '__module__', '')}.{qual}"


def func_id(func: Callable[..., Any]) -> str:
    """Stable short id of a function (survives restarts) used inside callback_data.

    Example::

        func_id(buy)   # "1a2b3c4d"
    """
    fid = format(zlib.crc32(_key(func).encode()) & 0xFFFFFFFF, "x")
    _FUNCS[fid] = func
    return fid


def func_by_id(fid: str) -> Callable[..., Any] | None:
    """Find the function for a button pressed before a restart by scanning loaded user modules once.

    Example::

        func_by_id(func_id(buy)) is buy   # True
    """
    global _SCANNED
    func = _FUNCS.get(fid)
    if func is not None or _SCANNED:
        return func
    import inspect
    import sys
    import sysconfig

    _SCANNED = True
    _PKG_DIR = str(__import__("pathlib").Path(__file__).resolve().parent)
    skip = tuple(p for p in {sysconfig.get_paths().get("stdlib"), sysconfig.get_paths().get("purelib"), sysconfig.get_paths().get("platlib")} if p)
    for mod in list(sys.modules.values()):
        path = getattr(mod, "__file__", None) or ""
        if not path or path.startswith(skip) or path.startswith(_PKG_DIR):
            continue
        for value in list(vars(mod).values()):
            if inspect.isfunction(value) or inspect.iscoroutinefunction(value):
                func_id(value)
    return _FUNCS.get(fid)


# ------------------------------------------------------------------ callback templates
_CONVERTERS = {
    "str": (r"[^:]+", str),
    "int": (r"-?\d+", int),
    "float": (r"-?\d+(?:\.\d+)?", float),
    "bool": (r"[01]|true|false", lambda v: v in ("1", "true")),
    "any": (r".*", str),
}
_PARAM_RE = re.compile(r"\{(\w+)(?::(\w+))?\}")


class CallbackTemplate:
    """``"product:{id:int}:{size}"`` → regex matcher + builder. Types: ``str``, ``int``, ``float``, ``bool``, ``any``.

    Example::

        tpl = CallbackTemplate("product:{id:int}")
        tpl.build(id=5)          # "product:5"
        tpl.match("product:5")   # {"id": 5}
    """

    def __init__(self, template: str):
        self.template = template
        self.params: dict[str, Callable[[str], Any]] = {}
        pattern, pos = "", 0
        for m in _PARAM_RE.finditer(template):
            pattern += re.escape(template[pos:m.start()])
            name, kind = m.group(1), m.group(2) or "str"
            if kind not in _CONVERTERS:
                raise ValueError(f"Unknown type {kind!r} in callback template (use: {', '.join(_CONVERTERS)})")
            rx, conv = _CONVERTERS[kind]
            pattern += f"(?P<{name}>{rx})"
            self.params[name] = conv
            pos = m.end()
        pattern += re.escape(template[pos:])
        self.regex = re.compile(f"^{pattern}$")

    def match(self, data: str) -> dict[str, Any] | None:
        """Parse ``data``; returns the converted values or ``None`` if it does not match.

        Example::

            CallbackTemplate("buy:{id:int}").match("buy:7")   # {"id": 7}
        """
        m = self.regex.match(data)
        if not m:
            return None
        return {k: self.params[k](v) for k, v in m.groupdict().items()}

    def build(self, **values: Any) -> str:
        """Fill the template.

        Example::

            CallbackTemplate("buy:{id:int}").build(id=7)   # "buy:7"
        """
        missing = set(self.params) - set(values)
        if missing:
            raise ValueError(f"{self.template}: missing values {missing}")
        out = _PARAM_RE.sub(lambda m: _fmt(values[m.group(1)]), self.template)
        return out

    def __repr__(self) -> str:
        return f"CallbackTemplate({self.template!r})"


def _fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


# ------------------------------------------------------------------ buttons
class Button:
    """One inline button. Give it exactly one action:

    * ``on_click=func``      — calls ``func(ctx, **params)`` when pressed (extra keyword arguments become params)
    * ``url="https://…"``    — opens a link
    * ``webapp="/path"``     — opens your Mini App (a path uses ``bot.public_url``; full HTTPS URLs work too)
    * ``copy="TEXT"``        — copies text to the clipboard
    * ``share="text"``       — lets the user share an inline query in any chat
    * ``share_here="text"``  — inline query in the current chat
    * ``login="https://…"``  — Telegram Login URL
    * ``pay=True``           — the pay button of an invoice
    * ``data="raw"``         — raw ``callback_data`` for ``@bot.callback("raw")``

    Safety options: ``ttl="10m"`` (expires), ``once=True`` (works one time), ``only=user_id`` (only that user may press).
    ``style`` and ``icon`` (custom emoji id) change the look.

    Example::

        async def buy(ctx: Context, product: str):
            await ctx.edit(f"✅ You bought {product}")

        Button("🛒 Buy", on_click=buy, product="book")
        Button("🌐 Website", url="https://example.com")
        Button("📱 Open app", webapp="/shop")
        Button("📋 Promo code", copy="NICE2026")
        Button("🎁 Bonus", on_click=bonus, once=True, ttl="1h")
    """

    __slots__ = ("text", "on_click", "data", "url", "webapp", "copy", "share", "share_here", "login", "pay", "ttl", "once", "only", "params", "style", "icon")

    def __init__(
        self,
        text: str,
        on_click: Callable[..., Any] | None = None,
        *,
        data: str | None = None,
        url: str | None = None,
        webapp: str | None = None,
        copy: str | None = None,
        share: str | None = None,
        share_here: str | None = None,
        login: str | None = None,
        pay: bool = False,
        ttl: str | float | None = None,
        once: bool = False,
        only: int | Iterable[int] | None = None,
        style: str | None = None,
        icon: str | None = None,
        **params: Any,
    ):
        self.text = text
        self.on_click = on_click
        self.data = data
        self.url = url
        self.webapp = webapp
        self.copy = copy
        self.share = share
        self.share_here = share_here
        self.login = login
        self.pay = pay
        self.ttl = parse_duration(ttl)
        self.once = once
        self.only = None if only is None else ([only] if isinstance(only, int) else list(only))
        self.style = style
        self.icon = icon
        self.params = params

    @property
    def needs_store(self) -> bool:
        """``True`` when the button's data must be kept in storage (``ttl``/``once``/``only``).

        Example::

            Button("Bonus", data="b", once=True).needs_store   # True
        """
        return bool(self.ttl or self.once or self.only)

    async def build(self, bot: "Nicebot") -> T.InlineKeyboardButton:
        """Turn the button into Telegram's ``InlineKeyboardButton``.

        Example::

            raw = await Button("Hi", data="hi").build(bot)
        """
        kw: dict[str, Any] = {"text": self.text}
        if self.style:
            kw["style"] = self.style
        if self.icon:
            kw["icon_custom_emoji_id"] = self.icon
        if self.url:
            return T.InlineKeyboardButton(url=self.url, **kw)
        if self.webapp:
            return T.InlineKeyboardButton(web_app=T.WebAppInfo(url=bot.webapp_url(self.webapp)), **kw)
        if self.copy is not None:
            return T.InlineKeyboardButton(copy_text=T.CopyTextButton(text=self.copy), **kw)
        if self.share is not None:
            return T.InlineKeyboardButton(switch_inline_query=self.share, **kw)
        if self.share_here is not None:
            return T.InlineKeyboardButton(switch_inline_query_current_chat=self.share_here, **kw)
        if self.login:
            return T.InlineKeyboardButton(login_url=T.LoginUrl(url=self.login), **kw)
        if self.pay:
            return T.InlineKeyboardButton(pay=True, **kw)
        return T.InlineKeyboardButton(callback_data=await self.callback_data(bot), **kw)

    def raw_data(self) -> str:
        """The callback data before shortening/storage.

        Example::

            Button("Yes", data="yes").raw_data()   # "yes"
        """
        if self.on_click is not None:
            tpl: CallbackTemplate | None = getattr(self.on_click, "_nb_template", None)
            if tpl is not None:
                return tpl.build(**self.params)
            fid = func_id(self.on_click)
            if self.params:
                return f"~f{fid}|{json.dumps(self.params, separators=(',', ':'), ensure_ascii=False)}"
            return f"~f{fid}"
        if self.data is not None:
            return self.data
        return self.text

    async def callback_data(self, bot: "Nicebot") -> str:
        """The final ``callback_data`` (long or protected data is stored and replaced with a short key).

        Example::

            data = await Button("Buy", on_click=buy, id=5).callback_data(bot)
        """
        data = self.raw_data()
        if self.needs_store or len(data.encode()) > CB_MAX:
            key = short_id(10)
            record = {"d": data}
            if self.ttl:
                record["exp"] = time.time() + self.ttl
            if self.once:
                record["once"] = 1
            if self.only:
                record["only"] = self.only
            await bot.storage.set(f"cb:{key}", record, ttl=self.ttl or 30 * 86400)
            return f"~k{key}"
        return data

    def __repr__(self) -> str:
        return f"Button({self.text!r})"


class Toggle(Button):
    """An on/off switch that redraws itself (✅/⬜️) and saves the value for each user.

    Example::

        await ctx.reply("⚙️ Settings", buttons=[
            [Toggle("🔔 Notifications", key="notify", default=True)],
            [Toggle("🌙 Night mode", key="night", on_change=night_changed)],
        ])

        async def night_changed(ctx: Context, value: bool):
            await ctx.answer("Night mode on" if value else "Night mode off")

        if await ctx.setting("notify"):      # read the value anywhere
            ...
    """

    __slots__ = ("key", "default", "on_change")

    def __init__(self, text: str, key: str, *, default: bool = False, on_change: Callable[..., Any] | None = None):
        super().__init__(text)
        self.key, self.default, self.on_change = key, default, on_change
        if on_change:
            func_id(on_change)

    async def build(self, bot: "Nicebot", user_id: int | None = None) -> T.InlineKeyboardButton:  # type: ignore[override]
        """Build the button showing the user's current value.

        Example::

            raw = await Toggle("Notify", key="notify").build(bot, user_id=42)
        """
        value = self.default
        if user_id is not None:
            value = await bot.get_setting(user_id, self.key, self.default)
        mark = "✅" if value else "⬜️"
        fid = func_id(self.on_change) if self.on_change else ""
        return T.InlineKeyboardButton(text=f"{mark} {self.text}", callback_data=f"~t{self.key}|{fid}|{int(self.default)}")


class ReplyButton:
    """A button of the reply keyboard (under the message field).

    Plain strings work too, with shortcuts: ``"📞 Send phone:contact"``, ``"📍 Send location:location"``.
    ``webapp=`` opens a Mini App that can send data back with ``Telegram.WebApp.sendData`` (``@bot.webapp_data``).

    Example::

        await ctx.reply("Share your contact", keyboard=[ReplyButton("📞 Send phone", contact=True)])
        await ctx.reply("Order", keyboard=[ReplyButton("🛍 Open shop", webapp="/order")])
        await ctx.reply("Poll", keyboard=[ReplyButton("📊 Create a poll", poll="quiz")])
    """

    __slots__ = ("text", "contact", "location", "webapp", "poll")

    def __init__(self, text: str, *, contact: bool = False, location: bool = False, webapp: str | None = None, poll: str | None = None):
        self.text, self.contact, self.location, self.webapp, self.poll = text, contact, location, webapp, poll

    def build(self, bot: "Nicebot | None" = None) -> T.KeyboardButton:
        """Turn it into Telegram's ``KeyboardButton`` (``bot`` resolves relative Mini App paths).

        Example::

            raw = ReplyButton("📍", location=True).build()
        """
        kw: dict[str, Any] = {"text": self.text}
        if self.contact:
            kw["request_contact"] = True
        if self.location:
            kw["request_location"] = True
        if self.webapp:
            kw["web_app"] = T.WebAppInfo(url=bot.webapp_url(self.webapp) if bot is not None else self.webapp)
        if self.poll is not None:
            kw["request_poll"] = T.KeyboardButtonPollType(type=self.poll or None)
        return T.KeyboardButton(**kw)


# ------------------------------------------------------------------ layout
def auto_columns(texts: Sequence[str], max_cols: int = 4, width: int = 28) -> list[int]:
    """Greedy row sizes so that short labels share a row and long ones stand alone.

    Example::

        auto_columns(["S", "M", "L", "XL"])   # [4]
        auto_columns(["A very long label for a button", "B"])   # [1, 1]
    """
    rows: list[int] = []
    cur, cur_w = 0, 0
    for t in texts:
        w = max(len(t), 4) + 2
        if cur and (cur >= max_cols or cur_w + w > width):
            rows.append(cur)
            cur, cur_w = 0, 0
        cur += 1
        cur_w += w
    if cur:
        rows.append(cur)
    return rows


def _normalize(buttons: Any, columns: int | str | None) -> list[list[Any]]:
    if buttons is None:
        return []
    if isinstance(buttons, dict):
        items: list[Any] = []
        for text, action in buttons.items():
            if isinstance(action, Button):
                items.append(action)
            elif callable(action):
                items.append(Button(text, on_click=action))
            elif isinstance(action, str) and action.startswith(("http://", "https://", "tg://")):
                items.append(Button(text, url=action))
            else:
                items.append(Button(text, data=str(action)))
        buttons = items
    if isinstance(buttons, (Button, str)):
        buttons = [buttons]
    buttons = list(buttons)
    if buttons and all(isinstance(r, (list, tuple)) for r in buttons):
        return [list(r) for r in buttons]
    flat = [b for b in buttons]
    if columns in (None, "auto"):
        sizes = auto_columns([b.text if hasattr(b, "text") else str(b) for b in flat])
    else:
        n = max(int(columns), 1)
        sizes = [n] * ((len(flat) + n - 1) // n)
    rows, i = [], 0
    for s in sizes:
        rows.append(flat[i:i + s])
        i += s
    return [r for r in rows if r]


async def build_inline(bot: "Nicebot", buttons: Any, columns: int | str | None = None, user_id: int | None = None) -> T.InlineKeyboardMarkup | None:
    """Build an ``InlineKeyboardMarkup`` from lists, rows, dicts or ``Button`` objects.

    Example::

        markup = await build_inline(bot, ["Yes", "No"])
        await bot.send_message(chat_id, "Sure?", reply_markup=markup)
    """
    if buttons is None:
        return None
    if isinstance(buttons, T.InlineKeyboardMarkup):
        return buttons
    rows = _normalize(buttons, columns)
    out: list[list[T.InlineKeyboardButton]] = []
    for row in rows:
        built = []
        for b in row:
            if isinstance(b, T.InlineKeyboardButton):
                built.append(b)
            elif isinstance(b, Toggle):
                built.append(await b.build(bot, user_id))
            elif isinstance(b, Button):
                built.append(await b.build(bot))
            else:
                built.append(await Button(str(b)).build(bot))
        out.append(built)
    return T.InlineKeyboardMarkup(inline_keyboard=out)


def _reply_button(b: Any, bot: "Nicebot | None" = None) -> T.KeyboardButton:
    if isinstance(b, T.KeyboardButton):
        return b
    if isinstance(b, ReplyButton):
        return b.build(bot)
    s = str(b)
    for suffix, kw in ((":contact", {"contact": True}), (":location", {"location": True})):
        if s.endswith(suffix):
            return ReplyButton(s[: -len(suffix)], **kw).build(bot)
    return T.KeyboardButton(text=s)


def build_reply(buttons: Any, columns: int | str | None = None, *, resize: bool = True, one_time: bool = False, placeholder: str | None = None,
                persistent: bool | None = None, bot: "Nicebot | None" = None) -> T.ReplyKeyboardMarkup:
    """Build a ``ReplyKeyboardMarkup`` (the keyboard under the message field).

    Example::

        markup = build_reply(["🛍 Shop", "📞 Contact", "📍 Location:location"], columns=2)
    """
    rows = _normalize(buttons, columns)
    return T.ReplyKeyboardMarkup(
        keyboard=[[_reply_button(b, bot) for b in row] for row in rows],
        resize_keyboard=resize,
        one_time_keyboard=one_time or None,
        input_field_placeholder=placeholder,
        is_persistent=persistent,
    )


def remove_keyboard() -> T.ReplyKeyboardRemove:
    """Markup that hides the reply keyboard.

    Example::

        await bot.send_message(chat_id, "Done", reply_markup=remove_keyboard())
    """
    return T.ReplyKeyboardRemove(remove_keyboard=True)


def iter_buttons(markup: Any) -> Iterable[T.InlineKeyboardButton]:
    """Iterate over every button of an inline keyboard.

    Example::

        texts = [b.text for b in iter_buttons(msg.reply_markup)]
    """
    if markup is None:
        return
    for row in getattr(markup, "inline_keyboard", None) or []:
        yield from row
