"""Built-in web server (aiohttp): webhook endpoint, Mini App files and a Mini App backend with verified ``initData``.

The server starts automatically with ``bot.start()`` when you use ``bot.webapp()``, ``@bot.api``, webhooks,
``tunnel=True`` or ``debug=True``.

Example::

    bot.webapp("webapp")                          # webapp/index.html is served at /

    @bot.api("/api/cart", methods=["GET"])
    async def cart(req: WebAppRequest):
        user = await req.db_user()
        return {"name": req.user.first_name, "items": user.data.get("cart", [])}

    bot.start(tunnel=True)                        # free HTTPS address for Telegram
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlparse

from aiohttp import web

if TYPE_CHECKING:
    from .bot import Nicebot

log = logging.getLogger("nicebot.server")


class InitDataError(ValueError):
    """``initData`` is missing, forged or too old.

    Example::

        try:
            data = validate_init_data(raw, bot.token)
        except InitDataError as e:
            print("rejected:", e)
    """


def validate_init_data(init_data: str, token: str, max_age: float | None = 86400) -> dict[str, Any]:
    """Verify Telegram Mini App ``initData`` (HMAC-SHA256 with your bot token) and return its fields.

    ``user``, ``receiver`` and ``chat`` are decoded from JSON. Raises ``InitDataError`` when the signature is
    wrong or the data is older than ``max_age`` seconds (``None`` disables the age check).

    Example::

        data = validate_init_data(request.headers["X-Init-Data"], bot.token)
        print(data["user"]["id"], data.get("start_param"))
    """
    if not init_data:
        raise InitDataError("initData is empty (open the page from Telegram, or use debug=True for browser testing)")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received = pairs.pop("hash", None)
    if not received:
        raise InitDataError("initData has no hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise InitDataError("initData signature is invalid")
    if max_age is not None:
        auth = int(pairs.get("auth_date", "0") or 0)
        if time.time() - auth > max_age:
            raise InitDataError("initData is too old")
    out: dict[str, Any] = dict(pairs)
    for k in ("user", "receiver", "chat"):
        if k in out:
            try:
                out[k] = json.loads(out[k])
            except ValueError:
                pass
    return out


def sign_init_data(fields: dict[str, Any], token: str) -> str:
    """Build a valid ``initData`` string for ``token`` — for tests and the ``debug=True`` browser mode.

    Example::

        raw = sign_init_data({"user": {"id": 1, "first_name": "Ali"}}, bot.token)
        assert validate_init_data(raw, bot.token)["user"]["first_name"] == "Ali"
    """
    data = {k: (json.dumps(v, separators=(",", ":"), ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)) for k, v in fields.items()}
    data.setdefault("auth_date", str(int(time.time())))
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


class WebAppUser(dict):
    """The Telegram user who opened the Mini App. Works like a dict (``user["id"]``) and with attributes.

    Example::

        @bot.api("/api/me", methods=["GET"])
        async def me(req: WebAppRequest):
            return {"hello": req.user.first_name, "premium": req.user.is_premium}
    """

    @property
    def id(self) -> int:
        """Telegram user id.

        Example::

            req.user.id   # 123456789
        """
        return int(self.get("id", 0))

    @property
    def first_name(self) -> str:
        """First name.

        Example::

            req.user.first_name   # "Ali"
        """
        return self.get("first_name", "")

    @property
    def last_name(self) -> str | None:
        """Last name (may be ``None``).

        Example::

            req.user.last_name
        """
        return self.get("last_name")

    @property
    def username(self) -> str | None:
        """Username without ``@`` (may be ``None``).

        Example::

            req.user.username   # "ali_dev"
        """
        return self.get("username")

    @property
    def language_code(self) -> str | None:
        """Language of the user's Telegram app.

        Example::

            req.user.language_code   # "uz"
        """
        return self.get("language_code")

    @property
    def is_premium(self) -> bool:
        """Telegram Premium subscriber?

        Example::

            if req.user.is_premium: ...
        """
        return bool(self.get("is_premium", False))

    @property
    def photo_url(self) -> str | None:
        """Profile photo URL (``.jpeg``/``.svg``), if available.

        Example::

            req.user.photo_url
        """
        return self.get("photo_url")

    @property
    def allows_write_to_pm(self) -> bool:
        """``True`` if the bot may message this user (``req.send`` works).

        Example::

            if req.user.allows_write_to_pm:
                await req.send("Thanks!")
        """
        return bool(self.get("allows_write_to_pm", False))


class UploadedFile:
    """A file sent from the Mini App with ``nicebot.upload()`` or a ``multipart/form-data`` form.

    Example::

        @bot.api("/api/avatar")
        async def avatar(req: WebAppRequest):
            form = await req.form()
            file = form["photo"]                       # UploadedFile
            await file.save(f"avatars/{req.user_id}.jpg")
            await req.send_photo(file.data, "Your new avatar")
            return {"size": file.size}
    """

    def __init__(self, name: str, filename: str, content_type: str, data: bytes):
        self.name = name
        self.filename = filename
        self.content_type = content_type
        self.data = data

    @property
    def size(self) -> int:
        """Size in bytes.

        Example::

            if file.size > 5_000_000:
                raise ValueError("max 5 MB")
        """
        return len(self.data)

    async def save(self, path: str | Path) -> str:
        """Write the file to ``path`` (folders are created) and return the path.

        Example::

            await file.save("uploads/receipt.pdf")
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(p.write_bytes, self.data)
        return str(p)

    def __repr__(self) -> str:
        return f"<UploadedFile {self.filename!r} {self.content_type} {self.size} bytes>"


