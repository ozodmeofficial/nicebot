"""Code samples shared by all three languages of the docs."""

CODE = {}

CODE["hello"] = '''from nicebot import Context, Nicebot

bot = Nicebot(token="123456:ABC...")

@bot.command("start")
async def start(ctx: Context):
    await ctx.reply(f"Salom, {ctx.name}!")

bot.start()'''

CODE["aiogram"] = '''import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

router = Router()

class Reg(StatesGroup):
    name = State()
    age = State()

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.set_state(Reg.name)
    await message.answer("Ismingiz?")

@router.message(Reg.name)
async def got_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Reg.age)
    await message.answer("Yoshingiz?")

@router.message(Reg.age)
async def got_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Butun son kiriting.")
        return
    data = await state.get_data()
    await state.clear()
    await message.answer(f"{data['name']}, {message.text} yosh")

async def main():
    bot = Bot("TOKEN")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)

asyncio.run(main())'''

CODE["nicebot_same"] = '''from nicebot import Context, Nicebot

bot = Nicebot(token="TOKEN")

@bot.command("start")
async def start(ctx: Context):
    name = await ctx.ask("Ismingiz?")
    age = await ctx.ask("Yoshingiz?", int)
    await ctx.reply(f"{name}, {age} yosh")

bot.start()'''

CODE["install"] = '''pip install nicebot                 # SQLite bilan
pip install "nicebot[postgres]"     # + PostgreSQL
pip install "nicebot[mysql]"        # + MySQL / MariaDB
pip install "nicebot[mongo]"        # + MongoDB
pip install "nicebot[redis]"        # + Redis
pip install "nicebot[all]"          # hammasi'''

CODE["new"] = '''nicebot new mybot
cd mybot
python bot.py'''

CODE["tree"] = '''mybot/
├── bot.py            # asosiy fayl
├── .env              # BOT_TOKEN, DATABASE_URL, ADMINS
├── handlers/
│   └── basic.py      # Router bilan handlerlar
└── locales/
    ├── uz.json
    ├── ru.json
    └── en.json'''

CODE["env"] = '''BOT_TOKEN=123456:ABC-your-token
DATABASE_URL=sqlite:///bot.db
ADMINS=123456789,987654321
TZ=Asia/Tashkent'''

CODE["from_env"] = '''from nicebot import Nicebot

bot = Nicebot.from_env()      # .env faylini o'qiydi
price = bot.config.int("PRICE", 1000)'''

CODE["options"] = '''bot = Nicebot(
    token="...",
    db="postgres://user:pass@localhost/mybot",
    admins=[123456789],
    lang="uz",                       # standart til
    required_channels=["@mykanal"],  # majburiy obuna
    support_chat=-1001234567890,     # yordam guruhi
    captcha="2m",                    # guruhga yangi kirganlarga
    tz="Asia/Tashkent",
)'''

CODE["handlers"] = '''@bot.command("help", description="Yordam")
async def help_(ctx: Context):
    await ctx.reply("Men nima qila olaman...")

@bot.text("salom")                       # aniq matn (katta-kichik harf farqsiz)
async def salom(ctx: Context):
    await ctx.reply("Va alaykum assalom!")

@bot.text(contains="narx")               # ichida "narx" bo'lsa
async def narx(ctx: Context):
    await ctx.reply("Narxlar: ...")

@bot.text(regex=r"^buy (?P<qty>\\d+)$")  # regex guruhlari parametr bo'ladi
async def buy(ctx: Context, qty: int):
    await ctx.reply(f"{qty} dona")

@bot.on("photo")                          # rasm kelsa
async def photo(ctx: Context):
    await ctx.reply("Chiroyli rasm!")

@bot.text()                               # istalgan oddiy matn
async def echo(ctx: Context):
    await ctx.reply(ctx.text)

@bot.fallback()                           # hech narsa mos kelmasa
async def unknown(ctx: Context):
    await ctx.reply("Tushunmadim 🤔")'''

CODE["handler_opts"] = '''@bot.command("admin", admin=True)              # faqat adminlar
@bot.command("bonus", throttle="1d")           # kuniga 1 marta
@bot.command("report", typing=True)            # "yozmoqda..." ko'rsatadi
@bot.text("salom", chat="private")             # faqat shaxsiy chatda
@bot.text(state="waiting_phone")               # faqat shu holatda
@bot.command("vip", users=[111, 222])          # faqat shu odamlar
@bot.message(F.photo & F.private)              # filtrlar
@bot.deep_link(r"promo_(?P<code>\\w+)")         # t.me/bot?start=promo_X
async def handler(ctx: Context): ...'''

CODE["filters"] = '''from nicebot import Context, F

@bot.message(F.photo | F.document)
@bot.message(F.text & ~F.command)
@bot.message(F.regex(r"\\d{4}"))
@bot.message(F.contains("chegirma", "aksiya"))
@bot.message(F.user(123, 456))
@bot.message(lambda ctx: len(ctx.text or "") > 100)   # o'z filtringiz
async def h(ctx: Context): ...'''

CODE["router"] = '''# handlers/shop.py
from nicebot import Context, Router

router = Router(chat="private")   # barcha handlerlarga qo'llanadi

@router.command("shop")
async def shop(ctx: Context):
    await ctx.reply("Do'kon")

# bot.py
bot.include("handlers")           # papkadagi barcha Router'lar
# yoki: from handlers.shop import router; bot.include(router)'''

