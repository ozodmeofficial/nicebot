"""O'zbekcha hujjat matni."""

UI = {
    "search": "Qidirish…",
    "on_this_page": "Shu sahifada",
    "copy": "Nusxa",
    "copied": "Olindi",
    "prev": "Oldingi",
    "next": "Keyingi",
    "menu": "Bo'limlar",
    "no_results": "Hech narsa topilmadi",
    "theme": "Mavzu",
    "edit_hint": "Bot API",
    "tagline": "Telegram botlar uchun Python kutubxonasi",
}

GROUPS = {
    "start": "Boshlash",
    "basics": "Asoslar",
    "ui": "Tugmalar va suhbat",
    "media": "Media va fayllar",
    "miniapp": "Mini App",
    "data": "Ma'lumotlar",
    "business": "Biznes vositalari",
    "advanced": "Ilg'or",
    "reference": "Ma'lumotnoma",
}

PAGES = {}

PAGES["intro"] = ("Kirish", """
nicebot — Telegram bot yozishni iloji boricha sodda qiladigan Python kutubxonasi. Bitta import, bitta obyekt va oddiy funksiyalar. Baza, tugmalar, suhbatlar, tarjimalar, statistika va admin panel ichida tayyor turadi.

{demo:hello}

Bu to'liq ishlaydigan bot. Unda `Dispatcher`, `Router` yoki holatlar klassi yo'q. Foydalanuvchi esa avtomatik bazaga saqlanadi.

## Nega nicebot?

Oddiy ro'yxatdan o'tish botini ikki usulda solishtiramiz. Avval aiogram:

{code:aiogram}

Endi xuddi shu bot nicebot'da:

{demo:nicebot_same}

`ctx.ask()` savol beradi va javobni kutadi. `int` bersangiz, son kiritilmaguncha muloyim qayta so'raydi. `StatesGroup` yozish, holatni saqlash va tozalash kerak emas.

## Ichida nimalar bor

- **Bot API 10.3 to'liq:** 403 ta tur va 185 ta metod rasmiy spetsifikatsiyadan generatsiya qilingan
- **Ichki ORM:** SQLite, PostgreSQL, MySQL va MongoDB uchun bitta API, avto-migratsiya bilan
- **Suhbatlar:** `ask`, `confirm`, `choose`, `form` va tayyor validatorlar
- **Tugmalar:** `on_click`, shablonlar, toggle, muddatli va bir martalik tugmalar, avto-joylashuv
- **Biznes:** referal, broadcast, statistika, admin panel, majburiy obuna, support, Telegram Stars
- **Media:** `ctx.media` — kelgan fayl bitta obyektda, `save()`, `download()`, aralash albomlar
- **Mini App:** `@bot.api`, `nicebot.js`, `tunnel=True` bilan domensiz HTTPS
- **Ishonchlilik:** flood-wait'ni o'zi kutadi, tarmoq xatosida qayta uradi, restartda update yo'qolmaydi
- **Tezlik:** msgspec turlari va bitta ulanish pooli

To'liq ro'yxat [50 ta imkoniyat](#features) sahifasida.

> nicebot `async` asosida ishlaydi. Har bir handler `async def` bo'ladi, Telegram'ga har bir murojaat esa `await` bilan yoziladi.
""")

PAGES["install"] = ("O'rnatish", """
Python 3.10 yoki undan yangi versiya kerak.

{code:install:bash}

Kvadrat qavs ichidagi qism kerakli baza drayverini qo'shib o'rnatadi. SQLite qo'shimchasiz ishlaydi.

## Tayyor loyiha yaratish

{code:new:bash}

Buyruq quyidagi tuzilmani yaratadi:

{code:tree:text}

`.env` faylini ochib, `BOT_TOKEN` o'rniga @BotFather bergan tokenni yozing.

{code:env:bash}

## Versiyani tekshirish

`nicebot version` buyrug'i kutubxona, Bot API va Python versiyalarini ko'rsatadi.
""")

