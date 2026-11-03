import asyncio
import json
import os
import socket

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from nicebot import BadRequest, Nicebot, User, cache, html
from nicebot.config import Config, load_env
from nicebot.errors import make_error
from nicebot.i18n import I18n
from nicebot.server import build_app, sign_init_data, validate_init_data, InitDataError
from nicebot.storage import MemoryStorage, RedisStorage
from nicebot.utils import parse_duration, human_duration
from nicebot.validators import format_phone, normalize_phone


def make_bot(**kw):
    kw.setdefault("token", "123:TEST")
    kw.setdefault("locales", None)
    return Nicebot(**kw)


# ---------------------------------------------------------------- groups
async def test_captcha_and_group_moderation():
    bot = make_bot(captcha="1s", admins=[1])

    @bot.command("warn")
    async def warn(ctx):
        if await ctx.is_chat_admin():
            await ctx.warn("spam", limit=2)

    async with bot.test(member_status="administrator") as t:
        newbie = t.user(id=50, first_name="Yangi", chat_id=-1001, chat_type="supergroup")
        await newbie.join()
        assert t.calls_of("restrictChatMember")[-1].params["permissions"]["can_send_messages"] is False
        assert "robot" in t.last.text.lower()
        await newbie.click("robot")
        assert t.calls_of("restrictChatMember")[-1].params["permissions"]["can_send_messages"] is True

        slow = t.user(id=51, first_name="Sekin", chat_id=-1001, chat_type="supergroup")
        await slow.join()
        await asyncio.sleep(1.2)
        await t.settle()
        assert t.calls_of("banChatMember")[-1].params["user_id"] == 51

        admin = t.user(id=1, chat_id=-1001, chat_type="supergroup")
        target = {"message_id": 9, "date": 1, "chat": {"id": -1001, "type": "supergroup"}, "from": {"id": 77, "is_bot": False, "first_name": "Spammer"}, "text": "spam"}
        await admin.send("/warn", reply_to_message=target)
        assert "1/2" in t.last.text
        await admin.send("/warn", reply_to_message=target)
        assert "chetlatildi" in t.last.text
        assert t.calls_of("banChatMember")[-1].params["user_id"] == 77


# ---------------------------------------------------------------- broadcast
async def test_broadcast_marks_blocked_and_resumes():
    bot = make_bot()

    @bot.command("start")
    async def start(ctx):
        await ctx.reply("hi")

    async with bot.test() as t:
        for i in range(1, 6):
            await t.user(id=i).send("/start")
        t.blocked = {3}
        progress = []
        stats = await bot.broadcast(html("<b>Yangilik</b> {}", "<3"), rate=1000, on_progress=lambda s: progress.append(s), id="news")
        assert stats == {"total": 5, "sent": 4, "failed": 1, "blocked": 1}
        assert (await User.get(id=3)).is_blocked is True
        assert progress[-1]["sent"] == 4
        assert await bot.storage.get("bc:news") is None
        sends = [c for c in t.calls_of("sendMessage") if c.params["text"].startswith("<b>Yangilik")]
        assert sends[0].params["text"] == "<b>Yangilik</b> &lt;3"
        stats2 = await bot.broadcast("ikkinchi", rate=1000)
        assert stats2["total"] == 4  # blocked user skipped


# ---------------------------------------------------------------- scheduler
async def test_scheduler_every_runs():
    from nicebot.scheduler import Job, run_jobs

    bot = make_bot()
    hits = []

    @bot.every("0.05s", first=0)
    async def tick(b):
        hits.append(b is bot)

    task = asyncio.create_task(run_jobs(bot, bot._jobs))
    await asyncio.sleep(0.2)
    task.cancel()
    assert len(hits) >= 3 and all(hits)
    assert Job(lambda: None, at="23:59", days=["sun"], tz="Asia/Tashkent").next_delay() <= 7 * 86400


