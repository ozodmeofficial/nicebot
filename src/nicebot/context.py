"""``ctx`` — everything about the current update, plus shortcuts to answer it.

Every handler receives a fresh ``Context`` as its first argument. Annotate it so your editor
(VS Code, PyCharm) can autocomplete ``ctx.`` for you::

    from nicebot import Context, Nicebot

    bot = Nicebot(token="...")

    @bot.command("start")
    async def start(ctx: Context):
        name = await ctx.ask("What is your name?")
        await ctx.reply(f"Hello, {name}!")
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterable, Sequence, TypedDict

from . import types as T
from ._base import InputFile
from .errors import AskTimeout, BadRequest, Cancelled, Forbidden, ValidationError
from .keyboards import Button, build_inline, build_reply, remove_keyboard
from .media import Media, guess_kind
from .utils import Html, escape, mention, parse_duration, short_id
from .validators import Validator, _LazyText, as_validator

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from .bot import Nicebot
    from .orm.builtin import User

log = logging.getLogger("nicebot")

MESSAGE_EVENTS = ("message", "edited_message", "channel_post", "edited_channel_post", "business_message", "edited_business_message")
_MEDIA_KINDS = {
    "photo": "send_photo",
    "video": "send_video",
    "document": "send_document",
    "audio": "send_audio",
    "voice": "send_voice",
    "animation": "send_animation",
    "sticker": "send_sticker",
    "video_note": "send_video_note",
}
_INPUT_MEDIA = {
    "photo": T.InputMediaPhoto, "video": T.InputMediaVideo, "document": T.InputMediaDocument,
    "audio": T.InputMediaAudio, "animation": T.InputMediaAnimation,
}


class SendOptions(TypedDict, total=False):
    """Keyword options accepted by every sending method (``reply``, ``photo``, ``video``…).

    Example::

        await ctx.reply("Pick one", buttons=["A", "B"], delete_after="1m", silent=True)
    """

    #: Inline buttons under the message: ``[Button(...)]``, ``["A", "B"]`` or ``{"Text": func}``.
    buttons: Any
    #: Reply keyboard at the bottom: ``["📞 Send phone:contact", "Menu"]``; ``False`` hides it.
    keyboard: Any
    #: Buttons per row (``"auto"`` by default — short labels share a row).
    columns: Any
    #: Hide the current reply keyboard.
    remove_keyboard: bool
    #: Delete the sent message after this long: ``"30s"``, ``"5m"``, ``60``.
    delete_after: Any
    #: Send without a notification sound.
    silent: bool
    #: Forbid forwarding and saving.
    protect: bool
    #: Reply to the incoming message (``True``) or to a message id.
    quote: "bool | int"
    #: ``False`` disables the link preview (text messages).
    preview: bool
    #: Hide the reply keyboard after one press.
    one_time: bool
    #: Placeholder text in the input field while the reply keyboard is shown.
    placeholder: str
    #: Message effect id (private chats).
    effect: str
    #: Forum topic id (defaults to the current topic).
    thread: int
    #: Send to another chat instead of the current one.
    chat_id: "int | str"


class MediaOptions(SendOptions, total=False):
    """``SendOptions`` plus the media fields Telegram understands.

    Example::

        await ctx.video("clip.mp4", "Look!", spoiler=True, supports_streaming=True, thumbnail="thumb.jpg")
    """

    #: Blur the photo/video until tapped.
    spoiler: bool
    #: Show the caption above the media.
    caption_above: bool
    #: Duration in seconds (video, audio, voice, video note).
    duration: int
    width: int
    height: int
    #: A small JPEG preview (path, bytes or ``InputFile``) for videos, documents and audio.
    thumbnail: Any
    #: Let the user start watching before the whole video is downloaded.
    supports_streaming: bool
    #: Audio metadata.
    performer: str
    title: str
    #: File name to show for ``bytes``/``BytesIO`` uploads, e.g. ``"report.pdf"``.
    filename: str
    #: Send a document as a file even if Telegram could detect a photo/video in it.
    disable_content_type_detection: bool


def _looks_like_path(s: str) -> bool:
    # file_ids are base64url (letters, digits, - and _) and never contain "/", "\\" or "."
    return "/" in s or "\\" in s or "." in s


def _as_file(f: Any, filename: str | None = None) -> Any:
    """Turn what the user passed into something the API layer can send.

    Local paths and bytes become uploads, URLs and file_ids are passed as they are.
    A path that does not exist raises ``FileNotFoundError`` (instead of a confusing Telegram error).
    """
    if isinstance(f, Media):
        return f.file_id
    if isinstance(f, InputFile):
        if filename:
            f.filename = filename
        return f
    if isinstance(f, (bytes, bytearray)):
        return InputFile(bytes(f), filename=filename)
    if hasattr(f, "read") or hasattr(f, "__fspath__"):
        return InputFile(f, filename=filename)
    if isinstance(f, str) and not f.startswith(("http://", "https://", "attach://")) and _looks_like_path(f):
        if os.path.isfile(f):
            return InputFile(f, filename=filename)
        raise FileNotFoundError(f"File not found: {f!r}. Pass an existing path, a URL, a file_id, bytes or an InputFile.")
    return f


class FormResult(dict):
    """The answers of ``ctx.form()``: a ``dict`` that also allows attribute access.

    Example::

        data = await ctx.form(name="Name?", age=Integer("Age?"))
        data.name == data["name"]   # True
    """

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item) from None


class Context:
    """Created for every update; handlers receive it as their first argument.

    Read data (``ctx.text``, ``ctx.user``, ``ctx.media``…), answer (``ctx.reply``, ``ctx.photo``…),
    talk (``ctx.ask``, ``ctx.confirm``, ``ctx.choose``, ``ctx.form``) and moderate (``ctx.ban``…).

    Example::

        @bot.command("start")
        async def start(ctx: Context):
            await ctx.reply(f"Hi {ctx.name}! Your id is {ctx.user_id}.")
    """

    def __init__(self, bot: "Nicebot", update: T.Update, event_name: str, event: Any):
        #: The ``Nicebot`` that received the update.
        self.bot: "Nicebot" = bot
        #: The raw Telegram ``Update``.
        self.update = update
        #: Update kind: ``"message"``, ``"callback_query"``, ``"inline_query"``…
        self.event_name = event_name
        #: The update payload (a ``Message``, ``CallbackQuery``, ``InlineQuery``…).
        self.event: Any = event
        #: The database row of the sender (``nb_users``); ``None`` when ``track_users=False`` or there is no sender.
        self.user: "User" = None  # type: ignore[assignment]
        #: Values parsed from callback templates / regex groups: ``{"id": 5}``.
        self.params: dict[str, Any] = {}
        #: The regex match object for ``@bot.text(regex=...)`` handlers.
        self.match: Any = None
        #: All messages of an album (``@bot.album`` handlers).
        self.album: list[T.Message] = []
        #: The value of a pressed ``Toggle`` / dict button.
        self.value: Any = None
        #: Free-form storage for middlewares: ``ctx.extra["started"] = time.time()``.
        self.extra: dict[str, Any] = {}
        self._answered = False
        self._lang: str | None = None
        self._started = time.monotonic()

    # ================================================================== reading the update
    @property
    def message(self) -> T.Message | None:
        """The incoming message (or the message whose button was pressed).

        Example::

            if ctx.message and ctx.message.reply_to_message:
                await ctx.reply("You replied to a message")
        """
        if self.event_name in MESSAGE_EVENTS:
            return self.event
        if self.event_name == "callback_query":
            return self.event.message
        return None

    @property
    def callback(self) -> T.CallbackQuery | None:
        """The pressed button's ``CallbackQuery`` (``None`` for other updates).

        Example::

            if ctx.callback:
                print(ctx.callback.data)
        """
        return self.event if self.event_name == "callback_query" else None

    @property
    def inline_query(self) -> T.InlineQuery | None:
        """The ``InlineQuery`` when the user types ``@yourbot something``.

        Example::

            @bot.inline()
            async def search(ctx: Context):
                print(ctx.inline_query.query)
        """
        return self.event if self.event_name == "inline_query" else None

    @property
    def from_user(self) -> T.User | None:
        """The Telegram ``User`` who caused the update.

        Example::

            await ctx.reply(ctx.from_user.language_code or "unknown")
        """
        ev = self.event
        return getattr(ev, "from_", None) or getattr(ev, "user", None)

    @property
    def user_id(self) -> int | None:
        """Telegram id of the sender (``None`` for anonymous channel posts).

        Example::

            await Order.create(user_id=ctx.user_id, product="Book")
        """
        u = self.from_user
        return u.id if u else None

    @property
    def chat(self) -> T.Chat | None:
        """The chat the update belongs to.

        Example::

            if ctx.chat and ctx.chat.type == "supergroup":
                await ctx.reply(ctx.chat.title)
        """
        ev = self.event
        chat = getattr(ev, "chat", None)
        if chat is None and self.event_name == "callback_query" and ev.message is not None:
            chat = ev.message.chat
        return chat

    @property
    def chat_id(self) -> int:
        """Id of the current chat (falls back to the sender's id, e.g. for inline queries).

        Example::

            await ctx.bot.send_message(ctx.chat_id, "Hello")
        """
        c = self.chat
        if c is not None:
            return c.id
        uid = self.user_id
        if uid is None:
            raise ValueError(f"This update ({self.event_name}) has no chat; pass chat_id= explicitly.")
        return uid

    def _chat_id_or_none(self) -> int | None:
        try:
            return self.chat_id
        except ValueError:
            return None

    @property
    def text(self) -> str | None:
        """Text of the message, its caption, or the inline query text.

        Example::

            if ctx.text and "price" in ctx.text.lower():
                await ctx.reply("50 000 so'm")
        """
        m = self.event if self.event_name in MESSAGE_EVENTS else None
        if m is None:
            if self.event_name == "inline_query":
                return self.event.query
            return None
        return m.text if m.text is not None else m.caption

    @property
    def data(self) -> str | None:
        """Raw ``callback_data`` of the pressed button.

        Example::

            @bot.callback()
            async def any_button(ctx: Context):
                await ctx.answer(f"You pressed {ctx.data}")
        """
        return self.event.data if self.event_name == "callback_query" else None

    @property
    def command(self) -> str | None:
        """The command without ``/`` and ``@botname``, lower-cased: ``"/Start@my_bot x"`` → ``"start"``.

        Example::

            if ctx.command == "help":
                ...
        """
        t = self.text if self.event_name in MESSAGE_EVENTS else None
        if not t or not t.startswith("/"):
            return None
        cmd = t.split(maxsplit=1)[0][1:]
        name, _, at = cmd.partition("@")
        if at and self.bot.username and at.lower() != self.bot.username.lower():
            return None
        return name.lower()

    @property
    def args(self) -> list[str]:
        """Words after the command: ``/give 10 ali`` → ``["10", "ali"]``.

        Example::

            @bot.command("give")
            async def give(ctx: Context):
                amount, who = ctx.args
        """
        t = self.text or ""
        return t.split()[1:] if self.command else []

    @property
    def arg(self) -> str:
        """Everything after the command as one string: ``/say hello world`` → ``"hello world"``.

        Example::

            await ctx.reply(ctx.arg or "Usage: /say <text>")
        """
        t = self.text or ""
        if not self.command:
            return ""
        parts = t.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""

    @property
    def payload(self) -> str:
        """Deep-link payload: ``t.me/your_bot?start=promo`` → ``"promo"``.

        Example::

            @bot.command("start")
            async def start(ctx: Context):
                if ctx.payload == "promo":
                    await ctx.reply("🎁 You got a discount")
        """
        return self.arg if self.command == "start" else ""

    @property
    def media(self) -> Media | None:
        """The file in the current message as a ``Media`` object (``None`` if there is no file).

        Works for photos, videos, animations, documents, audio, voice notes, video notes and stickers.

        Example::

            @bot.on("photo", "document")
            async def file(ctx: Context):
                m = ctx.media
                await ctx.reply(f"{m.kind}: {m.size_text}")
                await m.save("uploads/")
        """
        return Media.of(self.message, self.bot)

    @property
    def album_media(self) -> list[Media]:
        """Every file of an album as ``Media`` (``@bot.album`` handlers).

        Example::

            @bot.album()
            async def album(ctx: Context):
                for m in ctx.album_media:
                    await m.save("albums/")
        """
        out = []
        for msg in self.album:
            m = Media.of(msg, self.bot)
            if m is not None:
                out.append(m)
        return out

    @property
    def web_app_data(self) -> Any:
        """Data sent by a Mini App with ``Telegram.WebApp.sendData()`` (JSON is decoded for you).

        Example::

            @bot.webapp_data()
            async def got(ctx: Context):
                order = ctx.web_app_data       # {"items": [1, 2], "total": 90000}
                await ctx.reply(f"Total: {order['total']}")
        """
        m = self.message
        raw = m.web_app_data.data if m is not None and m.web_app_data is not None else None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return raw

    @property
    def is_private(self) -> bool:
        """``True`` in a one-to-one chat with the bot.

        Example::

            if not ctx.is_private:
                return await ctx.reply("Write to me in private")
        """
        return self.chat is not None and self.chat.type == "private"

    @property
    def is_group(self) -> bool:
        """``True`` in groups and supergroups.

        Example::

            if ctx.is_group:
                await ctx.delete()
        """
        return self.chat is not None and self.chat.type in ("group", "supergroup")

    @property
    def is_callback(self) -> bool:
        """``True`` when the update is a button press.

        Example::

            await (ctx.edit if ctx.is_callback else ctx.reply)("Menu")
        """
        return self.event_name == "callback_query"

    @property
    def is_admin(self) -> bool:
        """Is the sender one of ``Nicebot(admins=[...])``?

        Example::

            if not ctx.is_admin:
                return await ctx.reply("Admins only")
        """
        return self.user_id is not None and self.user_id in self.bot.admins

    @property
    def mention(self) -> Html:
        """A clickable HTML link to the sender.

        Example::

            await ctx.reply(f"Welcome, {ctx.mention}!")
        """
        u = self.from_user
        if u is None:
            return Html("")
        name = " ".join(p for p in (u.first_name, u.last_name) if p)
        return mention(name or str(u.id), u.id)

    @property
    def name(self) -> str:
        """The sender's first name (empty string if unknown).

        Example::

            await ctx.reply(f"Hi, {ctx.name}!")
        """
        u = self.from_user
        return u.first_name if u else ""

    @property
    def ref_link(self) -> str:
        """This user's referral link: ``https://t.me/<bot>?start=ref_<id>``.

        Example::

            await ctx.reply(f"Invite friends: {ctx.ref_link}")
        """
        return self.bot.ref_link(self.user_id or 0)

    @property
    def elapsed(self) -> float:
        """Seconds since the update arrived (useful in middlewares).

        Example::

            log.info("handled in %.3fs", ctx.elapsed)
        """
        return time.monotonic() - self._started

    def __repr__(self) -> str:
        return f"<Context {self.event_name} chat={self._chat_id_or_none()} user={self.user_id} text={self.text!r}>"

    # ================================================================== i18n
    @property
    def lang(self) -> str:
        """The user's language: saved choice → Telegram app language → ``Nicebot(lang=...)``.

        Example::

            if ctx.lang == "ru":
                ...
        """
        if self._lang:
            return self._lang
        stored = getattr(self.user, "lang", None) if self.user is not None else None
        code = stored or (self.from_user.language_code if self.from_user else None)
        self._lang = self.bot.i18n.resolve(code)
        return self._lang

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate ``key`` from ``locales/<lang>.json`` into the user's language.

        Example::

            # locales/en.json: {"hello": "Hello, {name}!"}
            await ctx.reply(ctx.t("hello", name=ctx.name))
        """
        return self.bot.i18n.t(key, self.lang, **kwargs)

    async def set_lang(self, lang: str) -> None:
        """Remember the user's language (saved in the database).

        Example::

            lang = await ctx.choose("Language?", {"🇺🇿 O'zbek": "uz", "🇬🇧 English": "en"})
            await ctx.set_lang(lang)
        """
        self._lang = self.bot.i18n.resolve(lang)
        if self.user is not None:
            await self.user.update(lang=self._lang)

    # ================================================================== sending
    async def _markup(self, buttons: Any, columns: Any, keyboard: Any, remove_kb: bool, **kb: Any) -> Any:
        if buttons is not None:
            return await build_inline(self.bot, buttons, columns, self.user_id)
        if keyboard is False or remove_kb:
            return remove_keyboard()
        if keyboard is not None:
            if isinstance(keyboard, _LazyText):
                keyboard = keyboard.resolve(self)
            return build_reply(keyboard, columns, bot=self.bot, **kb)
        return None

    async def _send(self, method: str, chat_id: Any, params: dict[str, Any], *, buttons: Any = None, columns: Any = None, keyboard: Any = None,
                    remove_keyboard: bool = False, delete_after: Any = None, silent: bool | None = None, protect: bool | None = None,
                    quote: bool | int = False, preview: bool | None = None, one_time: bool = False, placeholder: str | None = None,
                    effect: str | None = None, thread: int | None = None, **extra: Any) -> Any:
        if chat_id is None:
            chat_id = self.chat_id
        markup = await self._markup(buttons, columns, keyboard, remove_keyboard, one_time=one_time, placeholder=placeholder)
        if markup is not None:
            params["reply_markup"] = markup
        if silent is not None:
            params["disable_notification"] = silent
        if protect is not None:
            params["protect_content"] = protect
        if effect:
            params["message_effect_id"] = effect
        cur = self._chat_id_or_none()
        if thread is None and self.message is not None and self.message.is_topic_message and chat_id == cur:
            thread = self.message.message_thread_id
        if thread is not None:
            params["message_thread_id"] = thread
        if quote:
            mid = quote if isinstance(quote, int) and not isinstance(quote, bool) else (self.message.message_id if self.message else None)
            if mid:
                params["reply_parameters"] = T.ReplyParameters(message_id=mid, allow_sending_without_reply=True)
        if preview is False and method == "send_message":
            params["link_preview_options"] = T.LinkPreviewOptions(is_disabled=True)
        params.update(extra)
        msg = await self.bot._call_with_parse_fallback(method, chat_id=chat_id, **params)
        seconds = parse_duration(delete_after)
        if seconds and isinstance(msg, T.Message):
            self.bot.later(seconds, self.bot.safe_delete(msg.chat.id, msg.message_id))
        return msg

    async def reply(self, text: Any, *, parse_mode: str | None = ..., **kw: "Unpack[SendOptions]") -> T.Message:  # type: ignore[assignment]
        """Send a text message to the current chat.

        Options (all optional): ``buttons``, ``keyboard``, ``columns``, ``delete_after``, ``silent``, ``protect``,
        ``quote``, ``preview``, ``effect``, ``remove_keyboard``, ``chat_id`` — see ``SendOptions``.

        Example::

            await ctx.reply("Hello!")
            await ctx.reply("<b>Bold</b> text")                        # HTML by default
            await ctx.reply("Choose:", buttons=["Yes", "No"])          # inline buttons
            await ctx.reply("Menu", keyboard=["🛍 Shop", "📞 Contact"])  # bottom keyboard
            await ctx.reply("This disappears", delete_after="10s")
        """
        params: dict[str, Any] = {"text": str(text)}
        pm = self.bot.parse_mode if parse_mode is ... else parse_mode
        if pm:
            params["parse_mode"] = pm
        chat_id = kw.pop("chat_id", None)  # type: ignore[misc]
        return await self._send("send_message", chat_id, params, **kw)

    async def send(self, text: Any, *, parse_mode: str | None = ..., **kw: "Unpack[SendOptions]") -> T.Message:  # type: ignore[assignment]
        """Same as ``reply`` (kept for readability: ``await ctx.send("...")``).

        Example::

            await ctx.send("Done ✅")
        """
        return await self.reply(text, parse_mode=parse_mode, **kw)

    async def send_to(self, chat_id: int | str, text: Any, **kw: "Unpack[SendOptions]") -> T.Message:
        """Send a text message to another chat (a user id, group id or ``"@channel"``).

        Example::

            await ctx.send_to("@my_channel", "New post!")
        """
        kw["chat_id"] = chat_id
        return await self.reply(text, **kw)

    async def _media(self, kind: str, file: Any, caption: Any = None, **kw: Any) -> T.Message:
        params: dict[str, Any] = {kind: _as_file(file, kw.pop("filename", None))}
        if caption is not None:
            params["caption"] = str(caption)
            if self.bot.parse_mode:
                params["parse_mode"] = self.bot.parse_mode
        for k in ("spoiler", "has_spoiler"):
            if k in kw:
                params["has_spoiler"] = kw.pop(k)
        if "caption_above" in kw:
            params["show_caption_above_media"] = kw.pop("caption_above")
        if kw.get("thumbnail") is not None:
            kw["thumbnail"] = _as_file(kw["thumbnail"])
        return await self._send(_MEDIA_KINDS[kind], kw.pop("chat_id", None), params, **kw)

    async def photo(self, file: Any, caption: Any = None, **kw: "Unpack[MediaOptions]") -> T.Message:
        """Send a photo.

        ``file`` can be a local path, ``pathlib.Path``, URL, ``file_id``, ``Media``, ``bytes``, ``BytesIO`` or
        ``InputFile``. Local files are uploaded once; after that Telegram's ``file_id`` is reused automatically.

        Example::

            await ctx.photo("images/menu.jpg", "Today's menu")
            await ctx.photo("https://picsum.photos/600", spoiler=True)
            await ctx.photo(ctx.media.file_id)                     # send a received photo back
            await ctx.photo(png_bytes, filename="chart.png")       # generated in memory
        """
        return await self._media("photo", file, caption, **kw)

    async def video(self, file: Any, caption: Any = None, **kw: "Unpack[MediaOptions]") -> T.Message:
        """Send a video (MP4 plays inline).

        Example::

            await ctx.video("promo.mp4", "Watch this", supports_streaming=True)
        """
        return await self._media("video", file, caption, **kw)

    async def document(self, file: Any, caption: Any = None, **kw: "Unpack[MediaOptions]") -> T.Message:
        """Send any file as a document.

        Example::

            await ctx.document("reports/june.pdf", "June report")
            await ctx.document(csv_text.encode(), filename="users.csv")
        """
        return await self._media("document", file, caption, **kw)

    async def audio(self, file: Any, caption: Any = None, **kw: "Unpack[MediaOptions]") -> T.Message:
        """Send music (shown in the player with title and performer).

        Example::

            await ctx.audio("song.mp3", performer="Artist", title="Song")
        """
        return await self._media("audio", file, caption, **kw)

    async def voice(self, file: Any, caption: Any = None, **kw: "Unpack[MediaOptions]") -> T.Message:
        """Send a voice message (OGG/Opus, MP3 or M4A).

        Example::

            await ctx.voice("hello.ogg")
        """
        return await self._media("voice", file, caption, **kw)

    async def animation(self, file: Any, caption: Any = None, **kw: "Unpack[MediaOptions]") -> T.Message:
        """Send a GIF or a silent MP4 animation.

        Example::

            await ctx.animation("party.gif")
        """
        return await self._media("animation", file, caption, **kw)

    async def sticker(self, file: Any, **kw: "Unpack[MediaOptions]") -> T.Message:
        """Send a sticker (``file_id`` or a ``.webp``/``.tgs``/``.webm`` file).

        Example::

            await ctx.sticker("CAACAgIAAxkBAAE...")
        """
        return await self._media("sticker", file, None, **kw)

    async def video_note(self, file: Any, **kw: "Unpack[MediaOptions]") -> T.Message:
        """Send a round video message (square MP4, up to 1 minute).

        Example::

            await ctx.video_note("circle.mp4")
        """
        return await self._media("video_note", file, None, **kw)

    async def send_file(self, file: Any, caption: Any = None, *, kind: str | None = None, **kw: "Unpack[MediaOptions]") -> T.Message:
        """Send a file choosing the right method for you (photo, video, audio, voice or document).

        The kind is taken from a ``Media`` object or guessed from the file name; pass ``kind=`` to force it.

        Example::

            await ctx.send_file("cat.jpg")                 # sent as a photo
            await ctx.send_file("clip.mp4", "New clip")    # sent as a video
            await ctx.send_file(ctx.media)                 # echo whatever the user sent
            await ctx.send_file("photo.png", kind="document")
        """
        k = kind or guess_kind(file)
        if k not in _MEDIA_KINDS:
            raise ValueError(f"Unknown kind {k!r}. Use one of: {', '.join(_MEDIA_KINDS)}")
        if k in ("sticker", "video_note"):
            return await self._media(k, file, None, **kw)
        return await self._media(k, file, caption, **kw)

    async def media_group(self, files: Sequence[Any], caption: Any = None, *, kind: str | None = None, chat_id: Any = None, **kw: Any) -> list[T.Message]:
        """Send 2–10 files as one album.

        Photos and videos may be mixed; documents and audio must be sent in albums of their own.
        Items can be paths, URLs, file_ids, ``Media`` objects (e.g. ``ctx.album_media``) or ready ``InputMedia*`` objects.
        The caption goes under the first item. ``kind`` forces one type for every item.

        Example::

            await ctx.media_group(["a.jpg", "b.jpg", "c.mp4"], "Our trip")
            await ctx.media_group(ctx.album_media)               # send a received album back
            await ctx.media_group(["q1.pdf", "q2.pdf"], kind="document")
        """
        media = []
        for i, f in enumerate(files):
            if isinstance(f, (T.InputMediaPhoto, T.InputMediaVideo, T.InputMediaDocument, T.InputMediaAudio, T.InputMediaAnimation)):
                media.append(f)
                continue
            k = kind or guess_kind(f)
            if k not in _INPUT_MEDIA or k == "animation":
                k = "document" if k not in ("photo", "video", "audio") else k
            item: dict[str, Any] = {"media": _as_file(f)}
            if i == 0 and caption is not None:
                item["caption"] = str(caption)
                if self.bot.parse_mode:
                    item["parse_mode"] = self.bot.parse_mode
            media.append(_INPUT_MEDIA[k](**item))
        return await self.bot.send_media_group(chat_id or self.chat_id, media, **kw)

    async def location(self, latitude: float, longitude: float, **kw: "Unpack[SendOptions]") -> T.Message:
        """Send a map point.

        Example::

            await ctx.location(41.3111, 69.2797)
        """
        return await self._send("send_location", kw.pop("chat_id", None), {"latitude": latitude, "longitude": longitude}, **kw)

    async def venue(self, latitude: float, longitude: float, title: str, address: str, **kw: "Unpack[SendOptions]") -> T.Message:
        """Send a place with a name and an address.

        Example::

            await ctx.venue(41.31, 69.28, "Our shop", "Amir Temur 1, Tashkent")
        """
        return await self._send("send_venue", kw.pop("chat_id", None), {"latitude": latitude, "longitude": longitude, "title": title, "address": address}, **kw)

    async def contact(self, phone: str, first_name: str, last_name: str | None = None, **kw: "Unpack[SendOptions]") -> T.Message:
        """Send a phone contact card.

        Example::

            await ctx.contact("+998901234567", "Support")
        """
        return await self._send("send_contact", kw.pop("chat_id", None), {"phone_number": phone, "first_name": first_name, "last_name": last_name}, **kw)

    async def poll(self, question: str, options: Sequence[str], *, anonymous: bool = True, multiple: bool = False, **kw: "Unpack[SendOptions]") -> T.Message:
        """Send a poll.

        Example::

            await ctx.poll("Best day for the meetup?", ["Saturday", "Sunday"], anonymous=False)
        """
        opts = [T.InputPollOption(text=o) for o in options]
        return await self._send("send_poll", kw.pop("chat_id", None), {"question": question, "options": opts, "is_anonymous": anonymous, "allows_multiple_answers": multiple}, **kw)

    async def quiz(self, question: str, options: Sequence[str], correct: int, explanation: str | None = None, **kw: "Unpack[SendOptions]") -> T.Message:
        """Send a quiz with one correct answer (``correct`` is its index).

        Example::

            await ctx.quiz("2 + 2 = ?", ["3", "4", "5"], correct=1, explanation="Basic maths")
        """
        opts = [T.InputPollOption(text=o) for o in options]
        params = {"question": question, "options": opts, "type": "quiz", "correct_option_id": correct, "explanation": explanation}
        return await self._send("send_poll", kw.pop("chat_id", None), params, **kw)

    async def dice(self, emoji: str = "🎲", **kw: "Unpack[SendOptions]") -> T.Message:
        """Throw an animated dice (🎲 🎯 🏀 ⚽ 🎳 🎰). The result is in ``msg.dice.value``.

        Example::

            msg = await ctx.dice("🎯")
            await ctx.reply(f"You got {msg.dice.value}")
        """
        return await self._send("send_dice", kw.pop("chat_id", None), {"emoji": emoji}, **kw)

    async def action(self, action: str = "typing") -> None:
        """Show a status at the top of the chat for ~5 seconds: ``typing``, ``upload_photo``, ``record_voice``…

        Example::

            await ctx.action("upload_document")
            await ctx.document(build_report())
        """
        try:
            await self.bot.send_chat_action(self.chat_id, action)
        except Exception:  # noqa: BLE001
            pass

    def _require_message(self, message: T.Message | None, what: str) -> T.Message:
        m = message or self.message
        if m is None:
            raise ValueError(f"ctx.{what}() needs a message: this update ({self.event_name}) has none, pass message=")
        return m

    async def forward(self, to_chat: int | str, message: T.Message | None = None) -> T.Message:
        """Forward the current message (with the "Forwarded from" header) to another chat.

        Example::

            await ctx.forward(ADMIN_GROUP_ID)
        """
        m = self._require_message(message, "forward")
        return await self.bot.forward_message(to_chat, m.chat.id, m.message_id)

    async def copy(self, to_chat: int | str, message: T.Message | None = None, **kw: Any) -> T.MessageId:
        """Copy the current message to another chat without the "Forwarded" header (works for any media).

        Accepts ``buttons=``, ``columns=``, ``keyboard=`` and ``caption=``.

        Example::

            await ctx.copy("@my_channel", buttons=[Button("💬 Comment", url="https://t.me/my_group")])
        """
        m = self._require_message(message, "copy")
        markup = await self._markup(kw.pop("buttons", None), kw.pop("columns", None), kw.pop("keyboard", None), False)
        if markup is not None:
            kw["reply_markup"] = markup
        return await self.bot.copy_message(to_chat, m.chat.id, m.message_id, **kw)

    # ================================================================== editing
    def _target(self, message: T.Message | None) -> tuple[Any, Any, Any]:
        m = message or self.message
        if m is not None:
            return m.chat.id, m.message_id, None
        if self.callback is not None and self.callback.inline_message_id:
            return None, None, self.callback.inline_message_id
        raise ValueError("Nothing to edit: this update has no message. Pass message=...")

    async def edit(self, text: Any = None, *, buttons: Any = None, columns: Any = None, message: T.Message | None = None, preview: bool | None = None, **kw: Any) -> Any:
        """Edit the current message (the one whose button was pressed). Text or caption is chosen automatically.

        Pass only ``buttons=`` to change the keyboard alone; ``buttons=[]`` removes it.
        "message is not modified" errors are ignored.

        Example::

            @bot.callback("like")
            async def like(ctx: Context):
                await ctx.edit("Thanks for the like ❤️")
        """
        chat_id, message_id, inline_id = self._target(message)
        target = message or self.message
        markup = await build_inline(self.bot, buttons, columns, self.user_id) if buttons is not None else None
        ids = {"chat_id": chat_id, "message_id": message_id, "inline_message_id": inline_id}
        if markup is not None:
            ids["reply_markup"] = markup
        try:
            if text is None:
                return await self.bot.edit_message_reply_markup(**ids)
            pm = self.bot.parse_mode
            has_media = target is not None and any(getattr(target, a, None) for a in ("photo", "video", "document", "audio", "animation", "voice"))
            if has_media:
                return await self.bot._call_with_parse_fallback("edit_message_caption", caption=str(text), parse_mode=pm, **ids, **kw)
            if preview is False:
                kw["link_preview_options"] = T.LinkPreviewOptions(is_disabled=True)
            return await self.bot._call_with_parse_fallback("edit_message_text", text=str(text), parse_mode=pm, **ids, **kw)
        except BadRequest as e:
            if e.not_modified:
                return target
            raise

    async def edit_buttons(self, buttons: Any, columns: Any = None, message: T.Message | None = None) -> Any:
        """Replace only the inline keyboard of the current message (``None``/``[]`` removes it).

        Example::

            await ctx.edit_buttons([Button("✅ Done", data="noop")])
        """
        return await self.edit(None, buttons=buttons if buttons is not None else [], columns=columns, message=message)

    async def edit_media(self, file: Any, caption: Any = None, *, kind: str | None = None, buttons: Any = None,
                         columns: Any = None, message: T.Message | None = None) -> Any:
        """Replace the photo/video/document of the current message (e.g. an image gallery with ◀️ ▶️).

        Example::

            @bot.callback("next:{i:int}")
            async def next_photo(ctx: Context, i: int):
                await ctx.edit_media(PHOTOS[i], f"Photo {i + 1}", buttons=[Button("▶️", on_click=next_photo, i=i + 1)])
        """
        chat_id, message_id, inline_id = self._target(message)
        k = kind or guess_kind(file)
        if k not in _INPUT_MEDIA:
            k = "document"
        item: dict[str, Any] = {"media": _as_file(file)}
        if caption is not None:
            item["caption"] = str(caption)
            if self.bot.parse_mode:
                item["parse_mode"] = self.bot.parse_mode
        params: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "inline_message_id": inline_id}
        if buttons is not None:
            params["reply_markup"] = await build_inline(self.bot, buttons, columns, self.user_id)
        try:
            return await self.bot.edit_message_media(_INPUT_MEDIA[k](**item), **params)
        except BadRequest as e:
            if e.not_modified:
                return message or self.message
            raise

    async def respond(self, text: Any, **kw: Any) -> Any:
        """Smart answer: edits the message when a button was pressed, otherwise sends a new one.

        Example::

            async def show_menu(ctx: Context):
                await ctx.respond("🏠 Main menu", buttons=MENU)   # works from /start and from a button
        """
        if self.is_callback and self.message is not None and self.message.date:
            kw.pop("keyboard", None)
            try:
                return await self.edit(text, **{k: v for k, v in kw.items() if k in ("buttons", "columns", "preview")})
            except BadRequest:
                pass
        return await self.reply(text, **kw)

    async def delete(self, message: T.Message | int | None = None) -> bool:
        """Delete the current message (or another one by object or id). Never raises; returns ``False`` on failure.

        Example::

            await ctx.delete()            # e.g. remove a spam message in a group
        """
        if isinstance(message, int):
            return await self.bot.safe_delete(self.chat_id, message)
        m = message or self.message
        if m is None:
            return False
        return await self.bot.safe_delete(m.chat.id, m.message_id)

    async def pin(self, message: T.Message | None = None, silent: bool = True) -> bool:
        """Pin the current message (the bot must be allowed to pin).

        Example::

            msg = await ctx.reply("📌 Rules: be nice")
            await ctx.pin(msg)
        """
        m = self._require_message(message, "pin")
        return await self.bot.pin_chat_message(m.chat.id, m.message_id, disable_notification=silent)

    async def unpin(self, message: T.Message | None = None) -> bool:
        """Unpin the current message.

        Example::

            await ctx.unpin(old_msg)
        """
        m = self._require_message(message, "unpin")
        return await self.bot.unpin_chat_message(m.chat.id, message_id=m.message_id)

    async def react(self, emoji: str = "👍", big: bool = False, message: T.Message | None = None) -> bool:
        """Put a reaction on the current message.

        Example::

            await ctx.react("🔥")
        """
        m = self._require_message(message, "react")
        return await self.bot.set_message_reaction(m.chat.id, m.message_id, reaction=[T.ReactionTypeEmoji(emoji=emoji)], is_big=big)

    # ================================================================== callbacks & inline
    async def answer(self, text: Any = None, *, alert: bool = False, url: str | None = None, cache: int | None = None) -> Any:
        """Answer the pressed button with a small toast (or a popup with ``alert=True``).

        nicebot answers every button automatically, so call this only to show text.
        Outside button presses it simply sends ``text`` as a message.

        Example::

            await ctx.answer("Added to cart ✅")
            await ctx.answer("Out of stock", alert=True)
        """
        if self.callback is None:
            return await self.reply(text) if text is not None else None
        if self._answered:
            return True
        self._answered = True
        try:
            return await self.bot.answer_callback_query(self.callback.id, text=None if text is None else str(text), show_alert=alert or None, url=url, cache_time=cache)
        except BadRequest:
            return False

    async def alert(self, text: Any) -> Any:
        """Answer the pressed button with a popup window the user must close.

        Example::

            await ctx.alert("⛔ You have no access")
        """
        return await self.answer(text, alert=True)

    async def answer_inline(self, results: Iterable[Any], *, cache: int = 0, personal: bool = True, per_page: int = 50, button: Any = None) -> bool:
        """Answer an inline query (``@yourbot text``). Long lists are paginated for you.

        Items may be ``InlineQueryResult*`` objects or ``(title, text)`` / ``(title, text, description)`` tuples.

        Example::

            @bot.inline()
            async def search(ctx: Context):
                found = [p for p in PRODUCTS if ctx.text.lower() in p.lower()]
                await ctx.answer_inline((p, f"I like {p}") for p in found)
        """
        q = self.inline_query
        if q is None:
            raise ValueError("ctx.answer_inline() works only in @bot.inline() handlers")
        items = list(results)
        start = int(q.offset) if (q.offset or "").isdigit() else 0
        page = items[start:start + per_page]
        built = []
        for i, r in enumerate(page):
            if isinstance(r, tuple):
                title, text, *rest = r
                built.append(T.InlineQueryResultArticle(
                    id=str(start + i), title=str(title), description=rest[0] if rest else None,
                    input_message_content=T.InputTextMessageContent(message_text=str(text), parse_mode=self.bot.parse_mode),
                ))
            else:
                built.append(r)
        nxt = str(start + per_page) if start + per_page < len(items) else ""
        return await self.bot.answer_inline_query(q.id, built, cache_time=cache, is_personal=personal, next_offset=nxt, button=button)

    # ================================================================== files
    async def download(self, file: Any = None) -> bytes:
        """Download a file into memory and return the bytes.

        ``file`` may be a ``file_id``, ``Media``, a Telegram media object, a ``Message`` — or nothing,
        which means "the file in the current message". Raises ``FileTooBig`` above 20 MB (cloud Bot API).

        Example::

            @bot.on("document")
            async def doc(ctx: Context):
                data = await ctx.download()
                await ctx.reply(f"{len(data)} bytes, first line: {data.splitlines()[0][:50]!r}")
        """
        return await self.bot.download_file(self._file_or_current(file))

    async def save(self, path: str | os.PathLike[str] | None = None, file: Any = None, *, folder: str | os.PathLike[str] = "downloads") -> str:
        """Save a file to disk (streamed) and return its path. Without ``file`` the current message's file is saved.

        * ``path=None`` → ``downloads/<original name or unique id>``
        * ``path`` ending with ``/`` → the file keeps its name inside that folder

        Example::

            path = await ctx.save()                      # downloads/report.pdf
            path = await ctx.save(f"users/{ctx.user_id}/")
            path = await ctx.save("avatar.jpg")
        """
        return await self.bot.save_file(self._file_or_current(file), path, folder=folder)

    def _file_or_current(self, file: Any) -> Any:
        if file is not None:
            return file
        media = self.media
        if media is None:
            raise ValueError("There is no file in this message. Pass file=..., or use @bot.on('photo', 'document', ...)")
        return media

    # ================================================================== state
    def _state_key(self) -> str:
        return f"st:{self._chat_id_or_none()}:{self.user_id}"

    async def set_state(self, state: str | None, **data: Any) -> None:
        """Remember where the user is in a long flow (stored in the database, survives restarts).

        Example::

            await ctx.set_state("feedback", step=1)

            @bot.text(state="feedback")
            async def got_feedback(ctx: Context):
                await ctx.clear_state()
        """
        if state is None:
            await self.clear_state()
            return
        rec = await self.bot.storage.get(self._state_key()) or {}
        rec["s"] = state
        if data:
            rec.setdefault("d", {}).update(data)
        await self.bot.storage.set(self._state_key(), rec, ttl=self.bot.state_ttl)

    async def get_state(self) -> str | None:
        """The current state name or ``None``.

        Example::

            if await ctx.get_state() == "feedback":
                ...
        """
        rec = await self.bot.storage.get(self._state_key())
        return rec.get("s") if rec else None

    async def state_data(self) -> FormResult:
        """Data saved with ``set_state``/``update_data``.

        Example::

            data = await ctx.state_data()
            await ctx.reply(f"Step {data.step}")
        """
        rec = await self.bot.storage.get(self._state_key()) or {}
        return FormResult(rec.get("d", {}))

    async def update_data(self, **data: Any) -> FormResult:
        """Add values to the state data and return all of it.

        Example::

            await ctx.update_data(city="Tashkent")
        """
        rec = await self.bot.storage.get(self._state_key()) or {}
        rec.setdefault("d", {}).update(data)
        await self.bot.storage.set(self._state_key(), rec, ttl=self.bot.state_ttl)
        return FormResult(rec["d"])

    async def clear_state(self) -> None:
        """Forget the state and its data.

        Example::

            await ctx.clear_state()
        """
        await self.bot.storage.delete(self._state_key())

    # ================================================================== settings (toggles)
    async def setting(self, key: str, default: Any = False) -> Any:
        """Read a per-user setting (the value behind a ``Toggle`` button).

        Example::

            if await ctx.setting("notify", default=True):
                await ctx.reply("🔔 You will get news")
        """
        return await self.bot.get_setting(self.user_id or 0, key, default)

    async def set_setting(self, key: str, value: Any) -> None:
        """Save a per-user setting.

        Example::

            await ctx.set_setting("city", "Tashkent")
        """
        await self.bot.set_setting(self.user_id or 0, key, value)

    # ================================================================== conversations
    async def _wait(self, kind: str, *, token: str | None = None, timeout: Any = None) -> "Context":
        seconds = parse_duration(timeout if timeout is not None else self.bot.ask_timeout)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        key: Any = (self._chat_id_or_none(), self.user_id) if kind == "message" else token
        waiters = self.bot._waiters
        old = waiters.get(key)
        if old is not None and not old[0].done():
            old[0].set_exception(Cancelled())
        waiters[key] = (fut, self.user_id)
        try:
            return await asyncio.wait_for(fut, seconds)
        except asyncio.TimeoutError:
            raise AskTimeout() from None
        finally:
            if waiters.get(key, (None,))[0] is fut:
                waiters.pop(key, None)

    async def wait_message(self, timeout: Any = None) -> "Context":
        """Wait for the user's next message in this chat and return its ``ctx``.

        Example::

            await ctx.reply("Send me anything")
            answer = await ctx.wait_message(timeout="2m")
            await ctx.reply(f"You sent: {answer.text or answer.media}")
        """
        return await self._wait("message", timeout=timeout)

    async def ask(self, question: Any = None, type: Any = str, *, buttons: Any = None, keyboard: Any = None, columns: Any = None,
                  timeout: Any = None, retries: int = 5, silent_timeout: bool = False, **send_kw: Any) -> Any:
        """Ask a question and wait for the answer right here — no state classes needed.

        ``type`` checks and converts the answer: ``str`` (default), ``int``, ``float`` or any validator
        (``Phone``, ``Email``, ``Date``, ``Photo``, ``Media``…). Wrong answers are explained and asked again.
        The user can stop with ``/cancel`` (raises ``Cancelled``, handled for you).

        Example::

            name = await ctx.ask("What is your name?")
            age = await ctx.ask("How old are you?", int)
            phone = await ctx.ask("Your phone?", Phone)            # shows a "Send phone" button
            size = await ctx.ask("Size?", buttons=["S", "M", "L"])
            photo = await ctx.ask("Send a selfie", Photo)
        """
        if buttons is not None:
            return await self.choose(question, buttons, columns=columns, timeout=timeout)
        validator: Validator = as_validator(type)
        kb = keyboard if keyboard is not None else validator.keyboard
        if question is not None:
            await self.reply(question, keyboard=kb, columns=columns, one_time=True, **send_kw)
        for _ in range(max(retries, 1)):
            try:
                answer = await self.wait_message(timeout)
            except AskTimeout:
                if not silent_timeout:
                    await self.reply(self.t("nb.timeout"), remove_keyboard=kb is not None)
                raise
            m = answer.message
            if m is not None and m.text and (m.text.strip().lower() in ("/cancel", "/stop") or m.text == self.t("nb.cancel")):
                await self.reply(self.t("nb.cancelled"), remove_keyboard=True)
                raise Cancelled()
            try:
                value = await validator(answer, m)
            except ValidationError as e:
                await self.reply(str(e) or self.t("nb.invalid"))
                continue
            self.extra["last_answer"] = answer
            if kb is not None:
                self.extra["kb_shown"] = True
            return value
        await self.reply(self.t("nb.too_many_tries"), remove_keyboard=kb is not None)
        raise Cancelled()

    async def confirm(self, question: Any, *, yes: str | None = None, no: str | None = None, timeout: Any = None, edit: bool = True) -> bool:
        """Ask a yes/no question with two buttons. Returns ``True`` or ``False``.

        Example::

            if await ctx.confirm("Delete your account?"):
                await ctx.user.delete()
        """
        token = short_id(8)
        buttons = [[Button(yes or self.t("nb.yes"), data=f"~c{token}:1"), Button(no or self.t("nb.no"), data=f"~c{token}:0")]]
        msg = await self.reply(question, buttons=buttons)
        try:
            ans = await self._wait("callback", token=token, timeout=timeout)
        except AskTimeout:
            await self._strip_buttons(msg)
            raise
        await ans.answer()
        result = (ans.data or "").endswith(":1")
        if edit:
            chosen = buttons[0][0 if result else 1].text
            await self._strip_buttons(msg, suffix=f"\n\n<b>{escape(chosen)}</b>" if self.bot.parse_mode == "HTML" else f"\n\n{chosen}", original=question)
        return result

    async def _strip_buttons(self, msg: Any, suffix: str = "", original: Any = None) -> None:
        try:
            if suffix and msg.text is not None:
                text = str(original) if original is not None else escape(msg.text)
                await self.bot._call_with_parse_fallback("edit_message_text", chat_id=msg.chat.id, message_id=msg.message_id, text=text + suffix, parse_mode=self.bot.parse_mode)
            else:
                await self.bot.edit_message_reply_markup(chat_id=msg.chat.id, message_id=msg.message_id)
        except Exception:  # noqa: BLE001
            pass

    async def choose(self, question: Any, options: Any, *, multiple: bool = False, columns: Any = None, timeout: Any = None,
                     selected: Iterable[Any] = (), done: str | None = None, min: int = 0) -> Any:
        """Let the user pick one option (or several with ``multiple=True``) using inline buttons.

        ``options`` is a list of labels or a ``{label: value}`` dict. Returns the value (or a list of values).

        Example::

            city = await ctx.choose("City?", ["Tashkent", "Samarkand", "Bukhara"])
            tags = await ctx.choose("Interests?", {"⚽ Sport": "sport", "💻 IT": "it"}, multiple=True)
        """
        if isinstance(options, dict):
            labels, values = list(options.keys()), list(options.values())
        else:
            labels = [str(o) for o in options]
            values = list(options)
        token = short_id(8)
        pre = list(selected)
        chosen: set[int] = {i for i, v in enumerate(values) if any(v == s for s in pre)}

        def kb() -> list[list[Button]]:
            items = [Button((("✅ " if i in chosen else "⬜️ ") if multiple else "") + lab, data=f"~c{token}:{i}") for i, lab in enumerate(labels)]
            from .keyboards import _normalize

            rows = _normalize(items, columns)
            if multiple:
                rows.append([Button(done or self.t("nb.done"), data=f"~c{token}:done")])
            return rows

        msg = await self.reply(question if question is not None else self.t("nb.choose_hint"), buttons=kb())
        while True:
            try:
                ans = await self._wait("callback", token=token, timeout=timeout)
            except AskTimeout:
                await self._strip_buttons(msg)
                raise
            pick = (ans.data or ":").split(":", 1)[1]
            if not multiple:
                await ans.answer()
                idx = int(pick)
                await self._strip_buttons(msg, suffix=f"\n\n<b>{escape(labels[idx])}</b>" if self.bot.parse_mode == "HTML" else f"\n\n{labels[idx]}", original=question if question is not None else self.t("nb.choose_hint"))
                return values[idx]
            if pick == "done":
                if len(chosen) < min:
                    await ans.answer(self.t("nb.choose_hint"), alert=True)
                    continue
                await ans.answer()
                await self._strip_buttons(msg)
                return [values[i] for i in sorted(chosen)]
            idx = int(pick)
            chosen.symmetric_difference_update({idx})
            await ans.answer()
            try:
                await self.bot.edit_message_reply_markup(chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=await build_inline(self.bot, kb()))
            except BadRequest:
                pass

    async def form(self, _fields: dict[str, Any] | None = None, /, *, timeout: Any = None, done: Any = None, **fields: Any) -> FormResult:
        """Ask several questions in a row, validate each answer and return them all.

        Each field is a question text, a validator with a prompt, or a ``(type, "question")`` tuple.

        Example::

            data = await ctx.form(
                name="Your name?",
                age=Integer("Your age?", min=14),
                phone=Phone("Your phone?"),
            )
            await ctx.reply(f"{data.name}, {data.age}, {data.phone}")
        """
        spec = {**(_fields or {}), **fields}
        result = FormResult()
        for name, s in spec.items():
            prompt: Any = None
            if isinstance(s, str):
                validator: Any = str
                prompt = s
            elif isinstance(s, tuple):
                a, b = s
                validator, prompt = (a, b) if not isinstance(a, str) else (b, a)
            else:
                validator = s
            v = as_validator(validator, prompt)
            result[name] = await self.ask(v.prompt or f"{name}?", v, timeout=timeout)
        if self.extra.pop("kb_shown", False) or done is not None:
            await self.reply(done or "✅", remove_keyboard=True)
        return result

    # ================================================================== pagination & menus
    async def paginate(self, items: Sequence[Any], *, per_page: int = 10, title: Any = "", render: Callable[[Any, int], Any] | None = None,
                       columns: Any = 1, numbered: bool = True, ttl: Any = "7d", empty: Any = None, edit: bool = False) -> Any:
        """Show a long list page by page with ◀️ 2/5 ▶️ buttons.

        Items can be strings/objects (shown as text) or ``Button``s (shown as a keyboard).

        Example::

            products = await Product.all().order_by("title")
            await ctx.paginate(products, title="🛍 Products", render=lambda p, i: f"{i}. {p.title} — {p.price}")
        """
        from .pagination import start_pagination

        return await start_pagination(self, items, per_page=per_page, title=title, render=render, columns=columns, numbered=numbered, ttl=ttl, empty=empty, edit=edit)

    async def menu(self, menu: Any, *, edit: bool | None = None) -> Any:
        """Show a multi-level ``Menu``; navigation and the "Back" button are handled for you.

        Example::

            await ctx.menu(MAIN_MENU)
        """
        return await menu.show(self, edit=self.is_callback if edit is None else edit)

    # ================================================================== payments (Telegram Stars)
    async def invoice(self, title: str, description: str, amount: int, *, payload: str = "nb", photo: str | None = None, **kw: "Unpack[SendOptions]") -> T.Message:
        """Ask the user to pay ``amount`` Telegram Stars (⭐). Handle success with ``@bot.paid()``.

        Example::

            await ctx.invoice("Premium", "30 days of premium", 100, payload="premium_30")
        """
        params = {
            "title": title, "description": description, "payload": payload, "currency": "XTR",
            "prices": [T.LabeledPrice(label=title, amount=int(amount))], "photo_url": photo,
        }
        return await self._send("send_invoice", kw.pop("chat_id", None), params, **kw)

    async def refund(self, charge_id: str | None = None, user_id: int | None = None) -> bool:
        """Refund a Stars payment (by default the one in the current ``successful_payment`` message).

        Example::

            await ctx.refund(order.charge_id, order.user_id)
        """
        if charge_id is None and self.message and self.message.successful_payment:
            charge_id = self.message.successful_payment.telegram_payment_charge_id
        uid = user_id or self.user_id
        if charge_id is None or uid is None:
            raise ValueError("ctx.refund() needs charge_id= and user_id= outside a successful payment message")
        return await self.bot.refund_star_payment(uid, charge_id)

    # ================================================================== groups
    async def _member_target(self, user_id: int | None) -> int:
        if user_id is not None:
            return user_id
        m = self.message
        if m is not None and m.reply_to_message is not None and m.reply_to_message.from_ is not None:
            return m.reply_to_message.from_.id
        raise ValueError("Who? Reply to the user's message or pass user_id=")

    async def ban(self, user_id: int | None = None, *, for_: Any = None, revoke: bool = False) -> bool:
        """Ban a member (the replied user by default). ``for_="1d"`` makes the ban temporary.

        Example::

            @bot.command("ban", chat="supergroup")
            async def ban(ctx: Context):
                if await ctx.is_chat_admin():
                    await ctx.ban(for_="7d")
        """
        uid = await self._member_target(user_id)
        seconds = parse_duration(for_) if for_ else None
        until = int(time.time() + seconds) if seconds else None
        return await self.bot.ban_chat_member(self.chat_id, uid, until_date=until, revoke_messages=revoke or None)

    async def unban(self, user_id: int | None = None) -> bool:
        """Lift a ban.

        Example::

            await ctx.unban(123456789)
        """
        uid = await self._member_target(user_id)
        return await self.bot.unban_chat_member(self.chat_id, uid, only_if_banned=True)

    async def kick(self, user_id: int | None = None) -> bool:
        """Remove a member from the group; they can join again.

        Example::

            await ctx.kick()          # the replied user
        """
        uid = await self._member_target(user_id)
        await self.bot.ban_chat_member(self.chat_id, uid)
        return await self.bot.unban_chat_member(self.chat_id, uid, only_if_banned=True)

    async def mute(self, duration: Any = "1h", user_id: int | None = None) -> bool:
        """Forbid a member to write for ``duration`` (``None`` = forever).

        Example::

            await ctx.mute("30m")
        """
        uid = await self._member_target(user_id)
        seconds = parse_duration(duration) if duration else None
        until = int(time.time() + seconds) if seconds else None
        perms = T.ChatPermissions(can_send_messages=False)
        return await self.bot.restrict_chat_member(self.chat_id, uid, perms, until_date=until)

    async def unmute(self, user_id: int | None = None) -> bool:
        """Give the member their rights back.

        Example::

            await ctx.unmute(123456789)
        """
        uid = await self._member_target(user_id)
        perms = T.ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True,
            can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True,
        )
        return await self.bot.restrict_chat_member(self.chat_id, uid, perms)

    async def warn(self, reason: str = "", *, user_id: int | None = None, limit: int = 3, then: str = "ban", reset: Any = "30d") -> int:
        """Warn a member; after ``limit`` warnings they are banned (``then="ban"``), muted (``"mute"``) or kicked (``"kick"``).

        Returns the current number of warnings.

        Example::

            @bot.command("warn", chat="supergroup")
            async def warn(ctx: Context):
                if await ctx.is_chat_admin():
                    await ctx.warn(ctx.arg or "spam")
        """
        uid = await self._member_target(user_id)
        key = f"warn:{self.chat_id}:{uid}"
        count = await self.bot.storage.incr(key, 1, ttl=parse_duration(reset))
        member = await self.bot.get_chat_member(self.chat_id, uid)
        who = mention(member.user.first_name, uid)
        if count >= limit:
            await self.bot.storage.delete(key)
            if then == "mute":
                await self.mute(None, uid)
            elif then == "kick":
                await self.kick(uid)
            else:
                await self.ban(uid)
            await self.reply(self.t("nb.banned_after_warns", mention=who, limit=limit))
        else:
            await self.reply(self.t("nb.warned", mention=who, count=count, limit=limit, reason=escape(reason)))
        return count

    async def is_member(self, chat: int | str, user_id: int | None = None) -> bool:
        """Is the user (the sender by default) a member of ``chat``? The bot must be an admin there.

        Example::

            if not await ctx.is_member("@my_channel"):
                return await ctx.reply("Join @my_channel first")
        """
        uid = user_id or self.user_id
        if uid is None:
            return False
        try:
            m = await self.bot.get_chat_member(chat, uid)
        except (BadRequest, Forbidden):
            return False
        return m.status in ("creator", "administrator", "member") or (m.status == "restricted" and getattr(m, "is_member", False))

    async def is_chat_admin(self, user_id: int | None = None) -> bool:
        """Is the user an admin of the current group? (Always ``True`` in private chats.)

        Example::

            if not await ctx.is_chat_admin():
                return await ctx.reply("Only group admins can do this")
        """
        if self.is_private:
            return True
        uid = user_id or self.user_id
        if uid is None:
            return False
        try:
            m = await self.bot.get_chat_member(self.chat_id, uid)
        except (BadRequest, Forbidden):
            return False
        return m.status in ("creator", "administrator")

    # ================================================================== misc
    def background(self, func: Callable[..., Awaitable[Any]], *args: Any, retries: int = 3, delay: Any = "2s", **kwargs: Any) -> asyncio.Task:
        """Run slow work after the handler returns, retrying on errors.

        Example::

            await ctx.reply("Your report is being prepared…")
            ctx.background(send_report, ctx.chat_id)
        """
        return self.bot.background(func, *args, retries=retries, delay=delay, **kwargs)

    async def notify_admins(self, text: Any, **kw: Any) -> None:
        """Send a message to every admin from ``Nicebot(admins=[...])``.

        Example::

            await ctx.notify_admins(f"🛒 New order from {ctx.mention}")
        """
        await self.bot.notify_admins(text, **kw)
