import asyncio

import pytest

from nicebot import Button, F, Menu, Nicebot, Phone, Router, Toggle, User, html


def make_bot(**kw):
    kw.setdefault("token", "123:TEST")
    kw.setdefault("locales", None)
    return Nicebot(**kw)


async def test_command_and_reply():
    bot = make_bot()

    @bot.command("start", description="Boshlash")
    async def start(ctx):
        await ctx.reply(f"Salom, {ctx.name}!")

    async with bot.test() as t:
        ali = t.user(first_name="Ali")
        await ali.send("/start")
        assert t.last.text == "Salom, Ali!"
        assert t.calls_of("setMyCommands")[0].params["commands"][0]["command"] == "start" if t.calls_of("setMyCommands") else True


async def test_user_is_saved_and_referral():
    bot = make_bot()
    seen = []

    @bot.on_referral
    async def ref(ctx, referrer):
        seen.append(referrer.id)

    @bot.command("start")
    async def start(ctx, user: User):
        await ctx.reply(f"id={user.id} new={ctx.extra.get('new_user', False)}")

    async with bot.test() as t:
        a = t.user(id=10, first_name="A")
        await a.send("/start")
        assert t.last.text == "id=10 new=True"
        b = t.user(id=11, first_name="B")
        await b.send("/start ref_10")
        assert seen == [10]
        assert (await User.get(id=11)).referrer_id == 10
        await a.send("/start")
        assert t.last.text == "id=10 new=False"
        assert bot.ref_link(10) == "https://t.me/test_bot?start=ref_10"


async def test_ask_confirm_choose_form():
    bot = make_bot()
    result = {}

    @bot.command("reg")
    async def reg(ctx):
        result["name"] = await ctx.ask("Ismingiz?")
        result["age"] = await ctx.ask("Yoshingiz?", int)
        result["size"] = await ctx.ask("O'lcham?", buttons=["S", "M", "L"])
        result["ok"] = await ctx.confirm("Tasdiqlaysizmi?")
        result["many"] = await ctx.choose("Qaysilar?", {"Olma": 1, "Nok": 2, "Uzum": 3}, multiple=True)
        data = await ctx.form(phone=Phone("Raqam?"), city="Shahar?")
        result.update(data)
        await ctx.reply("tayyor")

    async with bot.test() as t:
        u = t.user()
        await u.send("/reg")
        assert t.last.text == "Ismingiz?"
        await u.send("Ali")
        await u.send("yigirma")
        assert "Butun son" in t.last.text
        await u.send("20")
        await u.click("M")
        size_msg = [m for m in t.messages if (m.text or "").startswith("O'lcham?")][0]
        assert "<b>M</b>" in size_msg.text and not size_msg.buttons
        assert t.last.text == "Tasdiqlaysizmi?"
        await u.click("Ha")
        await u.click("Olma")
        assert "✅ Olma" in t.last.buttons
        await u.click("Uzum")
        await u.click("Tayyor")
        assert "Raqam?" in t.last.text
        assert t.calls_of("sendMessage")[-1].params["reply_markup"]["keyboard"][0][0]["request_contact"] is True
        await u.send("90 123 45 67")
        await u.send("Navoiy")
        await asyncio.sleep(0)
        assert result == {"name": "Ali", "age": 20, "size": "M", "ok": True, "many": [1, 3], "phone": "+998901234567", "city": "Navoiy"}
        assert t.texts[-1] == "tayyor"


async def test_cancel_and_timeout():
    bot = make_bot(ask_timeout=0.2)
    done = []

    @bot.command("q")
    async def q(ctx):
        await ctx.ask("Savol?")
        done.append(True)

    async with bot.test() as t:
        u = t.user()
        await u.send("/q")
        await u.send("/cancel")
        assert t.last.text == "Bekor qilindi."
        await u.send("/q")
        await asyncio.sleep(0.35)
        await t.settle()
        assert "vaqti tugadi" in t.last.text
        assert done == []


async def test_buttons_on_click_template_and_params():
    bot = make_bot()
    log = []

    async def buy(ctx, id: int):
        log.append(("buy", id, ctx.value))
        await ctx.edit("Sotildi")

    @bot.callback("product:{id:int}:{size}")
    async def product(ctx, id: int, size: str):
        log.append(("product", id, size))

    @bot.command("shop")
    async def shop(ctx):
        await ctx.reply("Do'kon", buttons=[
            [Button("Sotib olish", on_click=buy, id=7)],
            [Button("Ko'rish", on_click=product, id=5, size="XL")],
            [Button("Sayt", url="https://tezbaraka.uz"), Button("Nusxa", copy="PROMO")],
        ])

    async with bot.test() as t:
        u = t.user()
        await u.send("/shop")
        assert t.last.buttons == ["Sotib olish", "Ko'rish", "Sayt", "Nusxa"]
        await u.click("Ko'rish")
        await u.click("Sotib olish")
        assert log == [("product", 5, "XL"), ("buy", 7, 7)]
        assert t.last.text == "Sotildi"
        assert t.answers  # callbacks answered automatically


