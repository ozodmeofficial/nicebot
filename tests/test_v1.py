"""Tests for the 1.0 features: media, Mini Apps, typing-friendly helpers and the bug fixes."""
import os
import sys

import pytest

from nicebot import Button, Context, Document, File, FileTooBig, Media, Nicebot, Photo, ReplyButton, Video, WebAppRequest
from nicebot.server import sign_init_data, validate_init_data
from nicebot.tunnel import Tunnel, TunnelError, find_url


def make_bot(**kw):
    kw.setdefault("token", "123:TEST")
    kw.setdefault("locales", None)
    return Nicebot(**kw)


# ----------------------------------------------------------------------------- bug fixes
async def test_deep_link_is_both_decorator_and_link():
    bot = make_bot()

    @bot.deep_link(r"promo_(?P<code>\w+)")
    async def promo(ctx: Context, code: str):
        await ctx.reply(f"code={code}")

    async with bot.test() as t:
        link = bot.deep_link("abc")
        assert link == "https://t.me/test_bot?start=abc" == bot.start_link("abc")
        ali = t.user()
        await ali.send("/start promo_X1")
        assert t.last.text == "code=X1"


async def test_answer_inline_accepts_a_generator():
    bot = make_bot()

    @bot.inline()
    async def search(ctx: Context):
        await ctx.answer_inline((f"Item {i}", f"text {i}") for i in range(60))

    async with bot.test() as t:
        await t.user().inline("x")
        call = t.calls_of("answerInlineQuery")[0]
        assert len(call.params["results"]) == 50 and call.params["next_offset"] == "50"


async def test_missing_local_file_raises_clear_error(tmp_path):
    bot = make_bot()
    errors = []

    @bot.command("pic")
    async def pic(ctx: Context):
        try:
            await ctx.photo(str(tmp_path / "nope.jpg"))
        except FileNotFoundError as e:
            errors.append(str(e))

    async with bot.test() as t:
        await t.user().send("/pic")
    assert errors and "nope.jpg" in errors[0]


async def test_pin_without_message_gives_readable_error():
    bot = make_bot()
    seen = []

    @bot.inline()
    async def inline(ctx: Context):
        try:
            await ctx.pin()
        except ValueError as e:
            seen.append(str(e))

    async with bot.test() as t:
        await t.user().inline("q")
    assert seen and "needs a message" in seen[0]


async def test_choose_with_unhashable_selected():
    bot = make_bot()
    result = []

    @bot.command("pick")
    async def pick(ctx: Context):
        result.append(await ctx.choose("?", {"A": {"v": 1}, "B": {"v": 2}}, multiple=True, selected=[{"v": 1}]))

    async with bot.test() as t:
        ali = t.user()
        await ali.send("/pick")
        assert t.last.buttons[0].startswith("✅") and t.last.buttons[1].startswith("⬜")
        await ali.click(t.last.buttons[-1])
    assert result == [[{"v": 1}]]


async def test_alert_is_a_real_method():
    bot = make_bot()

    async def warn(ctx: Context):
        await ctx.alert("careful")

    @bot.command("w")
    async def w(ctx: Context):
        await ctx.reply("press", buttons=[Button("warn", on_click=warn)])

    async with bot.test() as t:
        ali = t.user()
        await ali.send("/w")
        await ali.click("warn")
        assert t.answers[-1]["show_alert"] is True and t.answers[-1]["text"] == "careful"


async def test_admin_texts_follow_the_bot_language():
    bot = make_bot(admins=[555], lang="en")

    async with bot.test() as t:
        admin = t.user(id=555, lang="en")
        await admin.send("/stats")
        assert "Statistics" in t.last.text and "Total" in t.last.text


# ----------------------------------------------------------------------------- media
async def test_ctx_media_download_and_save(tmp_path):
    bot = make_bot()
    out = {}

    @bot.on("document", "photo")
    async def got(ctx: Context):
        m = ctx.media
        out["media"] = m
        out["bytes"] = await m.download()
        out["path"] = await m.save(str(tmp_path) + "/")
        out["auto"] = await ctx.save(folder=str(tmp_path / "auto"))

    async with bot.test() as t:
        ali = t.user()
        await ali.send_document("report.pdf", content=b"%PDF-1.7 hello")
    m = out["media"]
    assert isinstance(m, Media) and m.kind == "document" and m.name == "report.pdf" and m.mime == "application/pdf"
    assert m.size == 14 and m.size_text == "14 B" and m.extension == ".pdf"
    assert out["bytes"] == b"%PDF-1.7 hello"
    assert out["path"].endswith("report.pdf") and open(out["path"], "rb").read() == b"%PDF-1.7 hello"
    assert os.path.basename(out["auto"]) == "report.pdf"