# ---------------------------------------------------------------- mini app + webhook server
async def test_miniapp_api_and_webhook():
    bot = make_bot()
    got = []

    @bot.api("/score")
    async def score(req):
        return {"user": req.user_id, "got": req.json}

    @bot.api("/public", methods=["GET"], auth=False)
    async def public(req):
        return {"ok": True, "q": req.query.get("x")}

    @bot.command("start")
    async def start(ctx):
        got.append(ctx.text)

    async with bot.test():
        app = build_app(bot, webhook_path="/hook", secret="s3")
        async with TestClient(TestServer(app)) as client:
            init = sign_init_data({"user": {"id": 42, "first_name": "Ali"}, "query_id": "q"}, bot.token)
            r = await client.post("/score", json={"points": 5}, headers={"Authorization": f"tma {init}"})
            assert r.status == 200 and await r.json() == {"user": 42, "got": {"points": 5}}
            r = await client.post("/score", json={}, headers={"Authorization": "tma hash=bad&user=%7B%7D"})
            assert r.status == 401
            r = await client.get("/public?x=1")
            assert (await r.json())["q"] == "1"
            r = await client.get("/nicebot.js")
            assert "window.nicebot" in await r.text()
            upd = {"update_id": 1, "message": {"message_id": 1, "date": 1, "chat": {"id": 5, "type": "private"}, "from": {"id": 5, "is_bot": False, "first_name": "A"}, "text": "/start", "entities": [{"type": "bot_command", "offset": 0, "length": 6}]}}
            r = await client.post("/hook", json=upd)
            assert r.status == 401
            r = await client.post("/hook", json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": "s3"})
            assert r.status == 200
            await asyncio.sleep(0.1)
            assert got == ["/start"]

    with pytest.raises(InitDataError):
        validate_init_data(sign_init_data({"user": {"id": 1}}, "OTHER:TOKEN"), bot.token)
    old = sign_init_data({"user": {"id": 1}, "auth_date": 1}, bot.token)
    with pytest.raises(InitDataError):
        validate_init_data(old, bot.token)
    assert validate_init_data(old, bot.token, max_age=None)["user"]["id"] == 1


# ---------------------------------------------------------------- real HTTP client & polling against a fake Telegram
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def test_polling_end_to_end_with_fake_telegram(tmp_path):
    seen: list[tuple[str, dict]] = []
    state = {"updates_sent": False, "flooded": False, "confirmed": None}

    async def api(request: web.Request) -> web.Response:
        method = request.match_info["method"]
        if request.content_type.startswith("multipart"):
            form = await request.post()
            body = {k: (v.filename if hasattr(v, "filename") else v) for k, v in form.items()}
        else:
            body = await request.json() if request.can_read_body else {}
        seen.append((method, body))
        ok = lambda r: web.json_response({"ok": True, "result": r})  # noqa: E731
        if method == "getMe":
            return ok({"id": 1, "is_bot": True, "first_name": "B", "username": "real_bot"})
        if method == "getUpdates":
            if body.get("timeout") == 0:
                state["confirmed"] = body.get("offset")
                return ok([])
            if not state["updates_sent"]:
                state["updates_sent"] = True
                msg = {"message_id": 1, "date": 1, "chat": {"id": 9, "type": "private"}, "from": {"id": 9, "is_bot": False, "first_name": "Z"}, "text": "/photo", "entities": [{"type": "bot_command", "offset": 0, "length": 6}]}
                return ok([{"update_id": 100, "some_future_update": {"x": 1}}, {"update_id": 101, "message": msg}])
            await asyncio.sleep(0.2)
            return ok([])
        if method == "sendMessage":
            if not state["flooded"]:
                state["flooded"] = True
                return web.json_response({"ok": False, "error_code": 429, "description": "Too Many Requests: retry after 1", "parameters": {"retry_after": 0.1}})
            return ok({"message_id": 2, "date": 1, "chat": {"id": 9, "type": "private"}, "text": body["text"]})
        if method == "sendPhoto":
            return ok({"message_id": 3, "date": 1, "chat": {"id": 9, "type": "private"}, "photo": [{"file_id": "PHOTO_ID", "file_unique_id": "u", "width": 1, "height": 1}]})
        return ok(True)

    app = web.Application()
    app.router.add_post("/bot{token}/{method}", api)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    await web.TCPSite(runner, "127.0.0.1", port).start()

    img = tmp_path / "x.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"0" * 100)
    bot = Nicebot(token="42:REAL", api_url=f"http://127.0.0.1:{port}", locales=None)

    @bot.command("photo")
    async def photo(ctx):
        await ctx.reply("rasm keldi")
        await ctx.photo(str(img), caption="Mana")
        await ctx.photo(str(img), caption="Yana")
        bot.stop()

    try:
        await asyncio.wait_for(bot.run(handle_signals=False), timeout=10)
    finally:
        await runner.cleanup()

    methods = [m for m, _ in seen]
    assert methods.count("sendMessage") == 2  # first got 429 → retried automatically
    photos = [b for m, b in seen if m == "sendPhoto"]
    assert photos[0]["photo"] == "x.jpg"           # uploaded as multipart
    assert photos[1]["photo"] == "PHOTO_ID"        # second time: cached file_id
    assert state["confirmed"] == 102               # offset confirmed on graceful shutdown
    assert "deleteWebhook" in methods


# ---------------------------------------------------------------- storages
async def test_memory_and_redis_storage():
    stores = [MemoryStorage()]
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 6379)) == 0:
            stores.append(RedisStorage("redis://localhost:6379/15", prefix="nbtest:"))
    for st in stores:
        await st.set("a", {"x": [1, 2]})
        assert await st.get("a") == {"x": [1, 2]}
        assert await st.incr("n") == 1 and await st.incr("n", 5) == 6
        await st.set("t", 1, ttl=0.05)
        await asyncio.sleep(0.12)
        assert await st.get("t", "gone") == "gone"
        assert await st.pop("a") == {"x": [1, 2]} and await st.get("a") is None
        await st.delete("n")
        await st.close()