PAGES["first-bot"] = ("Birinchi bot", """
## 1. Token oling

Telegram'da @BotFather'ni oching, `/newbot` yozing, botga nom va username bering. U `123456:ABC-DEF...` ko'rinishidagi token beradi. Tokenni hech kimga ko'rsatmang.

## 2. Kod yozing

`bot.py` faylini yarating:

{demo:hello}

## 3. Ishga tushiring

```bash
python bot.py
```

Terminalda `✅ @sizning_bot ishga tushdi` yozuvi chiqadi. Telegram'da botingizga `/start` yozing, u ismingiz bilan salomlashadi.

## Nima bo'ldi?

| Qator | Ma'nosi |
|---|---|
| `Nicebot(token=...)` | Botni yaratadi. Baza berilmasa, xotiradagi SQLite ishlatiladi |
| `@bot.command("start")` | `/start` buyrug'i kelganda pastdagi funksiyani chaqiradi |
| `async def start(ctx: Context)` | `ctx` joriy xabar haqidagi hamma narsani biladi. `: Context` muharrirga avtomatik to'ldirishni yoqadi |
| `await ctx.reply(...)` | Shu chatga javob yuboradi |
| `bot.start()` | Telegram'dan xabarlarni olishni boshlaydi. To'xtatish uchun Ctrl+C |

> Ma'lumotlar restartdan keyin ham saqlansin desangiz, `Nicebot(token=..., db="sqlite:///bot.db")` deb yozing.

## Kod o'zgarganda avtomatik qayta yuklash

`bot.start(reload=True)` bilan har safar faylni saqlaganingizda bot o'zi qayta ishga tushadi. Ishlab chiqish paytida bu juda qulay.
""")

PAGES["concepts"] = ("Asosiy tushunchalar", """
nicebot'da faqat uchta tushuncha bor.

## Bot

`Nicebot` — butun ilovangiz. Token, baza, adminlar va til kabi sozlamalar shu yerda beriladi.

{code:options}

## Handler

Handler — biror hodisa bo'lganda chaqiriladigan `async` funksiya. Dekorator qachon chaqirilishini aytadi: `@bot.command("start")`, `@bot.text("salom")`, `@bot.callback("buy:{id:int}")` va hokazo. Handlerlar yozilgan tartibda tekshiriladi va birinchi mos kelgani ishlaydi.

## ctx (kontekst)

Har bir xabar uchun yangi `ctx` yaratiladi va handlerga birinchi argument bo'lib keladi. U ikki xil ish qiladi:

- **ma'lumot beradi:** `ctx.text`, `ctx.user`, `ctx.chat_id`, `ctx.args`…
- **amal bajaradi:** `ctx.reply()`, `ctx.edit()`, `ctx.ask()`, `ctx.photo()`…

## Hayot sikli

Xabar kelgach quyidagilar sodir bo'ladi:

1. Agar foydalanuvchi `ctx.ask()` javobini kutayotgan bo'lsa, xabar o'sha yerga uzatiladi
2. Ichki middleware'lar ishlaydi: foydalanuvchi bazaga saqlanadi, texnik ishlar rejimi va majburiy obuna tekshiriladi
3. Sizning middleware'laringiz ishlaydi
4. Birinchi mos handler chaqiriladi
5. Hech biri mos kelmasa, `@bot.fallback()` yoki support rejimi ishlaydi
6. Tugma bosilgan bo'lsa va siz javob bermagan bo'lsangiz, `answerCallbackQuery` avtomatik yuboriladi
""")

PAGES["handlers"] = ("Handlerlar", """
## Turlari

{code:handlers}

## Handler parametrlari

Har qanday dekoratorga quyidagi parametrlarni qo'shish mumkin:

{code:handler_opts}

| Parametr | Nima qiladi |
|---|---|
| `admin=True` | Faqat `Nicebot(admins=[...])` dagilar uchun |
| `chat="private"` | `private`, `group`, `supergroup`, `channel` |
| `throttle="3s"` | Bir foydalanuvchi uchun tezlik chegarasi. Oshib ketsa, "⏳ Biroz kuting" chiqadi |
| `typing=True` | Handler ishlayotgan paytda "yozmoqda…" ko'rinadi. `"upload_photo"` ham bo'ladi |
| `state="x"` | Faqat foydalanuvchi shu holatda bo'lsa ishlaydi |
| `users=[...]` | Faqat shu id'lar uchun |
| `description="..."` | Buyruq Telegram menyusida paydo bo'ladi. `{"uz": ..., "ru": ...}` ham bo'ladi |

## Filtrlar

`F` tayyor filtrlarni beradi. Ularni `&` (va), `|` (yoki) va `~` (emas) bilan birlashtirish mumkin.

{code:filters}

## Router: kodni fayllarga bo'lish

{code:router}

## Barcha hodisa turlari

`@bot.callback`, `@bot.inline`, `@bot.chosen_inline`, `@bot.edited`, `@bot.channel`, `@bot.join`, `@bot.leave`, `@bot.album`, `@bot.paid`, `@bot.pre_checkout`, `@bot.webapp_data`, `@bot.my_chat_member`, `@bot.chat_member`, `@bot.join_request`, `@bot.reaction`, `@bot.poll_answer`. Qolgan har qanday update uchun: `@bot.event("chat_boost")`.

> Handlerda `raise SkipHandler` desangiz, keyingi mos handler ishlaydi.
""")

