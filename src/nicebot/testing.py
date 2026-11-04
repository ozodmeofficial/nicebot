"""Test your bot without Telegram: fake users send messages, press buttons and upload files;
a fake Bot API records every call.

Example::

    async def test_register():
        async with bot.test() as t:
            ali = t.user(first_name="Ali")
            await ali.send("/start")
            assert t.last.text == "What is your name?"
            await ali.send("Ali")
            await ali.click("✅ Yes")
            assert t.last.text == "Welcome, Ali!"

            await ali.send_document("cv.pdf", content=b"%PDF-1.7 ...")   # files can be downloaded by the bot
            r = await t.api("/api/me", method="GET", user=ali)          # call a Mini App endpoint
            assert r.json["name"] == "Ali"
"""
from __future__ import annotations

import asyncio
import itertools
import time
from typing import TYPE_CHECKING, Any

import msgspec

from .client import decoder_for

if TYPE_CHECKING:
    from .bot import Nicebot

_SEND_MEDIA = {"sendPhoto": "photo", "sendVideo": "video", "sendDocument": "document", "sendAudio": "audio", "sendVoice": "voice", "sendAnimation": "animation", "sendSticker": "sticker", "sendVideoNote": "video_note"}
_enc = msgspec.json.Encoder()


class Call:
    """One recorded Bot API call: ``method``, ``params`` and the fake ``result``.

    Example::

        call = t.calls_of("sendPhoto")[0]
        assert call.params["caption"] == "Menu"
    """

    def __init__(self, method: str, params: dict[str, Any], result: Any = None):
        self.method, self.params, self.result = method, params, result

    def __repr__(self) -> str:
        return f"<Call {self.method} {self.params}>"


class SentMessage:
    """A message the bot sent (in its latest, possibly edited, state).

    Example::

        msg = t.last
        assert msg.text == "Choose:" and msg.buttons == ["A", "B"]
    """

    def __init__(self, data: dict[str, Any], method: str):
        self.data = data
        self.method = method

    @property
    def text(self) -> str | None:
        """Text or caption.

        Example::

            assert t.last.text == "Done"
        """
        return self.data.get("text") if self.data.get("text") is not None else self.data.get("caption")

    @property
    def chat_id(self) -> int:
        """Chat the message was sent to.

        Example::

            assert t.last.chat_id == ali.chat_id
        """
        return self.data["chat"]["id"]

    @property
    def message_id(self) -> int:
        """Message id.

        Example::

            t.last.message_id
        """
        return self.data["message_id"]

    @property
    def markup(self) -> dict[str, Any] | None:
        """Raw inline keyboard (dict) or ``None``.

        Example::

            t.last.markup["inline_keyboard"][0][0]["url"]
        """
        return self.data.get("reply_markup")

    @property
    def buttons(self) -> list[str]:
        """Texts of the inline buttons (flattened).

        Example::

            assert t.last.buttons == ["Yes", "No"]
        """
        m = self.markup or {}
        return [b["text"] for row in m.get("inline_keyboard", []) for b in row]

    @property
    def keyboard(self) -> list[str]:
        """Texts of the reply keyboard (flattened).

        Example::

            assert t.last.keyboard == ["🛍 Shop", "📞 Contact"]
        """
        m = self.reply_markup_raw or {}
        return [b["text"] if isinstance(b, dict) else b for row in m.get("keyboard", []) for b in row]

    @property
    def reply_markup_raw(self) -> dict[str, Any] | None:
        """Raw reply keyboard (dict) or ``None``.

        Example::

            t.last.reply_markup_raw["resize_keyboard"]
        """
        return self.data.get("_raw_markup")

    @property
    def media_kind(self) -> str | None:
        """``"photo"``, ``"video"``, ``"document"``… if the message carries a file.

        Example::

            assert t.last.media_kind == "photo"
        """
        for k in ("photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker"):
            if k in self.data:
                return k
        return None

    def __repr__(self) -> str:
        return f"<SentMessage {self.method} {self.text!r} buttons={self.buttons}>"


