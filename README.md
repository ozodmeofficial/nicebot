# nicebot

**Telegram botlar uchun Python kutubxonasi: kam kod, hamma narsa ichida.**

[![PyPI](https://img.shields.io/pypi/v/nicebot.svg)](https://pypi.org/project/nicebot/)
[![Python](https://img.shields.io/pypi/pyversions/nicebot.svg)](https://pypi.org/project/nicebot/)
[![Bot API](https://img.shields.io/badge/Bot%20API-10.3-c4613c.svg)](https://core.telegram.org/bots/api)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

🇺🇿 O'zbekcha · 🇷🇺 [Документация на русском](https://ozodmeofficial.github.io/nicebot/) · 🇬🇧 [English docs](https://ozodmeofficial.github.io/nicebot/)

```python
from nicebot import Nicebot

bot = Nicebot(token="123456:ABC...")

@bot.command("start")
async def start(ctx):
    name = await ctx.ask("Ismingiz?")
    age = await ctx.ask("Yoshingiz?", int)
    await ctx.reply(f"Salom, {name}! Siz {age} yoshdasiz.")

bot.start()
```

Bu kodda `Dispatcher`, `StatesGroup` va FSM yo'q. `ctx.ask()` savol berib, javobni o'sha joyda kutadi. Son kiritilmasa, o'zi qayta so'raydi. Foydalanuvchi esa bazaga avtomatik saqlanadi.

## O'rnatish

```bash
pip install nicebot                # SQLite bilan
pip install "nicebot[postgres]"    # + PostgreSQL
pip install "nicebot[mysql]"       # + MySQL / MariaDB
pip install "nicebot[mongo]"       # + MongoDB
pip install "nicebot[all]"         # hammasi + Redis
```

Tayyor loyiha yaratish:

```bash
nicebot new mybot && cd mybot && python bot.py
```

## Ichida nimalar bor

| | |
|---|---|
| **Bot API 10.3 to'liq** | 403 ta tur va 185 ta metod rasmiy spetsifikatsiyadan generatsiya qilingan, msgspec asosida |
| **Ichki ORM** | SQLite, PostgreSQL, MySQL va MongoDB uchun bitta API, avto-migratsiya bilan |
| **Suhbatlar** | `ask`, `confirm`, `choose(multiple=True)`, `form` va validatorlar (telefon +998, email, sana…) |
| **Tugmalar** | `Button(on_click=func)`, `"buy:{id:int}"` shablonlari, Toggle, `ttl`, `once`, `only`, avto-joylashuv |
| **UI** | Ko'p darajali `Menu`, `ctx.paginate()`, reply klaviatura qisqartmalari |
| **Biznes** | Referal, broadcast (davom ettirish bilan), statistika, admin panel, majburiy obuna, support, Telegram Stars |
| **Guruhlar** | `ban`, `mute`, `warn`, captcha |
| **Mini App** | `@bot.api` endpointlari, initData HMAC tekshiruvi, `nicebot.js` |
| **Arxitektura** | DI (type hint orqali), middleware, Router, `from_env()`, scheduler, fon vazifalari, kesh |
| **Ishonchlilik** | Flood-wait, retry, file_id keshi, to'g'ri to'xtash, xatolar haqida adminlarga hisobot |
| **Ishlab chiqish** | `reload=True`, `bot.test()` (Telegram'siz testlar), CLI |

To'liq ro'yxat va qo'llanma: **[hujjatlar sayti](https://ozodmeofficial.github.io/nicebot/)** (uz / ru / en).

## Yana misollar

```python
from nicebot import Nicebot, Button, Model, fields, Phone

bot = Nicebot(token="...", db="sqlite:///shop.db", admins=[123456789])

class Order(Model):
    user_id = fields.BigInt(index=True)
    product = fields.Str(100)
    phone = fields.Str(20)

async def buy(ctx, product: str):
    phone = await ctx.ask("Telefon raqamingiz?", Phone)
    if await ctx.confirm(f"{product} buyurtma qilinsinmi?"):
        await Order.create(user_id=ctx.user_id, product=product, phone=phone)
        await ctx.reply("✅ Qabul qilindi!")
        await ctx.notify_admins(f"🛒 Yangi buyurtma: {product}, {phone}")

@bot.command("shop", description="Do'kon")
async def shop(ctx):
    await ctx.reply("Mahsulotni tanlang:", buttons=[
        Button("📚 Kitob", on_click=buy, product="Kitob"),
        Button("🎧 Quloqchin", on_click=buy, product="Quloqchin"),
    ])

bot.start(reload=True)
```

Adminlar uchun `/stats`, `/broadcast`, `/maintenance` va `/backup` buyruqlari avtomatik ishlaydi.

## Testlash

```python
async def test_shop():
    async with bot.test() as t:
        user = t.user(first_name="Ali")
        await user.send("/shop")
        await user.click("Kitob")
        await user.send("90 123 45 67")
        await user.click("Ha")
        assert t.last_in(user.chat_id).text == "✅ Qabul qilindi!"
```

## Litsenziya

MIT © Ozodbek Sobirjonovich