class WebAppRequest:
    """What a ``@bot.api`` handler receives: the verified Telegram user plus the HTTP request.

    Attributes:
        user:     ``WebAppUser`` (``req.user.id``, ``req.user.first_name``…); empty for ``auth=False`` routes
        init:     every verified ``initData`` field (``query_id``, ``start_param``, ``chat_type``…)
        json:     the JSON body (``None`` if the body is not JSON)
        query:    URL query parameters as a dict
        params:   path parameters, e.g. ``{"id": "5"}`` for ``/api/item/{id}``
        request:  the raw ``aiohttp.web.Request``
        bot:      your ``Nicebot``

    Example::

        @bot.api("/api/order")
        async def order(req: WebAppRequest):
            items = req.json["items"]
            await Order.create(user_id=req.user_id, items=items)
            await req.send(f"✅ Order received: {len(items)} items")
            return {"ok": True}
    """

    def __init__(self, bot: "Nicebot", request: web.Request, init: dict[str, Any] | None, body: Any):
        self.bot = bot
        self.request = request
        self.init: dict[str, Any] = init or {}
        self.user = WebAppUser(self.init.get("user") or {})
        self.json: Any = body
        self.query: dict[str, str] = dict(request.query)
        self.params: dict[str, str] = dict(request.match_info)
        self._form: dict[str, Any] | None = None

    @property
    def user_id(self) -> int | None:
        """The Telegram id of the user (``None`` on ``auth=False`` routes).

        Example::

            orders = await Order.filter(user_id=req.user_id)
        """
        return self.user.id if self.user else None

    @property
    def start_param(self) -> str | None:
        """The ``startapp`` parameter from a direct link ``t.me/your_bot/app?startapp=promo``.

        Example::

            if req.start_param == "promo":
                discount = 10
        """
        return self.init.get("start_param")

    @property
    def query_id(self) -> str | None:
        """Set when the Mini App was opened from an inline keyboard button/inline menu; needed by ``req.answer()``.

        Example::

            if req.query_id:
                await req.answer("Done", "✅ Ordered")
        """
        return self.init.get("query_id")

    @property
    def chat_type(self) -> str | None:
        """Where the app was opened: ``"sender"``, ``"private"``, ``"group"``, ``"supergroup"`` or ``"channel"``.

        Example::

            req.chat_type   # "private"
        """
        return self.init.get("chat_type")

    @property
    def headers(self) -> Any:
        """HTTP headers of the request.

        Example::

            req.headers.get("User-Agent")
        """
        return self.request.headers

    @property
    def ip(self) -> str | None:
        """Client IP (respects ``X-Forwarded-For`` from proxies).

        Example::

            log.info("request from %s", req.ip)
        """
        fwd = self.request.headers.get("X-Forwarded-For")
        return fwd.split(",")[0].strip() if fwd else self.request.remote

    async def db_user(self) -> Any:
        """The database row of this user (``nb_users``) or ``None`` if they never wrote to the bot.

        Example::

            user = await req.db_user()
            return {"balance": user.data.get("balance", 0) if user else 0}
        """
        if self.user_id is None:
            return None
        return await self.bot.User.get_or_none(id=self.user_id)

    async def form(self) -> dict[str, Any]:
        """Read a ``multipart/form-data`` body: text fields become ``str``, files become ``UploadedFile``.

        Example::

            form = await req.form()
            comment, photo = form["comment"], form["photo"]
        """
        if self._form is not None:
            return self._form
        out: dict[str, Any] = {}
        if self.request.content_type.startswith("multipart/"):
            reader = await self.request.multipart()
            async for part in reader:  # type: ignore[union-attr]
                if part is None or not getattr(part, "name", None):
                    continue
                if getattr(part, "filename", None):
                    data = await part.read(decode=False)  # type: ignore[union-attr]
                    out[part.name] = UploadedFile(part.name, part.filename, part.headers.get("Content-Type", "application/octet-stream"), bytes(data))  # type: ignore[arg-type]
                else:
                    out[part.name] = await part.text()  # type: ignore[union-attr]
        elif self.request.content_type == "application/x-www-form-urlencoded":
            out = dict(await self.request.post())  # type: ignore[arg-type]
        self._form = out
        return out

    async def files(self) -> list[UploadedFile]:
        """Only the uploaded files of a multipart body.

        Example::

            for f in await req.files():
                await f.save(f"uploads/{f.filename}")
        """
        return [v for v in (await self.form()).values() if isinstance(v, UploadedFile)]

    def _need_user(self) -> int:
        if self.user_id is None:
            raise PermissionError("No Telegram user on this request (route has auth=False)")
        return self.user_id

    async def send(self, text: Any, *, buttons: Any = None, **kw: Any) -> Any:
        """Send a chat message from the bot to the user who uses the Mini App.

        The user must have started the bot (or allowed messages when opening the app).

        Example::

            await req.send("✅ Payment received", buttons=[Button("📦 My orders", on_click=orders)])
        """
        from .keyboards import build_inline

        uid = self._need_user()
        if buttons is not None:
            kw["reply_markup"] = await build_inline(self.bot, buttons, user_id=uid)
        return await self.bot._call_with_parse_fallback("send_message", chat_id=uid, text=str(text), parse_mode=self.bot.parse_mode, **kw)

    async def send_photo(self, photo: Any, caption: Any = None, **kw: Any) -> Any:
        """Send a photo (path, URL, file_id or bytes) to the Mini App user.

        Example::

            await req.send_photo(qr_png_bytes, "Your ticket")
        """
        from .context import _as_file

        uid = self._need_user()
        params: dict[str, Any] = {"chat_id": uid, "photo": _as_file(photo, kw.pop("filename", None))}
        if caption is not None:
            params.update(caption=str(caption), parse_mode=self.bot.parse_mode)
        return await self.bot._call_with_parse_fallback("send_photo", **params, **kw)

    async def send_document(self, document: Any, caption: Any = None, **kw: Any) -> Any:
        """Send a file to the Mini App user.

        Example::

            await req.send_document(pdf_bytes, "Invoice", filename="invoice.pdf")
        """
        from .context import _as_file

        uid = self._need_user()
        params: dict[str, Any] = {"chat_id": uid, "document": _as_file(document, kw.pop("filename", None))}
        if caption is not None:
            params.update(caption=str(caption), parse_mode=self.bot.parse_mode)
        return await self.bot._call_with_parse_fallback("send_document", **params, **kw)

    async def answer(self, title: str, text: Any, *, description: str | None = None) -> Any:
        """Reply on behalf of the user in the chat where the Mini App was opened (``answerWebAppQuery``).

        Needs ``req.query_id`` (Mini Apps opened from an inline keyboard button or the attachment/inline menu).

        Example::

            await req.answer("Order #15", f"🛒 I ordered: {', '.join(names)}")
        """
        from . import types as T

        if not self.query_id:
            raise ValueError("req.answer() needs query_id: open the Mini App from an inline button or the inline menu")
        result = T.InlineQueryResultArticle(
            id=secrets.token_hex(8), title=title, description=description,
            input_message_content=T.InputTextMessageContent(message_text=str(text), parse_mode=self.bot.parse_mode),
        )
        return await self.bot.answer_web_app_query(self.query_id, result)

    def __repr__(self) -> str:
        return f"<WebAppRequest {self.request.method} {self.request.path} user={self.user_id}>"


