"""Code samples shared by all three languages of the docs."""

CODE = {}

CODE["hello"] = '''from nicebot import Nicebot

bot = Nicebot(token="123456:ABC...")

@bot.command("start")
async def start(ctx):
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

CODE["nicebot_same"] = '''from nicebot import Nicebot

bot = Nicebot(token="TOKEN")

@bot.command("start")
async def start(ctx):
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
async def help_(ctx):
    await ctx.reply("Men nima qila olaman...")

@bot.text("salom")                       # aniq matn (katta-kichik harf farqsiz)
async def salom(ctx):
    await ctx.reply("Va alaykum assalom!")

@bot.text(contains="narx")               # ichida "narx" bo'lsa
async def narx(ctx):
    await ctx.reply("Narxlar: ...")

@bot.text(regex=r"^buy (?P<qty>\\d+)$")  # regex guruhlari parametr bo'ladi
async def buy(ctx, qty: int):
    await ctx.reply(f"{qty} dona")

@bot.on("photo")                          # rasm kelsa
async def photo(ctx):
    await ctx.reply("Chiroyli rasm!")

@bot.text()                               # istalgan oddiy matn
async def echo(ctx):
    await ctx.reply(ctx.text)

@bot.fallback()                           # hech narsa mos kelmasa
async def unknown(ctx):
    await ctx.reply("Tushunmadim 🤔")'''

CODE["handler_opts"] = '''@bot.command("admin", admin=True)              # faqat adminlar
@bot.command("bonus", throttle="1d")           # kuniga 1 marta
@bot.command("report", typing=True)            # "yozmoqda..." ko'rsatadi
@bot.text("salom", chat="private")             # faqat shaxsiy chatda
@bot.text(state="waiting_phone")               # faqat shu holatda
@bot.command("vip", users=[111, 222])          # faqat shu odamlar
@bot.message(F.photo & F.private)              # filtrlar
@bot.deep_link(r"promo_(?P<code>\\w+)")         # t.me/bot?start=promo_X
async def handler(ctx): ...'''

CODE["filters"] = '''from nicebot import F

@bot.message(F.photo | F.document)
@bot.message(F.text & ~F.command)
@bot.message(F.regex(r"\\d{4}"))
@bot.message(F.contains("chegirma", "aksiya"))
@bot.message(F.user(123, 456))
@bot.message(lambda ctx: len(ctx.text or "") > 100)   # o'z filtringiz
async def h(ctx): ...'''

CODE["router"] = '''# handlers/shop.py
from nicebot import Router

router = Router(chat="private")   # barcha handlerlarga qo'llanadi

@router.command("shop")
async def shop(ctx):
    await ctx.reply("Do'kon")

# bot.py
bot.include("handlers")           # papkadagi barcha Router'lar
# yoki: from handlers.shop import router; bot.include(router)'''

CODE["ctx_props"] = '''@bot.message()
async def info(ctx):
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

CODE["html"] = '''from nicebot import html, bold, link, mention

name = ctx.text                                 # foydalanuvchi yozgan matn
await ctx.reply(html("<b>Salom, {}!</b>", name))  # name xavfsiz escape qilinadi
await ctx.reply(bold("Muhim") + " xabar")
await ctx.reply(link("Saytimiz", "https://tezbaraka.uz"))'''

CODE["buttons"] = '''from nicebot import Button

async def buy(ctx):
    await ctx.edit("✅ Sotib olindi")

@bot.command("shop")
async def shop(ctx):
    await ctx.reply("Mahsulot: Kitob — 50 000 so'm", buttons=[
        [Button("🛒 Sotib olish", on_click=buy)],
        [Button("🌐 Sayt", url="https://tezbaraka.uz"),
         Button("📋 Promo", copy="NICE2026")],
        [Button("📱 Ilova", webapp="https://app.tezbaraka.uz")],
    ])'''

CODE["buttons_params"] = '''async def add_to_cart(ctx, id: int, qty: int):
    await ctx.answer(f"{id} dan {qty} ta qo'shildi")

Button("➕ Savatga", on_click=add_to_cart, id=15, qty=2)'''

CODE["buttons_template"] = '''@bot.callback("product:{id:int}")
async def product(ctx, id: int):
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

CODE["toggle"] = '''from nicebot import Toggle

@bot.command("sozlamalar")
async def settings_menu(ctx):
    await ctx.reply("⚙️ Sozlamalar", buttons=[
        [Toggle("Bildirishnomalar", key="notify", default=True)],
        [Toggle("Kechki rejim", key="night")],
    ])

# istalgan joyda qiymatni o'qing:
if await ctx.setting("notify"):
    ...'''

CODE["ask"] = '''from nicebot import Phone, Email, Date

@bot.command("register")
async def register(ctx):
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

CODE["form"] = '''from nicebot import Phone, Email, Date, Integer

data = await ctx.form(
    name="Ismingiz?",
    age=Integer("Yoshingiz?", min=14, max=99),
    phone=Phone("Telefon raqamingiz?"),
    email=Email("Email manzilingiz?"),
    birthday=Date("Tug'ilgan kuningiz? (KK.OO.YYYY)"),
)
await ctx.reply(f"{data.name}, {data.phone}")'''

CODE["validators"] = '''from nicebot import Text, Integer, Number, Phone, Email, Url, Date, Choice, Regex, Photo, File, Location

