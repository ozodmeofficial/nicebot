"""``ctx`` — everything about the current update plus 100+ shortcuts to act on it."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterable, Sequence

from . import types as T
from ._base import InputFile
from .errors import AskTimeout, BadRequest, Cancelled, Forbidden, ValidationError
from .keyboards import Button, build_inline, build_reply, remove_keyboard
from .utils import Html, escape, mention, parse_duration, short_id
from .validators import Validator, as_validator, _LazyText

if TYPE_CHECKING:
    from .bot import Nicebot

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


def _as_file(f: Any) -> Any:
    """Path-like strings that exist on disk become uploads; everything else is a file_id/URL."""
    if isinstance(f, (InputFile, bytes, bytearray)):
        return f if isinstance(f, InputFile) else InputFile(f)
    if hasattr(f, "read"):
        return InputFile(f)
    if hasattr(f, "__fspath__"):
        return InputFile(f)
    if isinstance(f, str) and not f.startswith(("http://", "https://")) and ("/" in f or "\\" in f or "." in f[-6:]):
        import os

        if os.path.exists(f):
            return InputFile(f)
    return f


class FormResult(dict):
    """``dict`` with attribute access: ``data.name`` == ``data["name"]``."""

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item) from None


class Context:
    """Created for every update. Handlers receive it as their first argument."""

    def __init__(self, bot: "Nicebot", update: T.Update, event_name: str, event: Any):
        self.bot = bot
        self.update = update
        self.event_name = event_name
        self.event = event
        self.user: Any = None  # ORM user (filled by the user-tracking middleware)
        self.params: dict[str, Any] = {}
        self.match: Any = None
        self.album: list[T.Message] = []
        self.value: Any = None
        self.extra: dict[str, Any] = {}
        self._answered = False
        self._lang: str | None = None
        self._started = time.monotonic()

    # ================================================================== basics
    @property
    def message(self) -> T.Message | None:
        if self.event_name in MESSAGE_EVENTS:
            return self.event
        if self.event_name == "callback_query":
            return self.event.message
        return None

    @property
    def callback(self) -> T.CallbackQuery | None:
        return self.event if self.event_name == "callback_query" else None

    @property
    def inline_query(self) -> T.InlineQuery | None:
        return self.event if self.event_name == "inline_query" else None

    @property
    def from_user(self) -> T.User | None:
        ev = self.event
        return getattr(ev, "from_", None) or getattr(ev, "user", None)

    @property
    def user_id(self) -> int | None:
        u = self.from_user
        return u.id if u else None

    @property
    def chat(self) -> T.Chat | None:
        ev = self.event
        chat = getattr(ev, "chat", None)
        if chat is None and self.event_name == "callback_query" and ev.message is not None:
            chat = ev.message.chat
        return chat

    @property
    def chat_id(self) -> int | None:
        c = self.chat
        if c is not None:
            return c.id
        return self.user_id

    @property
    def text(self) -> str | None:
        m = self.event if self.event_name in MESSAGE_EVENTS else None
        if m is None:
            if self.event_name == "inline_query":
                return self.event.query
            return None
        return m.text if m.text is not None else m.caption

    @property
    def data(self) -> str | None:
        """Callback data of the pressed button."""
        return self.event.data if self.event_name == "callback_query" else None

    @property
    def command(self) -> str | None:
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
        """``/give 10 ali`` → ``["10", "ali"]``"""
        t = self.text or ""
        return t.split()[1:] if self.command else []

    @property
    def arg(self) -> str:
        """Everything after the command as one string."""
        t = self.text or ""
        if not self.command:
            return ""
        parts = t.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""

    @property
    def payload(self) -> str:
        """Deep-link payload: ``t.me/bot?start=promo`` → ``"promo"``."""
        return self.arg if self.command == "start" else ""

    @property
    def is_private(self) -> bool:
        return self.chat is not None and self.chat.type == "private"

    @property
    def is_group(self) -> bool:
        return self.chat is not None and self.chat.type in ("group", "supergroup")

    @property
    def is_callback(self) -> bool:
        return self.event_name == "callback_query"

    @property
    def is_admin(self) -> bool:
        """Is the sender one of ``Nicebot(admins=[...])``?"""
        return self.user_id is not None and self.user_id in self.bot.admins

    @property
    def mention(self) -> Html:
        u = self.from_user
        if u is None:
            return Html("")
        name = " ".join(p for p in (u.first_name, u.last_name) if p)
        return mention(name or str(u.id), u.id)

    @property
    def name(self) -> str:
        u = self.from_user
        return u.first_name if u else ""

    @property
    def ref_link(self) -> str:
        return self.bot.ref_link(self.user_id or 0)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._started

    def __repr__(self) -> str:
        return f"<Context {self.event_name} chat={self.chat_id} user={self.user_id} text={self.text!r}>"

    # ================================================================== i18n
    @property
    def lang(self) -> str:
        if self._lang:
            return self._lang
        stored = getattr(self.user, "lang", None) if self.user is not None else None
        code = stored or (self.from_user.language_code if self.from_user else None)
        self._lang = self.bot.i18n.resolve(code)
        return self._lang

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate ``key`` into the user's language."""
        return self.bot.i18n.t(key, self.lang, **kwargs)

    async def set_lang(self, lang: str) -> None:
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
            return build_reply(keyboard, columns, **kb)
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
        if thread is None and self.message is not None and self.message.is_topic_message and chat_id == self.chat_id:
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

    async def reply(self, text: Any, *, chat_id: int | str | None = None, parse_mode: str | None = ..., **kw: Any) -> T.Message:  # type: ignore[assignment]
        """Send a text message to the current chat.

        ``buttons=``, ``keyboard=``, ``columns=``, ``delete_after="30s"``, ``silent=True``, ``protect=True``,
        ``quote=True``, ``preview=False``, ``effect=``, ``remove_keyboard=True``
        """
        params: dict[str, Any] = {"text": str(text)}
        pm = self.bot.parse_mode if parse_mode is ... else parse_mode
        if pm:
            params["parse_mode"] = pm
        return await self._send("send_message", chat_id, params, **kw)

    send = reply

    async def send_to(self, chat_id: int | str, text: Any, **kw: Any) -> T.Message:
        """Send a message to another chat."""
        return await self.reply(text, chat_id=chat_id, **kw)

    async def _media(self, kind: str, file: Any, caption: Any = None, **kw: Any) -> T.Message:
        params: dict[str, Any] = {kind: _as_file(file)}
        if caption is not None:
            params["caption"] = str(caption)
            if self.bot.parse_mode:
                params["parse_mode"] = self.bot.parse_mode
        for k in ("spoiler", "has_spoiler"):
            if k in kw:
                params["has_spoiler"] = kw.pop(k)
        return await self._send(_MEDIA_KINDS[kind], kw.pop("chat_id", None), params, **kw)

    async def photo(self, file: Any, caption: Any = None, **kw: Any) -> T.Message:
        """Path, URL, file_id, bytes or ``InputFile``. Local files are uploaded once, then cached by file_id."""
        return await self._media("photo", file, caption, **kw)

    async def video(self, file: Any, caption: Any = None, **kw: Any) -> T.Message:
        return await self._media("video", file, caption, **kw)

    async def document(self, file: Any, caption: Any = None, **kw: Any) -> T.Message:
        return await self._media("document", file, caption, **kw)

    async def audio(self, file: Any, caption: Any = None, **kw: Any) -> T.Message:
        return await self._media("audio", file, caption, **kw)

    async def voice(self, file: Any, caption: Any = None, **kw: Any) -> T.Message:
        return await self._media("voice", file, caption, **kw)

    async def animation(self, file: Any, caption: Any = None, **kw: Any) -> T.Message:
        return await self._media("animation", file, caption, **kw)

    async def sticker(self, file: Any, **kw: Any) -> T.Message:
        return await self._media("sticker", file, None, **kw)

    async def video_note(self, file: Any, **kw: Any) -> T.Message:
        return await self._media("video_note", file, None, **kw)

    async def media_group(self, files: Sequence[Any], caption: Any = None, *, kind: str = "photo", chat_id: Any = None, **kw: Any) -> list[T.Message]:
        """Send 2–10 files as one album. ``files`` may mix paths/URLs/file_ids or ready ``InputMedia*`` objects."""
        cls = {"photo": T.InputMediaPhoto, "video": T.InputMediaVideo, "document": T.InputMediaDocument, "audio": T.InputMediaAudio}[kind]
        media = []
        for i, f in enumerate(files):
            if isinstance(f, (T.InputMediaPhoto, T.InputMediaVideo, T.InputMediaDocument, T.InputMediaAudio)):
                media.append(f)
                continue
            item: dict[str, Any] = {"media": _as_file(f)}
            if i == 0 and caption is not None:
                item["caption"] = str(caption)
                if self.bot.parse_mode:
                    item["parse_mode"] = self.bot.parse_mode
            media.append(cls(**item))
        return await self.bot.send_media_group(chat_id or self.chat_id, media, **kw)

    async def location(self, latitude: float, longitude: float, **kw: Any) -> T.Message:
        return await self._send("send_location", kw.pop("chat_id", None), {"latitude": latitude, "longitude": longitude}, **kw)

    async def venue(self, latitude: float, longitude: float, title: str, address: str, **kw: Any) -> T.Message:
        return await self._send("send_venue", kw.pop("chat_id", None), {"latitude": latitude, "longitude": longitude, "title": title, "address": address}, **kw)

    async def contact(self, phone: str, first_name: str, last_name: str | None = None, **kw: Any) -> T.Message:
        return await self._send("send_contact", kw.pop("chat_id", None), {"phone_number": phone, "first_name": first_name, "last_name": last_name}, **kw)

    async def poll(self, question: str, options: Sequence[str], *, anonymous: bool = True, multiple: bool = False, **kw: Any) -> T.Message:
        opts = [T.InputPollOption(text=o) for o in options]
        return await self._send("send_poll", kw.pop("chat_id", None), {"question": question, "options": opts, "is_anonymous": anonymous, "allows_multiple_answers": multiple}, **kw)

    async def quiz(self, question: str, options: Sequence[str], correct: int, explanation: str | None = None, **kw: Any) -> T.Message:
        opts = [T.InputPollOption(text=o) for o in options]
        params = {"question": question, "options": opts, "type": "quiz", "correct_option_id": correct, "explanation": explanation}
        return await self._send("send_poll", kw.pop("chat_id", None), params, **kw)

    async def dice(self, emoji: str = "🎲", **kw: Any) -> T.Message:
        return await self._send("send_dice", kw.pop("chat_id", None), {"emoji": emoji}, **kw)

    async def action(self, action: str = "typing") -> None:
        """Show "typing…", "upload_photo"… status."""
        try:
            await self.bot.send_chat_action(self.chat_id, action)
        except Exception:  # noqa: BLE001
            pass

    async def forward(self, to_chat: int | str, message: T.Message | None = None) -> T.Message:
        m = message or self.message
        return await self.bot.forward_message(to_chat, m.chat.id, m.message_id)

    async def copy(self, to_chat: int | str, message: T.Message | None = None, **kw: Any) -> T.MessageId:
        """Copy the message without the "forwarded" header."""
        m = message or self.message
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
        raise ValueError("Tahrirlash uchun xabar topilmadi")

    async def edit(self, text: Any = None, *, buttons: Any = None, columns: Any = None, message: T.Message | None = None, preview: bool | None = None, **kw: Any) -> Any:
        """Edit the current message (the one whose button was pressed). Text or caption is detected automatically.

        Pass only ``buttons=`` to change the keyboard alone; ``buttons=[]`` removes it.
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
        return await self.edit(None, buttons=buttons if buttons is not None else [], columns=columns, message=message)

    async def respond(self, text: Any, **kw: Any) -> Any:
        """Smart reply: edits the message when a button was pressed, otherwise sends a new one."""
        if self.is_callback and self.message is not None and self.message.date:
            kw.pop("keyboard", None)
            try:
                return await self.edit(text, **{k: v for k, v in kw.items() if k in ("buttons", "columns", "preview")})
            except BadRequest:
                pass
        return await self.reply(text, **kw)

    async def delete(self, message: T.Message | int | None = None) -> bool:
        if isinstance(message, int):
            return await self.bot.safe_delete(self.chat_id, message)
        m = message or self.message
        if m is None:
            return False
        return await self.bot.safe_delete(m.chat.id, m.message_id)

    async def pin(self, message: T.Message | None = None, silent: bool = True) -> bool:
        m = message or self.message
        return await self.bot.pin_chat_message(m.chat.id, m.message_id, disable_notification=silent)

    async def unpin(self, message: T.Message | None = None) -> bool:
        m = message or self.message
        return await self.bot.unpin_chat_message(m.chat.id, message_id=m.message_id)

    async def react(self, emoji: str = "👍", big: bool = False, message: T.Message | None = None) -> bool:
        m = message or self.message
        return await self.bot.set_message_reaction(m.chat.id, m.message_id, reaction=[T.ReactionTypeEmoji(emoji=emoji)], is_big=big)

    # ================================================================== callbacks
    async def answer(self, text: Any = None, *, alert: bool = False, url: str | None = None, cache: int | None = None) -> Any:
        """Answer the pressed button (toast or alert). Outside callbacks it just sends ``text``."""
        if self.callback is None:
            return await self.reply(text) if text is not None else None
        if self._answered:
            return True
        self._answered = True
        try:
            return await self.bot.answer_callback_query(self.callback.id, text=None if text is None else str(text), show_alert=alert or None, url=url, cache_time=cache)
        except BadRequest:
            return False

    alert = lambda self, text: self.answer(text, alert=True)  # noqa: E731

    async def answer_inline(self, results: Sequence[Any], *, cache: int = 0, personal: bool = True, per_page: int = 50, button: Any = None) -> bool:
        """Answer an inline query. Long result lists are paginated automatically (``next_offset``).

        Items may be ``InlineQueryResult*`` objects or ``(title, text)`` / ``(title, text, description)`` tuples.
        """
        q = self.inline_query
        start = int(q.offset or 0) if (q.offset or "").isdigit() else 0
        page = list(results)[start:start + per_page]
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
        nxt = str(start + per_page) if start + per_page < len(results) else ""
        return await self.bot.answer_inline_query(q.id, built, cache_time=cache, is_personal=personal, next_offset=nxt, button=button)

    # ================================================================== files
    async def download(self, file: Any = None) -> bytes:
        """Download a file (``file_id``, media object, or the media of the current message)."""
        if file is None:
            m = self.message
            from .client import extract_file_id

            file = extract_file_id(m) if m else None
            if file is None:
                raise ValueError("Xabarda fayl yo'q")
        file_id = file if isinstance(file, str) else getattr(file, "file_id", None) or getattr(file[-1], "file_id")
        info = await self.bot.get_file(file_id)
        return await self.bot.client.download(info.file_path)

    async def save(self, path: str, file: Any = None) -> str:
        from pathlib import Path

        data = await self.download(file)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(data)
        return path

    # ================================================================== state
    def _state_key(self) -> str:
        return f"st:{self.chat_id}:{self.user_id}"

    async def set_state(self, state: str | None, **data: Any) -> None:
        """Remember where the user is: ``await ctx.set_state("ask_phone", step=1)``."""
        if state is None:
            await self.clear_state()
            return
        rec = await self.bot.storage.get(self._state_key()) or {}
        rec["s"] = state
        if data:
            rec.setdefault("d", {}).update(data)
        await self.bot.storage.set(self._state_key(), rec, ttl=self.bot.state_ttl)

    async def get_state(self) -> str | None:
        rec = await self.bot.storage.get(self._state_key())
        return rec.get("s") if rec else None

    async def state_data(self) -> FormResult:
        rec = await self.bot.storage.get(self._state_key()) or {}
        return FormResult(rec.get("d", {}))

    async def update_data(self, **data: Any) -> FormResult:
        rec = await self.bot.storage.get(self._state_key()) or {}
        rec.setdefault("d", {}).update(data)
        await self.bot.storage.set(self._state_key(), rec, ttl=self.bot.state_ttl)
        return FormResult(rec["d"])

    async def clear_state(self) -> None:
        await self.bot.storage.delete(self._state_key())

    # ================================================================== settings (toggles)
    async def setting(self, key: str, default: Any = False) -> Any:
        return await self.bot.get_setting(self.user_id or 0, key, default)

    async def set_setting(self, key: str, value: Any) -> None:
        await self.bot.set_setting(self.user_id or 0, key, value)

    # ================================================================== conversations
    async def _wait(self, kind: str, *, token: str | None = None, timeout: Any = None) -> "Context":
        seconds = parse_duration(timeout if timeout is not None else self.bot.ask_timeout)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        key: Any = (self.chat_id, self.user_id) if kind == "message" else token
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
        """Wait for the next message from this user in this chat. Returns its ``ctx``."""
        return await self._wait("message", timeout=timeout)

    async def ask(self, question: Any = None, type: Any = str, *, buttons: Any = None, keyboard: Any = None, columns: Any = None,
                  timeout: Any = None, retries: int = 5, silent_timeout: bool = False, **send_kw: Any) -> Any:
        """Ask and wait for the answer — no FSM classes needed.

        >>> name = await ctx.ask("Ismingiz?")
        >>> age = await ctx.ask("Yoshingiz?", int)
        >>> phone = await ctx.ask("Raqamingiz?", Phone)
        >>> size = await ctx.ask("O'lcham?", buttons=["S", "M", "L"])
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
        """Yes/No question with buttons. Returns ``True`` or ``False``."""
        token = short_id(8)
        buttons = [[Button(yes or self.t("nb.yes"), data=f"~c{token}:1"), Button(no or self.t("nb.no"), data=f"~c{token}:0")]]
        msg = await self.reply(question, buttons=buttons)
        try:
            ans = await self._wait("callback", token=token, timeout=timeout)
        except AskTimeout:
            await self._strip_buttons(msg)
            raise
        await ans.answer()
        result = ans.data.endswith(":1")
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
        """Pick one (or several with ``multiple=True``) of the options using inline buttons.

        ``options`` is a list of labels or a ``{label: value}`` dict. Returns the value(s).
        """
        if isinstance(options, dict):
            labels, values = list(options.keys()), list(options.values())
        else:
            labels = [str(o) for o in options]
            values = list(options)
        token = short_id(8)
        chosen: set[int] = {i for i, v in enumerate(values) if v in set(selected)}

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
            pick = ans.data.split(":", 1)[1]
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
        """Ask several questions in a row, validate each, return all answers.

        >>> data = await ctx.form(
        ...     name="Ismingiz?",
        ...     age=(int, "Yoshingiz?"),
        ...     phone=Phone("Telefon raqamingiz?"),
        ... )
        >>> data.name, data.age, data.phone
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
        """
        from .pagination import start_pagination

        return await start_pagination(self, items, per_page=per_page, title=title, render=render, columns=columns, numbered=numbered, ttl=ttl, empty=empty, edit=edit)

    async def menu(self, menu: Any, *, edit: bool | None = None) -> Any:
        """Show a multi-level ``Menu``; navigation and "Back" are handled for you."""
        return await menu.show(self, edit=self.is_callback if edit is None else edit)

    # ================================================================== payments (Telegram Stars)
    async def invoice(self, title: str, description: str, amount: int, *, payload: str = "nb", photo: str | None = None, **kw: Any) -> T.Message:
        """Ask for ``amount`` Telegram Stars (⭐). Handle success with ``@bot.paid``."""
        params = {
            "title": title, "description": description, "payload": payload, "currency": "XTR",
            "prices": [T.LabeledPrice(label=title, amount=int(amount))], "photo_url": photo,
        }
        return await self._send("send_invoice", kw.pop("chat_id", None), params, **kw)

    async def refund(self, charge_id: str | None = None, user_id: int | None = None) -> bool:
        if charge_id is None and self.message and self.message.successful_payment:
            charge_id = self.message.successful_payment.telegram_payment_charge_id
        return await self.bot.refund_star_payment(user_id or self.user_id, charge_id)

    # ================================================================== groups
    async def _member_target(self, user_id: int | None) -> int:
        if user_id is not None:
            return user_id
        m = self.message
        if m is not None and m.reply_to_message is not None and m.reply_to_message.from_ is not None:
            return m.reply_to_message.from_.id
        raise ValueError("Kimni? Foydalanuvchi xabariga reply qiling yoki user_id bering")

    async def ban(self, user_id: int | None = None, *, for_: Any = None, revoke: bool = False) -> bool:
        """Ban (the replied user by default). ``for_="1d"`` for a temporary ban."""
        uid = await self._member_target(user_id)
        until = int(time.time() + parse_duration(for_)) if for_ else None
        return await self.bot.ban_chat_member(self.chat_id, uid, until_date=until, revoke_messages=revoke or None)

    async def unban(self, user_id: int | None = None) -> bool:
        uid = await self._member_target(user_id)
        return await self.bot.unban_chat_member(self.chat_id, uid, only_if_banned=True)

    async def kick(self, user_id: int | None = None) -> bool:
        """Remove from the group but allow re-joining."""
        uid = await self._member_target(user_id)
        await self.bot.ban_chat_member(self.chat_id, uid)
        return await self.bot.unban_chat_member(self.chat_id, uid, only_if_banned=True)

    async def mute(self, duration: Any = "1h", user_id: int | None = None) -> bool:
        uid = await self._member_target(user_id)
        until = int(time.time() + (parse_duration(duration) or 0)) if duration else None
        perms = T.ChatPermissions(can_send_messages=False)
        return await self.bot.restrict_chat_member(self.chat_id, uid, perms, until_date=until)

    async def unmute(self, user_id: int | None = None) -> bool:
        uid = await self._member_target(user_id)
        perms = T.ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True,
            can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True,
        )
        return await self.bot.restrict_chat_member(self.chat_id, uid, perms)

    async def warn(self, reason: str = "", *, user_id: int | None = None, limit: int = 3, then: str = "ban", reset: Any = "30d") -> int:
        """Count warnings; after ``limit`` the user is banned (``then="ban"``), muted (``"mute"``) or kicked (``"kick"``)."""
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
        try:
            m = await self.bot.get_chat_member(chat, user_id or self.user_id)
        except (BadRequest, Forbidden):
            return False
        return m.status in ("creator", "administrator", "member") or (m.status == "restricted" and getattr(m, "is_member", False))

    async def is_chat_admin(self, user_id: int | None = None) -> bool:
        if self.is_private:
            return True
        try:
            m = await self.bot.get_chat_member(self.chat_id, user_id or self.user_id)
        except (BadRequest, Forbidden):
            return False
        return m.status in ("creator", "administrator")

    # ================================================================== misc
    def background(self, func: Callable[..., Awaitable[Any]], *args: Any, retries: int = 3, delay: Any = "2s", **kwargs: Any) -> asyncio.Task:
        """Run work after the handler returns, with automatic retries."""
        return self.bot.background(func, *args, retries=retries, delay=delay, **kwargs)

    async def notify_admins(self, text: Any, **kw: Any) -> None:
        await self.bot.notify_admins(text, **kw)