class TestUser:
    """A fake Telegram user created with ``t.user()``. Sends messages, files and button presses to the bot.

    Example::

        ali = t.user(first_name="Ali", lang="en")
        await ali.send("/start")
        await ali.click("Buy")
        await ali.send_photo(caption="my cat", content=jpeg_bytes)
    """

    def __init__(self, session: "TestSession", id: int, first_name: str, username: str | None, lang: str | None, chat_id: int | None, chat_type: str, is_premium: bool):
        self.s = session
        self.id = id
        self.first_name = first_name
        self.username = username
        self.lang = lang
        self.chat_id = chat_id if chat_id is not None else id
        self.chat_type = chat_type

    @property
    def tg(self) -> dict[str, Any]:
        """The user as a Telegram ``User`` dict.

        Example::

            ali.tg   # {"id": 100001, "is_bot": False, "first_name": "Ali"}
        """
        d: dict[str, Any] = {"id": self.id, "is_bot": False, "first_name": self.first_name}
        if self.username:
            d["username"] = self.username
        if self.lang:
            d["language_code"] = self.lang
        return d

    def _chat(self) -> dict[str, Any]:
        if self.chat_type == "private":
            return {"id": self.chat_id, "type": "private", "first_name": self.first_name}
        return {"id": self.chat_id, "type": self.chat_type, "title": "Test group"}

    def _message(self, **fields: Any) -> dict[str, Any]:
        mid = next(self.s._ids)
        msg = {"message_id": mid, "date": int(time.time()), "chat": self._chat(), "from": self.tg, **fields}
        text = fields.get("text")
        if text and text.startswith("/"):
            cmd = text.split()[0]
            msg["entities"] = [{"type": "bot_command", "offset": 0, "length": len(cmd)}]
        return msg

    async def send(self, text: str | None = None, **fields: Any) -> None:
        """Send a text (or any message fields) to the bot and wait until it reacts.

        Example::

            await ali.send("/start")
            await ali.send(None, dice={"emoji": "🎲", "value": 6})
        """
        if text is not None:
            fields["text"] = text
        await self.s.feed({"message": self._message(**fields)})

    def _file(self, file_id: str | None, content: bytes | None, size: int | None, prefix: str) -> dict[str, Any]:
        fid = file_id or f"{prefix}{next(self.s._ids)}"
        if content is not None:
            self.s.files[fid] = content
        d: dict[str, Any] = {"file_id": fid, "file_unique_id": fid + "_u"}
        real = size if size is not None else (len(content) if content is not None else None)
        if real is not None:
            d["file_size"] = real
        return d

    async def send_photo(self, caption: str | None = None, file_id: str | None = None, *, content: bytes | None = None, size: int | None = None) -> None:
        """Send a photo. ``content`` is what the bot gets when it downloads it.

        Example::

            await ali.send_photo("my cat", content=b"\xff\xd8...")
        """
        photo = [{**self._file(file_id or "test_photo", content, size, "photo"), "width": 800, "height": 600}]
        await self.send(None, photo=photo, **({"caption": caption} if caption else {}))

    async def send_document(self, file_name: str = "file.pdf", file_id: str | None = None, *, content: bytes | None = None, size: int | None = None,
                            mime: str | None = None, caption: str | None = None) -> None:
        """Send a document.

        Example::

            await ali.send_document("report.pdf", content=b"%PDF...", mime="application/pdf")
        """
        doc = {**self._file(file_id or "test_doc", content, size, "doc"), "file_name": file_name}
        import mimetypes

        doc["mime_type"] = mime or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        await self.send(None, document=doc, **({"caption": caption} if caption else {}))

    async def send_video(self, caption: str | None = None, file_id: str | None = None, *, content: bytes | None = None, size: int | None = None, duration: int = 5) -> None:
        """Send a video.

        Example::

            await ali.send_video(size=30 * 1024 * 1024)    # too big to download on the cloud API
        """
        video = {**self._file(file_id, content, size, "video"), "width": 640, "height": 360, "duration": duration, "mime_type": "video/mp4"}
        await self.send(None, video=video, **({"caption": caption} if caption else {}))

    async def send_voice(self, file_id: str | None = None, *, content: bytes | None = None, duration: int = 3) -> None:
        """Send a voice message.

        Example::

            await ali.send_voice(content=b"OggS...")
        """
        await self.send(None, voice={**self._file(file_id, content, None, "voice"), "duration": duration, "mime_type": "audio/ogg"})

    async def send_audio(self, file_id: str | None = None, *, content: bytes | None = None, title: str = "Song", duration: int = 180) -> None:
        """Send a music file.

        Example::

            await ali.send_audio(title="My song")
        """
        await self.send(None, audio={**self._file(file_id, content, None, "audio"), "duration": duration, "title": title, "mime_type": "audio/mpeg"})

    async def send_web_app_data(self, data: Any, button_text: str = "Open") -> None:
        """Simulate ``Telegram.WebApp.sendData(...)`` from a reply-keyboard Mini App.

        Example::

            await ali.send_web_app_data({"items": [1, 2]})
        """
        import json as _json

        raw = data if isinstance(data, str) else _json.dumps(data)
        await self.send(None, web_app_data={"data": raw, "button_text": button_text})

    async def send_contact(self, phone: str = "+998901234567", own: bool = True) -> None:
        """Share a phone contact (``own=False`` sends somebody else's).

        Example::

            await ali.send_contact("+998901234567")
        """
        await self.send(None, contact={"phone_number": phone, "first_name": self.first_name, "user_id": self.id if own else self.id + 1})

    async def send_location(self, latitude: float = 40.1, longitude: float = 65.37) -> None:
        """Share a location.

        Example::

            await ali.send_location(41.31, 69.28)
        """
        await self.send(None, location={"latitude": latitude, "longitude": longitude})

    async def send_album(self, count: int = 3) -> None:
        """Send ``count`` photos as one album (media group).

        Example::

            await ali.send_album(3)
        """
        gid = f"album{next(self.s._ids)}"
        for i in range(count):
            photo = [{"file_id": f"p{i}", "file_unique_id": f"p{i}u", "width": 100, "height": 100}]
            await self.s.feed({"message": self._message(photo=photo, media_group_id=gid)}, settle=False)
        await asyncio.sleep(1.0)
        await self.s.settle()

    async def join(self, chat_id: int | None = None) -> None:
        """Join a group (service message).

        Example::

            await ali.join(chat_id=-100123)
        """
        msg = self._message(new_chat_members=[self.tg])
        if chat_id is not None:
            msg["chat"] = {"id": chat_id, "type": "supergroup", "title": "Test group"}
        await self.s.feed({"message": msg})

    async def click(self, text: str | None = None, *, data: str | None = None, message: SentMessage | None = None) -> None:
        """Press an inline button by (part of) its text, or by raw ``data``.

        Example::

            await ali.click("✅ Yes")
            await ali.click(data="buy:5")
        """
        target = message or self.s.last_with_buttons(self.chat_id)
        if target is None:
            raise AssertionError("No message with inline buttons was found in this chat")
        if data is None:
            found = None
            for row in (target.markup or {}).get("inline_keyboard", []):
                for b in row:
                    if b["text"] == text:
                        found = b
            if found is None:
                for row in (target.markup or {}).get("inline_keyboard", []):
                    for b in row:
                        if text and text in b["text"] and found is None:
                            found = b
            if found is None:
                raise AssertionError(f"Button {text!r} not found. Available: {target.buttons}")
            if "callback_data" not in found:
                raise AssertionError(f"This button has no callback data (url/webapp/copy?): {found}")
            data = found["callback_data"]
        cq = {"id": str(next(self.s._ids)), "from": self.tg, "chat_instance": "test", "data": data, "message": {k: v for k, v in target.data.items() if not k.startswith("_")}}
        await self.s.feed({"callback_query": cq})

    async def inline(self, query: str = "", offset: str = "") -> None:
        """Type ``@your_bot <query>`` (an inline query).

        Example::

            await ali.inline("book")
            assert t.calls_of("answerInlineQuery")
        """
        await self.s.feed({"inline_query": {"id": str(next(self.s._ids)), "from": self.tg, "query": query, "offset": offset}})