async def test_bot_with_redis_storage():
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 6379)) != 0:
            pytest.skip("redis yo'q")
    bot = make_bot(storage="redis://localhost:6379/15")

    @bot.command("s")
    async def s(ctx):
        await ctx.set_state("x", a=1)
        await ctx.reply(str(await ctx.get_state()))

    async with bot.test() as t:
        await t.user(id=999).send("/s")
        assert t.last.text == "x"


# ---------------------------------------------------------------- helpers
def test_validators_and_utils():
    assert normalize_phone("90 123 45 67") == "+998901234567"
    assert normalize_phone("+998 (93) 123-45-67") == "+998931234567"
    assert normalize_phone("8 90 123 45 67") == "+998901234567"
    assert normalize_phone("+998 12 345 67 89") is None  # wrong operator code
    assert normalize_phone("+7 916 123 45 67") == "+79161234567"
    assert normalize_phone("salom") is None
    assert format_phone("+998901234567") == "+998 90 123 45 67"
    assert parse_duration("1h30m") == 5400 and parse_duration("500ms") == 0.5 and parse_duration(10) == 10
    with pytest.raises(ValueError):
        parse_duration("5 kun")
    assert human_duration(3725) == "1h2m5s"
    assert html("<b>{}</b>", "<i>") == "<b>&lt;i&gt;</b>"


async def test_cache_decorator():
    calls = []

    @cache("1m")
    async def slow(x):
        calls.append(x)
        return x * 2

    assert await slow(2) == 4 and await slow(2) == 4 and await slow(3) == 6
    assert calls == [2, 3]


def test_i18n_files_and_env(tmp_path, monkeypatch):
    loc = tmp_path / "locales"
    loc.mkdir()
    (loc / "uz.json").write_text(json.dumps({"hello": "Salom {name}", "menu": {"shop": "Do'kon"}}), encoding="utf-8")
    (loc / "ru.json").write_text(json.dumps({"hello": "Привет {name}"}), encoding="utf-8")
    i = I18n(loc, default="uz")
    assert i.t("hello", "ru", name="Ali") == "Привет Ali"
    assert i.t("menu.shop", "ru") == "Do'kon"          # falls back to default language
    assert i.resolve("ru-RU") == "ru" and i.resolve("de") == "uz"
    assert i.t("nb.yes", "en") == "✅ Yes"

    env = tmp_path / ".env"
    env.write_text('BOT_TOKEN=9:XYZ\nADMINS=1, 2\nPRICE=1500\nNAME="Nice bot"  \n# comment\n', encoding="utf-8")
    for k in ("BOT_TOKEN", "ADMINS", "PRICE", "NAME"):
        monkeypatch.delenv(k, raising=False)
    bot = Nicebot.from_env(str(env), locales=None)
    assert bot.token == "9:XYZ" and bot.admins == {1, 2}
    assert bot.config.int("PRICE") == 1500 and bot.config.NAME == "Nice bot"
    assert Config({"A": "1,2"}).ints("A") == [1, 2]