async def test_too_big_file_raises_file_too_big():
    bot = make_bot()
    seen = []

    @bot.on("video")
    async def got(ctx: Context):
        assert not ctx.media.can_download
        try:
            await ctx.download()
        except FileTooBig as e:
            seen.append(e.size)

    async with bot.test() as t:
        await t.user().send_video(size=30 * 1024 * 1024)
    assert seen == [30 * 1024 * 1024]


async def test_send_file_guesses_kind_and_mixed_album(tmp_path):
    img = tmp_path / "cat.jpg"
    img.write_bytes(b"\xff\xd8 jpeg")
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"mp4")
    bot = make_bot()

    @bot.command("go")
    async def go(ctx: Context):
        await ctx.send_file(str(img), "a cat")
        await ctx.send_file(b"col1,col2", filename="data.csv")
        await ctx.media_group([str(img), str(vid)], "trip")

    async with bot.test() as t:
        await t.user().send("/go")
        assert t.calls_of("sendPhoto")[0].params["caption"] == "a cat"
        assert t.calls_of("sendDocument")[0].params["document"] == "<upload:data.csv>"
        types = [m["type"] for m in t.calls_of("sendMediaGroup")[0].params["media"]]
        assert types == ["photo", "video"]


async def test_edit_media_replaces_the_photo():
    bot = make_bot()

    async def nxt(ctx: Context):
        await ctx.edit_media("https://example.com/2.jpg", "second")

    @bot.command("gallery")
    async def gallery(ctx: Context):
        await ctx.photo("https://example.com/1.jpg", "first", buttons=[Button("▶️", on_click=nxt)])

    async with bot.test() as t:
        ali = t.user()
        await ali.send("/gallery")
        await ali.click("▶️")
        call = t.calls_of("editMessageMedia")[0]
        assert call.params["media"]["media"] == "https://example.com/2.jpg" and t.last.text == "second"


async def test_file_validators_with_limits():
    bot = make_bot()
    got = {}

    @bot.command("cv")
    async def cv(ctx: Context):
        got["cv"] = await ctx.ask("CV?", Document(mime="application/pdf", max_size="1KB"))
        got["any"] = await ctx.ask("Any?", File)
        got["photo"] = await ctx.ask("Photo?", Photo)
        got["video"] = await ctx.ask("Video?", Video)

    async with bot.test() as t:
        ali = t.user(lang="en")
        await ali.send("/cv")
        await ali.send_document("big.pdf", size=5000)
        assert "too big" in t.last.text
        await ali.send_document("x.png", size=10)
        assert "not accepted" in t.last.text
        await ali.send_document("ok.pdf", size=10)
        await ali.send_voice()
        await ali.send_photo()
        await ali.send_video()
    assert got["cv"].name == "ok.pdf" and got["any"].kind == "voice"
    assert got["photo"].width == 800 and got["video"].kind == "video"


# ----------------------------------------------------------------------------- mini apps
def test_webapp_url_rules():
    bot = make_bot()
    with pytest.raises(ValueError, match="public HTTPS"):
        bot.webapp_url("/shop")
    with pytest.raises(ValueError, match="only over HTTPS"):
        bot.webapp_url("http://localhost:8080/")
    bot.public_url = "https://abc.trycloudflare.com"
    assert bot.webapp_url("/shop?x=1") == "https://abc.trycloudflare.com/shop?x=1"
    assert make_bot(test_server=True).webapp_url("http://192.168.1.5:8080/") == "http://192.168.1.5:8080/"
    assert make_bot(test_server=True).client.method_url("getMe").endswith("/bot123:TEST/test/getMe")


async def test_relative_webapp_buttons_use_public_url():
    bot = make_bot(public_url="https://my.app")

    @bot.command("open")
    async def open_(ctx: Context):
        await ctx.reply("Shop", buttons=[Button("🛍", webapp="/shop")])
        await ctx.reply("Order", keyboard=[ReplyButton("📝", webapp="/order")])

    async with bot.test() as t:
        await t.user().send("/open")
        first, second = t.calls_of("sendMessage")[:2]
        assert first.params["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"] == "https://my.app/shop"
        assert second.params["reply_markup"]["keyboard"][0][0]["web_app"]["url"] == "https://my.app/order"