async def test_button_ttl_once_only_and_long_data():
    bot = make_bot()
    hits = []

    async def press(ctx):
        hits.append(ctx.user_id)

    @bot.command("b")
    async def b(ctx):
        await ctx.reply("x", buttons=[
            Button("once", on_click=press, once=True),
            Button("mine", on_click=press, only=ctx.user_id),
            Button("long", on_click=press, note="x" * 80),
        ])

    async with bot.test() as t:
        a, other = t.user(id=1), t.user(id=2)
        await a.send("/b")
        msg = t.last
        assert all(len(d.encode()) <= 64 for d in [btn["callback_data"] for row in msg.markup["inline_keyboard"] for btn in row])
        await a.click("once", message=msg)
        await a.click("once", message=msg)
        assert t.answers[-1]["text"] == "Bu tugma allaqachon ishlatilgan."
        await other.click("mine", message=msg)
        assert t.answers[-1]["text"].startswith("🙅")
        await a.click("long", message=msg)
        assert hits == [1, 1]


async def test_toggle_menu_pagination():
    bot = make_bot()
    changed = []

    async def on_notify(ctx, value):
        changed.append(value)

    menu = Menu("Bosh menyu", {
        "🛍 Do'kon": Menu("Do'kon", {"Kiyim": "Kiyimlar ro'yxati", "Poyabzal": "Tez kunda"}),
        "🌐 Sayt": "https://tezbaraka.uz",
    })

    @bot.command("settings")
    async def settings(ctx):
        await ctx.reply("Sozlamalar", buttons=[Toggle("Bildirishnoma", key="notify", on_change=on_notify)])

    @bot.command("menu")
    async def m(ctx):
        await ctx.menu(menu)

    @bot.command("list")
    async def lst(ctx):
        await ctx.paginate([f"Mahsulot {i}" for i in range(1, 26)], per_page=10, title="Mahsulotlar")

    async with bot.test() as t:
        u = t.user()
        await u.send("/settings")
        assert t.last.buttons == ["⬜️ Bildirishnoma"]
        await u.click("Bildirishnoma")
        assert t.last.buttons == ["✅ Bildirishnoma"]
        assert changed == [True]
        await u.click("Bildirishnoma")
        assert changed == [True, False]

        await u.send("/menu")
        await u.click("Do'kon")
        assert t.last.text == "Do'kon"
        await u.click("Kiyim")
        assert t.last.text == "Kiyimlar ro'yxati"
        await u.click("Orqaga")
        assert t.last.text == "Do'kon"
        await u.click("Orqaga")
        assert t.last.text == "Bosh menyu"

        await u.send("/list")
        assert "1. Mahsulot 1" in t.last.text and "1/3" in t.last.buttons
        await u.click("▶️")
        assert "11. Mahsulot 11" in t.last.text and "2/3" in t.last.buttons


async def test_text_filters_state_router_and_di():
    bot = make_bot()
    shop = Router(chat="private")

    class Config:
        price = 100

    bot.provide(Config, Config())

    @shop.text("narx")
    async def narx(ctx, cfg: Config):
        await ctx.reply(f"Narx {cfg.price}")

    @bot.text(regex=r"^buy (?P<qty>\d+)$")
    async def buy(ctx, qty: int):
        await ctx.reply(f"qty={qty * 2}")

    @bot.message(F.photo)
    async def photo(ctx):
        await ctx.reply("rasm")

    @bot.command("wait")
    async def w(ctx):
        await ctx.set_state("waiting", step=1)
        await ctx.reply("kutyapman")

    @bot.text(state="waiting")
    async def got(ctx, text):
        data = await ctx.state_data()
        await ctx.clear_state()
        await ctx.reply(f"oldim {text} {data.step}")

    @bot.fallback()
    async def fb(ctx):
        await ctx.reply("tushunmadim")

    bot.include(shop)

    async with bot.test() as t:
        u = t.user()
        await u.send("NARX")
        assert t.last.text == "Narx 100"
        await u.send("buy 21")
        assert t.last.text == "qty=42"
        await u.send_photo()
        assert t.last.text == "rasm"
        await u.send("/wait")
        await u.send("salom")
        assert t.last.text == "oldim salom 1"
        await u.send("nimadir")
        assert t.last.text == "tushunmadim"