PAGES["ctx"] = ("ctx — kontekst", """
`ctx` — har bir handler birinchi argument sifatida oladigan obyekt. Bu sahifa eng ko'p ishlatiladigan qismlarini ko'rsatadi; to'liq ro'yxat — [ctx: to'liq ma'lumotnoma](#ref-ctx).

> [!TIP]
> `async def handler(ctx: Context)` deb yozing — VS Code `ctx.` dan keyin barcha metodlarni ko'rsatadi. [Batafsil](#vscode).

## Ma'lumotlar

{code:ctx_props}

## Yuborish

{code:ctx_send}

Yuborish metodlarining hammasi bir xil qo'shimcha parametrlarni qabul qiladi:

| Parametr | Ma'nosi |
|---|---|
| `buttons=` | Inline tugmalar ([Tugmalar](#buttons)) |
| `keyboard=` | Pastki klaviatura. `False` bo'lsa yopadi |
| `columns=` | Tugmalar ustunlari soni |
| `delete_after="1m"` | Xabarni avtomatik o'chirish |
| `silent=True` | Ovozsiz bildirishnoma |
| `protect=True` | Forward va saqlashni taqiqlash |
| `quote=True` | Kelgan xabarga reply qilib yuborish |
| `preview=False` | Havola preview'sini o'chirish |
| `chat_id=` | Boshqa chatga yuborish |

## Tahrirlash va javob

{code:ctx_edit}

`ctx.edit()` xabarda rasm bo'lsa izohni, bo'lmasa matnni o'zi tanlab tahrirlaydi. "message is not modified" xatosini esa jimgina o'tkazib yuboradi.

## Yana foydali metodlar

| Metod | Nima qiladi |
|---|---|
| `ctx.forward(chat)` / `ctx.copy(chat)` | Xabarni boshqa chatga yuborish |
| `ctx.download()` / `ctx.save(path)` | Faylni yuklab olish |
| `ctx.action("upload_photo")` | Status ko'rsatish |
| `ctx.is_member("@kanal")` | Obunani tekshirish |
| `ctx.notify_admins(text)` | Adminlarga xabar |
| `ctx.background(func)` | Fon vazifasi |
| `ctx.t("key")` | Tarjima |
""")

PAGES["formatting"] = ("Matn formatlash", """
nicebot standart holatda HTML parse mode'dan foydalanadi, shuning uchun `<b>`, `<i>`, `<code>` va `<a href>` teglari darhol ishlaydi.

## Foydalanuvchi matni bilan xavfsiz ishlash

Foydalanuvchi yozgan matnda `<` yoki `&` belgilari bo'lishi mumkin. To'g'ridan-to'g'ri qo'shilsa, Telegram xato beradi. `html()` qiymatlarni xavfsiz qiladi, shablon esa o'zgarmaydi:

{code:html}

Tayyor yordamchilar: `bold`, `italic`, `underline`, `strike`, `spoiler`, `code`, `pre`, `link`, `mention`, `quote`, `escape`.

> Agar formatlashda xato bo'lsa ham bot yiqilmaydi. nicebot xabarni formatlashsiz qayta yuboradi va logga ogohlantirish yozadi.

## Boshqa rejimlar

`Nicebot(parse_mode="MarkdownV2")` yoki formatlashsiz ishlash uchun `parse_mode=None`.
""")