await ctx.ask("Izoh?", Text(min=10, max=500))
await ctx.ask("Summa?", Number(min=1000))
await ctx.ask("Rasm yuboring", Photo)              # -> PhotoSize (file_id bor)
await ctx.ask("Pasport seriyasi?", Regex(r"[A-Z]{2}\\d{7}"))
await ctx.ask("Kod?", lambda t: t.upper())         # o'z funksiyangiz'''

CODE["state"] = '''@bot.command("feedback")
async def feedback(ctx):
    await ctx.set_state("feedback", step=1)
    await ctx.reply("Fikringizni yozing:")

@bot.text(state="feedback")
async def got_feedback(ctx, text):
    data = await ctx.state_data()      # {"step": 1}
    await ctx.clear_state()
    await ctx.reply("Rahmat!")'''

CODE["menu"] = '''from nicebot import Menu

main = Menu("🏠 Bosh menyu", {
    "🛍 Do'kon": Menu("Bo'limni tanlang", {
        "👕 Kiyim": "Kiyimlar tez orada qo'shiladi",
        "📚 Kitoblar": show_books,        # funksiya chaqiriladi
    }),
    "📞 Aloqa": "+998 90 123 45 67",
    "🌐 Sayt": "https://tezbaraka.uz",
})

@bot.command("menu")
async def menu(ctx):
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

from nicebot import Q, Col
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

CODE["user_model"] = '''from nicebot import Nicebot, User, fields

class Customer(User):              # o'sha "nb_users" jadvali, yangi ustunlar
    balance = fields.Int(default=0)
    city = fields.Str(64, null=True)

bot = Nicebot(token="...", user_model=Customer)

@bot.command("balans")
async def balans(ctx, user: Customer):
    await ctx.reply(f"Balans: {user.balance} so'm")'''

CODE["referral"] = '''@bot.command("taklif")
async def invite(ctx):
    n = await ctx.user.referrals_count()
    await ctx.reply(f"Havolangiz: {ctx.ref_link}\\nTaklif qilganlaringiz: {n}")

@bot.on_referral
async def rewarded(ctx, referrer):
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
async def timing(ctx, next):
    start = time.perf_counter()
    await next()                                  # keyingi qadam / handler
    print(f"{ctx.text!r}: {time.perf_counter() - start:.3f}s")

@bot.middleware
async def ban_check(ctx, next):
    if ctx.user and ctx.user.data.get("banned"):
        return                                    # next() chaqirilmasa — to'xtaydi
    await next()'''

CODE["di"] = '''from dataclasses import dataclass

@dataclass
class Settings:
    price: int = 50_000

bot.provide(Settings, Settings())

@bot.callback("buy:{id:int}")
async def buy(ctx, id: int, user: Customer, cfg: Settings, text, args):
    ...   # kerakli narsani nomi yoki turi bilan so'raysiz'''

CODE["i18n_files"] = '''// locales/uz.json
{ "hello": "Assalomu alaykum, {name}!", "menu": { "shop": "🛍 Do'kon" } }

// locales/ru.json
{ "hello": "Здравствуйте, {name}!", "menu": { "shop": "🛍 Магазин" } }'''

CODE["i18n_use"] = '''await ctx.reply(ctx.t("hello", name=ctx.name))
await ctx.reply(ctx.t("menu.shop"))
await ctx.set_lang("ru")        # foydalanuvchi tilini saqlaydi'''

CODE["group"] = '''@bot.command("warn")
async def warn(ctx):
    if await ctx.is_chat_admin():
        await ctx.warn("Reklama taqiqlangan", limit=3)   # 3 tadan keyin ban

@bot.command("mute")
async def mute(ctx):
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
async def premium(ctx):
    await ctx.invoice("Premium", "30 kunlik obuna", amount=100, payload="premium30")

@bot.paid()
async def paid(ctx):
    sp = ctx.message.successful_payment
    await ctx.user.update(data={**ctx.user.data, "premium": True})
    await ctx.reply(f"⭐️ {sp.total_amount} Stars uchun rahmat!")'''

CODE["miniapp_py"] = '''bot.webapp("webapp")                # webapp/index.html ni beradi

@bot.api("/api/score")
async def score(req):
    user = await req.db_user()          # initData tekshirilgan, foydalanuvchi aniq
    points = int(req.json["points"])
    await user.update(data={**user.data, "score": points})
    return {"ok": True, "score": points}

@bot.command("play")
async def play(ctx):
    await ctx.reply("O'ynash", buttons=[Button("🎮 Boshlash", webapp="https://game.tezbaraka.uz")])

bot.start(port=8080)'''

CODE["miniapp_js"] = '''<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script src="/nicebot.js"></script>
<script>
  nicebot.post("/api/score", { points: 120 }).then(r => console.log(r.score));
  console.log(nicebot.user.first_name);
</script>'''

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
async def report(ctx):
    ctx.background(build_heavy_report, ctx.user_id, retries=3)   # handler darhol tugaydi
    await ctx.reply("Hisobot tayyorlanmoqda, tayyor bo'lgach yuboraman")

bot.later("10m", bot.send_message(admin_id, "10 daqiqa o'tdi"))'''

CODE["cache"] = '''from nicebot import cache

@cache("10m")
async def dollar_rate():
    ...   # 10 daqiqada bir marta haqiqiy so'rov'''

CODE["files"] = '''@bot.on("document")
async def doc(ctx):
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
async def bad_value(ctx, error):
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
async def welcome(ctx, user):
    await bot.notify_admins(f"🆕 Yangi foydalanuvchi: {user.mention}")'''