CODE["ctx_props"] = '''@bot.message()
async def info(ctx: Context):
    ctx.text        # xabar matni (yoki rasm izohi)
    ctx.name        # foydalanuvchi ismi
    ctx.user        # bazadagi foydalanuvchi (avtomatik saqlanadi)
    ctx.user_id     # Telegram id
    ctx.chat_id     # chat id
    ctx.command     # "/start ref_5" -> "start"
    ctx.args        # "/give 10 ali" -> ["10", "ali"]
    ctx.payload     # deep link: "ref_5"
    ctx.lang        # "uz", "ru", "en"
    ctx.is_private  # shaxsiy chatmi
    ctx.is_admin    # bot adminimi
    ctx.message     # to'liq Message obyekti
    ctx.mention     # bosiladigan ism (HTML)'''

CODE["ctx_send"] = '''await ctx.reply("Salom!")                          # matn
await ctx.reply("Tanlang", buttons=["A", "B"])    # inline tugmalar bilan
await ctx.reply("Yozing", keyboard=["Menyu"])     # pastki klaviatura
await ctx.reply("30 soniyada o'chadi", delete_after="30s")
await ctx.reply("Ovozsiz", silent=True, protect=True)

await ctx.photo("rasm.jpg", caption="Mana")       # fayl, URL yoki file_id
await ctx.video("https://site.uz/v.mp4")
await ctx.document("hisobot.pdf")
await ctx.media_group(["1.jpg", "2.jpg", "3.jpg"], caption="Albom")
await ctx.location(40.10, 65.37)
await ctx.poll("Qaysi biri?", ["Python", "Go"])
await ctx.dice("🎯")'''

CODE["ctx_edit"] = '''await ctx.edit("Yangi matn")               # tugma bosilgan xabarni tahrirlash
await ctx.edit_buttons([Button("OK", data="ok")])
await ctx.respond("Javob")                 # tugmadan bo'lsa tahrirlaydi, aks holda yuboradi
await ctx.answer("Saqlandi ✅")             # tugma ustida kichik xabar
await ctx.answer("Diqqat!", alert=True)    # oyna ko'rinishida
await ctx.delete()                          # xabarni o'chirish
await ctx.react("🔥")                       # reaksiya
await ctx.pin()'''

CODE["html"] = '''from nicebot import bold, html, link, mention

name = ctx.text                                 # foydalanuvchi yozgan matn
await ctx.reply(html("<b>Salom, {}!</b>", name))  # name xavfsiz escape qilinadi
await ctx.reply(bold("Muhim") + " xabar")
await ctx.reply(link("Saytimiz", "https://tezbaraka.uz"))'''

CODE["buttons"] = '''from nicebot import Button, Context

async def buy(ctx: Context):
    await ctx.edit("✅ Sotib olindi")

@bot.command("shop")
async def shop(ctx: Context):
    await ctx.reply("Mahsulot: Kitob — 50 000 so'm", buttons=[
        [Button("🛒 Sotib olish", on_click=buy)],
        [Button("🌐 Sayt", url="https://tezbaraka.uz"),
         Button("📋 Promo", copy="NICE2026")],
        [Button("📱 Ilova", webapp="https://app.tezbaraka.uz")],
    ])'''

CODE["buttons_params"] = '''async def add_to_cart(ctx: Context, id: int, qty: int):
    await ctx.answer(f"{id} dan {qty} ta qo'shildi")

Button("➕ Savatga", on_click=add_to_cart, id=15, qty=2)'''

CODE["buttons_template"] = '''@bot.callback("product:{id:int}")
async def product(ctx: Context, id: int):
    p = await Product.get(id=id)
    await ctx.edit(f"{p.title} — {p.price} so'm")

# tugma shu shablonni o'zi to'ldiradi:
Button("Ko'rish", on_click=product, id=5)      # callback_data = "product:5"'''

CODE["buttons_layout"] = '''# ro'yxat berilsa — qisqa tugmalar bir qatorga o'zi joylashadi
await ctx.reply("O'lcham?", buttons=["S", "M", "L", "XL"])

# ustunlar sonini o'zingiz bering
await ctx.reply("Tanlang", buttons=items, columns=2)

# dict: matn -> amal (funksiya, URL yoki data)
await ctx.reply("Menyu", buttons={"Profil": profile, "Sayt": "https://tezbaraka.uz"})'''

CODE["buttons_safe"] = '''Button("🎁 Bonus olish", on_click=bonus, once=True)          # faqat bir marta
Button("⏳ Taklif", on_click=offer, ttl="10m")              # 10 daqiqadan keyin eskiradi
Button("👤 Faqat siz", on_click=mine, only=ctx.user_id)     # boshqalar bosolmaydi'''

CODE["reply_kb"] = '''await ctx.reply("Raqamingizni yuboring", keyboard=["📞 Raqam yuborish:contact"])
await ctx.reply("Qayerdasiz?", keyboard=["📍 Joylashuv:location"])
await ctx.reply("Menyu", keyboard=["🛍 Do'kon", "📞 Aloqa", "ℹ️ Haqida"], columns=2)
await ctx.reply("Yopildi", remove_keyboard=True)'''

CODE["toggle"] = '''from nicebot import Context, Toggle

@bot.command("sozlamalar")
async def settings_menu(ctx: Context):
    await ctx.reply("⚙️ Sozlamalar", buttons=[
        [Toggle("Bildirishnomalar", key="notify", default=True)],
        [Toggle("Kechki rejim", key="night")],
    ])

# istalgan joyda qiymatni o'qing:
if await ctx.setting("notify"):
    ...'''

CODE["ask"] = '''from nicebot import Context, Date, Email, Phone

@bot.command("register")
async def register(ctx: Context):
    name  = await ctx.ask("Ismingiz?")
    age   = await ctx.ask("Yoshingiz?", int)        # son bo'lmasa qayta so'raydi
    phone = await ctx.ask("Raqamingiz?", Phone)     # "Raqam yuborish" tugmasi bilan
    size  = await ctx.ask("O'lcham?", buttons=["S", "M", "L"])
    await ctx.reply(f"Rahmat, {name}!")'''

