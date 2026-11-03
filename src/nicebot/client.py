"""HTTP layer: one pooled aiohttp session, msgspec encode/decode, smart retries."""
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
    key = returns if isinstance(returns, str) else repr(returns)
    dec = _DECODERS.get(key)
    if dec is None:
        typ = eval(returns, _NS) if isinstance(returns, str) else returns  # noqa: S307 - generated, trusted
        dec = _DECODERS[key] = msgspec.json.Decoder(typ)
    return dec


_FILE_FIELDS = ("photo", "document", "video", "audio", "voice", "animation", "sticker", "video_note")


def extract_file_id(message: Any) -> str | None:
    """Return the file_id of the media inside a sent Message (for the file cache)."""
    for name in _FILE_FIELDS:
        val = getattr(message, name, None)
        if val:
            if isinstance(val, list):
                val = val[-1]
            return getattr(val, "file_id", None)
    return None


class Client:
    """Talks to the Bot API.  Handles flood-wait (429), 5xx and network errors."""

    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.telegram.org",
        timeout: float = 30.0,
        retries: int = 3,
        flood_wait_max: float = 60.0,
        file_cache: Any = None,
    ):
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.flood_wait_max = flood_wait_max
        self.file_cache = file_cache  # Storage-like (get/set) or None
        self._session: aiohttp.ClientSession | None = None
        self.on_request: Callable[[str, dict], None] | None = None

    # ------------------------------------------------------------- session
    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
                json_serialize=lambda o: _ENCODER.encode(o).decode(),
            )
        return self._session

    async def close(self) -> None:
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
        payload, files, cache_keys = await self._prepare(params or {})
        if self.on_request:
            self.on_request(method, payload)
        url = f"{self.api_url}/bot{self.token}/{method}"
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
                log.warning("Flood control on %s: kutilyapti %.0fs", method, wait)
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
        """Store the file_id Telegram gave an uploaded local file, so it is never uploaded twice."""
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

    async def download(self, file_path: str) -> bytes:
        session = await self.session()
        async with session.get(f"{self.api_url}/file/bot{self.token}/{file_path}") as resp:
            resp.raise_for_status()
            return await resp.read()