PAGES["buttons"] = ("Inline tugmalar", """
## Tugma va uning amali

`Button` matn va bitta amalni oladi. Eng qulayi `on_click`: tugma bosilganda oddiy funksiya chaqiriladi. Callback data o'ylab topish va uni alohida handlerda tutib olish shart emas.

{demo:buttons}

| Turi | Yozilishi |
|---|---|
| Funksiya | `Button("OK", on_click=func)` |
| Havola | `Button("Sayt", url="https://...")` |
| Mini App | `Button("Ilova", webapp="https://...")` |
| Nusxa olish | `Button("Kod", copy="PROMO")` |
| Ulashish | `Button("Ulashish", share="matn")` |
| Oddiy data | `Button("Ha", data="yes")` |
| To'lov | `Button("To'lash", pay=True)` |

## Parametr uzatish

{code:buttons_params}

## Callback shablonlari

{code:buttons_template}

Turlar: `int`, `float`, `bool`, `str` (standart) va `any`. Qiymatlar handlerga to'g'ri turda keladi.

## Avtomatik joylashuv

{code:buttons_layout}

## Xavfsiz tugmalar

{code:buttons_safe}

> Telegram callback_data'ni 64 bayt bilan cheklaydi. nicebot uzun ma'lumotni bazada saqlab, tugmaga qisqa kalit qo'yadi, buni siz sezmaysiz ham. Bosilgan tugmalarga javob ham avtomatik yuboriladi, shuning uchun "soat" belgisi qotib qolmaydi.
""")

PAGES["keyboards"] = ("Klaviatura va toggle", """
## Pastki (reply) klaviatura

{code:reply_kb}

Matn oxiridagi `:contact` raqam so'raydigan, `:location` esa joylashuv so'raydigan tugma yasaydi. Murakkabroq holatlar uchun `ReplyButton("...", webapp=...)` bor.

## Toggle: yoqish va o'chirish

Sozlamalar menyusi uchun. Tugma bosilganda ✅ va ⬜️ o'zi almashadi, qiymat esa har bir foydalanuvchi uchun saqlanadi.

{demo:toggle}

O'zgarishni darhol ushlash uchun `Toggle(..., on_change=func)` yozing, `func(ctx, value)` chaqiriladi.
""")

PAGES["conversations"] = ("Suhbatlar", """
nicebot'ning eng katta qulayligi shu. Savol berasiz va javobni o'sha funksiya ichida kutasiz.

## ask

{demo:ask}

- Foydalanuvchi `/cancel` yozsa yoki "🚫 Bekor qilish" tugmasini bossa, suhbat jimgina tugaydi
- 10 daqiqa javob bo'lmasa, "⌛️ Javob kutish vaqti tugadi" chiqadi. Buni `timeout="5m"` bilan o'zgartirish mumkin
- Noto'g'ri qiymat kiritilsa, tushunarli xato ko'rsatiladi va savol qayta so'raladi. Urinishlar soni `retries=` bilan beriladi

## confirm

{demo:confirm}

## choose

{code:choose}

## form: bir nechta savol ketma-ket

{code:form}

`form` natijasi `dict` bo'ladi, lekin maydonlarga nuqta orqali ham murojaat qilish mumkin: `data.name`.

> Bir vaqtda minglab foydalanuvchi bilan suhbat qilish mumkin. Har biri o'z handlerida kutadi va bir-biriga xalaqit bermaydi.
""")

PAGES["validators"] = ("Validatorlar", """
Validator foydalanuvchi javobini tekshiradi va toza qiymatga aylantiradi.

{code:validators}

| Validator | Qaytaradi | Qo'shimcha |
|---|---|---|
| `Text(min=, max=)` | `str` | Uzunlik chegarasi |
| `Integer(min=, max=)` / `int` | `int` | `1 000 000` kabi bo'shliqlarni tushunadi |
| `Number` / `float` | `float` | Vergulni ham qabul qiladi: `12,5` |
| `Phone` | `"+998901234567"` | Kontakt tugmasi. O'zbek operator kodlarini tekshiradi |
| `Email` | `str` | Kichik harfga o'tkazadi |
| `Url` | `str` | `https://` bilan boshlanishi kerak |
| `Date(format=)` | `date` | Standart format: `KK.OO.YYYY` |
| `Choice(choices=)` | `str` | Variantlarni tugma qilib ko'rsatadi |
| `Regex(pattern)` | `str` | |
| `Photo` / `File` | media obyekti | `.file_id` bor |
| `Location` | `Location` | Joylashuv tugmasi |

Telefon raqami har qanday ko'rinishda kiritilishi mumkin: `90 123 45 67`, `+998 (90) 123-45-67` yoki `8 90 1234567`. Natija har doim `+998901234567` bo'ladi.
""")

