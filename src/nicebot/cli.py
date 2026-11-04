"""``nicebot`` command line: create a project, run a bot, show versions.

Example::

    $ nicebot new mybot       # bot.py, handlers/, locales/, .env
    $ nicebot run --reload
    $ nicebot version
"""
from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path

BOT_PY = '''from nicebot import Button, Context, Nicebot

bot = Nicebot.from_env()          # BOT_TOKEN, DATABASE_URL, ADMINS from .env
bot.include("handlers")           # every Router in the handlers/ folder


@bot.command("start", description="Start the bot")
async def start(ctx: Context):
    await ctx.reply(
        ctx.t("hello", name=ctx.name),
        buttons=[Button("ℹ️ Help", on_click=help_button)],
    )


async def help_button(ctx: Context):
    await ctx.respond(ctx.t("help"))


if __name__ == "__main__":
    bot.start(reload=True)        # restarts by itself when you change the code
'''

HANDLER_PY = '''from nicebot import Context, Router

router = Router()


@router.command("ping", description="Is the bot alive?")
async def ping(ctx: Context):
    await ctx.reply(f"🏓 pong ({ctx.elapsed * 1000:.0f} ms)")


@router.text("salom", "hello", "привет")
async def hello(ctx: Context):
    await ctx.reply(ctx.t("hello", name=ctx.name))
'''

ENV = """BOT_TOKEN=123456:ABC-your-token-from-BotFather
DATABASE_URL=sqlite:///bot.db
ADMINS=123456789
# REDIS_URL=redis://localhost:6379/0
# SUPPORT_CHAT=-1001234567890
# REQUIRED_CHANNELS=@your_channel
TZ=Asia/Tashkent
"""

LOCALES = {
    "uz": '{\n  "hello": "Assalomu alaykum, {name}! 👋",\n  "help": "Men nicebot bilan yasalganman. /ping — tekshirish"\n}\n',
    "ru": '{\n  "hello": "Здравствуйте, {name}! 👋",\n  "help": "Я сделан на nicebot. /ping — проверка"\n}\n',
    "en": '{\n  "hello": "Hello, {name}! 👋",\n  "help": "I am built with nicebot. /ping — check"\n}\n',
}

GITIGNORE = ".env\n*.db\n*.db-*\n__pycache__/\n.venv/\n"


def cmd_new(args: argparse.Namespace) -> int:
    """``nicebot new <name>`` — create a ready project (bot.py, handlers/, locales/, .env).

    Example::

        $ nicebot new mybot && cd mybot && python bot.py
    """
    root = Path(args.name)
    if root.exists() and any(root.iterdir()):
        print(f"❌ The folder '{root}' is not empty")
        return 1
    (root / "handlers").mkdir(parents=True, exist_ok=True)
    (root / "locales").mkdir(exist_ok=True)
    (root / "bot.py").write_text(BOT_PY, encoding="utf-8")
    (root / "handlers" / "__init__.py").write_text("", encoding="utf-8")
    (root / "handlers" / "basic.py").write_text(HANDLER_PY, encoding="utf-8")
    (root / ".env.example").write_text(ENV, encoding="utf-8")
    (root / ".env").write_text(ENV, encoding="utf-8")
    (root / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    for lang, text in LOCALES.items():
        (root / "locales" / f"{lang}.json").write_text(text, encoding="utf-8")
    print(f"✅ Project created: {root}/\n")
    print(f"   cd {root}")
    print("   # put your token from @BotFather into .env (BOT_TOKEN=...)")
    print("   python bot.py\n")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """``nicebot run [file] [--reload]`` — run a bot file.

    Example::

        $ nicebot run bot.py --reload
    """
    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}")
        return 1
    if args.reload:
        from .reload import supervise

        sys.argv = [str(path)]
        if supervise():
            return 0
    sys.path.insert(0, str(path.resolve().parent))
    runpy.run_path(str(path), run_name="__main__")
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    """``nicebot version`` — print nicebot, Bot API and Python versions.

    Example::

        $ nicebot version
        nicebot 1.0.0 · Telegram Bot API 10.3 · Python 3.12.4
    """
    from . import __version__
    from .types import API_VERSION

    print(f"nicebot {__version__} · Telegram {API_VERSION} · Python {sys.version.split()[0]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point of the ``nicebot`` command.

    Example::

        main(["new", "mybot"])
    """
    p = argparse.ArgumentParser(prog="nicebot", description="nicebot — the friendliest Python library for Telegram bots")
    sub = p.add_subparsers(dest="cmd")
    n = sub.add_parser("new", help="create a new bot project")
    n.add_argument("name", help="folder name")
    n.set_defaults(func=cmd_new)
    r = sub.add_parser("run", help="run a bot file (default: bot.py)")
    r.add_argument("file", nargs="?", default="bot.py")
    r.add_argument("--reload", action="store_true", help="restart when the code changes")
    r.set_defaults(func=cmd_run)
    v = sub.add_parser("version", help="show nicebot, Bot API and Python versions")
    v.set_defaults(func=cmd_version)
    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