CODE["confirm"] = '''if await ctx.confirm("Buyurtmani tasdiqlaysizmi?"):
    await ctx.reply("✅ Qabul qilindi")
else:
    await ctx.reply("Bekor qilindi")'''

CODE["choose"] = '''city = await ctx.choose("Shahringiz?", ["Toshkent", "Navoiy", "Buxoro"])

tags = await ctx.choose(
    "Qiziqishlaringiz?",
    {"⚽️ Sport": "sport", "🎵 Musiqa": "music", "💻 IT": "it"},
    multiple=True,       # ✅/⬜️ belgilab, "Tayyor" bosiladi
)                        # -> ["sport", "it"]'''

CODE["form"] = '''from nicebot import Date, Email, Integer, Phone

data = await ctx.form(
    name="Ismingiz?",
    age=Integer("Yoshingiz?", min=14, max=99),
    phone=Phone("Telefon raqamingiz?"),
    email=Email("Email manzilingiz?"),
    birthday=Date("Tug'ilgan kuningiz? (KK.OO.YYYY)"),
)
await ctx.reply(f"{data.name}, {data.phone}")'''

CODE["validators"] = '''from nicebot import Choice, Date, Email, File, Integer, Location, Number, Phone, Photo, Regex, Text, Url

await ctx.ask("Izoh?", Text(min=10, max=500))
await ctx.ask("Summa?", Number(min=1000))
await ctx.ask("Rasm yuboring", Photo)              # -> PhotoSize (file_id bor)
await ctx.ask("Pasport seriyasi?", Regex(r"[A-Z]{2}\\d{7}"))
await ctx.ask("Kod?", lambda t: t.upper())         # o'z funksiyangiz'''

CODE["state"] = '''@bot.command("feedback")
async def feedback(ctx: Context):
    await ctx.set_state("feedback", step=1)
    await ctx.reply("Fikringizni yozing:")

@bot.text(state="feedback")
async def got_feedback(ctx: Context, text):
    data = await ctx.state_data()      # {"step": 1}
    await ctx.clear_state()
    await ctx.reply("Rahmat!")'''

CODE["menu"] = '''from nicebot import Context, Menu

main = Menu("🏠 Bosh menyu", {
    "🛍 Do'kon": Menu("Bo'limni tanlang", {
        "👕 Kiyim": "Kiyimlar tez orada qo'shiladi",
        "📚 Kitoblar": show_books,        # funksiya chaqiriladi
    }),
    "📞 Aloqa": "+998 90 123 45 67",
    "🌐 Sayt": "https://tezbaraka.uz",
})

@bot.command("menu")
async def menu(ctx: Context):
    await ctx.menu(main)    # "⬅️ Orqaga" o'zi qo'shiladi'''

CODE["paginate"] = '''products = await Product.all().order_by("title")
await ctx.paginate(
    products,
    per_page=10,
    title="📦 Mahsulotlar",
    render=lambda p, i: f"{i + 1}. {p.title} — {p.price} so'm",
)
# tugmalarni ham sahifalash mumkin:
await ctx.paginate([Button(p.title, on_click=open_product, id=p.id) for p in products], columns=2)'''

CODE["orm_model"] = '''from nicebot import Model, fields

class Product(Model):
    title = fields.Str(120)
    price = fields.Int(default=0)
    active = fields.Bool(default=True)
    tags = fields.JSON(default=list)
    created = fields.DateTime(auto_now_add=True)

class Order(Model):
    user = fields.ForeignKey("User")
    product = fields.ForeignKey(Product)
    qty = fields.Int(default=1)'''

CODE["orm_crud"] = '''p = await Product.create(title="Kitob", price=50_000)

p = await Product.get(id=1)              # topilmasa DoesNotExist
p = await Product.get_or_none(title="X") # topilmasa None
user, created = await User.get_or_create(id=5, defaults={"first_name": "Ali"})

p.price = 45_000
await p.save()
await p.update(price=40_000)            # faqat shu maydon
await p.increment("price", 1000)
await p.delete()'''

CODE["orm_query"] = '''cheap = await Product.filter(price__lt=100_000, active=True).order_by("price")
count = await Product.filter(title__icontains="kitob").count()
last5 = await Product.all().order_by("-created").limit(5)
page2 = await Product.all().page(2, 10)
titles = await Product.all().values_list("title")
total = await Order.filter(user=ctx.user).sum("qty")

from nicebot import Col, Q
await Product.filter(Q(price__gt=1_000_000) | Q(active=False))
await User.filter(id=5).update(balance=Col("balance") + 1000)'''

CODE["orm_urls"] = '''Nicebot(db="sqlite:///bot.db")
Nicebot(db="postgres://user:pass@localhost:5432/mybot")
Nicebot(db="mysql://user:pass@localhost:3306/mybot")
Nicebot(db="mongodb://localhost:27017/mybot")'''

CODE["orm_tx"] = '''async with bot.db.transaction():
    await Order.create(user=ctx.user, product=p)
    await p.update(stock=Col("stock") - 1)
# xato bo'lsa — ikkalasi ham bekor bo'ladi'''

CODE["user_model"] = '''from nicebot import Context, Nicebot, User, fields

class Customer(User):              # o'sha "nb_users" jadvali, yangi ustunlar
    balance = fields.Int(default=0)
    city = fields.Str(64, null=True)

bot = Nicebot(token="...", user_model=Customer)

@bot.command("balans")
async def balans(ctx: Context, user: Customer):
    await ctx.reply(f"Balans: {user.balance} so'm")'''

CODE["referral"] = '''@bot.command("taklif")
async def invite(ctx: Context):
    n = await ctx.user.referrals_count()
    await ctx.reply(f"Havolangiz: {ctx.ref_link}\\nTaklif qilganlaringiz: {n}")

@bot.on_referral
async def rewarded(ctx: Context, referrer):
    await referrer.update(balance=Col("balance") + 5000)
    await bot.send_message(referrer.id, "🎉 Do'stingiz qo'shildi, +5000!")'''

