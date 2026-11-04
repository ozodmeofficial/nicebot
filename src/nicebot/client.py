"""HTTP layer: one pooled aiohttp session, msgspec encoding/decoding, smart retries, uploads and downloads.

Example::

    data = await bot.client.download((await bot.get_file(file_id)).file_path)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import aiohttp
import msgspec

from . import types as _types
from ._base import InputFile
from .errors import NetworkError, RetryAfter, ServerError, TelegramError, make_error

log = logging.getLogger("nicebot.client")

_NS: dict[str, Any] = {**vars(_types), "Any": Any, "Raw": msgspec.Raw, "list": list, "bool": bool, "int": int, "str": str, "float": float}
_DECODERS: dict[str, msgspec.json.Decoder] = {}


class _Envelope(msgspec.Struct):
    ok: bool
    result: msgspec.Raw = msgspec.Raw(b"null")
    description: str = ""
    error_code: int = 0
    parameters: dict | None = None


_ENVELOPE = msgspec.json.Decoder(_Envelope)
_ENCODER = msgspec.json.Encoder()


def decoder_for(returns: Any) -> msgspec.json.Decoder:
    """A cached msgspec decoder for a return type such as ``"Message"`` or ``"list[Update]"``.

    Example::

        msg = decoder_for("Message").decode(raw_json)
    """
    key = returns if isinstance(returns, str) else repr(returns)
    dec = _DECODERS.get(key)
    if dec is None:
        typ = eval(returns, _NS) if isinstance(returns, str) else returns  # noqa: S307 - generated, trusted
        dec = _DECODERS[key] = msgspec.json.Decoder(typ)
    return dec


_FILE_FIELDS = ("photo", "document", "video", "audio", "voice", "animation", "sticker", "video_note")


def extract_file_id(message: Any) -> str | None:
    """The ``file_id`` of the media inside a sent ``Message`` (used by the upload cache).

    Example::

        extract_file_id(await ctx.photo("a.jpg"))   # "AgACAgIAAxk..."
    """
    for name in _FILE_FIELDS:
        val = getattr(message, name, None)
        if val:
            if isinstance(val, list):
                val = val[-1]
            return getattr(val, "file_id", None)
    return None


class Client:
    """Talks to the Bot API over one pooled aiohttp session. Handles flood-wait (429), 5xx and network errors with retries,
    uploads files, and remembers ``file_id`` of uploaded local files so they are never uploaded twice.

    You normally use it through the bot (``bot.client``).

    Example::

        client = Client("123456:ABC...")
        me = await client.request("getMe", returns="User")
        await client.close()
    """

    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.telegram.org",
        test_server: bool = False,
        timeout: float = 30.0,
        retries: int = 3,
        flood_wait_max: float = 60.0,
        file_cache: Any = None,
    ):
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.test_server = test_server
        self.timeout = timeout
        self.retries = retries
        self.flood_wait_max = flood_wait_max
        self.file_cache = file_cache  # Storage-like (get/set) or None
        self._session: aiohttp.ClientSession | None = None
        self.on_request: Callable[[str, dict], None] | None = None

    # ------------------------------------------------------------- session
    async def session(self) -> aiohttp.ClientSession:
        """The shared ``aiohttp.ClientSession`` (created on first use).

        Example::

            session = await bot.client.session()
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
                json_serialize=lambda o: _ENCODER.encode(o).decode(),
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session.

        Example::

            await bot.client.close()
        """
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    # ------------------------------------------------------------- encoding
    async def _prepare(self, params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, InputFile], dict[str, str]]:
        files: dict[str, InputFile] = {}
        cache_keys: dict[str, str] = {}
        counter = [0]

        async def cached(f: InputFile) -> str | None:
            if self.file_cache is None or f.cache_key is None:
                return None
            return await self.file_cache.get(f"fid:{f.cache_key}")

        # resolve cache hits first (async), then encode synchronously
        hits: dict[int, str] = {}

        found: list[InputFile] = []

        def collect(v: Any) -> None:
            if isinstance(v, InputFile):
                found.append(v)
            elif isinstance(v, dict):
                for x in v.values():
                    collect(x)
            elif isinstance(v, (list, tuple)):
                for x in v:
                    collect(x)
            elif isinstance(v, msgspec.Struct):
                for f in v.__struct_fields__:
                    collect(getattr(v, f))

        collect(params)
        for f in found:
            fid = await cached(f)
            if fid:
                hits[id(f)] = fid

        def enc_hook(obj: Any) -> Any:
            if isinstance(obj, InputFile):
                if id(obj) in hits:
                    return hits[id(obj)]
                if obj.url:
                    return obj.url
                counter[0] += 1
                name = f"file{counter[0]}"
                files[name] = obj
                if obj.cache_key:
                    cache_keys[name] = obj.cache_key
                return f"attach://{name}"
            raise TypeError(f"Unsupported type: {type(obj)!r}")

        out: dict[str, Any] = {}
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, InputFile):
                # top-level files are sent directly as form fields (not attach://)
                if id(v) in hits:
                    out[k] = hits[id(v)]
                elif v.url:
                    out[k] = v.url
                else:
                    files[k] = v
                    if v.cache_key:
                        cache_keys[k] = v.cache_key
                continue
            out[k] = msgspec.to_builtins(v, enc_hook=enc_hook)
        return out, files, cache_keys

    # ------------------------------------------------------------- request
    async def request(self, method: str, params: dict[str, Any] | None = None, returns: Any = "Any", *, timeout: float | None = None) -> Any:
        """Call a Bot API method by its Telegram name and decode the result into ``returns``.

        Example::

            msg = await bot.client.request("sendMessage", {"chat_id": 42, "text": "hi"}, "Message")
        """
        payload, files, cache_keys = await self._prepare(params or {})
        if self.on_request:
            self.on_request(method, payload)
        url = self.method_url(method)
        attempt = 0
        flood_waited = 0.0
        while True:
            attempt += 1
            try:
                raw = await self._post(url, payload, files, timeout or self.timeout)
                env = _ENVELOPE.decode(raw)
                if not env.ok:
                    raise make_error(method, env.description, env.error_code, env.parameters)
                result = decoder_for(returns).decode(env.result)
                await self.remember_files(cache_keys, result)
                return result
            except RetryAfter as e:
                wait = e.retry_after
                if flood_waited + wait > self.flood_wait_max:
                    raise
                log.warning("Flood control on %s: waiting %.0fs", method, wait)
                flood_waited += wait
                await asyncio.sleep(wait)
            except ServerError:
                if attempt > self.retries:
                    raise
                await asyncio.sleep(min(2 ** attempt, 10))
            except TelegramError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                if attempt > self.retries:
                    raise NetworkError(f"{method}: {e!r}") from e
                log.debug("Network error on %s (%r), retry %d", method, e, attempt)
                await asyncio.sleep(min(0.5 * 2 ** attempt, 8))

    async def remember_files(self, cache_keys: dict[str, str], result: Any) -> None:
        """Store the file_id Telegram gave an uploaded local file (internal).

        Example::

            await client.remember_files(cache_keys, result)
        """
        if not cache_keys or self.file_cache is None:
            return
        fid = extract_file_id(result)
        if fid:
            for key in cache_keys.values():
                await self.file_cache.set(f"fid:{key}", fid)

    async def _post(self, url: str, payload: dict[str, Any], files: dict[str, InputFile], timeout: float) -> bytes:
        session = await self.session()
        to = aiohttp.ClientTimeout(total=timeout + 10)
        if files:
            form = aiohttp.FormData(quote_fields=False)
            for k, v in payload.items():
                form.add_field(k, v if isinstance(v, str) else _ENCODER.encode(v).decode())
            for name, f in files.items():
                form.add_field(name, f.read(), filename=f.filename, content_type=f.mime)
            async with session.post(url, data=form, timeout=to) as resp:
                return await resp.read()
        async with session.post(url, data=_ENCODER.encode(payload), headers={"Content-Type": "application/json"}, timeout=to) as resp:
            return await resp.read()

    @property
    def is_cloud(self) -> bool:
        """``True`` when talking to Telegram's cloud Bot API (20 MB download limit), ``False`` for a local server.

        Example::

            Client("123:ABC").is_cloud                                   # True
            Client("123:ABC", api_url="http://localhost:8081").is_cloud  # False
        """
        return "api.telegram.org" in self.api_url

    def method_url(self, method: str) -> str:
        """Full URL of a Bot API method (``/test/`` is added on the test server).

        Example::

            client.method_url("getMe")   # https://api.telegram.org/bot<token>/getMe
        """
        return f"{self.api_url}/bot{self.token}/{'test/' if self.test_server else ''}{method}"

    def file_url(self, file_path: str) -> str:
        """Download URL of a file returned by ``getFile``.

        Example::

            info = await bot.get_file(file_id)
            url = bot.client.file_url(info.file_path)
        """
        return f"{self.api_url}/file/bot{self.token}/{'test/' if self.test_server else ''}{file_path}"

    async def download(self, file_path: str) -> bytes:
        """Download a file by its ``file_path`` (from ``getFile``) into memory.

        With a local Bot API server started with ``--local``, ``file_path`` is an absolute path on disk and is read directly.

        Example::

            info = await bot.get_file(file_id)
            data = await bot.client.download(info.file_path)
        """
        import os

        if os.path.isabs(file_path) and os.path.isfile(file_path):
            return await asyncio.to_thread(_read_bytes, file_path)
        session = await self.session()
        async with session.get(self.file_url(file_path)) as resp:
            resp.raise_for_status()
            return await resp.read()

    async def download_to(self, file_path: str, dest: Any, chunk_size: int = 256 * 1024) -> None:
        """Stream a file to ``dest`` on disk in chunks (big files never sit in memory).

        Example::

            info = await bot.get_file(file_id)
            await bot.client.download_to(info.file_path, "video.mp4")
        """
        import os
        import shutil

        if os.path.isabs(file_path) and os.path.isfile(file_path):
            await asyncio.to_thread(shutil.copyfile, file_path, dest)
            return
        session = await self.session()
        async with session.get(self.file_url(file_path), timeout=aiohttp.ClientTimeout(total=None, sock_read=120)) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                async for chunk in resp.content.iter_chunked(chunk_size):
                    fh.write(chunk)


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()
