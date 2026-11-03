"""Test your bot without Telegram.

    async def test_start():
        async with bot.test() as t:
            ali = t.user(first_name="Ali")
            await ali.send("/start")
            assert "Ismingiz" in t.last.text
            await ali.send("Ali")
            await ali.click("🛒 Buyurtma")
            assert t.last.text == "✅ Qabul qilindi"
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
    def __init__(self, method: str, params: dict[str, Any], result: Any = None):
        self.method, self.params, self.result = method, params, result

    def __repr__(self) -> str:
        return f"<Call {self.method} {self.params}>"


class SentMessage:
    """A message the bot sent (or its latest edited state)."""

    def __init__(self, data: dict[str, Any], method: str):
        self.data = data
        self.method = method

    @property
    def text(self) -> str | None:
        return self.data.get("text") if self.data.get("text") is not None else self.data.get("caption")

    @property
    def chat_id(self) -> int:
        return self.data["chat"]["id"]

    @property
    def message_id(self) -> int:
        return self.data["message_id"]

    @property
    def markup(self) -> dict[str, Any] | None:
        return self.data.get("reply_markup")

    @property
    def buttons(self) -> list[str]:
        """Texts of the inline buttons (flattened)."""
        m = self.markup or {}
        return [b["text"] for row in m.get("inline_keyboard", []) for b in row]

    @property
    def keyboard(self) -> list[str]:
        """Texts of the reply keyboard (flattened)."""
        m = self.reply_markup_raw or {}
        return [b["text"] if isinstance(b, dict) else b for row in m.get("keyboard", []) for b in row]

    @property
    def reply_markup_raw(self) -> dict[str, Any] | None:
        return self.data.get("_raw_markup")

    def __repr__(self) -> str:
        return f"<SentMessage {self.method} {self.text!r} buttons={self.buttons}>"


class TestUser:
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
        """Send a text (or any message fields) to the bot and wait until it reacts."""
        if text is not None:
            fields["text"] = text
        await self.s.feed({"message": self._message(**fields)})

    async def send_photo(self, caption: str | None = None, file_id: str = "test_photo") -> None:
        photo = [{"file_id": file_id, "file_unique_id": file_id + "_u", "width": 800, "height": 600}]
        await self.send(None, photo=photo, **({"caption": caption} if caption else {}))

    async def send_document(self, file_name: str = "file.pdf", file_id: str = "test_doc") -> None:
        await self.send(None, document={"file_id": file_id, "file_unique_id": file_id + "_u", "file_name": file_name})

    async def send_contact(self, phone: str = "+998901234567", own: bool = True) -> None:
        await self.send(None, contact={"phone_number": phone, "first_name": self.first_name, "user_id": self.id if own else self.id + 1})

    async def send_location(self, latitude: float = 40.1, longitude: float = 65.37) -> None:
        await self.send(None, location={"latitude": latitude, "longitude": longitude})

    async def send_album(self, count: int = 3) -> None:
        gid = f"album{next(self.s._ids)}"
        for i in range(count):
            photo = [{"file_id": f"p{i}", "file_unique_id": f"p{i}u", "width": 100, "height": 100}]
            await self.s.feed({"message": self._message(photo=photo, media_group_id=gid)}, settle=False)
        await asyncio.sleep(1.0)
        await self.s.settle()

    async def join(self, chat_id: int | None = None) -> None:
        """This user joins a group (service message)."""
        msg = self._message(new_chat_members=[self.tg])
        if chat_id is not None:
            msg["chat"] = {"id": chat_id, "type": "supergroup", "title": "Test group"}
        await self.s.feed({"message": msg})

    async def click(self, text: str | None = None, *, data: str | None = None, message: SentMessage | None = None) -> None:
        """Press an inline button by (part of) its text, or by raw callback ``data``."""
        target = message or self.s.last_with_buttons(self.chat_id)
        if target is None:
            raise AssertionError("Tugmali xabar topilmadi")
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
                raise AssertionError(f"Tugma topilmadi: {text!r}. Mavjud: {target.buttons}")
            if "callback_data" not in found:
                raise AssertionError(f"Bu tugma callback emas: {found}")
            data = found["callback_data"]
        cq = {"id": str(next(self.s._ids)), "from": self.tg, "chat_instance": "test", "data": data, "message": {k: v for k, v in target.data.items() if not k.startswith("_")}}
        await self.s.feed({"callback_query": cq})

    async def inline(self, query: str = "", offset: str = "") -> None:
        await self.s.feed({"inline_query": {"id": str(next(self.s._ids)), "from": self.tg, "query": query, "offset": offset}})


class TestSession:
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

    # ---------------------------------------------------------------- lifecycle
    async def __aenter__(self) -> "TestSession":
        self._orig = self.bot.client.request
        self.bot.client.request = self._request  # type: ignore[method-assign]
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
        await self.bot.close()
        self.bot.client.request = self._orig  # type: ignore[method-assign]
        self.bot.me = None

    def user(self, id: int | None = None, first_name: str = "Test", *, username: str | None = None, lang: str | None = "uz",
             chat_id: int | None = None, chat_type: str = "private", is_premium: bool = False) -> TestUser:
        return TestUser(self, id or next(self._ids) + 100_000, first_name, username, lang, chat_id, chat_type, is_premium)

    # ---------------------------------------------------------------- feeding
    async def feed(self, update: dict[str, Any], settle: bool = True) -> None:
        update = {"update_id": next(self._update_id), **update}
        task = asyncio.create_task(self.bot.feed(_enc.encode(update)))
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)
        if settle:
            await self.settle()

    async def settle(self) -> None:
        """Wait until the bot finished reacting (or is waiting for the user's next answer)."""
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
                out.append(self._new_message(p["chat_id"], photo=[{"file_id": fid, "file_unique_id": fid, "width": 1, "height": 1}], **({"caption": item["caption"]} if item.get("caption") else {})))
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
        if method == "exportChatInviteLink":
            return "https://t.me/+test"
        return True

    # ---------------------------------------------------------------- inspection
    def calls_of(self, method: str) -> list[Call]:
        return [c for c in self.calls if c.method == method]

    @property
    def messages(self) -> list[SentMessage]:
        """Every message the bot sent, in order, as their latest (edited) state."""
        seen: list[tuple[int, int]] = []
        for k in self._order:
            if k not in seen:
                seen.append(k)
        return [SentMessage(self._msgs[k], "message") for k in seen]

    @property
    def last(self) -> SentMessage:
        """The most recently sent or edited message."""
        if not self._order:
            raise AssertionError("Bot hali hech narsa yubormadi")
        return SentMessage(self._msgs[self._order[-1]], "message")

    def last_in(self, chat_id: int) -> SentMessage | None:
        for k in reversed(self._order):
            if k[0] == chat_id:
                return SentMessage(self._msgs[k], "message")
        return None

    def last_with_buttons(self, chat_id: int) -> SentMessage | None:
        for k in reversed(self._order):
            if k[0] == chat_id and self._msgs[k].get("reply_markup"):
                return SentMessage(self._msgs[k], "message")
        return None

    @property
    def texts(self) -> list[str]:
        return [m.text or "" for m in self.messages]

    @property
    def answers(self) -> list[dict[str, Any]]:
        """``answerCallbackQuery`` calls (toasts/alerts)."""
        return [c.params for c in self.calls_of("answerCallbackQuery")]

    def reset(self) -> None:
        self.calls.clear()
        self._order.clear()


def _sleeping_later(task: asyncio.Task) -> bool:
    coro = task.get_coro()
    name = getattr(coro, "__qualname__", "")
    return "later" in name or "runner" in name or "_run" in name or "loop" in name