CODE["stats"] = '''s = await bot.stats()
# {"users": 1520, "dau": 310, "mau": 1104, "new_today": 42, "blocked": 37,
#  "retention_d7": 34.5, "top_commands": [("start", 900), ...], ...}'''

CODE["broadcast"] = '''result = await bot.broadcast(
    "🎉 Yangi aksiya boshlandi!",
    buttons=[Button("Ko'rish", url="https://tezbaraka.uz")],
    id="aksiya-noyabr",     # to'xtab qolsa, shu id bilan davom etadi
)
# {"total": 1500, "sent": 1462, "failed": 38, "blocked": 35}

await bot.broadcast(lambda uid: f"Salom! Sizning id: {uid}")
await bot.broadcast(None, copy_from=(chat_id, message_id))   # istalgan xabarni nusxalash'''

CODE["middleware"] = '''import time

@bot.middleware
async def timing(ctx: Context, next):
    start = time.perf_counter()
    await next()                                  # keyingi qadam / handler
    print(f"{ctx.text!r}: {time.perf_counter() - start:.3f}s")

@bot.middleware
async def ban_check(ctx: Context, next):
    if ctx.user and ctx.user.data.get("banned"):
        return                                    # next() chaqirilmasa — to'xtaydi
    await next()'''

CODE["di"] = '''from dataclasses import dataclass

@dataclass
class Settings:
    price: int = 50_000

bot.provide(Settings, Settings())

@bot.callback("buy:{id:int}")
async def buy(ctx: Context, id: int, user: Customer, cfg: Settings, text, args):
    ...   # kerakli narsani nomi yoki turi bilan so'raysiz'''

CODE["i18n_files"] = '''// locales/uz.json
{ "hello": "Assalomu alaykum, {name}!", "menu": { "shop": "🛍 Do'kon" } }

// locales/ru.json
{ "hello": "Здравствуйте, {name}!", "menu": { "shop": "🛍 Магазин" } }'''

CODE["i18n_use"] = '''await ctx.reply(ctx.t("hello", name=ctx.name))
await ctx.reply(ctx.t("menu.shop"))
await ctx.set_lang("ru")        # foydalanuvchi tilini saqlaydi'''

CODE["group"] = '''@bot.command("warn")
async def warn(ctx: Context):
    if await ctx.is_chat_admin():
        await ctx.warn("Reklama taqiqlangan", limit=3)   # 3 tadan keyin ban

@bot.command("mute")
async def mute(ctx: Context):
    if await ctx.is_chat_admin():
        await ctx.mute("1h")       # reply qilingan odamni 1 soatga

await ctx.ban(for_="7d")
await ctx.unban()
await ctx.kick()'''

CODE["captcha"] = '''bot = Nicebot(token="...", captcha="2m")
# guruhga kirgan odam 2 daqiqada "🤖 Men robot emasman" ni bosmasa — chiqariladi'''

CODE["subscribe"] = '''bot = Nicebot(token="...", required_channels=["@kanalim", "@yangiliklar"])
# obuna bo'lmagan foydalanuvchi kanallar ro'yxati va "✅ Tekshirish" tugmasini ko'radi'''

CODE["support"] = '''bot = Nicebot(token="...", support_chat=-1001234567890)
# hech bir handlerga tushmagan shaxsiy xabarlar guruhga boradi;
# guruhda o'sha xabarga reply qilsangiz — javob foydalanuvchiga ketadi'''

CODE["stars"] = '''@bot.command("premium")
async def premium(ctx: Context):
    await ctx.invoice("Premium", "30 kunlik obuna", amount=100, payload="premium30")

@bot.paid()
async def paid(ctx: Context):
    sp = ctx.message.successful_payment
    await ctx.user.update(data={**ctx.user.data, "premium": True})
    await ctx.reply(f"⭐️ {sp.total_amount} Stars uchun rahmat!")'''

CODE["schedule"] = '''@bot.every("1h")
async def sync_prices(bot):
    ...

@bot.at("09:00", tz="Asia/Tashkent")
async def morning(bot):
    await bot.broadcast("☀️ Xayrli tong!")

@bot.at("18:00", days=["mon", "fri"])
async def weekly_report(bot):
    await bot.notify_admins(str(await bot.stats()))'''

CODE["background"] = '''@bot.command("report")
async def report(ctx: Context):
    ctx.background(build_heavy_report, ctx.user_id, retries=3)   # handler darhol tugaydi
    await ctx.reply("Hisobot tayyorlanmoqda, tayyor bo'lgach yuboraman")

bot.later("10m", bot.send_message(admin_id, "10 daqiqa o'tdi"))'''

CODE["cache"] = '''from nicebot import cache

@cache("10m")
async def dollar_rate():
    ...   # 10 daqiqada bir marta haqiqiy so'rov'''

CODE["files"] = '''@bot.on("document")
async def doc(ctx: Context):
    data = await ctx.download()               # bytes
    await ctx.save(f"uploads/{ctx.message.document.file_name}")

await ctx.photo("logo.png")   # birinchi marta yuklanadi,
await ctx.photo("logo.png")   # keyingi safar file_id bilan — bir zumda'''

CODE["run"] = '''bot.start()                                   # polling
bot.start(reload=True)                        # kod o'zgarsa o'zi qayta ishga tushadi
bot.start(webhook="https://bot.tezbaraka.uz/hook", port=8080)
Nicebot.run_all(shop_bot, support_bot)        # bitta jarayonda bir nechta bot'''

CODE["docker"] = '''FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir "nicebot[postgres]"
CMD ["python", "bot.py"]'''

