"""Declarative multi-level inline menus with automatic "⬅️ Back".

    shop = Menu("🛍 Bo'limni tanlang", {
        "👕 Kiyim": Menu("Kiyimlar", {"Ko'ylak": "Narxi: 120 000 so'm", "Shim": show_pants}),
        "📞 Aloqa": "+998 90 123 45 67",
        "🌐 Sayt": "https://tezbaraka.uz",
    })

    @bot.command("shop")
    async def _(ctx): await ctx.menu(shop)
"""
from __future__ import annotations

import inspect
import zlib
from typing import TYPE_CHECKING, Any, Callable

from .keyboards import Button, _normalize, build_inline
from .utils import Html

if TYPE_CHECKING:
    from .context import Context

_MENUS: dict[str, "Menu"] = {}


class Menu:
    def __init__(self, text: Any, items: dict[str, Any] | None = None, *, columns: Any = "auto", back: bool = True, id: str | None = None):
        self.text = text
        self.items: dict[str, Any] = dict(items or {})
        self.columns = columns
        self.back = back
        self.id = id or format(zlib.crc32(repr((str(text), list(self.items))).encode()) & 0xFFFFFFFF, "x")
        _MENUS[self.id] = self

    def add(self, label: str, value: Any) -> "Menu":
        self.items[label] = value
        return self

    def __setitem__(self, label: str, value: Any) -> None:
        self.items[label] = value

    def item(self, label: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator: ``@menu.item("📦 Buyurtmalarim")``"""

        def deco(func: Callable[..., Any]) -> Callable[..., Any]:
            self.items[label] = func
            return func

        return deco

    # ------------------------------------------------------------ navigation
    def node(self, path: list[int]) -> tuple[Any, list[Menu]]:
        cur: Any = self
        trail: list[Menu] = [self]
        for idx in path:
            if not isinstance(cur, Menu):
                break
            cur = list(cur.items.values())[idx]
            if isinstance(cur, dict):
                cur = Menu(list(trail[-1].items.keys())[idx], cur, id=f"{trail[-1].id}.{idx}")
            if isinstance(cur, Menu):
                trail.append(cur)
        return cur, trail

    async def render(self, ctx: "Context", path: list[int]) -> tuple[Any, Any]:
        node, trail = self.node(path)
        menu = node if isinstance(node, Menu) else trail[-1]
        here = path if isinstance(node, Menu) else path[:-1]
        buttons: list[Any] = []
        for i, (label, value) in enumerate(menu.items.items()):
            if isinstance(value, Button):
                buttons.append(value)
            elif isinstance(value, str) and value.startswith(("http://", "https://", "tg://")):
                buttons.append(Button(label, url=value))
            else:
                buttons.append(Button(label, data=f"~m{self.id}:{'.'.join(map(str, here + [i]))}"))
        rows = _normalize(buttons, menu.columns)
        if here and menu.back:
            rows.append([Button(ctx.t("nb.back"), data=f"~m{self.id}:{'.'.join(map(str, here[:-1]))}")])
        return menu.text, await build_inline(ctx.bot, rows)

    async def show(self, ctx: "Context", path: list[int] | None = None, edit: bool = False) -> Any:
        text, markup = await self.render(ctx, path or [])
        if edit and ctx.is_callback:
            return await ctx.edit(text, buttons=markup)
        return await ctx.reply(text, buttons=markup)


async def handle_menu(ctx: "Context", data: str) -> None:
    mid, _, raw = data[2:].partition(":")
    menu = _MENUS.get(mid)
    if menu is None:
        await ctx.answer(ctx.t("nb.expired"), alert=True)
        return
    path = [int(x) for x in raw.split(".") if x != ""]
    node, trail = menu.node(path)
    if isinstance(node, Menu):
        await ctx.answer()
        await menu.show(ctx, path, edit=True)
        return
    if callable(node):
        from .di import call_handler

        await call_handler(node, ctx)
        if not ctx._answered:
            await ctx.answer()
        return
    await ctx.answer()
    back = [[Button(ctx.t("nb.back"), data=f"~m{menu.id}:{'.'.join(map(str, path[:-1]))}")]]
    text = node if isinstance(node, (str, Html)) else str(node)
    await ctx.edit(text, buttons=back)


def is_coroutine(func: Any) -> bool:
    return inspect.iscoroutinefunction(func)
