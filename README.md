<div align="center">

# nicebot

**Telegram bot yozing. Kam kod bilan.**

Savol-javob, tugmalar, fayllar, baza, Mini App va admin panel bitta importda tayyor turadigan Python kutubxonasi.<br>
Siz faqat botingiz nima qilishini yozasiz.

[**Hujjatlar**](https://ozodmeofficial.github.io/nicebot/) · [Tez start](#-tez-start) · [Fayllar](#-fayllar) · [Mini App](#-mini-app) · [Imkoniyatlar](#-ichida-nimalar-bor) · [Misol](#-tolaroq-misol)

🇺🇿 O'zbekcha · 🇷🇺 [Документация](https://ozodmeofficial.github.io/nicebot/) · 🇬🇧 [Documentation](https://ozodmeofficial.github.io/nicebot/)

</div>

---

## Bir qarashda

```python
from nicebot import Context, Nicebot

bot = Nicebot(token="123456:ABC...")

@bot.command("start")
async def start(ctx: Context):
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
| Mini App backend va HTTPS | alohida server | `@bot.api` va `tunnel=True` |

---

## 🚀 Tez start

**1. O'rnating** — Python 3.10 yoki yangisi kerak:

```bash
pip install nicebot
```

**2. Yozing** — @BotFather'dan token oling va `bot.py` yarating:

```python
from nicebot import Context, Nicebot

bot = Nicebot(token="123456:ABC...")

@bot.command("start")
async def start(ctx: Context):
    await ctx.reply(f"Salom, {ctx.name}!")

bot.start()
```

**3. Ishga tushiring:**

```bash
python bot.py
```

Telegram'da botingizga `/start` yozing — u ismingiz bilan salomlashadi. 🎉

> **VS Code maslahati:** handler parametriga `ctx: Context` deb yozing. Shunda `ctx.` dan keyin barcha metodlar, ularning parametrlari va ishlatish misollari ko'rinadi. Kutubxonaning har bir funksiyasida inglizcha tavsif va misol bor. [Batafsil →](https://ozodmeofficial.github.io/nicebot/#vscode)

Tayyor loyiha tuzilmasi kerak bo'lsa:

```bash
nicebot new mybot && cd mybot && python bot.py
```

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

## 📎 Fayllar

Kelgan rasm, video, hujjat yoki ovozli xabar — bitta `Media` obyekti:

```python
from nicebot import Context, Document

@bot.on("photo", "video", "document", "voice")
async def got_file(ctx: Context):
    m = ctx.media                                   # turi, hajmi, nomi, MIME
    path = await m.save("uploads/")                 # diskka (bo'laklab), nom o'zi qo'yiladi
    await ctx.reply(f"{m.kind}, {m.size_text} → {path}")

@bot.command("cv")
async def cv(ctx: Context):
    file = await ctx.ask("Rezyume yuboring (PDF, 5 MB gacha)", Document(mime="application/pdf", max_size="5MB"))
    await file.save("cvs/")
```

Yuborish ham oson: `ctx.photo("menu.jpg")`, `ctx.document(csv_bytes, filename="users.csv")`, `ctx.send_file("clip.mp4")` (turini o'zi aniqlaydi), `ctx.media_group([...])` (rasm + video aralash), `ctx.edit_media(...)`. Lokal fayl bir marta yuklanadi, keyin `file_id` qayta ishlatiladi. [Media bo'limi →](https://ozodmeofficial.github.io/nicebot/#media)

## 📱 Mini App

Telegram ichida ochiladigan veb-ilova — backend, frontend yordamchisi va HTTPS bilan:

```python
from nicebot import Button, Context, Nicebot, WebAppRequest

bot = Nicebot(token="...", debug=True)
bot.webapp("webapp")                                # webapp/index.html

@bot.command("start")
async def start(ctx: Context):
    await ctx.reply("Do'konni oching 👇", buttons=[Button("🛍 Do'kon", webapp="/")])

@bot.api("/api/order")                              # Telegram imzosi avtomatik tekshiriladi
async def order(req: WebAppRequest):
    await req.send(f"✅ {req.user.first_name}, buyurtmangiz qabul qilindi")
    return {"ok": True}

bot.start(tunnel=True)                              # bepul HTTPS manzil — domen kerak emas
```

Frontend'da `/nicebot.js` ulanadi: `nicebot.post("/api/order", {...})`, `nicebot.mainButton(...)`, `nicebot.upload(...)`, `nicebot.theme()`.

| Vaziyat | Yechim |
|---|---|
| Ishlab chiqish | `bot.start(tunnel=True)` — bepul HTTPS (cloudflared yoki ssh) |
| Brauzerda sinash | `Nicebot(debug=True)` → `http://localhost:8080` |
| Telegram test serveri | `Nicebot(test_server=True)` — HTTP ham ishlaydi |
| Production | o'z domeningiz + `Nicebot(public_url="https://...")` |

[Mini App bo'limi (7 sahifa, to'liq do'kon misoli bilan) →](https://ozodmeofficial.github.io/nicebot/#miniapp)

---

## 📦 Ichida nimalar bor

Hammasi kutubxonaning o'zida — qo'shimcha paket o'rnatmasdan.

| Mavzu | Nima beradi | Qo'llanma |
|---|---|---|
| 💬 **Suhbatlar** | `ask`, `confirm`, `choose(multiple=True)`, `form` — FSM klasslarisiz savol-javob | [Suhbatlar](https://ozodmeofficial.github.io/nicebot/#conversations) |
| ✅ **Validatorlar** | Telefon (+998), email, sana, son, URL, rasm, fayl (hajm va MIME bilan), joylashuv… | [Validatorlar](https://ozodmeofficial.github.io/nicebot/#validators) |
| 🔘 **Tugmalar** | `Button(on_click=func)`, `"buy:{id:int}"` shablonlari, Toggle, `ttl`, `once`, `only`, avto-joylashuv | [Tugmalar](https://ozodmeofficial.github.io/nicebot/#buttons) |
| 🧭 **Menyular** | Ko'p darajali `Menu` ("Orqaga" o'zi qo'shiladi), `ctx.paginate()` | [Menyular](https://ozodmeofficial.github.io/nicebot/#menus) |
| 📎 **Media** | `ctx.media`, `save()`/`download()`, 20 MB nazorati, aralash albomlar, `edit_media` | [Media](https://ozodmeofficial.github.io/nicebot/#media) |
| 📱 **Mini App** | `@bot.api`, `nicebot.js`, `tunnel=True`, brauzerda sinash, CORS, `req.send()` | [Mini App](https://ozodmeofficial.github.io/nicebot/#miniapp) |
| 🗄 **Baza (ORM)** | SQLite, PostgreSQL, MySQL va MongoDB uchun bitta API, avto-migratsiya | [Baza](https://ozodmeofficial.github.io/nicebot/#database) |
| 👥 **Foydalanuvchilar** | Avtomatik saqlash, o'z maydonlaringiz, referal tizimi | [Foydalanuvchilar](https://ozodmeofficial.github.io/nicebot/#users) |
| 🌍 **Ko'p tillilik** | `ctx.t()`, JSON tarjimalar, uz / ru / en tayyor matnlar | [i18n](https://ozodmeofficial.github.io/nicebot/#i18n) |
| 📊 **Admin panel** | `/stats`, `/broadcast`, `/maintenance`, `/backup`, xatolar haqida hisobot | [Admin](https://ozodmeofficial.github.io/nicebot/#admin) |
| 📣 **Broadcast** | Tezlik chegarasi, bloklanganlarni belgilash, to'xtagan joydan davom ettirish | [Broadcast](https://ozodmeofficial.github.io/nicebot/#broadcast) |
| ⭐ **To'lovlar** | Telegram Stars: `ctx.invoice()` va `@bot.paid` | [To'lovlar](https://ozodmeofficial.github.io/nicebot/#payments) |
| 🛡 **Guruhlar** | `ban`, `mute`, `warn`, captcha, majburiy obuna, support rejimi | [Guruhlar](https://ozodmeofficial.github.io/nicebot/#groups) |
| 🧩 **Arxitektura** | DI (type hint orqali), middleware, Router, `from_env()`, scheduler, fon vazifalari, kesh | [Middleware](https://ozodmeofficial.github.io/nicebot/#middleware) |
| 🔁 **Ishonchlilik** | Flood-wait, retry, file_id keshi, to'g'ri to'xtash — restartda update yo'qolmaydi | [Deploy](https://ozodmeofficial.github.io/nicebot/#deploy) |
| 🧪 **Testlar** | `bot.test()` — botni Telegram'siz sinash: xabar, tugma, fayl va Mini App endpointlari | [Testlash](https://ozodmeofficial.github.io/nicebot/#testing) |
| 🤖 **Bot API 10.3** | 185 ta metod va 403 ta tur rasmiy spetsifikatsiyadan generatsiya qilingan, har birida misol | [Bot API](https://ozodmeofficial.github.io/nicebot/#api) |

Barcha 50 ta imkoniyat: **[Imkoniyatlar ro'yxati →](https://ozodmeofficial.github.io/nicebot/#features)** · Har bir metod: **[To'liq ma'lumotnoma →](https://ozodmeofficial.github.io/nicebot/#ref-ctx)**

---

## 🛒 To'laroq misol

Mahsulot tanlash, telefon so'rash, tasdiqlash, bazaga yozish va adminga xabar — barchasi bitta faylda:

```python
from nicebot import Nicebot, Button, Context, Model, fields, Phone

bot = Nicebot(token="...", db="sqlite:///shop.db", admins=[123456789])

class Order(Model):
    user_id = fields.BigInt(index=True)
    product = fields.Str(100)
    phone = fields.Str(20)

async def buy(ctx: Context, product: str):
    phone = await ctx.ask("Telefon raqamingiz?", Phone)
    if await ctx.confirm(f"{product} buyurtma qilinsinmi?"):
        await Order.create(user_id=ctx.user_id, product=product, phone=phone)
        await ctx.reply("✅ Qabul qilindi!")
        await ctx.notify_admins(f"🛒 Yangi buyurtma: {product}, {phone}")

@bot.command("shop", description="Do'kon")
async def shop(ctx: Context):
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

`pytest` va `pytest-asyncio` bilan ishlaydi. Fayl yuborish (`user.send_document(...)`) va Mini App endpointlari (`await t.api(...)`) ham sinaladi.

---

## 📚 Hujjatlar

To'liq qo'llanma o'zbek, rus va ingliz tillarida: **https://ozodmeofficial.github.io/nicebot/**

| Bo'lim | Ichida |
|---|---|
| [Boshlash](https://ozodmeofficial.github.io/nicebot/#start) | Kirish, o'rnatish, birinchi bot, asosiy tushunchalar, VS Code |
| [Asoslar](https://ozodmeofficial.github.io/nicebot/#basics) | Handlerlar, `ctx`, matn formatlash |
| [Tugmalar va suhbat](https://ozodmeofficial.github.io/nicebot/#ui) | Tugmalar, klaviatura, suhbatlar, validatorlar, holat, menyular |
| [Media va fayllar](https://ozodmeofficial.github.io/nicebot/#media) | Qabul qilish, yuklab olish, yuborish, albomlar |
| [Ma'lumotlar](https://ozodmeofficial.github.io/nicebot/#data) | Baza (ORM), foydalanuvchilar, ko'p tillilik |
| [Biznes vositalari](https://ozodmeofficial.github.io/nicebot/#business) | Admin panel, broadcast, to'lovlar, guruhlar |
| [Mini App](https://ozodmeofficial.github.io/nicebot/#miniapp) | Ochish usullari, backend, nicebot.js, HTTPS'siz ishlab chiqish, deploy, misol |
| [Ilg'or](https://ozodmeofficial.github.io/nicebot/#advanced) | Middleware, rejalashtirish, deploy, testlash |
| [Ma'lumotnoma](https://ozodmeofficial.github.io/nicebot/#reference) | `ctx`, `Nicebot`, tugmalar, media, Mini App, testlar — har bir metod misol bilan |

## 🛠 Ishlab chiqish

```bash
pip install -e ".[dev]"
pytest                       # testlar
python docs/src/build.py     # hujjatlar sayti → docs/index.html
```

O'zgarishlar tarixi: [CHANGELOG.md](CHANGELOG.md).

## Litsenziya

MIT © Ozodbek Sobirjonovich