PAGES["state"] = ("Holat (state)", """
Ko'p hollarda `ctx.ask()` yetarli. Ammo foydalanuvchi bot bilan uzoq vaqt, masalan bir necha kun davomida bir qadamda tursa, holatdan foydalaning. Holat bazada saqlanadi va restartdan keyin ham yo'qolmaydi.

{code:state}

| Metod | Ma'nosi |
|---|---|
| `await ctx.set_state("nom", **data)` | Holatni o'rnatish |
| `await ctx.get_state()` | Joriy holat yoki `None` |
| `await ctx.state_data()` | Saqlangan ma'lumotlar |
| `await ctx.update_data(**data)` | Ma'lumot qo'shish |
| `await ctx.clear_state()` | Tozalash |
""")

PAGES["menus"] = ("Menyu va sahifalash", """
## Ko'p darajali menyu

Menyuni lug'at ko'rinishida yozasiz. Navigatsiya va "⬅️ Orqaga" tugmasi avtomatik ishlaydi, xabar esa yangisi yuborilmasdan joyida tahrirlanadi.

{demo:menu}

Qiymat turlari: matn (ko'rsatiladi), `Menu` yoki `dict` (ichki menyu), funksiya (chaqiriladi), URL (havola tugmasi) yoki `Button`.

## Sahifalash

Uzun ro'yxatni ◀️ 2/5 ▶️ tugmalari bilan sahifalarga bo'ladi.

{code:paginate}
""")

PAGES["database"] = ("Baza (ORM)", """
nicebot'da o'z ORM'i bor. Bitta kod SQLite, PostgreSQL, MySQL/MariaDB va MongoDB'da bir xil ishlaydi. To'rttalasi ham avtomatik testlar bilan tekshirilgan.

{code:orm_urls}

## Model

{code:orm_model}

Maydonlar: `Int`, `BigInt`, `Float`, `Str(max_length)`, `Text`, `Bool`, `DateTime(auto_now_add=, auto_now=)`, `Date`, `JSON` va `ForeignKey`. Umumiy parametrlar: `default=`, `null=`, `unique=`, `index=` va `choices=`.

> **Avto-migratsiya:** bot ishga tushganda jadvallar yaratiladi. Modelga yangi maydon qo'shsangiz, ustun ham o'zi qo'shiladi. Ma'lumotlaringiz hech qachon o'chirilmaydi.

## Yaratish, o'qish, yangilash, o'chirish

{code:orm_crud}

## So'rovlar

{code:orm_query}

| Lookup | Ma'nosi |
|---|---|
| `price=5` | teng |
| `price__ne=5` | teng emas |
| `__gt` `__gte` `__lt` `__lte` | katta yoki kichik |
| `__in=[...]` / `__not_in` | ro'yxat ichida yoki tashqarisida |
| `__contains` / `__icontains` | ichida bor (`i` — harf katta-kichikligiga qaramaydi) |
| `__startswith` / `__endswith` | bilan boshlanadi yoki tugaydi |
| `__isnull=True` | bo'sh |
| `__between=(a, b)` | oraliqda |

## ForeignKey

`await order.product` bog'langan obyektni yuklaydi va keshlaydi. `order.product_id` esa raqamning o'zi.

## Tranzaksiya

{code:orm_tx}

MongoDB'da tranzaksiya faqat replica set'da ishlaydi, shuning uchun u yerda `transaction()` hech narsa qilmaydi.
""")

PAGES["users"] = ("Foydalanuvchilar va referal", """
Botga yozgan har bir odam `nb_users` jadvaliga avtomatik saqlanadi va `ctx.user` orqali keladi. Ism, username va oxirgi faollik vaqti ham o'zi yangilanib turadi.

| Maydon | |
|---|---|
| `id` | Telegram id |
| `first_name`, `last_name`, `username` | |
| `lang` | Tanlangan til |
| `phone` | Telefon |
| `is_blocked` | Botni bloklaganmi (avtomatik) |
| `is_premium` | Telegram Premium |
| `referrer_id` | Kim taklif qilgan |
| `data` | Istalgan JSON |
| `created_at`, `last_seen` | |

## O'z maydonlaringizni qo'shish

{code:user_model}

## Referal tizimi

`ctx.ref_link` havolasi orqali kirgan yangi foydalanuvchiga `referrer_id` o'zi yoziladi.

{code:referral}

## Hayot sikli hodisalari

{code:lifecycle}
""")