def test_cli_new_and_include(tmp_path, monkeypatch):
    from nicebot.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["new", "mybot"]) == 0
    assert (tmp_path / "mybot" / "bot.py").exists() and (tmp_path / "mybot" / "locales" / "ru.json").exists()
    monkeypatch.syspath_prepend(str(tmp_path / "mybot"))
    bot = make_bot()
    bot.include(str(tmp_path / "mybot" / "handlers"))
    names = {h.name for h in bot.all_handlers()}
    assert {"ping", "salom"} <= names


async def test_parse_mode_fallback():
    bot = make_bot()

    @bot.command("x")
    async def x(ctx):
        await ctx.reply("2 < 3 va <b")

    async with bot.test() as t:
        t.fail_next["sendMessage"] = make_error("sendMessage", "Bad Request: can't parse entities: unclosed tag", 400, None)
        await t.user().send("/x")
        last = t.calls_of("sendMessage")[-1].params
        assert "parse_mode" not in last and last["text"] == "2 < 3 va <b"


async def test_edit_not_modified_is_ignored():
    bot = make_bot()

    @bot.command("e")
    async def e(ctx):
        m = await ctx.reply("a")
        await ctx.edit("a", message=m)
        await ctx.reply("ok")

    async with bot.test() as t:
        t.fail_next["editMessageText"] = BadRequest("editMessageText", "Bad Request: message is not modified", 400)
        await t.user().send("/e")
        assert t.last.text == "ok"


async def test_multiple_handlers_skip_and_middleware_order():
    from nicebot import SkipHandler

    bot = make_bot()
    order = []

    @bot.middleware
    async def mw(ctx, nxt):
        order.append("mw")
        await nxt()
        order.append("after")

    @bot.text()
    async def first(ctx):
        order.append("first")
        raise SkipHandler

    @bot.text()
    async def second(ctx):
        order.append("second")

    async with bot.test() as t:
        await t.user().send("hey")
    assert order == ["mw", "first", "second", "after"]


async def test_model_extension_used_as_ctx_user():
    from nicebot import Model, fields
    from nicebot import User as BaseUser

    class Customer(BaseUser):
        balance = fields.Int(default=0)

    bot = make_bot(user_model=Customer)

    @bot.command("pay")
    async def pay(ctx, user: Customer):
        await user.increment("balance", 500)
        await ctx.reply(f"balans {user.balance}")

    async with bot.test() as t:
        u = t.user(id=321)
        await u.send("/pay")
        await u.send("/pay")
        assert t.last.text == "balans 1000"


async def test_webapp_static_files(tmp_path):
    (tmp_path / "index.html").write_text("<h1>app</h1>")
    (tmp_path / "app.js").write_text("console.log(1)")
    bot = make_bot()
    bot.webapp(str(tmp_path))

    @bot.api("/api/ping", methods=["GET"], auth=False)
    async def ping(req):
        return {"pong": True}

    app = build_app(bot)
    async with TestClient(TestServer(app)) as client:
        assert "app" in await (await client.get("/")).text()
        assert "console" in await (await client.get("/app.js")).text()
        assert "app" in await (await client.get("/some/route")).text()
        assert (await (await client.get("/api/ping")).json()) == {"pong": True}
        assert "window.nicebot" in await (await client.get("/nicebot.js")).text()
        r = await client.get("/../../etc/passwd")
        assert "root:" not in await r.text()
