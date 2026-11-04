"""Incoming files made easy: one ``Media`` object for photos, videos, documents, voice notes and the rest.

Example::

    @bot.on("photo", "video", "document")
    async def got_file(ctx: Context):
        media = ctx.media                      # Media(kind="photo", size=48213, ...)
        await ctx.reply(f"{media.kind}, {media.size_text}")
        path = await media.save("downloads/")   # downloads/<original name or unique id>.jpg
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .bot import Nicebot

#: Message fields that carry a file, in the order they are checked.
MEDIA_FIELDS = ("photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker")

#: Telegram's cloud Bot API refuses to download files bigger than this (20 MB).
DOWNLOAD_LIMIT = 20 * 1024 * 1024

_DEFAULT_EXT = {
    "photo": ".jpg", "video": ".mp4", "animation": ".mp4", "audio": ".mp3",
    "voice": ".ogg", "video_note": ".mp4", "sticker": ".webp", "document": "",
}
_VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_AUDIO_EXT = {".mp3", ".m4a", ".aac", ".flac", ".wav"}
_VOICE_EXT = {".ogg", ".oga", ".opus"}


def human_size(num: int | None) -> str:
    """Format a byte count for people.

    Example::

        human_size(1536)        # "1.5 KB"
        human_size(5_242_880)   # "5.0 MB"
    """
    if num is None:
        return "?"
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover


def parse_size(value: int | str | None) -> int | None:
    """Turn ``"10MB"``, ``"512 KB"`` or ``1048576`` into bytes.

    Example::

        parse_size("10MB")    # 10485760
        parse_size(2048)      # 2048
    """
    if value is None or isinstance(value, int):
        return value
    s = str(value).strip().upper().replace(" ", "")
    for unit, mult in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024), ("B", 1)):
        if s.endswith(unit):
            return int(float(s[: -len(unit)]) * mult)
    return int(float(s))


def guess_kind(file: Any) -> str:
    """Guess how a file should be sent (``photo``, ``video``, ``audio``, ``voice`` or ``document``) from its name.

    Example::

        guess_kind("cat.jpg")     # "photo"
        guess_kind("clip.MP4")    # "video"
        guess_kind("report.pdf")  # "document"
    """
    if isinstance(file, Media):
        return file.kind
    name = getattr(file, "filename", None) or getattr(file, "name", None) or (file if isinstance(file, str) else "")
    ext = Path(str(name)).suffix.lower()
    if ext in _PHOTO_EXT:
        return "photo"
    if ext in _VIDEO_EXT:
        return "video"
    if ext in _AUDIO_EXT:
        return "audio"
    if ext in _VOICE_EXT:
        return "voice"
    return "document"


class Media:
    """One received file, whatever its type. Get it with ``ctx.media`` or ``Media.of(message)``.

    Attributes:
        kind:            ``"photo"``, ``"video"``, ``"animation"``, ``"document"``, ``"audio"``,
                         ``"voice"``, ``"video_note"`` or ``"sticker"``
        file_id:         send the same file again without uploading: ``await ctx.photo(media.file_id)``
        file_unique_id:  stable id of the file (the same for every bot) — good as a database key
        size:            size in bytes (``None`` if Telegram did not say)
        name:            original file name (documents, audio, video) or ``None``
        mime:            MIME type such as ``"image/jpeg"`` or ``None``
        width, height:   pixels (photo, video, animation, sticker)
        duration:        seconds (video, audio, voice, video note)
        caption:         the message caption, if any
        raw:             the Telegram object (``PhotoSize``, ``Video``, ``Document``…)

    Example::

        @bot.on("document")
        async def doc(ctx: Context):
            m = ctx.media
            if m.size and m.size > 5 * 1024 * 1024:
                return await ctx.reply("Please send a file smaller than 5 MB")
            data = await m.download()                 # bytes
            path = await m.save("uploads/")           # uploads/report.pdf
            await ctx.reply(f"Saved {m.name} ({m.size_text}) to {path}")
    """

    __slots__ = ("kind", "file_id", "file_unique_id", "size", "name", "mime", "width", "height", "duration", "caption", "raw", "_bot")

    def __init__(self, kind: str, raw: Any, *, caption: str | None = None, bot: "Nicebot | None" = None):
        self.kind = kind
        self.raw = raw
        self.file_id: str = raw.file_id
        self.file_unique_id: str = raw.file_unique_id
        self.size: int | None = getattr(raw, "file_size", None)
        self.name: str | None = getattr(raw, "file_name", None)
        mime = getattr(raw, "mime_type", None)
        if mime is None and kind == "photo":
            mime = "image/jpeg"
        self.mime: str | None = mime
        self.width: int | None = getattr(raw, "width", None) or getattr(raw, "length", None)
        self.height: int | None = getattr(raw, "height", None) or getattr(raw, "length", None)
        self.duration: int | None = getattr(raw, "duration", None)
        self.caption = caption
        self._bot = bot

    @classmethod
    def of(cls, message: Any, bot: "Nicebot | None" = None) -> "Media | None":
        """Build a ``Media`` from a Telegram ``Message`` (``None`` if it has no file).

        Photos come in several sizes; the largest one is used.

        Example::

            media = Media.of(ctx.message.reply_to_message, ctx.bot)
            if media:
                await ctx.reply(media.kind)
        """
        if message is None:
            return None
        for name in MEDIA_FIELDS:
            val = getattr(message, name, None)
            if val:
                if isinstance(val, list):
                    val = max(val, key=lambda p: (p.width or 0) * (p.height or 0))
                return cls(name, val, caption=getattr(message, "caption", None), bot=bot)
        return None

    # ------------------------------------------------------------------ info
    @property
    def file_size(self) -> int | None:
        """Same as ``size`` (the Telegram field name).

        Example::

            ctx.media.file_size   # 48213
        """
        return self.size

    @property
    def size_text(self) -> str:
        """Human readable size.

        Example::

            ctx.media.size_text   # "2.4 MB"
        """
        return human_size(self.size)

    @property
    def extension(self) -> str:
        """File extension with the dot, guessed from the name, the MIME type or the kind.

        Example::

            ctx.media.extension   # ".pdf"
        """
        if self.name and Path(self.name).suffix:
            return Path(self.name).suffix.lower()
        if self.mime:
            ext = mimetypes.guess_extension(self.mime)
            if ext:
                return ".jpg" if ext == ".jpe" else ext
        return _DEFAULT_EXT.get(self.kind, "")

    @property
    def filename(self) -> str:
        """A safe file name to save under: the original name, or ``<file_unique_id><ext>``.

        Example::

            ctx.media.filename   # "invoice.pdf" or "AQADx1kx.jpg"
        """
        if self.name:
            return Path(self.name).name
        return f"{self.file_unique_id}{self.extension}"

    @property
    def is_image(self) -> bool:
        """``True`` for photos and image documents (``image/*``).

        Example::

            if not ctx.media.is_image:
                await ctx.reply("Please send a picture")
        """
        return self.kind == "photo" or bool(self.mime and self.mime.startswith("image/"))

    @property
    def can_download(self) -> bool:
        """``False`` when the file is bigger than the 20 MB cloud Bot API download limit.

        A local Bot API server (``Nicebot(api_url=...)``) has no such limit.

        Example::

            if not ctx.media.can_download:
                await ctx.reply("This file is too big for me to download")
        """
        if self._bot is not None and not self._bot.client.is_cloud:
            return True
        return self.size is None or self.size <= DOWNLOAD_LIMIT

    # ------------------------------------------------------------------ actions
    def _need_bot(self) -> "Nicebot":
        if self._bot is None:
            raise RuntimeError("This Media is not bound to a bot. Use ctx.media, or Media.of(message, bot).")
        return self._bot

    async def download(self) -> bytes:
        """Download the file into memory and return its bytes.

        Raises ``FileTooBig`` for files over 20 MB on the cloud Bot API.

        Example::

            data = await ctx.media.download()
            image = PIL.Image.open(io.BytesIO(data))
        """
        return await self._need_bot().download_file(self)

    async def save(self, path: str | Path | None = None, *, folder: str | Path = "downloads") -> str:
        """Save the file to disk (streamed, so big files do not fill the memory). Returns the path.

        * ``path=None`` → ``<folder>/<filename>`` (``downloads/`` by default)
        * ``path`` ending with ``/`` or an existing folder → the file keeps its name inside it
        * any other ``path`` is used as is; missing folders are created

        Example::

            await ctx.media.save()                     # downloads/photo_123.jpg
            await ctx.media.save("users/42/")          # users/42/AQADx1kx.jpg
            await ctx.media.save("avatars/42.jpg")     # exactly this path
        """
        return await self._need_bot().save_file(self, path, folder=folder)

    def input(self) -> str:
        """The value to pass when sending this file again (its ``file_id``).

        Example::

            await ctx.send_file(ctx.media.input(), kind=ctx.media.kind)
        """
        return self.file_id

    def __repr__(self) -> str:
        extra = f" name={self.name!r}" if self.name else ""
        return f"<Media {self.kind} {self.size_text}{extra} file_id={self.file_id[:12]}…>"