CODE["errors"] = '''@bot.error(ValueError)
async def bad_value(ctx: Context, error):
    await ctx.reply(f"Xato qiymat: {error}")

# qolgan xatolar: foydalanuvchiga muloyim xabar,
# adminlarga esa traceback bilan hisobot avtomatik yuboriladi'''

CODE["testing"] = '''from bot import bot

async def test_register():
    async with bot.test() as t:
        ali = t.user(first_name="Ali")
        await ali.send("/register")
        assert t.last.text == "Ismingiz?"
        await ali.send("Ali")
        await ali.send("25")
        await ali.click("M")
        assert "Rahmat" in t.last.text'''

CODE["admin"] = '''bot = Nicebot(token="...", admins=[123456789])
# adminlar menyusida avtomatik paydo bo'ladi:
# /stats        — statistika
# /broadcast    — xabarga reply qilib hammaga yuborish
# /maintenance  — texnik ishlar rejimi (on / off)
# /backup       — SQLite bazaning nusxasi'''

CODE["raw_api"] = '''# Bot API'ning barcha 185 metodi — snake_case nomlar bilan
await bot.send_message(chat_id, "Salom")
await bot.set_chat_title(chat_id, "Yangi nom")
member = await bot.get_chat_member(chat_id, user_id)
print(member.status)      # "member", "administrator", ...'''

CODE["lifecycle"] = '''@bot.on_startup
async def ready(bot):
    await bot.notify_admins("✅ Bot ishga tushdi")

@bot.on_new_user
async def welcome(ctx: Context, user):
    await bot.notify_admins(f"🆕 Yangi foydalanuvchi: {user.mention}")'''


# ============================================================== VS Code
CODE["vscode_hint"] = '''from nicebot import Context, Nicebot

bot = Nicebot(token="...")

@bot.command("start")
async def start(ctx: Context):      # ← ": Context" muharrirga ctx turini aytadi
    ctx.                            # ← endi bu yerda hamma metodlar ro'yxati chiqadi'''

CODE["vscode_settings"] = '''{
  "python.languageServer": "Pylance",
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.inlayHints.functionReturnTypes": true,
  "editor.quickSuggestions": { "strings": true }
}'''

CODE["vscode_types"] = '''from nicebot import Context, Media, Nicebot, User, WebAppRequest

@bot.on("photo")
async def photo(ctx: Context):
    media: Media = ctx.media        # media. → kind, size, save(), download()…
    user: User = ctx.user           # user. → first_name, phone, lang, update()…

@bot.api("/api/me")
async def me(req: WebAppRequest):   # req. → user, json, form(), send()…
    return {"name": req.user.first_name}'''

# ============================================================== media
CODE["media_receive"] = '''@bot.on("photo", "video", "document", "voice")
async def got_file(ctx: Context):
    m = ctx.media                       # Media obyekti
    await ctx.reply(
        f"Turi: {m.kind}\\n"           # photo, video, document, voice…
        f"Hajmi: {m.size_text}\\n"     # "2.4 MB"
        f"Nomi: {m.name or '-'}\\n"    # hujjatlarda asl nom
        f"MIME: {m.mime}"               # "image/jpeg", "application/pdf"…
    )'''

CODE["media_fields"] = '''m = ctx.media
m.kind            # "photo" | "video" | "animation" | "document" | "audio" | "voice" | "video_note" | "sticker"
m.file_id         # shu faylni qayta yuborish uchun
m.file_unique_id  # barqaror id — bazada kalit sifatida qulay
m.size            # baytlarda (None bo'lishi mumkin)
m.name            # asl fayl nomi (document, audio, video)
m.mime            # MIME turi
m.width, m.height # rasm/video o'lchami
m.duration        # video, audio, ovozli xabar davomiyligi (soniya)
m.caption         # xabar izohi
m.extension       # ".pdf", ".jpg"…
m.is_image        # rasm yoki image/* hujjat
m.can_download    # 20 MB dan kichikmi
m.raw             # Telegram obyektining o'zi (PhotoSize, Document…)'''

CODE["media_ask"] = '''from nicebot import Document, File, Photo, Video, Voice

photo = await ctx.ask("Mahsulot rasmini yuboring", Photo)          # PhotoSize
cv    = await ctx.ask("Rezyume (PDF, 5 MB gacha)", Document(mime="application/pdf", max_size="5MB"))
clip  = await ctx.ask("Video yuboring", Video(max_size="50MB"))
voice = await ctx.ask("Ovozli xabar yozing", Voice)
pic   = await ctx.ask("Rasm yuboring", File(mime="image/*"))       # rasm yoki rasmli hujjat
path  = await cv.save("cvs/")                                      # Media obyekti — darhol saqlash mumkin'''

CODE["media_download"] = '''@bot.on("document")
async def doc(ctx: Context):
    data = await ctx.download()                 # xotiraga: bytes
    path = await ctx.save()                     # downloads/<asl nom>
    path = await ctx.save(f"users/{ctx.user_id}/")   # papka ichiga, nom saqlanadi
    path = await ctx.save("avatar.jpg")         # aynan shu yo'lga
    await ctx.reply(f"Saqlandi: {path} ({len(data)} bayt)")'''

CODE["media_too_big"] = '''from nicebot import FileTooBig

@bot.on("video")
async def video(ctx: Context):
    if not ctx.media.can_download:              # 20 MB dan katta
        return await ctx.reply("Fayl juda katta, 20 MB gacha yuboring")
    try:
        await ctx.media.save("videos/")
    except FileTooBig:
        await ctx.reply("Fayl juda katta")'''

CODE["media_local_api"] = '''# 2 GB gacha fayllar uchun o'z Bot API serveringiz:
# docker run -p 8081:8081 -e TELEGRAM_API_ID=... -e TELEGRAM_API_HASH=... aiogram/telegram-bot-api
bot = Nicebot(token="...", api_url="http://localhost:8081")'''