async def test_admin_throttle_errors_and_maintenance():
    bot = make_bot(admins=[1])
    errors = []

    @bot.command("secret", admin=True)
    async def secret(ctx):
        await ctx.reply("maxfiy")

    @bot.command("slow", throttle="1h")
    async def slow(ctx):
        await ctx.reply("ok")

    @bot.command("boom")
    async def boom(ctx):
        raise RuntimeError("portladi")

    @bot.command("handled")
    async def handled(ctx):
        raise KeyError("k")

    @bot.error(KeyError)
    async def on_key(ctx, error):
        errors.append(repr(error))
        await ctx.reply("key xato")

    async with bot.test() as t:
        admin, user = t.user(id=1), t.user(id=2)
        await user.send("/secret")
        assert not t.messages
        await admin.send("/secret")
        assert t.last.text == "maxfiy"
        await user.send("/slow")
        await user.send("/slow")
        await user.send("/slow")
        assert t.texts[-2:] == ["ok", "⏳ Biroz kuting..."]
        await user.send("/boom")
        assert "Xatolik" in t.texts[-1] or "Xatolik" in t.texts[-2]
        assert any("portladi" in (m.text or "") for m in t.messages if m.chat_id == 1)
        await user.send("/handled")
        assert t.last.text == "key xato" and errors
        await admin.send("/maintenance on")
        await user.send("/slow")
        assert "texnik ishlar" in t.last.text.lower()
        await admin.send("/maintenance off")
        await admin.send("/stats")
        assert "Statistika" in t.last.text and "Jami: <b>2</b>" in t.last.text


async def test_required_channels_and_support_relay():
    bot = make_bot(required_channels=["@kanal"], support_chat=-100500, admins=[1])

    @bot.command("start")
    async def start(ctx):
        await ctx.reply("xush kelibsiz")

    async with bot.test(member_status="left") as t:
        u = t.user(id=5)
        await u.send("/start")
        assert "obuna" in t.last.text and t.last.buttons[0] == "@kanal"
        t.member_status = "member"
        await u.click("Tekshirish")
        assert t.last.text == "xush kelibsiz"
        await u.send("Yordam kerak")
        support_msgs = [m for m in t.messages if m.chat_id == -100500]
        assert support_msgs and "<code>5</code>" in support_msgs[0].text
        assert t.last.text.startswith("✅ Xabaringiz")
        admin_group = t.user(id=1, chat_id=-100500, chat_type="supergroup")
        reply_to = {k: v for k, v in support_msgs[-1].data.items() if not k.startswith("_")}
        await admin_group.send("Salom, yordam beramiz", reply_to_message=reply_to)
        assert t.calls_of("copyMessage")[-1].params["chat_id"] == 5


async def test_album_inline_and_files(tmp_path):
    bot = make_bot()

    @bot.album()
    async def album(ctx, album):
        await ctx.reply(f"{len(album)} ta rasm")

    @bot.inline()
    async def inline(ctx):
        await ctx.answer_inline([(f"Natija {i}", f"matn {i}") for i in range(120)])

    @bot.command("pic")
    async def pic(ctx):
        await ctx.photo(str(tmp_path / "a.png"), caption=html("<b>{}</b>", "<rasm>"), delete_after="1h")

    (tmp_path / "a.png").write_bytes(b"\x89PNG....")

    async with bot.test() as t:
        u = t.user()
        await u.send_album(3)
        assert t.last.text == "3 ta rasm"
        await u.inline("x")
        call = t.calls_of("answerInlineQuery")[-1].params
        assert len(call["results"]) == 50 and call["next_offset"] == "50"
        await u.inline("x", offset="100")
        assert t.calls_of("answerInlineQuery")[-1].params["next_offset"] == ""
        await u.send("/pic")
        first = t.calls_of("sendPhoto")[-1].params
        assert first["photo"].startswith("<upload:") and first["caption"] == "<b>&lt;rasm&gt;</b>"
        await u.send("/pic")
        second = t.calls_of("sendPhoto")[-1].params
        assert second["photo"].startswith("fid_")  # file_id cache hit, no re-upload


async def test_parse_fallback_and_respond():
    bot = make_bot()

    @bot.command("x")
    async def x(ctx):
        await ctx.reply("plain", buttons=[Button("tahrir", data="edit")])

    @bot.callback("edit")
    async def e(ctx):
        await ctx.respond("tahrirlandi")

    async with bot.test() as t:
        u = t.user()
        await u.send("/x")
        await u.click("tahrir")
        assert t.last.text == "tahrirlandi" and len(t.messages) == 1