NICEBOT_JS = r"""/* nicebot.js — Mini App helper (served by your bot at /nicebot.js). Include after telegram-web-app.js.
   Docs: https://ozodmeofficial.github.io/nicebot/#miniapp-frontend */
(function () {
  var tg = window.Telegram && window.Telegram.WebApp;
  var script = document.currentScript;
  var base = script && script.src ? script.src.replace(/\/nicebot\.js(\?.*)?$/, "") : "";
  if (base === location.origin) base = "";
  var initData = tg && tg.initData ? tg.initData : "";
  var devReady = null;
  if (tg) { try { tg.ready(); tg.expand(); } catch (e) {} }

  function url(path) { return /^https?:/.test(path) ? path : (nb.base || "") + path; }
  function ensureInit() {
    if (initData || !nb.dev) return Promise.resolve(initData);
    if (!devReady) {
      devReady = fetch(url("/nicebot/dev-init")).then(function (r) { return r.ok ? r.json() : {}; })
        .then(function (j) { if (j.initData) { initData = j.initData; nb.user = j.user; } return initData; })
        .catch(function () { return ""; });
    }
    return devReady;
  }
  function request(method, path, body, isForm) {
    return ensureInit().then(function (init) {
      var opts = { method: method, headers: { "Authorization": "tma " + init } };
      if (body !== undefined && method !== "GET") {
        if (isForm) opts.body = body;
        else { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
      }
      return fetch(url(path), opts).then(function (r) {
        return r.text().then(function (t) {
          var j; try { j = t ? JSON.parse(t) : {}; } catch (e) { j = { text: t }; }
          if (!r.ok) { var err = new Error(j.error || r.statusText); err.status = r.status; err.data = j; throw err; }
          return j;
        });
      });
    });
  }
  function cloud(fn, args) {
    return new Promise(function (resolve, reject) {
      if (!tg || !tg.CloudStorage) { reject(new Error("CloudStorage is available only inside Telegram")); return; }
      tg.CloudStorage[fn].apply(tg.CloudStorage, args.concat([function (err, val) { err ? reject(err) : resolve(val); }]));
    });
  }
  var nb = {
    tg: tg,
    base: base,
    dev: !initData,
    isTelegram: !!initData,
    user: tg && tg.initDataUnsafe ? tg.initDataUnsafe.user || null : null,
    startParam: tg && tg.initDataUnsafe ? tg.initDataUnsafe.start_param || null : null,
    platform: tg ? tg.platform : "browser",
    get: function (path) { return request("GET", path); },
    post: function (path, data) { return request("POST", path, data === undefined ? {} : data); },
    put: function (path, data) { return request("PUT", path, data === undefined ? {} : data); },
    del: function (path) { return request("DELETE", path); },
    api: function (path, data, method) { return request((method || (data === undefined ? "GET" : "POST")).toUpperCase(), path, data); },
    upload: function (path, files, fields) {
      var fd = new FormData();
      if (files instanceof File || files instanceof Blob) files = { file: files };
      Object.keys(files || {}).forEach(function (k) { fd.append(k, files[k]); });
      Object.keys(fields || {}).forEach(function (k) { fd.append(k, fields[k]); });
      return request("POST", path, fd, true);
    },
    mainButton: function (text, onClick, opts) {
      if (!tg) return null;
      var b = tg.MainButton; b.setText(text);
      if (opts && opts.color) b.setParams({ color: opts.color });
      if (nb._main) b.offClick(nb._main);
      nb._main = onClick; b.onClick(onClick); b.show(); return b;
    },
    hideMainButton: function () { if (tg) tg.MainButton.hide(); },
    backButton: function (onClick) {
      if (!tg) return null;
      if (nb._back) tg.BackButton.offClick(nb._back);
      if (!onClick) { tg.BackButton.hide(); return null; }
      nb._back = onClick; tg.BackButton.onClick(onClick); tg.BackButton.show(); return tg.BackButton;
    },
    progress: function (on) { if (tg) on ? tg.MainButton.showProgress() : tg.MainButton.hideProgress(); },
    alert: function (text) { return new Promise(function (res) { tg && tg.showAlert ? tg.showAlert(text, res) : (window.alert(text), res()); }); },
    confirm: function (text) { return new Promise(function (res) { tg && tg.showConfirm ? tg.showConfirm(text, res) : res(window.confirm(text)); }); },
    haptic: function (kind) { try { if (kind === "success" || kind === "error" || kind === "warning") tg.HapticFeedback.notificationOccurred(kind); else tg.HapticFeedback.impactOccurred(kind || "light"); } catch (e) {} },
    theme: function () {
      var p = (tg && tg.themeParams) || {}, root = document.documentElement;
      Object.keys(p).forEach(function (k) { root.style.setProperty("--tg-" + k.replace(/_/g, "-"), p[k]); });
      root.dataset.theme = tg && tg.colorScheme ? tg.colorScheme : "light";
      return p;
    },
    sendData: function (obj) { if (tg) tg.sendData(typeof obj === "string" ? obj : JSON.stringify(obj)); },
    openLink: function (link) { tg ? tg.openLink(link) : window.open(link, "_blank"); },
    openTelegramLink: function (link) { tg ? tg.openTelegramLink(link) : window.open(link, "_blank"); },
    share: function (text, link) { nb.openTelegramLink("https://t.me/share/url?url=" + encodeURIComponent(link || "") + "&text=" + encodeURIComponent(text || "")); },
    close: function () { if (tg) tg.close(); },
    storage: {
      get: function (key) { return cloud("getItem", [key]); },
      set: function (key, value) { return cloud("setItem", [key, String(value)]); },
      remove: function (key) { return cloud("removeItem", [key]); },
      keys: function () { return cloud("getKeys", []); }
    },
    ready: function () { return ensureInit().then(function () { return nb; }); }
  };
  window.nicebot = nb;
})();
"""