CODE["media_send"] = '''await ctx.photo("images/menu.jpg", "Bugungi menyu")             # lokal fayl
await ctx.photo("https://picsum.photos/600")                     # URL — Telegram o'zi yuklaydi
await ctx.photo(ctx.media.file_id)                               # qabul qilingan faylni qayta yuborish
await ctx.video("promo.mp4", "Yangi video", supports_streaming=True)
await ctx.document("reports/june.pdf", "Iyun hisoboti")
await ctx.audio("song.mp3", performer="Ijrochi", title="Qo'shiq")
await ctx.voice("hello.ogg")
await ctx.animation("party.gif")
await ctx.video_note("circle.mp4")
await ctx.sticker("CAACAgIAAxkBAAE...")
await ctx.send_file("cat.jpg")                                   # turini o'zi aniqlaydi'''

CODE["media_bytes"] = '''import io

csv_text = "id,ism\\n1,Ali\\n2,Vali"
await ctx.document(csv_text.encode(), filename="users.csv")      # bytes

buf = io.BytesIO()
chart.savefig(buf, format="png")                                 # matplotlib, Pillow, qrcode…
await ctx.photo(buf.getvalue(), "Grafik", filename="chart.png")'''

CODE["media_options"] = '''await ctx.photo("secret.jpg", "Bosib ko'ring", spoiler=True)     # xira, bosilganda ochiladi
await ctx.photo("a.jpg", "Izoh tepada", caption_above=True)
await ctx.video("big.mp4", thumbnail="thumb.jpg", width=1280, height=720, duration=95)
await ctx.document("price.xlsx", buttons=[Button("🛒 Buyurtma", on_click=order)])
await ctx.photo("ad.jpg", chat_id="@kanalim")                    # boshqa chatga'''

CODE["media_album_send"] = '''await ctx.media_group(["a.jpg", "b.jpg", "c.mp4"], "Sayohatimiz")      # rasm + video aralash
await ctx.media_group(["q1.pdf", "q2.pdf"], kind="document")            # hujjatlar albomi'''

CODE["media_album_receive"] = '''@bot.album()
async def album(ctx: Context):
    for m in ctx.album_media:              # albomdagi har bir fayl — Media
        await m.save(f"albums/{ctx.user_id}/")
    await ctx.reply(f"{len(ctx.album_media)} ta fayl saqlandi")
    await ctx.media_group(ctx.album_media)  # albomni o'zini qaytarib yuborish'''

CODE["media_edit"] = '''PHOTOS = ["1.jpg", "2.jpg", "3.jpg"]

async def show(ctx: Context, i: int):
    nav = [Button("◀️", on_click=show, i=(i - 1) % len(PHOTOS)), Button("▶️", on_click=show, i=(i + 1) % len(PHOTOS))]
    await ctx.edit_media(PHOTOS[i], f"Rasm {i + 1}/{len(PHOTOS)}", buttons=nav)

@bot.command("gallery")
async def gallery(ctx: Context):
    await ctx.photo(PHOTOS[0], "Rasm 1/3", buttons=[Button("▶️", on_click=show, i=1)])'''

CODE["media_cache"] = '''@bot.command("menu")
async def menu(ctx: Context):
    await ctx.photo("images/menu.jpg")     # 1-marta: fayl yuklanadi
                                           # keyingi safar: file_id qayta ishlatiladi (bir zumda)'''

CODE["media_forward"] = '''@bot.on("photo", "video")
async def to_channel(ctx: Context):
    await ctx.copy("@kanalim")                       # "Forwarded" belgisisiz nusxa
    await ctx.forward(ADMIN_GROUP)                   # "Forwarded from …" bilan'''

# ============================================================== mini app
CODE["miniapp_tree"] = '''mybot/
├── bot.py
└── webapp/
    ├── index.html      # Mini App sahifasi
    ├── app.js
    └── style.css'''

CODE["miniapp_quick_py"] = '''from nicebot import Button, Context, Nicebot, WebAppRequest

bot = Nicebot(token="...", debug=True)
bot.webapp("webapp")                         # webapp/index.html  →  https://<manzil>/

@bot.command("start")
async def start(ctx: Context):
    await ctx.reply("Do'konni oching 👇", buttons=[Button("🛍 Do'kon", webapp="/")])

@bot.api("/api/hello", methods=["GET"])
async def hello(req: WebAppRequest):
    return {"text": f"Salom, {req.user.first_name}!"}

bot.start(tunnel=True)                       # bepul HTTPS manzil — domen kerak emas'''

CODE["miniapp_quick_html"] = '''<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <script src="/nicebot.js"></script>
</head>
<body>
  <h1 id="hello">...</h1>
  <script>
    nicebot.get("/api/hello").then(r => {
      document.getElementById("hello").textContent = r.text;
    });
  </script>
</body>
</html>'''

CODE["miniapp_log"] = '''🔐 Tunnel (cloudflared): https://red-cat-42.trycloudflare.com → http://localhost:8080
🌐 Web server: http://localhost:8080
📱 Mini App: https://red-cat-42.trycloudflare.com  (browser: http://localhost:8080)
✅ @my_shop_bot is running (polling). Stop with Ctrl+C'''

CODE["miniapp_open"] = '''# 1) Inline tugma — eng ko'p ishlatiladi
await ctx.reply("Do'kon", buttons=[Button("🛍 Ochish", webapp="/shop")])

# 2) Pastki klaviatura tugmasi — sendData() bilan botga ma'lumot qaytaradi
await ctx.reply("Buyurtma", keyboard=[ReplyButton("📝 Buyurtma berish", webapp="/order")])

# 3) Menyu tugmasi (xabar maydoni yonida) — hamma uchun
bot.menu_app("🛍 Do'kon", "/")

# 4) To'g'ridan-to'g'ri havola: t.me/bot/app?startapp=promo
bot.app_link("shop", startapp="promo")      # BotFather → /newapp da "shop" nomi bilan'''

