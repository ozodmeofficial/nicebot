"""nicebot — Telegram botlar uchun eng qulay Python kutubxonasi.

    from nicebot import Nicebot

    bot = Nicebot(token="...")

    @bot.command("start")
    async def start(ctx):
        name = await ctx.ask("Ismingiz?")
        await ctx.reply(f"Salom, {name}!")

    bot.start()
"""
from . import types
from .__about__ import __version__
from ._base import InputFile
from .bot import Nicebot
from .config import Config, load_env
from .context import Context, FormResult
from .errors import (
    AskTimeout,
    BadRequest,
    Cancelled,
    DoesNotExist,
    Forbidden,
    IntegrityError,
    NicebotError,
    RetryAfter,
    SkipHandler,
    StopHandling,
    TelegramError,
    ValidationError,
)
from .filters import F, Filter
from .i18n import I18n
from .keyboards import Button, ReplyButton, Toggle
from .menu import Menu
from .orm import Database, Model, Q, fields
from .orm import F as Col
from .orm.builtin import User
from .router import Router
from .server import WebAppRequest, validate_init_data
from .storage import DBStorage, MemoryStorage, RedisStorage, Storage
from .types import API_VERSION
from .utils import bold, cache, code, escape, html, italic, link, mention, parse_duration, pre, quote, spoiler, strike, underline
from .validators import Choice, Date, Email, File, Location, Phone, Photo, Regex, Text, Url
from .validators import Float as Number
from .validators import Int as Integer

__all__ = [
    "Nicebot", "Router", "Context", "F", "Filter", "Button", "ReplyButton", "Toggle", "Menu",
    "Model", "fields", "Database", "Q", "Col", "User",
    "Phone", "Email", "Date", "Choice", "Regex", "Photo", "File", "Location", "Url", "Text", "Integer", "Number",
    "html", "escape", "bold", "italic", "underline", "strike", "spoiler", "code", "pre", "link", "mention", "quote", "cache", "parse_duration",
    "InputFile", "Config", "load_env", "I18n", "FormResult", "WebAppRequest", "validate_init_data",
    "Storage", "MemoryStorage", "RedisStorage", "DBStorage",
    "NicebotError", "TelegramError", "BadRequest", "Forbidden", "RetryAfter", "Cancelled", "AskTimeout", "ValidationError",
    "SkipHandler", "StopHandling", "DoesNotExist", "IntegrityError",
    "types", "API_VERSION", "__version__",
]