class TestSession:
    """The fake Telegram created by ``async with bot.test() as t:``.

    Attributes: ``calls`` (every API call), ``files`` (file_id → bytes for downloads), ``blocked`` (user ids
    that blocked the bot), ``fail_next`` (method → exception raised once), ``chat_members``.

    Example::

        async with bot.test() as t:
            ali = t.user(first_name="Ali")
            await ali.send("/start")
            assert t.texts == ["Hello, Ali!"]
            assert t.calls_of("sendMessage")[0].params["chat_id"] == ali.id
    """

    __test__ = False  # not a pytest class

    def __init__(self, bot: "Nicebot", *, member_status: str = "member", bot_username: str = "test_bot", timeout: float = 3.0):
        self.bot = bot
        self.calls: list[Call] = []
        self.member_status = member_status
        self.bot_username = bot_username
        self.timeout = timeout
        self._ids = itertools.count(1000)
        self._msgs: dict[tuple[int, int], dict[str, Any]] = {}
        self._order: list[tuple[int, int]] = []
        self._update_id = itertools.count(1)
        self._inflight: set[asyncio.Task] = set()
        self._orig = None
        self.chat_members: dict[tuple[int, int], str] = {}
        self.blocked: set[int] = set()  # users who "blocked" the bot → 403 on send
        self.fail_next: dict[str, Exception] = {}  # method -> error raised once
        self.files: dict[str, bytes] = {}  # file_id -> content returned by downloads
        self._orig_dl: Any = None

    # ---------------------------------------------------------------- lifecycle
    async def __aenter__(self) -> "TestSession":
        self._orig = self.bot.client.request
        self.bot.client.request = self._request  # type: ignore[method-assign]
        self._orig_dl = (self.bot.client.download, self.bot.client.download_to)
        self.bot.client.download = self._download  # type: ignore[method-assign]
        self.bot.client.download_to = self._download_to  # type: ignore[method-assign]
        await self.bot.setup()
        self.calls.clear()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.settle()
        for t in list(self._inflight):
            t.cancel()
        for fut, _ in list(self.bot._waiters.values()):
            if not fut.done():
                fut.cancel()
        await self.bot.shutdown()
        self.bot.client.request = self._orig  # type: ignore[method-assign]
        self.bot.client.download, self.bot.client.download_to = self._orig_dl  # type: ignore[method-assign]
        self.bot.me = None

    def user(self, id: int | None = None, first_name: str = "Test", *, username: str | None = None, lang: str | None = "uz",
             chat_id: int | None = None, chat_type: str = "private", is_premium: bool = False) -> TestUser:
        """Create a fake user (``chat_type="supergroup"`` + ``chat_id`` puts them in a group).

        Example::

            ali = t.user(first_name="Ali", lang="en")
            member = t.user(chat_id=-100123, chat_type="supergroup")
        """
        return TestUser(self, id or next(self._ids) + 100_000, first_name, username, lang, chat_id, chat_type, is_premium)

    # ---------------------------------------------------------------- feeding
    async def feed(self, update: dict[str, Any], settle: bool = True) -> None:
        """Send a raw update dict to the bot (``update_id`` is added).

        Example::

            await t.feed({"message": {...}})
        """
        update = {"update_id": next(self._update_id), **update}
        task = asyncio.create_task(self.bot.feed(_enc.encode(update)))
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)
        if settle:
            await self.settle()

    async def settle(self) -> None:
        """Wait until the bot finished reacting (or is waiting for the user's next answer).

        Example::

            await t.settle()
        """
        deadline = time.monotonic() + self.timeout
        quiet = 0
        last = len(self.calls)
        while time.monotonic() < deadline:
            pending = [t for t in self._inflight | self.bot._tasks if not t.done() and not getattr(t, "_nb_later", False)]
            if not pending:
                await asyncio.sleep(0)
                if not [t for t in self._inflight | self.bot._tasks if not t.done() and not getattr(t, "_nb_later", False)]:
                    return
            await asyncio.sleep(0.01)
            waiting = any(not f.done() for f, _ in self.bot._waiters.values())
            if len(self.calls) == last:
                quiet += 1
            else:
                quiet, last = 0, len(self.calls)
            if waiting and quiet >= 5:
                return
            if quiet >= 40 and all(_sleeping_later(t) for t in pending):
                return

    # ---------------------------------------------------------------- fake API
    def _bot_user(self) -> dict[str, Any]:
        return {"id": 1, "is_bot": True, "first_name": "Test Bot", "username": self.bot_username}

    def _new_message(self, chat_id: Any, **fields: Any) -> dict[str, Any]:
        cid = int(chat_id) if str(chat_id).lstrip("-").isdigit() else -1
        mid = next(self._ids)
        chat = {"id": cid, "type": "private" if cid > 0 else "supergroup"}
        if cid <= 0:
            chat["title"] = "Test group"
        msg = {"message_id": mid, "date": int(time.time()), "chat": chat, "from": self._bot_user(), **fields}
        self._msgs[(cid, mid)] = msg
        self._order.append((cid, mid))
        return msg

    def _markup(self, params: dict[str, Any], msg: dict[str, Any]) -> None:
        rm = params.get("reply_markup")
        if rm is None:
            return
        if "inline_keyboard" in rm:
            msg["reply_markup"] = rm
        else:
            msg["_raw_markup"] = rm

    async def _request(self, method: str, params: dict[str, Any] | None = None, returns: Any = "Any", *, timeout: float | None = None) -> Any:
        payload, files, cache_keys = await self.bot.client._prepare(params or {})
        for name, f in files.items():
            payload[name] = f"<upload:{f.filename}>"
        if method in self.fail_next:
            self.calls.append(Call(method, payload, None))
            raise self.fail_next.pop(method)
        if method.startswith(("send", "copy", "forward")) and str(payload.get("chat_id")).lstrip("-").isdigit() and int(payload["chat_id"]) in self.blocked:
            from .errors import make_error

            self.calls.append(Call(method, payload, None))
            raise make_error(method, "Forbidden: bot was blocked by the user", 403, None)
        result = self._fake(method, payload)
        self.calls.append(Call(method, payload, result))
        decoded = decoder_for(returns).decode(_enc.encode(result))
        await self.bot.client.remember_files(cache_keys, decoded)
        return decoded

    def _fake(self, method: str, p: dict[str, Any]) -> Any:
        if method == "getMe":
            return self._bot_user()
        if method == "getUpdates":
            return []
        if method == "sendMessage":
            msg = self._new_message(p["chat_id"], text=p.get("text", ""))
            self._markup(p, msg)
            return msg
        if method in _SEND_MEDIA:
            kind = _SEND_MEDIA[method]
            fid = f"fid_{next(self._ids)}"
            media: Any = {"file_id": fid, "file_unique_id": fid + "u"}
            if kind == "photo":
                media = [{**media, "width": 100, "height": 100}]
            elif kind in ("video", "animation"):
                media.update(width=100, height=100, duration=1)
            elif kind in ("audio", "voice"):
                media["duration"] = 1
            elif kind == "video_note":
                media.update(length=100, duration=1)
            elif kind == "sticker":
                media.update(type="regular", width=100, height=100, is_animated=False, is_video=False)
            msg = self._new_message(p["chat_id"], **{kind: media}, **({"caption": p["caption"]} if p.get("caption") else {}))
            self._markup(p, msg)
            return msg
        if method == "sendMediaGroup":
            out = []
            for item in p["media"]:
                fid = f"fid_{next(self._ids)}"
                kind = item.get("type", "photo")
                media: Any = [{"file_id": fid, "file_unique_id": fid, "width": 1, "height": 1}] if kind == "photo" else {"file_id": fid, "file_unique_id": fid}
                if kind == "video":
                    media.update(width=1, height=1, duration=1)
                elif kind == "audio":
                    media["duration"] = 1
                out.append(self._new_message(p["chat_id"], **{kind: media}, **({"caption": item["caption"]} if item.get("caption") else {})))
            return out
        if method in ("sendLocation", "sendVenue", "sendContact", "sendPoll", "sendDice", "sendInvoice"):
            msg = self._new_message(p["chat_id"], text=f"<{method}>")
            self._markup(p, msg)
            return msg
        if method in ("editMessageText", "editMessageCaption", "editMessageReplyMarkup"):
            key = (int(p.get("chat_id", 0)), int(p.get("message_id", 0)))
            msg = self._msgs.get(key)
            if msg is None:
                return True
            if method == "editMessageText":
                msg["text"] = p["text"]
            elif method == "editMessageCaption":
                msg["caption"] = p.get("caption")
            if "reply_markup" in p:
                msg["reply_markup"] = p["reply_markup"]
            else:
                msg.pop("reply_markup", None)
            self._order.append(key)
            return msg
        if method == "copyMessage":
            src = self._msgs.get((int(p["from_chat_id"]), int(p["message_id"])))
            msg = self._new_message(p["chat_id"], text=(src or {}).get("text", "<copy>"))
            return {"message_id": msg["message_id"]}
        if method == "forwardMessage":
            return self._new_message(p["chat_id"], text="<forward>")
        if method == "getChatMember":
            status = self.chat_members.get((int(p["chat_id"]) if str(p["chat_id"]).lstrip("-").isdigit() else 0, int(p["user_id"])), self.member_status)
            m: dict[str, Any] = {"status": status, "user": {"id": int(p["user_id"]), "is_bot": False, "first_name": "User"}}
            if status == "administrator":
                m.update(can_be_edited=False, is_anonymous=False, can_manage_chat=True, can_delete_messages=True, can_manage_video_chats=True,
                         can_restrict_members=True, can_promote_members=False, can_change_info=True, can_invite_users=True, can_post_stories=False,
                         can_edit_stories=False, can_delete_stories=False)
            if status == "creator":
                m.update(is_anonymous=False)
            if status == "kicked":
                m.update(until_date=0)
            if status == "restricted":
                m.update(is_member=True, can_send_messages=False, can_send_audios=False, can_send_documents=False, can_send_photos=False, can_send_videos=False,
                         can_send_video_notes=False, can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False, can_add_web_page_previews=False,
                         can_change_info=False, can_invite_users=False, can_pin_messages=False, can_manage_topics=False, until_date=0)
            return m
        if method == "getChat":
            cid = p["chat_id"]
            return {"id": int(cid) if str(cid).lstrip("-").isdigit() else -100, "type": "channel", "title": "Kanal", "accent_color_id": 0, "max_reaction_count": 11, "accepted_gift_types": {"unlimited_gifts": True, "limited_gifts": True, "unique_gifts": True, "premium_subscription": True}, "invite_link": "https://t.me/+test"}
        if method == "getFile":
            return {"file_id": p["file_id"], "file_unique_id": p["file_id"], "file_path": f"files/{p['file_id']}"}
        if method == "editMessageMedia":
            key = (int(p.get("chat_id", 0)), int(p.get("message_id", 0)))
            msg = self._msgs.get(key)
            if msg is None:
                return True
            media = p["media"]
            kind = media.get("type", "photo")
            for k in ("photo", "video", "animation", "document", "audio"):
                msg.pop(k, None)
            fid = f"fid_{next(self._ids)}"
            msg[kind] = [{"file_id": fid, "file_unique_id": fid, "width": 1, "height": 1}] if kind == "photo" else {"file_id": fid, "file_unique_id": fid}
            if media.get("caption") is not None:
                msg["caption"] = media["caption"]
            if "reply_markup" in p:
                msg["reply_markup"] = p["reply_markup"]
            self._order.append(key)
            return msg
        if method == "answerWebAppQuery":
            return {"inline_message_id": "test_inline"}
        if method == "exportChatInviteLink":
            return "https://t.me/+test"
        return True

    async def _download(self, file_path: str) -> bytes:
        fid = file_path.rsplit("/", 1)[-1]
        return self.files.get(fid, f"test-file:{fid}".encode())

    async def _download_to(self, file_path: str, dest: Any, chunk_size: int = 0) -> None:
        from pathlib import Path

        Path(dest).write_bytes(await self._download(file_path))

    async def api(self, path: str, json: Any = None, *, method: str = "POST", user: TestUser | None = None, headers: dict[str, str] | None = None,
                  data: Any = None, auth: bool = True) -> "ApiResponse":
        """Call a Mini App endpoint (``@bot.api``) as ``user`` would from inside Telegram (initData is signed for you).

        Example::

            r = await t.api("/api/order", {"items": [1, 2]}, user=ali)
            assert r.status == 200 and r.json["ok"]
        """
        from aiohttp.test_utils import TestClient, TestServer

        from .server import build_app, sign_init_data

        h = dict(headers or {})
        if auth and user is not None:
            h["Authorization"] = "tma " + sign_init_data({"user": user.tg, "query_id": "test_query"}, self.bot.token)
        client = TestClient(TestServer(build_app(self.bot)))
        await client.start_server()
        try:
            kw: dict[str, Any] = {"headers": h}
            if json is not None:
                kw["json"] = json
            if data is not None:
                kw["data"] = data
            resp = await client.request(method, path, **kw)
            body = await resp.read()
            await self.settle()
            return ApiResponse(resp.status, body, dict(resp.headers))
        finally:
            await client.close()

    # ---------------------------------------------------------------- inspection
    def calls_of(self, method: str) -> list[Call]:
        """Every recorded call of one Bot API method.

        Example::

            assert len(t.calls_of("sendPhoto")) == 1
        """
        return [c for c in self.calls if c.method == method]

    @property
    def messages(self) -> list[SentMessage]:
        """Every message the bot sent, in order, in their latest (edited) state.

        Example::

            assert [m.text for m in t.messages] == ["Hi", "Bye"]
        """
        seen: list[tuple[int, int]] = []
        for k in self._order:
            if k not in seen:
                seen.append(k)
        return [SentMessage(self._msgs[k], "message") for k in seen]

    @property
    def last(self) -> SentMessage:
        """The most recently sent or edited message.

        Example::

            assert t.last.text == "Welcome!"
        """
        if not self._order:
            raise AssertionError("The bot has not sent anything yet")
        return SentMessage(self._msgs[self._order[-1]], "message")

    def last_in(self, chat_id: int) -> SentMessage | None:
        """The latest message in one chat (``None`` if there is none).

        Example::

            assert t.last_in(ali.chat_id).text == "Done"
        """
        for k in reversed(self._order):
            if k[0] == chat_id:
                return SentMessage(self._msgs[k], "message")
        return None

    def last_with_buttons(self, chat_id: int) -> SentMessage | None:
        """The latest message with inline buttons in a chat.

        Example::

            assert t.last_with_buttons(ali.chat_id).buttons == ["Yes", "No"]
        """
        for k in reversed(self._order):
            if k[0] == chat_id and self._msgs[k].get("reply_markup"):
                return SentMessage(self._msgs[k], "message")
        return None

    @property
    def texts(self) -> list[str]:
        """Texts/captions of every sent message.

        Example::

            assert "Done" in t.texts
        """
        return [m.text or "" for m in self.messages]

    @property
    def answers(self) -> list[dict[str, Any]]:
        """``answerCallbackQuery`` calls (button toasts/alerts).

        Example::

            assert t.answers[-1]["text"] == "Added"
        """
        return [c.params for c in self.calls_of("answerCallbackQuery")]

    def reset(self) -> None:
        """Forget recorded calls and messages.

        Example::

            t.reset()
        """
        self.calls.clear()
        self._order.clear()


class ApiResponse:
    """The answer of ``t.api(...)``: ``status``, ``body`` (bytes), ``json`` (decoded) and ``headers``.

    Example::

        r = await t.api("/api/me", method="GET", user=ali)
        assert r.status == 200
        print(r.json)
    """

    def __init__(self, status: int, body: bytes, headers: dict[str, str]):
        self.status = status
        self.body = body
        self.headers = headers

    @property
    def json(self) -> Any:
        """The body decoded as JSON (``None`` if it is not JSON).

        Example::

            r.json["ok"]
        """
        import json as _json

        try:
            return _json.loads(self.body or b"null")
        except ValueError:
            return None

    @property
    def text(self) -> str:
        """The body as text.

        Example::

            r.text
        """
        return self.body.decode(errors="replace")

    def __repr__(self) -> str:
        return f"<ApiResponse {self.status} {self.body[:80]!r}>"


def _sleeping_later(task: asyncio.Task) -> bool:
    coro = task.get_coro()
    name = getattr(coro, "__qualname__", "")
    return "later" in name or "runner" in name or "_run" in name or "loop" in name