PAGES["i18n"] = ("Ko'p tillilik", """
`locales/` papkasiga har bir til uchun JSON fayl qo'ying:

{code:i18n_files:json}

{code:i18n_use}

Foydalanuvchi tili quyidagi tartibda aniqlanadi: avval `ctx.set_lang()` bilan saqlangan til, keyin Telegram ilovasidagi til, oxirida `Nicebot(lang="uz")`. Kalit topilmasa, standart tildagi matn olinadi. Kutubxonaning o'z matnlari ("Ha", "Bekor qilindi" va boshqalar) uz, ru va en tillarida tayyor turadi. Ularni ham o'z faylingizda qayta yozishingiz mumkin, masalan: `"nb.yes": "Albatta"`.
""")

PAGES["admin"] = ("Admin panel va statistika", """
{code:admin}

Admin buyruqlari faqat adminlarning menyusida ko'rinadi. Oddiy foydalanuvchilar ularni ko'rmaydi va ishlata olmaydi.

## Statistika

{code:stats}

| Ko'rsatkich | Ma'nosi |
|---|---|
| DAU / WAU / MAU | 1, 7 va 30 kunda faol bo'lganlar |
| `retention_d7` | 7–14 kun oldin kelganlarning qanchasi so'nggi haftada qaytgan (%) |
| `top_commands` | 30 kundagi eng ko'p ishlatilgan buyruqlar |

## Texnik ishlar rejimi

`await bot.maintenance(True)` yoqilganda adminlardan boshqa hamma "🛠 texnik ishlar" xabarini oladi. Rejim restartdan keyin ham saqlanadi.

## Xatolar haqida hisobot

Handlerda xato bo'lsa, foydalanuvchi muloyim xabar oladi, adminlar esa traceback'li hisobot oladi. Bir xil xato 10 daqiqada faqat bir marta yuboriladi.
""")

PAGES["broadcast"] = ("Broadcast (hammaga xabar)", """
{code:broadcast}

- Telegram chegarasi hisobga olinadi: standart tezlik soniyasiga 25 ta. `rate=` bilan o'zgartirish mumkin
- 429 flood xatosida kerakli vaqt kutib, davom etadi
- Botni bloklaganlar `is_blocked=True` deb belgilanadi va keyingi safar o'tkazib yuboriladi
- `id=` berilsa, jarayon har 20 ta xabarda saqlanadi. Bot to'xtab qolsa, o'sha `id` bilan qayta chaqiring, u qolgan joyidan davom etadi
- `on_progress=` funksiyasi har 3 soniyada joriy holatni oladi
""")

PAGES["payments"] = ("To'lovlar (Telegram Stars)", """
{code:stars}

`pre_checkout_query` avtomatik tasdiqlanadi. O'zingiz tekshirmoqchi bo'lsangiz, `@bot.pre_checkout()` handlerini yozing. Pulni qaytarish: `await ctx.refund()`.
""")

PAGES["groups"] = ("Guruhlar, obuna va support", """
## Guruhni boshqarish

{code:group}

Bu metodlar reply qilingan odam ustida ishlaydi yoki `user_id=` qabul qiladi. Bot guruhda admin bo'lishi kerak.

## Captcha

{code:captcha}

## Majburiy obuna

{code:subscribe}

Bot kanalda admin bo'lishi kerak, aks holda a'zolikni tekshira olmaydi. Natija bir daqiqa keshlanadi, shuning uchun Telegram'ga ortiqcha so'rov ketmaydi.

## Support rejimi

{code:support}
""")

PAGES["middleware"] = ("Middleware, DI va xatolar", """
## Middleware

Middleware har bir update atrofida ishlaydi va handlerdan oldin ham, keyin ham kod bajarishi mumkin.

{code:middleware}

## Bog'liqlik kiritish (DI)

Handler o'ziga kerakli narsani parametr nomi yoki turi orqali so'raydi:

{code:di}

Nom bo'yicha keladiganlar: `bot`, `message`, `callback`, `user`, `chat`, `text`, `args`, `arg`, `payload`, `data`, `value`, `album`, `lang`, `state`, `config`, `db` va `storage`, shuningdek callback va regex parametrlari.

## Xatolar

{code:errors}
""")

