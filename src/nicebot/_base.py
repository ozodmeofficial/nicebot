"""Base classes shared by generated types."""
from __future__ import annotations

import io
import mimetypes
import os
from pathlib import Path
from typing import Any

import msgspec


class TelegramObject(msgspec.Struct, kw_only=True, omit_defaults=True, dict=True):
    """Base of every Telegram type. Fast (msgspec), typed, and convertible to dict."""

    def to_dict(self) -> dict[str, Any]:
        return msgspec.to_builtins(self)

    def __getitem__(self, item: str) -> Any:  # dict-like access for convenience
        return getattr(self, item)


class InputFile:
    """A file to upload: local path, bytes, file-like object or URL.

    >>> InputFile("photo.jpg")
    >>> InputFile(b"...", filename="report.pdf")
    >>> InputFile.from_url("https://example.com/a.png")   # Telegram downloads it
    """

    __slots__ = ("data", "filename", "url", "path")

    def __init__(self, data: str | os.PathLike | bytes | io.IOBase, filename: str | None = None):
        self.url: str | None = None
        self.path: Path | None = None
        if isinstance(data, (str, os.PathLike)):
            self.path = Path(data)
            self.data = None
            self.filename = filename or self.path.name
        elif isinstance(data, (bytes, bytearray)):
            self.data = bytes(data)
            self.filename = filename or "file"
        else:
            self.data = data.read()
            self.filename = filename or Path(getattr(data, "name", "file")).name

    @classmethod
    def from_url(cls, url: str) -> "InputFile":
        obj = cls.__new__(cls)
        obj.url, obj.data, obj.path, obj.filename = url, None, None, url.rsplit("/", 1)[-1]
        return obj

    def read(self) -> bytes:
        if self.data is not None:
            return self.data
        assert self.path is not None
        return self.path.read_bytes()

    @property
    def mime(self) -> str:
        return mimetypes.guess_type(self.filename)[0] or "application/octet-stream"

    @property
    def cache_key(self) -> str | None:
        """Stable key used by the file_id cache (local paths only)."""
        if self.path is None:
            return None
        try:
            st = self.path.stat()
        except OSError:
            return None
        return f"{self.path.resolve()}:{st.st_size}:{int(st.st_mtime)}"

    def __repr__(self) -> str:
        return f"InputFile({self.filename!r})"