CODE["miniapp_senddata"] = '''@bot.webapp_data()
async def order(ctx: Context):
    data = ctx.web_app_data                  # JSON bo'lsa — dict
    await ctx.reply(f"Buyurtma qabul qilindi: {data['total']} so'm")

# webapp/order.html ichida:
# nicebot.sendData({ items: [1, 2], total: 90000 })   → Mini App yopiladi, bot xabar oladi'''

CODE["miniapp_api"] = '''from nicebot import WebAppRequest

@bot.api("/api/products", methods=["GET"], auth=False)      # ochiq: initData shart emas
async def products(req: WebAppRequest):
    return [p.to_dict() for p in await Product.filter(active=True)]

@bot.api("/api/order")                                       # POST, initData tekshiriladi
async def order(req: WebAppRequest):
    items = req.json["items"]                                # JSON tana
    order = await Order.create(user_id=req.user_id, items=items)
    await req.send(f"✅ Buyurtma #{order.id} qabul qilindi")  # foydalanuvchiga chatda xabar
    return {"ok": True, "id": order.id}

@bot.api("/api/order/{id}", methods=["GET"])
async def order_status(req: WebAppRequest):
    order = await Order.get(id=int(req.params["id"]), user_id=req.user_id)
    return {"status": order.status}'''

CODE["miniapp_req"] = '''req.user                 # WebAppUser: .id .first_name .username .language_code .is_premium …
req.user_id              # Telegram id
req.json                 # JSON tana (dict/list) yoki None
req.query                # ?a=1 → {"a": "1"}
req.params               # /api/item/{id} → {"id": "5"}
req.start_param          # t.me/bot/app?startapp=promo → "promo"
req.query_id             # inline tugmadan ochilganda (req.answer uchun)
req.init                 # tekshirilgan initData'ning hamma maydonlari
await req.db_user()      # bazadagi User (ctx.user kabi)
await req.form()         # multipart forma: matnlar va UploadedFile'lar
await req.send("...")    # foydalanuvchiga botdan xabar
await req.send_photo(png_bytes, "Chiptangiz")
await req.answer("Buyurtma", "🛒 Men buyurtma berdim")   # Mini App ochilgan chatga javob'''

CODE["miniapp_errors"] = '''@bot.api("/api/buy")
async def buy(req: WebAppRequest):
    product = await Product.get_or_none(id=req.json.get("id"))
    if product is None:
        raise ValueError("Mahsulot topilmadi")      # → 400 {"ok": false, "error": "..."}
    if not (await req.db_user()).phone:
        raise PermissionError("Avval telefon raqam") # → 403
    return {"ok": True}                              # → 200'''

CODE["miniapp_upload_py"] = '''@bot.api("/api/avatar")
async def avatar(req: WebAppRequest):
    form = await req.form()
    photo = form["photo"]                            # UploadedFile
    if photo.size > 5_000_000:
        raise ValueError("5 MB gacha")
    path = await photo.save(f"avatars/{req.user_id}.jpg")
    await req.send_photo(photo.data, "Yangi avataringiz")
    return {"ok": True, "size": photo.size}'''

CODE["miniapp_js_basic"] = '''<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script src="/nicebot.js"></script>
<script>
  nicebot.theme();                                    // Telegram ranglarini CSS o'zgaruvchilariga
  document.querySelector("#name").textContent = nicebot.user?.first_name ?? "mehmon";

  const products = await nicebot.get("/api/products");
  const r = await nicebot.post("/api/order", { items: [1, 2] });
  nicebot.haptic("success");
</script>'''

CODE["miniapp_js_ui"] = '''// Asosiy tugma (pastdagi katta tugma)
nicebot.mainButton("Buyurtma berish", async () => {
  nicebot.progress(true);
  try {
    await nicebot.post("/api/order", { items: cart });
    await nicebot.alert("✅ Qabul qilindi");
    nicebot.close();
  } catch (e) {
    await nicebot.alert(e.message);                   // backend xatosi matni
  } finally {
    nicebot.progress(false);
  }
});

// Orqaga tugmasi
nicebot.backButton(() => showPage("home"));           // nicebot.backButton(null) — yashirish

if (await nicebot.confirm("Savatni tozalaymi?")) cart = [];'''

CODE["miniapp_js_more"] = '''await nicebot.upload("/api/avatar", { photo: fileInput.files[0] }, { comment: "yangi" });
await nicebot.storage.set("cart", JSON.stringify(cart));     // Telegram CloudStorage
const saved = await nicebot.storage.get("cart");
nicebot.share("Zo'r do'kon!", "https://t.me/my_shop_bot/shop");
nicebot.openLink("https://example.com");
nicebot.sendData({ total: 90000 });                          // faqat pastki klaviatura tugmasidan ochilganda
nicebot.startParam;                                          // "promo"
nicebot.isTelegram;                                          // Telegram ichidami yoki brauzerda
nicebot.platform;                                            // "ios", "android", "tdesktop", "browser"…'''

CODE["miniapp_js_theme"] = '''body {
  background: var(--tg-bg-color, #fff);
  color: var(--tg-text-color, #000);
}
button {
  background: var(--tg-button-color, #2481cc);
  color: var(--tg-button-text-color, #fff);
}'''

CODE["miniapp_dev_tunnel"] = '''bot.start(tunnel=True)                    # avtomatik: cloudflared yoki ssh
bot.start(tunnel="cloudflared")           # aniq tanlash
bot.start(tunnel="localhost.run")         # faqat ssh kerak (Windows 10+, macOS, Linux'da bor)
bot.start(tunnel=["ngrok", "http", "{port}", "--log", "stdout"])   # o'zingizning buyrug'ingiz'''

