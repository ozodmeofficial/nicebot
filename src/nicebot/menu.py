"""Declarative multi-level inline menus with an automatic "⬅️ Back" button.

Example::

    SHOP = Menu("🛍 Choose a category", {
        "👕 Clothes": Menu("Clothes", {"Shirt": "120 000 so'm", "Trousers": show_trousers}),
        "📞 Contact": "+998 90 123 45 67",
        "🌐 Website": "https://example.com",
    })

    @bot.command("shop")
    async def shop(ctx: Context):
        await ctx.menu(SHOP)
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
    """A multi-level inline menu written as a dict. Navigation and "⬅️ Back" work by themselves; the message is edited in place.

    Values: text (shown), ``Menu``/``dict`` (a submenu), a function (called with ``ctx``), a URL (link button) or a ``Button``.

    Example::

        async def my_orders(ctx: Context):
            await ctx.respond("📦 You have no orders yet")

        MAIN = Menu("🏠 Main menu", {
            "🛍 Shop": Menu("Choose a category", {
                "👕 Clothes": "Coming soon",
                "📚 Books": show_books,
            }),
            "📦 My orders": my_orders,
            "🌐 Website": "https://example.com",
        })

        @bot.command("menu")
        async def menu(ctx: Context):
            await ctx.menu(MAIN)
    """
    def __init__(self, text: Any, items: dict[str, Any] | None = None, *, columns: Any = "auto", back: bool = True, id: str | None = None):
        self.text = text
        self.items: dict[str, Any] = dict(items or {})
        self.columns = columns
        self.back = back
        self.id = id or format(zlib.crc32(repr((str(text), list(self.items))).encode()) & 0xFFFFFFFF, "x")
        _MENUS[self.id] = self

    def add(self, label: str, value: Any) -> "Menu":
        """Add an item and return the menu (chainable).

        Example::

            MAIN.add("📞 Contact", "+998 90 123 45 67").add("ℹ️ About", about)
        """
        self.items[label] = value
        return self

    def __setitem__(self, label: str, value: Any) -> None:
        self.items[label] = value

    def item(self, label: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator: add a function as a menu item.

        Example::

            @MAIN.item("📦 My orders")
            async def orders(ctx: Context):
                await ctx.respond("No orders yet")
        """

        def deco(func: Callable[..., Any]) -> Callable[..., Any]:
            self.items[label] = func
            return func

        return deco

    # ------------------------------------------------------------ navigation
    def node(self, path: list[int]) -> tuple[Any, list[Menu]]:
        """Walk ``path`` (item indexes) and return ``(node, trail_of_menus)``.

        Example::

            node, trail = MAIN.node([0, 1])
        """
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
        """Build the text and keyboard for ``path``.

        Example::

            text, markup = await MAIN.render(ctx, [])
        """
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
        """Send (or edit, with ``edit=True``) the menu at ``path``. Usually you call ``ctx.menu(menu)``.

        Example::

            await MAIN.show(ctx)
        """
        text, markup = await self.render(ctx, path or [])
        if edit and ctx.is_callback:
            return await ctx.edit(text, buttons=markup)
        return await ctx.reply(text, buttons=markup)


async def handle_menu(ctx: "Context", data: str) -> None:
    """Handle a press on a menu button (internal ``~m…`` callback data).

    Example::

        await handle_menu(ctx, ctx.data)
    """
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
    """``True`` for ``async def`` functions.

    Example::

        is_coroutine(my_orders)   # True
    """
    return inspect.iscoroutinefunction(func)
