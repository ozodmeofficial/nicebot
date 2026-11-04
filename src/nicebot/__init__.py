"""nicebot — the friendliest Python library for Telegram bots.

Example::

    from nicebot import Context, Nicebot

    bot = Nicebot(token="123456:ABC...")

    @bot.command("start")
    async def start(ctx: Context):
        name = await ctx.ask("What is your name?")
        await ctx.reply(f"Hello, {name}!")

    bot.start()

Docs (uz / ru / en): https://ozodmeofficial.github.io/nicebot/
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
    FileTooBig,
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
from .media import Media
from .menu import Menu
from .orm import Database, Model, Q, fields
from .orm import F as Col
from .orm.builtin import User
from .router import Router
from .server import UploadedFile, WebAppRequest, WebAppUser, sign_init_data, validate_init_data
from .tunnel import Tunnel, TunnelError
from .storage import DBStorage, MemoryStorage, RedisStorage, Storage
from .types import API_VERSION
from .utils import bold, cache, code, escape, html, italic, link, mention, parse_duration, pre, quote, spoiler, strike, underline
from .validators import Audio, Choice, Custom, Date, Document, Email, File, Location, Phone, Photo, Regex, Text, Url, Validator, Video, Voice
from .validators import Float as Number
from .validators import Int as Integer

__all__ = [
    "Nicebot", "Router", "Context", "F", "Filter", "Button", "ReplyButton", "Toggle", "Menu",
    "Model", "fields", "Database", "Q", "Col", "User",
    "Phone", "Email", "Date", "Choice", "Regex", "Photo", "File", "Video", "Document", "Audio", "Voice", "Location", "Url", "Text",
    "Integer", "Number", "Validator", "Custom", "Media",
    "html", "escape", "bold", "italic", "underline", "strike", "spoiler", "code", "pre", "link", "mention", "quote", "cache", "parse_duration",
    "InputFile", "Config", "load_env", "I18n", "FormResult",
    "WebAppRequest", "WebAppUser", "UploadedFile", "validate_init_data", "sign_init_data", "Tunnel", "TunnelError",
    "Storage", "MemoryStorage", "RedisStorage", "DBStorage",
    "NicebotError", "FileTooBig", "TelegramError", "BadRequest", "Forbidden", "RetryAfter", "Cancelled", "AskTimeout", "ValidationError",
    "SkipHandler", "StopHandling", "DoesNotExist", "IntegrityError",
    "types", "API_VERSION", "__version__",
]
