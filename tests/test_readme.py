"""The README example must keep working."""
from nicebot import Button, Model, Nicebot, Phone, fields


class ReadmeOrder(Model):
    user_id = fields.BigInt(index=True)
    product = fields.Str(100)
    phone = fields.Str(20)


async def test_readme_shop_example():
    bot = Nicebot(token="1:X", admins=[123456789], locales=None)

    async def buy(ctx, product: str):
        phone = await ctx.ask("Telefon raqamingiz?", Phone)
        if await ctx.confirm(f"{product} buyurtma qilinsinmi?"):
            await ReadmeOrder.create(user_id=ctx.user_id, product=product, phone=phone)
            await ctx.reply("✅ Qabul qilindi!")
            await ctx.notify_admins(f"🛒 Yangi buyurtma: {product}, {phone}")

    @bot.command("shop", description="Do'kon")
    async def shop(ctx):
        await ctx.reply("Mahsulotni tanlang:", buttons=[
            Button("📚 Kitob", on_click=buy, product="Kitob"),
            Button("🎧 Quloqchin", on_click=buy, product="Quloqchin"),
        ])

    async with bot.test() as t:
        user = t.user(first_name="Ali")
        await user.send("/shop")
        await user.click("Kitob")
        await user.send("90 123 45 67")
        await user.click("Ha")
        assert t.last_in(user.chat_id).text == "✅ Qabul qilindi!"
        order = await ReadmeOrder.get(user_id=user.id)
        assert order.phone == "+998901234567" and order.product == "Kitob"
        assert any("Yangi buyurtma" in (m.text or "") for m in t.messages if m.chat_id == 123456789)
