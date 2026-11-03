import asyncio
import time

from nicebot import Button, Nicebot
from nicebot.keyboards import auto_columns
from nicebot.reload import _snapshot


def make_bot(**kw):
    kw.setdefault("token", "123:TEST")
    kw.setdefault("locales", None)
    return Nicebot(**kw)


async def test_stars_invoice_and_auto_pre_checkout():
    bot = make_bot()
    paid = []

    @bot.command("buy")
    async def buy(ctx):
        await ctx.invoice("Premium", "1 oylik", 50, payload="premium")

    @bot.paid()
    async def ok(ctx):
        paid.append(ctx.message.successful_payment.total_amount)

    async with bot.test() as t:
        u = t.user(id=7)
        await u.send("/buy")
        inv = t.calls_of("sendInvoice")[-1].params
        assert inv["currency"] == "XTR" and inv["prices"][0]["amount"] == 50
        await t.feed({"pre_checkout_query": {"id": "pc1", "from": u.tg, "currency": "XTR", "total_amount": 50, "invoice_payload": "premium"}})
        assert t.calls_of("answerPreCheckoutQuery")[-1].params == {"pre_checkout_query_id": "pc1", "ok": True}
        await u.send(None, successful_payment={"currency": "XTR", "total_amount": 50, "invoice_payload": "premium", "telegram_payment_charge_id": "c1", "provider_payment_charge_id": "p1"})
        assert paid == [50]


async def test_typing_background_and_ttl():
    bot = make_bot()
    attempts = []

    async def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("hali emas")

    @bot.command("work", typing=True)
    async def work(ctx):
        ctx.background(flaky, retries=3, delay="10ms")
        await asyncio.sleep(0.05)
        await ctx.reply("tayyor", buttons=[Button("tez", data="fast", ttl=0.05)])

    @bot.callback("fast")
    async def fast(ctx):
        await ctx.reply("bosildi")

    async with bot.test() as t:
        u = t.user()
        await u.send("/work")
        assert t.calls_of("sendChatAction")[0].params["action"] == "typing"
        await asyncio.sleep(0.1)
        assert len(attempts) == 3
        await u.click("tez")
        assert "muddati tugagan" in t.answers[-1]["text"]


def test_auto_layout():
    assert auto_columns(["Ha", "Yo'q"]) == [2]
    assert auto_columns(["S", "M", "L", "XL", "XXL"]) == [4, 1]
    assert auto_columns(["Juda uzun tugma matni bu yerda", "Ikkinchi uzun tugma matni"]) == [1, 1]


def test_reload_snapshot_sees_changes(tmp_path):
    f = tmp_path / "bot.py"
    f.write_text("x = 1")
    a = _snapshot(tmp_path)
    time.sleep(0.01)
    f.write_text("x = 2")
    import os

    os.utime(f, (time.time() + 5, time.time() + 5))
    assert _snapshot(tmp_path) != a


async def test_unknown_update_is_skipped_safely():
    bot = make_bot()
    async with bot.test():
        await bot.feed(b'{"update_id": 5, "brand_new_update_kind": {"a": 1}}')
        await bot.feed(b'{"update_id": 6, "message": {"broken": true}}')  # invalid → logged, skipped


async def test_reply_keyboard_shortcuts_and_lang():
    bot = make_bot()

    @bot.command("kb")
    async def kb(ctx):
        await ctx.reply(ctx.t("nb.yes"), keyboard=["📞 Raqam:contact", "📍 Joy:location", "Menyu"], columns=2)

    async with bot.test() as t:
        await t.user(lang="ru").send("/kb")
        p = t.calls_of("sendMessage")[-1].params
        assert p["text"] == "✅ Да"
        rows = p["reply_markup"]["keyboard"]
        assert rows[0][0] == {"text": "📞 Raqam", "request_contact": True}
        assert rows[0][1] == {"text": "📍 Joy", "request_location": True}
        assert p["reply_markup"]["resize_keyboard"] is True


async def test_fk_to_extended_user_by_name():
    from nicebot import Model, User, fields

    class Member(User):
        points = fields.Int(default=0)

    class Ticket(Model):
        user = fields.ForeignKey("User")
        title = fields.Str(50)

    bot = make_bot(user_model=Member)

    @bot.command("t")
    async def t_(ctx, user: Member):
        await Ticket.create(user=user, title="x")
        tk = await Ticket.get(user=user)
        owner = await tk.user
        await ctx.reply(f"{type(owner).__name__}:{owner.id}:{await Ticket.filter(user=ctx.user).count()}")

    async with bot.test() as t:
        await t.user(id=77).send("/t")
        assert t.last.text == "Member:77:1"