PAGES["scheduler"] = ("Rejalashtirish, fon va kesh", """
## Rejalashtirilgan vazifalar

{code:schedule}

Kunlar inglizcha (`mon`…`sun`) yoki o'zbekcha (`du`, `se`, `chor`, `pay`, `ju`, `shan`, `yak`) yoziladi.

## Fon vazifalari

{code:background}

Fon vazifasi xato bersa, eksponensial kutish bilan qayta uriniladi. Bot to'xtatilganda tugallanmagan vazifalar kutib olinadi.

## Kesh

{code:cache}

## Fayllar

{code:files}
""")

PAGES["deploy"] = ("Ishga tushirish va deploy", """
{code:run}

## Polling yoki webhook

Polling sozlash talab qilmaydi va kichik hamda o'rta botlar uchun yetarli. Webhook uchun HTTPS domen kerak. nicebot `setWebhook`'ni maxfiy token bilan o'zi chaqiradi va kelgan so'rovlarni tekshiradi. Server sog'lig'ini `/nicebot/health` manzilida tekshirish mumkin.

## To'g'ri to'xtash

Ctrl+C yoki SIGTERM kelganda bot yangi update olishni to'xtatadi va ishlayotgan handlerlar tugashini kutadi. Keyin offset'ni Telegram'ga tasdiqlaydi, shuning uchun restartda birorta update yo'qolmaydi va ikki marta ham ishlanmaydi.

## Docker

{code:docker:docker}

## Ishonchlilik

- Flood control (429): kerakli soniya kutiladi va so'rov qayta yuboriladi
- Tarmoq va 5xx xatolari: eksponensial kutish bilan 3 marta qayta urinadi
- Noma'lum yangi update turlari bot ishini to'xtatmaydi, ular logga yozilib, o'tkazib yuboriladi
- Bir vaqtdagi handlerlar soni `max_concurrency=256` bilan cheklangan

## Domensiz webhook

`bot.start(tunnel=True, webhook=True)` — webhook bepul HTTPS tunnel orqali ishlaydi. Production'da: `Nicebot(public_url="https://bot.example.uz")` va `bot.start(webhook=True, port=8080)`.
""")

PAGES["testing"] = ("Testlash", """
Botni Telegram'siz, haqiqiy foydalanuvchidek sinab ko'rish mumkin. Soxta API barcha chaqiruvlarni yozib boradi.

{code:testing}

| | |
|---|---|
| `t.user(...)` | Soxta foydalanuvchi |
| `user.send(text)` | Xabar yuborish |
| `user.click("matn")` | Tugmani bosish |
| `user.send_photo()` / `send_contact()` / `send_location()` / `send_album()` | Media yuborish |
| `t.last` | Oxirgi xabar: `.text`, `.buttons`, `.keyboard` |
| `t.messages` / `t.texts` | Barcha xabarlar |
| `t.calls_of("sendPhoto")` | API chaqiruvlari |
| `t.blocked = {id}` | Botni bloklagan foydalanuvchi |

`pytest` va `pytest-asyncio` bilan ishlaydi.

## Fayllar va Mini App

`user.send_document("report.pdf", content=b"...")`, `send_photo`, `send_video`, `send_voice` — bot bu fayllarni `ctx.download()` bilan haqiqatan yuklab oladi. Mini App endpointlarini `await t.api("/api/...", {...}, user=ali)` bilan tekshiring — [misol](#miniapp-backend).
""")

PAGES["features"] = ("50 ta imkoniyat", """
{features}
""")

PAGES["api"] = ("Bot API", """
`Nicebot` Bot API'ning barcha metodlarini to'g'ridan-to'g'ri beradi. Ular rasmiy spetsifikatsiyadan avtomatik yaratilgan va to'liq turlangan, shuning uchun muharriringiz har bir parametrni taklif qiladi.

{code:raw_api}

Turlar `from nicebot import types` orqali olinadi, masalan `types.Message` yoki `types.InlineKeyboardButton`. Ular msgspec asosida qurilgan, shuning uchun JSON'ni juda tez o'qiydi. Telegram yangi maydon qo'shsa ham kod buzilmaydi.

## Versiyalar

| | |
|---|---|
| nicebot | 1.0.0 |
| Bot API | 10.3 |
| Python | 3.10+ |
| Litsenziya | MIT |
""")

