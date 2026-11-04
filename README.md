<div align="center">

# nicebot

**Telegram bot yozing. Kam kod bilan.**

Savol-javob, tugmalar, baza va admin panel bitta importda tayyor turadigan Python kutubxonasi.<br>
Siz faqat botingiz nima qilishini yozasiz.

[**Hujjatlar**](https://ozodmeofficial.github.io/nicebot/) · [Tez start](#-tez-start) · [Imkoniyatlar](#-ichida-nimalar-bor) · [Misol](#-tolaroq-misol)

🇺🇿 O'zbekcha · 🇷🇺 [Документация](https://ozodmeofficial.github.io/nicebot/) · 🇬🇧 [Documentation](https://ozodmeofficial.github.io/nicebot/)

</div>

---

## Bir qarashda

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

Telegram'da foydalanuvchi ko'radigan natija:

```text
👤  /start
🤖  Ismingiz?
👤  Ali
🤖  Yoshingiz?
👤  yigirma
🤖  Butun son kiriting.          ← son bo'lmasa, o'zi qayta so'raydi
👤  20
🤖  Salom, Ali! Siz 20 yoshdasiz.
```

Bu kodda `Dispatcher`, `StatesGroup` va FSM yo'q. `ctx.ask()` savol beradi va javobni **shu funksiya ichida** kutadi. Foydalanuvchi esa bazaga avtomatik saqlanadi.

### aiogram bilan solishtirganda

Ism va yoshni so'raydigan bir xil bot:

| | aiogram 3 | nicebot |
|---|:---:|:---:|
| Kod hajmi | 34 qator | **8 qator** |
| Holatlar klassi (`StatesGroup`) | kerak | yo'q |
| `FSMContext`, `Dispatcher`, `Router` | kerak | yo'q |
| Son tekshiruvi va qayta so'rash | o'zingiz yozasiz | `int` deb yozish kifoya |
| Foydalanuvchini bazaga saqlash | o'zingiz yozasiz | avtomatik |

---

## 🚀 Tez start

**1. O'rnating** — Python 3.10 yoki yangisi kerak:

```bash
pip install nicebot
```

**2. Yozing** — @BotFather'dan token oling va `bot.py` yarating:

```python
from nicebot import Nicebot

bot = Nicebot(token="123456:ABC...")

@bot.command("start")
async def start(ctx):
    await ctx.reply(f"Salom, {ctx.name}!")

bot.start()
```

**3. Ishga tushiring:**

```bash
python bot.py
```

Telegram'da botingizga `/start` yozing — u ismingiz bilan salomlashadi. 🎉

> Tayyor loyiha tuzilmasi kerakmi? `nicebot new mybot && cd mybot && python bot.py` — `.env`, `handlers/` va `locales/` bilan loyiha yaratadi.

### Boshqa bazalar bilan

| Buyruq | Nima qo'shadi |
|---|---|
| `pip install nicebot` | SQLite (qo'shimcha o'rnatishsiz) |
| `pip install "nicebot[postgres]"` | PostgreSQL |
| `pip install "nicebot[mysql]"` | MySQL / MariaDB |
| `pip install "nicebot[mongo]"` | MongoDB |
| `pip install "nicebot[redis]"` | Redis |
| `pip install "nicebot[all]"` | hammasi |

Kod bir xil qoladi, faqat manzil o'zgaradi: `Nicebot(token=..., db="postgresql://...")`.

---

## 📦 Ichida nimalar bor

Hammasi kutubxonaning o'zida — qo'shimcha paket o'rnatmasdan.

| Mavzu | Nima beradi | Qo'llanma |
|---|---|---|
| 💬 **Suhbatlar** | `ask`, `confirm`, `choose(multiple=True)`, `form` — FSM klasslarisiz savol-javob | [Suhbatlar](https://ozodmeofficial.github.io/nicebot/#conversations) |
| ✅ **Validatorlar** | Telefon (+998), email, sana, son, URL, rasm, joylashuv… | [Validatorlar](https://ozodmeofficial.github.io/nicebot/#validators) |
| 🔘 **Tugmalar** | `Button(on_click=func)`, `"buy:{id:int}"` shablonlari, Toggle, `ttl`, `once`, `only`, avto-joylashuv | [Tugmalar](https://ozodmeofficial.github.io/nicebot/#buttons) |
| 🧭 **Menyular** | Ko'p darajali `Menu` ("Orqaga" o'zi qo'shiladi), `ctx.paginate()` | [Menyular](https://ozodmeofficial.github.io/nicebot/#menus) |
| 🗄 **Baza (ORM)** | SQLite, PostgreSQL, MySQL va MongoDB uchun bitta API, avto-migratsiya | [Baza](https://ozodmeofficial.github.io/nicebot/#database) |
| 👥 **Foydalanuvchilar** | Avtomatik saqlash, o'z maydonlaringiz, referal tizimi | [Foydalanuvchilar](https://ozodmeofficial.github.io/nicebot/#users) |
| 🌍 **Ko'p tillilik** | `ctx.t()`, JSON tarjimalar, uz / ru / en tayyor matnlar | [i18n](https://ozodmeofficial.github.io/nicebot/#i18n) |
| 📊 **Admin panel** | `/stats`, `/broadcast`, `/maintenance`, `/backup`, xatolar haqida hisobot | [Admin](https://ozodmeofficial.github.io/nicebot/#admin) |
| 📣 **Broadcast** | Tezlik chegarasi, bloklanganlarni belgilash, to'xtagan joydan davom ettirish | [Broadcast](https://ozodmeofficial.github.io/nicebot/#broadcast) |
| ⭐ **To'lovlar** | Telegram Stars: `ctx.invoice()` va `@bot.paid` | [To'lovlar](https://ozodmeofficial.github.io/nicebot/#payments) |
| 🛡 **Guruhlar** | `ban`, `mute`, `warn`, captcha, majburiy obuna, support rejimi | [Guruhlar](https://ozodmeofficial.github.io/nicebot/#groups) |
| 📱 **Mini App** | `@bot.api` endpointlari, initData HMAC tekshiruvi, tayyor `nicebot.js` | [Mini App](https://ozodmeofficial.github.io/nicebot/#miniapp) |
| 🧩 **Arxitektura** | DI (type hint orqali), middleware, Router, `from_env()`, scheduler, fon vazifalari, kesh | [Middleware](https://ozodmeofficial.github.io/nicebot/#middleware) |
| 🔁 **Ishonchlilik** | Flood-wait, retry, file_id keshi, to'g'ri to'xtash — restartda update yo'qolmaydi | [Deploy](https://ozodmeofficial.github.io/nicebot/#deploy) |
| 🧪 **Testlar** | `bot.test()` — botni Telegram'siz, haqiqiy foydalanuvchidek sinash | [Testlash](https://ozodmeofficial.github.io/nicebot/#testing) |
| 🤖 **Bot API 10.3** | 185 ta metod va 403 ta tur rasmiy spetsifikatsiyadan generatsiya qilingan (msgspec) | [Bot API](https://ozodmeofficial.github.io/nicebot/#api) |

Barcha 50 ta imkoniyat bitta sahifada: **[Imkoniyatlar ro'yxati →](https://ozodmeofficial.github.io/nicebot/#features)**

---

## 🛒 To'laroq misol

Mahsulot tanlash, telefon so'rash, tasdiqlash, bazaga yozish va adminga xabar — barchasi bitta faylda:

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

Nima bo'layapti:

- `Button(..., on_click=buy, product="Kitob")` — tugma bosilganda `buy(ctx, product="Kitob")` chaqiriladi
- `ctx.ask(..., Phone)` — raqamni istalgan ko'rinishda qabul qiladi va `+998901234567` ga keltiradi
- `ctx.confirm()` — "✅ Ha / ❌ Yo'q" tugmalari bilan so'raydi, `True` yoki `False` qaytaradi
- `Order` jadvali bot ishga tushganda o'zi yaratiladi
- `admins=[...]` berilgani uchun `/stats`, `/broadcast`, `/maintenance` va `/backup` ham ishlaydi
- `reload=True` — faylni saqlaganingizda bot o'zi qayta ishga tushadi

### Telegram'siz test

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

`pytest` va `pytest-asyncio` bilan ishlaydi.

---

## 📚 Hujjatlar

To'liq qo'llanma o'zbek, rus va ingliz tillarida: **https://ozodmeofficial.github.io/nicebot/**

| Bo'lim | Ichida |
|---|---|
| [Boshlash](https://ozodmeofficial.github.io/nicebot/#start) | Kirish, o'rnatish, birinchi bot, asosiy tushunchalar |
| [Asoslar](https://ozodmeofficial.github.io/nicebot/#basics) | Handlerlar, `ctx`, matn formatlash |
| [Tugmalar va suhbat](https://ozodmeofficial.github.io/nicebot/#ui) | Tugmalar, klaviatura, suhbatlar, validatorlar, holat, menyular |
| [Ma'lumotlar](https://ozodmeofficial.github.io/nicebot/#data) | Baza (ORM), foydalanuvchilar, ko'p tillilik |
| [Biznes vositalari](https://ozodmeofficial.github.io/nicebot/#business) | Admin panel, broadcast, to'lovlar, guruhlar |
| [Ilg'or](https://ozodmeofficial.github.io/nicebot/#advanced) | Middleware, Mini App, rejalashtirish, deploy, testlash |

## 🛠 Ishlab chiqish

```bash
pip install -e ".[dev]"
pytest                       # testlar
python docs/src/build.py     # hujjatlar sayti → docs/index.html
```

## Litsenziya

MIT © Ozodbek Sobirjonovich