async def test_api_route_user_send_answer_and_upload(tmp_path):
    bot = make_bot()

    @bot.api("/api/me", methods=["GET"])
    async def me(req: WebAppRequest):
        await req.send(f"hi {req.user.first_name}")
        return {"id": req.user.id, "name": req.user["first_name"], "query": req.query_id}

    @bot.api("/api/upload")
    async def upload(req: WebAppRequest):
        form = await req.form()
        path = await form["photo"].save(tmp_path / "a.jpg")
        await req.answer("Order", "ordered!")
        return {"size": form["photo"].size, "comment": form["comment"], "path": path}

    async with bot.test() as t:
        ali = t.user(first_name="Ali")
        r = await t.api("/api/me", method="GET", user=ali)
        assert r.status == 200 and r.json == {"id": ali.id, "name": "Ali", "query": "test_query"}
        assert t.last_in(ali.chat_id).text == "hi Ali"
        assert (await t.api("/api/me", method="GET")).status == 401

        import aiohttp

        form = aiohttp.FormData()
        form.add_field("comment", "nice")
        form.add_field("photo", b"12345", filename="a.jpg", content_type="image/jpeg")
        r = await t.api("/api/upload", data=form, user=ali)
        assert r.json["size"] == 5 and r.json["comment"] == "nice"
        assert (tmp_path / "a.jpg").read_bytes() == b"12345"
        assert t.calls_of("answerWebAppQuery")[0].params["web_app_query_id"] == "test_query"


async def test_cors_and_dev_init():
    bot = make_bot(cors=["https://me.github.io"], debug=True, dev_user={"id": 7, "first_name": "Dev"})

    @bot.api("/api/ping")
    async def ping(req: WebAppRequest):
        return {"user": req.user.id}

    async with bot.test() as t:
        r = await t.api("/api/ping", method="OPTIONS", headers={"Origin": "https://me.github.io", "Access-Control-Request-Method": "POST"}, auth=False)
        assert r.status == 204 and r.headers["Access-Control-Allow-Origin"] == "https://me.github.io"
        r = await t.api("/api/ping", method="OPTIONS", headers={"Origin": "https://evil.example"}, auth=False)
        assert "Access-Control-Allow-Origin" not in r.headers
        r = await t.api("/nicebot/dev-init", method="GET", auth=False)
        assert r.status == 200 and validate_init_data(r.json["initData"], bot.token)["user"]["id"] == 7
        r = await t.api("/nicebot.js", method="GET", auth=False)
        assert "window.nicebot" in r.text and "upload" in r.text


async def test_webapp_data_and_menu_app():
    bot = make_bot(public_url="https://my.app")
    got = []

    @bot.webapp_data()
    async def data(ctx: Context):
        got.append(ctx.web_app_data)

    async with bot.test() as t:
        await t.user().send_web_app_data({"total": 90000})
        assert got == [{"total": 90000}]
        await bot.set_menu_app("🛍 Shop", "/")
        mb = t.calls_of("setChatMenuButton")[0].params["menu_button"]
        assert mb["type"] == "web_app" and mb["web_app"]["url"] == "https://my.app/"


def test_init_data_roundtrip_and_app_link():
    raw = sign_init_data({"user": {"id": 1, "first_name": "Ali"}, "start_param": "promo"}, "123:TEST")
    assert validate_init_data(raw, "123:TEST")["start_param"] == "promo"
    bot = make_bot()
    bot.username = "shop_bot"
    assert bot.app_link("store", startapp="x") == "https://t.me/shop_bot/store?startapp=x"


def test_find_url():
    assert find_url("|  https://red-cat-42.trycloudflare.com  |") == "https://red-cat-42.trycloudflare.com"
    assert find_url("abc.lhr.life tunneled with tls termination, https://abc123.lhr.life") == "https://abc123.lhr.life"
    assert find_url("see https://developers.cloudflare.com/x") is None


async def test_tunnel_with_custom_command():
    cmd = [sys.executable, "-c", "import time; print('ready at https://demo-1.trycloudflare.com', flush=True); time.sleep(30)"]
    tun = await Tunnel.open(8080, cmd, timeout=10)
    try:
        assert tun.url == "https://demo-1.trycloudflare.com"
    finally:
        await tun.close()
    with pytest.raises(TunnelError):
        await Tunnel.open(8080, [sys.executable, "-c", "print('no url')"], timeout=10)