def _cors_headers(origin: str | None, allowed: list[str]) -> dict[str, str]:
    if not origin or not allowed:
        return {}
    if "*" in allowed:
        allow = "*"
    elif origin in allowed:
        allow = origin
    else:
        return {}
    return {
        "Access-Control-Allow-Origin": allow,
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Init-Data",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
    }


def _is_local(request: web.Request) -> bool:
    host = (request.remote or "").split("%")[0]
    return host in ("127.0.0.1", "::1", "localhost") and "X-Forwarded-For" not in request.headers


def build_app(bot: "Nicebot", webhook_path: str | None = None, secret: str | None = None) -> web.Application:
    """Create the aiohttp application (webhook, ``/nicebot.js``, health check, Mini App files and ``@bot.api`` routes).

    Useful to mount nicebot into your own aiohttp app or to test it with ``aiohttp.test_utils``.

    Example::

        app = build_app(bot)
        web.run_app(app, port=8080)       # usually bot.start() does this for you
    """
    cors = list(bot.cors)

    @web.middleware
    async def cors_mw(request: web.Request, handler: Any) -> web.StreamResponse:
        headers = _cors_headers(request.headers.get("Origin"), cors)
        if request.method == "OPTIONS" and headers:
            return web.Response(status=204, headers=headers)
        resp = await handler(request)
        for k, v in headers.items():
            resp.headers[k] = v
        return resp

    app = web.Application(client_max_size=50 * 1024 * 1024, middlewares=[cors_mw])

    if webhook_path:
        async def webhook(request: web.Request) -> web.Response:
            if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
                return web.Response(status=401)
            raw = await request.read()
            bot._track(asyncio.create_task(bot.feed(raw)))
            return web.Response(text="ok")

        app.router.add_post(webhook_path, webhook)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"ok": True, "bot": bot.username, "uptime": round(time.time() - (bot.started_at or time.time()))})

    app.router.add_get("/nicebot/health", health)

    async def js(_: web.Request) -> web.Response:
        return web.Response(text=NICEBOT_JS, content_type="application/javascript", headers={"Cache-Control": "public, max-age=600"})

    app.router.add_get("/nicebot.js", js)

    async def dev_init(request: web.Request) -> web.Response:
        # Browser testing without Telegram: a signed initData for a fake user. Only with debug=True and only from localhost.
        if not bot.debug or not _is_local(request):
            return web.json_response({"ok": False, "error": "dev mode is off (Nicebot(debug=True)) or request is not from localhost"}, status=403)
        user = dict(bot.dev_user)
        return web.json_response({"ok": True, "initData": sign_init_data({"user": user, "query_id": "dev"}, bot.token), "user": user})

    app.router.add_get("/nicebot/dev-init", dev_init)

    for method, path, func in bot._api_routes:
        app.router.add_route(method, path, _api_handler(bot, func))

    for path, folder in bot._static:
        prefix = "/" + path.strip("/")
        root = Path(folder).resolve()
        if not (root / "index.html").is_file():
            log.warning("Mini App folder %s has no index.html", root)

        async def static(request: web.Request, root: Path = root, prefix: str = prefix) -> web.StreamResponse:
            rel = request.path[len(prefix):].lstrip("/") if prefix != "/" else request.path.lstrip("/")
            target = (root / rel).resolve() if rel else root / "index.html"
            if target != root and root not in target.parents:
                raise web.HTTPForbidden()
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                if Path(rel).suffix:  # a missing asset like /app.js → real 404
                    raise web.HTTPNotFound()
                target = root / "index.html"  # single-page app routes
            return web.FileResponse(target, headers={"Cache-Control": "no-cache"} if target.name == "index.html" else None)

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
        if request.can_read_body and request.content_type == "application/json":
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
            log.exception("API handler error on %s", request.path)
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
    """Start the web server and (with ``webhook``) register the webhook in Telegram. Returns the runner.

    Called by ``bot.run()``; use it directly only for custom setups.

    Example::

        runner = await run_server(bot, webhook=None, host="0.0.0.0", port=8080)
        ...
        await runner.cleanup()
    """
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
    log.info("🌐 Web server: http://localhost:%d", port)
    if webhook:
        await bot.set_webhook(webhook, secret_token=secret, allowed_updates=bot.allowed_updates, drop_pending_updates=bot._drop_pending)
    return runner