FEATURE_GROUPS = [
    ("Suhbat", [
        ("await ctx.ask()", "FSM klasslarisiz savol-javob"),
        ("ctx.confirm()", "Ha/Yo'q savol, True/False qaytaradi"),
        ("ctx.choose(multiple=True)", "✅/⬜️ bilan bir nechta variant tanlash"),
        ("ctx.form()", "Bir nechta savol, validatsiya va qayta so'rash"),
        ("Validatorlar", "Telefon (+998), email, sana, son, URL, rasm va boshqalar"),
    ]),
    ("Tugmalar", [
        ("Button(on_click=)", "Tugma to'g'ridan-to'g'ri funksiyaga bog'lanadi"),
        ("Callback shablonlari", "\"buy:{id:int}\" avtomatik parse qilinadi"),
        ("Avto-joylashuv", "Qisqa tugmalar bir qatorga o'zi joylashadi"),
        ("Toggle", "✅/⬜️ sozlamalar, qiymat saqlanadi"),
        ("ttl= va only=", "Muddatli va faqat bir kishi bosa oladigan tugmalar"),
        ("once=True", "Bir martalik tugma"),
        ("64 bayt chegarasi yo'q", "Uzun callback ma'lumoti bazada saqlanadi"),
        ("Avto-javob", "Tugmadagi soat belgisi qotib qolmaydi"),
        ("Reply qisqartmalari", "\"📞 Raqam:contact\", \":location\""),
        ("ctx.respond()", "Tugmadan bo'lsa tahrirlaydi, aks holda yuboradi"),
        ("Ko'p darajali Menu", "\"Orqaga\" tugmasi avtomatik"),
        ("ctx.paginate()", "◀️ 2/5 ▶️ sahifalash"),
    ]),
    ("Ma'lumotlar", [
        ("Ichki ORM", "SQLite, PostgreSQL, MySQL va MongoDB uchun bitta API, avto-migratsiya bilan"),
        ("ctx.user", "Foydalanuvchi bazaga avtomatik yoziladi"),
        ("i18n", "ctx.t(), uz/ru/en tayyor matnlar"),
        ("file_id keshi", "Lokal fayl bir marta yuklanadi"),
    ]),
    ("Biznes", [
        ("Referal tizimi", "ctx.ref_link, referrer_id va @bot.on_referral"),
        ("Broadcast", "Tezlik chegarasi, bloklanganlarni belgilash va davom ettirish"),
        ("Admin panel", "/stats, /broadcast, /maintenance va /backup"),
        ("Analitika", "DAU/MAU, retention va top buyruqlar"),
        ("Majburiy obuna", "required_channels=[…]"),
        ("Support rejimi", "Xabar guruhga boradi, javob foydalanuvchiga qaytadi"),
        ("Texnik ishlar rejimi", "Adminlar baribir ishlata oladi"),
        ("Telegram Stars", "ctx.invoice() va @bot.paid"),
        ("Guruh va captcha", "ban, mute, warn (3 → ban), yangi a'zolarga captcha"),
        ("Xato hisoboti", "Adminlarga traceback avtomatik yuboriladi"),
    ]),
    ("Arxitektura", [
        ("Type hint orqali DI", "async def h(ctx, user: Customer, cfg: Settings)"),
        ("Nicebot.from_env()", ".env faylidan sozlash"),
        ("bot.include(\"handlers\")", "Router'larni avtomatik topish"),
        ("@cache(\"5m\")", "Async funksiyalar uchun kesh"),
        ("ctx.background()", "Retry bilan fon vazifalari"),
        ("@bot.every / @bot.at", "Rejalashtiruvchi, vaqt zonasi bilan"),
        ("Albomlar", "Media group bitta handlerga ro'yxat bo'lib keladi"),
        ("Mini App server", "Fayllar va initData HMAC tekshiruvi bot jarayonida"),
        ("Mini App RPC", "@bot.api endpointlari va tayyor nicebot.js"),
        ("Bir nechta bot", "Nicebot.run_all(bot1, bot2)"),
        ("typing=True", "Handler ishlayotganda \"yozmoqda…\" ko'rinadi"),
    ]),
    ("Ishonchlilik", [
        ("Flood himoyasi", "429 xatosida kutib, qayta yuboradi"),
        ("throttle=", "Spamga qarshi tezlik chegarasi"),
        ("To'g'ri to'xtash", "Restartda update yo'qolmaydi"),
        ("Xavfsiz formatlash", "html() va formatlash xatosida qayta yuborish"),
        ("delete_after=", "Xabarni avtomatik o'chirish"),
        ("Hot reload", "bot.start(reload=True)"),
        ("Test to'plami", "bot.test(): Telegram'siz test"),
        ("CLI", "nicebot new mybot"),
    ]),
]

