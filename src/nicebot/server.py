"""Built-in web server (aiohttp): webhook endpoint + Mini App backend with verified ``initData``."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlparse

from aiohttp import web

if TYPE_CHECKING:
    from .bot import Nicebot

log = logging.getLogger("nicebot.server")


class InitDataError(ValueError):
    pass


def validate_init_data(init_data: str, token: str, max_age: float | None = 86400) -> dict[str, Any]:
    """Verify Telegram Mini App ``initData`` (HMAC-SHA256). Returns parsed fields; ``user`` is a dict.

    Raises ``InitDataError`` when the signature is wrong or the data is too old.
    """
    if not init_data:
        raise InitDataError("initData bo'sh")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received = pairs.pop("hash", None)
    if not received:
        raise InitDataError("hash yo'q")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise InitDataError("imzo noto'g'ri")
    if max_age is not None:
        auth = int(pairs.get("auth_date", "0") or 0)
        if time.time() - auth > max_age:
            raise InitDataError("initData eskirgan")
    out: dict[str, Any] = dict(pairs)
    for k in ("user", "receiver", "chat"):
        if k in out:
            try:
                out[k] = json.loads(out[k])
            except ValueError:
                pass
    return out


def sign_init_data(fields: dict[str, Any], token: str) -> str:
    """Build a valid initData string (useful in tests)."""
    from urllib.parse import urlencode

    data = {k: (json.dumps(v, separators=(",", ":")) if isinstance(v, (dict, list)) else str(v)) for k, v in fields.items()}
    data.setdefault("auth_date", str(int(time.time())))
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


class WebAppRequest:
    """What a ``@bot.api`` handler receives."""

    def __init__(self, bot: "Nicebot", request: web.Request, init: dict[str, Any] | None, body: Any):
        self.bot = bot
        self.request = request
        self.init = init or {}
        self.user: dict[str, Any] = self.init.get("user") or {}
        self.json = body
        self.query = dict(request.query)
        self.params = dict(request.match_info)

    @property
    def user_id(self) -> int | None:
        return self.user.get("id")

    async def db_user(self) -> Any:
        """The ORM user row for this Mini App user (or None)."""
        if self.user_id is None:
            return None
        return await self.bot.User.get_or_none(id=self.user_id)


NICEBOT_JS = r"""/* nicebot.js — Mini App helper. Include after telegram-web-app.js */
(function () {
  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) { tg.ready(); tg.expand(); }
  function api(path, data, method) {
    method = (method || (data === undefined ? "GET" : "POST")).toUpperCase();
    var opts = { method: method, headers: { "Authorization": "tma " + (tg ? tg.initData : "") } };
    if (method !== "GET") { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(data || {}); }
    return fetch(path, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) { var e = new Error(j.error || r.statusText); e.status = r.status; throw e; }
        return j;
      });
    });
  }
  window.nicebot = {
    api: api,
    get: function (p) { return api(p, undefined, "GET"); },
    post: function (p, d) { return api(p, d, "POST"); },
    tg: tg,
    user: tg && tg.initDataUnsafe ? tg.initDataUnsafe.user : null,
    haptic: function (k) { try { tg.HapticFeedback.impactOccurred(k || "light"); } catch (e) {} },
    close: function () { tg && tg.close(); },
    mainButton: function (text, onClick) {
      if (!tg) return; tg.MainButton.setText(text); tg.MainButton.show(); tg.MainButton.onClick(onClick);
    },
    sendData: function (obj) { tg && tg.sendData(typeof obj === "string" ? obj : JSON.stringify(obj)); }
  };
})();
"""


def build_app(bot: "Nicebot", webhook_path: str | None = None, secret: str | None = None) -> web.Application:
    app = web.Application(client_max_size=20 * 1024 * 1024)

    if webhook_path:
        async def webhook(request: web.Request) -> web.Response:
            if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
                return web.Response(status=401)
            raw = await request.read()
            bot._track(__import__("asyncio").create_task(bot.feed(raw)))
            return web.Response(text="ok")

        app.router.add_post(webhook_path, webhook)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"ok": True, "bot": bot.username, "uptime": round(time.time() - (bot.started_at or time.time()))})

    app.router.add_get("/nicebot/health", health)
    async def js(_: web.Request) -> web.Response:
        return web.Response(text=NICEBOT_JS, content_type="application/javascript", headers={"Cache-Control": "public, max-age=3600"})

    app.router.add_get("/nicebot.js", js)

    for method, path, func in bot._api_routes:
        app.router.add_route(method, path, _api_handler(bot, func))

    for path, folder in bot._static:
        from pathlib import Path

        prefix = "/" + path.strip("/")
        root = Path(folder).resolve()

        async def static(request: web.Request, root: Path = root, prefix: str = prefix) -> web.StreamResponse:
            rel = request.path[len(prefix):].lstrip("/") if prefix != "/" else request.path.lstrip("/")
            target = (root / rel).resolve() if rel else root / "index.html"
            if root not in target.parents and target != root / "index.html":
                raise web.HTTPForbidden()
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                target = root / "index.html"  # single-page apps
            return web.FileResponse(target)

        pattern = "/{tail:.*}" if prefix == "/" else prefix + "{tail:.*}"
        app.router.add_get(pattern, static)
    return app


def _api_handler(bot: "Nicebot", func: Any) -> Any:
    from .utils import maybe_await

    async def handler(request: web.Request) -> web.StreamResponse:
        init = None
        if getattr(func, "_nb_auth", True):
            auth = request.headers.get("Authorization", "")
            raw = auth[4:] if auth.lower().startswith("tma ") else request.headers.get("X-Init-Data", "") or request.query.get("initData", "")
            try:
                init = validate_init_data(raw, bot.token)
            except InitDataError as e:
                return web.json_response({"ok": False, "error": f"unauthorized: {e}"}, status=401)
        body: Any = None
        if request.can_read_body:
            try:
                body = await request.json()
            except (ValueError, json.JSONDecodeError):
                body = None
        req = WebAppRequest(bot, request, init, body)
        try:
            result = await maybe_await(func(req))
        except web.HTTPException:
            raise
        except PermissionError as e:
            return web.json_response({"ok": False, "error": str(e) or "forbidden"}, status=403)
        except (ValueError, KeyError) as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        except Exception:  # noqa: BLE001
            log.exception("API xatosi %s", request.path)
            return web.json_response({"ok": False, "error": "internal error"}, status=500)
        if isinstance(result, web.StreamResponse):
            return result
        if isinstance(result, str):
            return web.Response(text=result)
        if result is None:
            result = {"ok": True}
        return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))

    return handler


async def run_server(bot: "Nicebot", *, webhook: str | None, host: str, port: int) -> web.AppRunner:
    secret = None
    path = None
    if webhook:
        secret = secrets.token_urlsafe(32)
        path = urlparse(webhook).path or "/webhook"
    app = build_app(bot, path, secret)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("🌐 Web server: http://%s:%d", host, port)
    if webhook:
        await bot.set_webhook(webhook, secret_token=secret, allowed_updates=bot.allowed_updates, drop_pending_updates=False)
    return runner