CODE["miniapp_dev_browser"] = '''bot = Nicebot(
    token="...",
    debug=True,                                            # brauzerda sinash rejimi
    dev_user={"id": 123456789, "first_name": "Ali"},       # soxta foydalanuvchi
)
bot.webapp("webapp")
bot.start()        # → http://localhost:8080 ni oddiy brauzerda oching'''

CODE["miniapp_dev_test_server"] = '''# Telegram test serveri: HTTP havolalar ham ishlaydi
bot = Nicebot(token="TEST_SERVER_TOKEN", test_server=True)
await ctx.reply("Ochish", buttons=[Button("📱", webapp="http://192.168.1.5:8080/")])'''

CODE["miniapp_deploy"] = '''bot = Nicebot(
    token="...",
    public_url="https://shop.example.uz",     # yoki PUBLIC_URL muhit o'zgaruvchisi
)
bot.webapp("webapp")
bot.menu_app("🛍 Do'kon")
bot.start(port=8080)                          # Nginx/Caddy HTTPS'ni shu portga yo'naltiradi'''

CODE["miniapp_caddy"] = '''shop.example.uz {
    reverse_proxy localhost:8080
}'''

CODE["miniapp_cors"] = '''# Frontend GitHub Pages/Vercel'da, backend — bot serverida
bot = Nicebot(token="...", public_url="https://api.example.uz", cors=["https://me.github.io"])

# frontend index.html ichida nicebot.js'ni bot serveridan ulang —
# shunda so'rovlar avtomatik o'sha serverga ketadi:
# <script src="https://api.example.uz/nicebot.js"></script>'''

CODE["miniapp_webhook"] = '''bot.start(tunnel=True, webhook=True)       # webhook ham tunnel orqali, domensiz'''

CODE["miniapp_security"] = '''from nicebot import validate_init_data

# @bot.api buni o'zi qiladi; o'z serveringizda (FastAPI, Django) kerak bo'lsa:
data = validate_init_data(init_data_string, BOT_TOKEN, max_age=3600)
user_id = data["user"]["id"]'''

CODE["miniapp_test"] = '''async def test_order():
    async with bot.test() as t:
        ali = t.user(first_name="Ali")
        r = await t.api("/api/order", {"items": [1, 2]}, user=ali)   # initData avtomatik imzolanadi
        assert r.status == 200 and r.json["ok"]
        assert "qabul qilindi" in t.last_in(ali.chat_id).text'''

CODE["miniapp_shop_py"] = '''from nicebot import Button, Context, Model, Nicebot, WebAppRequest, fields

bot = Nicebot(token="...", db="sqlite:///shop.db", admins=[123456789], debug=True)
bot.webapp("webapp")
bot.menu_app("🛍 Do'kon")

PRODUCTS = {1: ("📚 Kitob", 50_000), 2: ("🎧 Quloqchin", 250_000), 3: ("☕️ Krujka", 30_000)}

class Order(Model):
    user_id = fields.BigInt(index=True)
    items = fields.JSON(default=list)
    total = fields.Int()
    created_at = fields.DateTime(auto_now_add=True)

@bot.command("start")
async def start(ctx: Context):
    await ctx.reply("Xush kelibsiz! Do'konni oching 👇", buttons=[Button("🛍 Do'kon", webapp="/")])

@bot.api("/api/products", methods=["GET"], auth=False)
async def products(req: WebAppRequest):
    return [{"id": i, "title": t, "price": p} for i, (t, p) in PRODUCTS.items()]

@bot.api("/api/order")
async def order(req: WebAppRequest):
    ids = [int(i) for i in req.json.get("items", []) if int(i) in PRODUCTS]
    if not ids:
        raise ValueError("Savat bo'sh")
    total = sum(PRODUCTS[i][1] for i in ids)
    o = await Order.create(user_id=req.user_id, items=ids, total=total)
    names = ", ".join(PRODUCTS[i][0] for i in ids)
    await req.send(f"✅ Buyurtma #{o.id}: {names}\\nJami: {total:,} so'm")
    await bot.notify_admins(f"🛒 #{o.id} — {req.user.first_name}: {total:,} so'm")
    return {"ok": True, "id": o.id}

bot.start(tunnel=True)'''

CODE["miniapp_shop_html"] = '''<!doctype html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <script src="/nicebot.js"></script>
  <style>
    body { font-family: system-ui; margin: 0; padding: 16px; background: var(--tg-bg-color, #fff); color: var(--tg-text-color, #000); }
    .item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #8883; }
    button { border: 0; border-radius: 8px; padding: 8px 14px; background: var(--tg-button-color, #2481cc); color: var(--tg-button-text-color, #fff); }
  </style>
</head>
<body>
  <h2>Salom, <span id="name">mehmon</span>!</h2>
  <div id="list"></div>
  <script>
    nicebot.theme();
    document.getElementById("name").textContent = nicebot.user?.first_name ?? "mehmon";
    const cart = [];

    nicebot.get("/api/products").then(products => {
      document.getElementById("list").innerHTML = products.map(p =>
        `<div class="item"><span>${p.title} — ${p.price.toLocaleString()} so'm</span>
         <button onclick="add(${p.id})">+</button></div>`).join("");
    });

    function add(id) {
      cart.push(id);
      nicebot.haptic("light");
      nicebot.mainButton(`Buyurtma berish (${cart.length})`, checkout);
    }

    async function checkout() {
      nicebot.progress(true);
      try {
        const r = await nicebot.post("/api/order", { items: cart });
        await nicebot.alert(`✅ Buyurtma #${r.id} qabul qilindi`);
        nicebot.close();
      } catch (e) {
        await nicebot.alert(e.message);
      } finally {
        nicebot.progress(false);
      }
    }
  </script>
</body>
</html>'''
