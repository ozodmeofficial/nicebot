"""Yangi sahifalar (o'zbekcha): VS Code, Media, Mini App."""

PAGES = {}

PAGES["vscode"] = ("VS Code va avtomatik to'ldirish", """
`ctx.` deb yozganingizda muharrir barcha metodlarni ko'rsatishi uchun **bitta narsa** kerak: handler parametriga tur yozing.

{code:vscode_hint}

## Nega bu kerak?

Python dinamik til. `async def start(ctx)` deb yozsangiz, muharrir `ctx` nima ekanini bilmaydi va hech narsa taklif qilmaydi. `ctx: Context` deb yozsangiz, VS Code (Pylance), PyCharm va boshqa muharrirlar quyidagilarni ko'rsatadi:

- `ctx.` dan keyin barcha xususiyat va metodlar ro'yxati
- har bir metodning parametrlari: `ctx.reply("...", ` deb yozganda `buttons=`, `keyboard=`, `delete_after=`, `silent=` va boshqalar
- sichqonchani metod ustiga olib borganda inglizcha tavsif va **ishlatish misoli**
- noto'g'ri parametr nomi yozilsa (masalan `butons=`) qizil chiziq

> [!TIP]
> Kutubxonaning har bir funksiyasi va klassida misol bor. Metod ustiga sichqonchani olib boring yoki `Ctrl` + bosib manba kodini oching.

## Boshqa obyektlar uchun ham

Xuddi shu qoida hamma joyda ishlaydi: `Media`, `User`, `WebAppRequest`, `Nicebot` turlarini yozing.

{code:vscode_types}

| Nima | Tur | Qayerdan |
|---|---|---|
| Handler konteksti | `Context` | `from nicebot import Context` |
| Kelgan fayl | `Media` | `ctx.media` |
| Foydalanuvchi (baza) | `User` yoki o'z modelingiz | `ctx.user` |
| Mini App so'rovi | `WebAppRequest` | `@bot.api` handleri |
| Bot | `Nicebot` | `ctx.bot` |
| Test sessiyasi | `TestSession` | `bot.test()` |

## VS Code sozlamalari

1. **Python** kengaytmasini o'rnating (Pylance u bilan birga keladi).
2. Pastki o'ng burchakdan nicebot o'rnatilgan Python interpretatorini tanlang (`Ctrl+Shift+P` → *Python: Select Interpreter*).
3. Ixtiyoriy: `.vscode/settings.json`:

{code:vscode_settings:json}

> [!NOTE]
> PyCharm'da sozlash shart emas — `ctx: Context` yozishning o'zi yetarli.
""")

PAGES["media-receive"] = ("Fayllarni qabul qilish", """
Foydalanuvchi rasm, video, hujjat, ovozli xabar yoki boshqa fayl yuborganda nicebot uni bitta qulay `Media` obyektiga aylantiradi: `ctx.media`.

{code:media_receive}

## Qaysi turlarni ushlash

`@bot.on(...)` ga kontent turlarini bering. Bir nechta tur birga yozilishi mumkin.

| Tur | Nima |
|---|---|
| `"photo"` | Rasm (Telegram siqib yuboradi) |
| `"video"` | Video |
| `"animation"` | GIF yoki ovozsiz MP4 |
| `"document"` | Har qanday fayl (PDF, ZIP, siqilmagan rasm…) |
| `"audio"` | Musiqa |
| `"voice"` | Ovozli xabar |
| `"video_note"` | Dumaloq video |
| `"sticker"` | Stiker |
| `"any"` | Istalgan xabar |

> [!TIP]
> Foydalanuvchi rasmni **fayl sifatida** yuborsa, u `"document"` bo'lib keladi. Ikkalasini ham qabul qilish uchun `@bot.on("photo", "document")` yozing va `ctx.media.is_image` bilan tekshiring.

## Media obyekti

{code:media_fields}

Rasmlar Telegram'da bir nechta o'lchamda keladi — `ctx.media` avtomatik eng kattasini oladi.

## Savol berib fayl so'rash

Faylni suhbat ichida so'rash uchun `ctx.ask` ga fayl validatorini bering. Noto'g'ri fayl yuborilsa (turi, hajmi yoki MIME mos kelmasa), bot tushunarli xato yozadi va qayta so'raydi.

{code:media_ask}

| Validator | Qabul qiladi | Qaytaradi |
|---|---|---|
| `Photo` | faqat rasm | `PhotoSize` |
| `File` | istalgan fayl | `Media` |
| `Document` | hujjat | `Media` |
| `Video` | video | `Media` |
| `Audio` | musiqa | `Media` |
| `Voice` | ovozli xabar | `Media` |

`File`, `Document`, `Video`, `Audio` va `Voice` quyidagi parametrlarni oladi: `max_size="10MB"`, `mime="application/pdf"` yoki `mime="image/*"` (ro'yxat ham bo'ladi), `kinds=[...]`.

## Albomlar

Bir nechta rasm yoki video bitta albom bo'lib kelsa, `@bot.album()` hammasini **bitta chaqiruvda** beradi — [Albom va tahrirlash](#media-albums) sahifasiga qarang.
""")

PAGES["media-download"] = ("Yuklab olish va saqlash", """
Faylni ikki xil olish mumkin: xotiraga (`bytes`) yoki to'g'ridan-to'g'ri diskka.

{code:media_download}

| Metod | Natija | Qachon |
|---|---|---|
| `await ctx.download()` | `bytes` | faylni darhol qayta ishlash (rasmni o'zgartirish, CSV o'qish) |
| `await ctx.save(path)` | yo'l (`str`) | faylni saqlab qo'yish |
| `await ctx.media.download()` / `.save()` | xuddi shunday | `Media` obyektidan |
| `await bot.download_file(file_id)` | `bytes` | handlerdan tashqarida, `file_id` bo'yicha |
| `await bot.save_file(file_id, path)` | yo'l | handlerdan tashqarida |

`save()` faylni **bo'laklab** yozadi, shuning uchun katta fayl xotirani to'ldirmaydi.

## Fayl qayerga saqlanadi

- `save()` — `downloads/` papkasiga, faylning asl nomi bilan (nomi bo'lmasa — `file_unique_id` + kengaytma)
- `save("uploads/")` — `/` bilan tugasa yoki papka mavjud bo'lsa, fayl o'z nomi bilan shu papkaga
- `save("avatar.jpg")` — aynan shu yo'lga
- yetishmayotgan papkalar o'zi yaratiladi

## 20 MB chegarasi

Telegram'ning bulutli Bot API'si botlarga **20 MB gacha** fayllarni yuklab olishga ruxsat beradi. Kattaroq faylda nicebot `FileTooBig` xatosini beradi. Buni oldindan `ctx.media.can_download` bilan tekshirish mumkin.

{code:media_too_big}

> [!NOTE]
> Yuborish chegarasi boshqacha: bot **50 MB gacha** fayl yubora oladi.

## Katta fayllar: o'z Bot API serveringiz

2 GB gacha fayllar uchun Telegram'ning ochiq kodli [Bot API serveri](https://github.com/tdlib/telegram-bot-api)ni o'zingizda ishga tushiring va manzilini bering. nicebot `--local` rejimini ham taniydi: fayllar tarmoqsiz, to'g'ridan-to'g'ri diskdan o'qiladi.

{code:media_local_api}
""")

PAGES["media-send"] = ("Fayl yuborish", """
Har bir fayl turi uchun alohida metod bor. Ularning hammasi bir xil ishlaydi: birinchi argument — fayl, ikkinchisi — izoh (caption).

{code:media_send}

## Faylni qayerdan berish mumkin

| Manba | Misol |
|---|---|
| Lokal fayl yo'li | `"images/menu.jpg"`, `Path("menu.jpg")` |
| URL | `"https://example.com/a.jpg"` — Telegram o'zi yuklab oladi |
| `file_id` | Telegram'dagi fayl, yuklashsiz bir zumda |
| `Media` obyekti | `ctx.media` — qabul qilingan faylni qayta yuborish |
| `bytes` / `BytesIO` | xotirada yaratilgan fayl (`filename=` bering) |
| `InputFile` | to'liq nazorat: `InputFile(data, filename="a.pdf")` |

Mavjud bo'lmagan lokal yo'l berilsa, nicebot tushunarsiz Telegram xatosi o'rniga aniq `FileNotFoundError` beradi.

## Xotirada yaratilgan fayllar

Grafik, QR-kod, Excel yoki CSV'ni diskka yozmasdan yuborish mumkin:

{code:media_bytes}

## Qo'shimcha parametrlar

Barcha yuborish metodlari `ctx.reply` dagi parametrlarni (`buttons=`, `keyboard=`, `delete_after=`, `silent=`, `protect=`, `quote=`, `chat_id=`) va media parametrlarini qabul qiladi:

{code:media_options}

| Parametr | Ma'nosi |
|---|---|
| `spoiler=True` | rasm/video xira ko'rinadi, bosilganda ochiladi |
| `caption_above=True` | izoh rasm tepasida |
| `thumbnail=` | video yoki hujjat uchun kichik rasm |
| `duration=`, `width=`, `height=` | video/audio ma'lumotlari |
| `supports_streaming=True` | videoni yuklab bo'lmasdan ko'rish |
| `performer=`, `title=` | audio uchun |
| `filename=` | `bytes` yuborilganda fayl nomi |

## Avtomatik kesh

Bitta lokal faylni ikkinchi marta yuborganda nicebot uni qayta yuklamaydi — Telegram bergan `file_id` saqlanib qoladi va keyingi safar ishlatiladi. Fayl o'zgarsa (hajmi yoki vaqti), yana yuklanadi.

{code:media_cache}

## Turini o'zi aniqlash

`ctx.send_file()` fayl kengaytmasiga qarab metodni o'zi tanlaydi: `.jpg/.png` → rasm, `.mp4` → video, `.mp3` → audio, `.ogg` → ovozli xabar, qolganlari → hujjat. `Media` berilsa, asl turi ishlatiladi. Kerak bo'lsa `kind="document"` bilan majburlash mumkin.

## Nusxa olish va forward

{code:media_forward}
""")

PAGES["media-albums"] = ("Albom va tahrirlash", """
## Albom yuborish

2–10 ta fayl bitta albom bo'lib ketadi. Rasm va video aralash bo'lishi mumkin; hujjatlar va audiolar alohida albom bo'ladi. Izoh birinchi faylning ostida chiqadi.

{code:media_album_send}

## Albom qabul qilish

Telegram albomni alohida-alohida xabarlar qilib yuboradi. `@bot.album()` ularni yig'ib, handlerni **bir marta** chaqiradi.

{code:media_album_receive}

> [!TIP]
> `@bot.album()` handleri bo'lmasa, albomdagi har bir fayl odatdagidek `@bot.on("photo")` kabi handlerlarga alohida keladi.

## Rasmni joyida almashtirish

`ctx.edit_media()` xabarni o'chirmasdan rasm, video yoki hujjatni almashtiradi. Galereya, katalog yoki ◀️ ▶️ bilan varaqlash uchun qulay.

{code:media_edit}

## Statuslar

Katta faylni tayyorlayotganda foydalanuvchiga holatni ko'rsating: `await ctx.action("upload_photo")`, `"upload_video"`, `"upload_document"`, `"record_voice"`. Handler parametrida `typing="upload_photo"` desangiz, status handler ishlab turgan butun vaqt davomida ko'rinadi.
""")

PAGES["miniapp"] = ("Mini App: umumiy ko'rinish", """
**Mini App** — Telegram ichida ochiladigan veb-sahifa (HTML, CSS, JavaScript). Do'kon, o'yin, forma, kalendar — oddiy saytda nima qilsangiz, shu yerda ham qilasiz, faqat foydalanuvchi Telegram'dan chiqmaydi va siz uni login-parolsiz taniysiz.

nicebot Mini App uchun kerak bo'lgan hamma narsani **bot bilan bitta jarayonda** beradi:

- veb-server: `bot.webapp("webapp")` — HTML/JS/CSS fayllaringizni beradi
- backend API: `@bot.api("/api/...")` — foydalanuvchi Telegram imzosi bilan avtomatik tekshiriladi
- frontend yordamchi: `nicebot.js` — so'rovlar, tugmalar, tema, fayl yuklash
- HTTPS: `bot.start(tunnel=True)` — domen va sertifikatsiz bepul HTTPS manzil

## Qanday ishlaydi

1. Bot foydalanuvchiga Mini App tugmasini yuboradi.
2. Foydalanuvchi bosadi — Telegram sahifangizni ochadi va unga `initData` beradi (kim ochganini bildiruvchi imzolangan ma'lumot).
3. Sahifa `nicebot.js` orqali `@bot.api` endpointlaringizga so'rov yuboradi; `initData` har bir so'rovga o'zi qo'shiladi.
4. nicebot imzoni bot tokeningiz bilan tekshiradi va handleringizga **ishonchli** `req.user` beradi.
5. Handler bazaga yozadi, foydalanuvchiga chatda xabar yuboradi (`req.send`) va javob qaytaradi.

## 5 daqiqada birinchi Mini App

Loyiha tuzilishi:

{code:miniapp_tree:text}

`bot.py`:

{code:miniapp_quick_py}

`webapp/index.html`:

{code:miniapp_quick_html:html}

Ishga tushiring: `python bot.py`. Terminalda shunday yozuvlar chiqadi:

{code:miniapp_log:text}

Telegram'da botga `/start` yozing va **🛍 Do'kon** tugmasini bosing — sahifa ochilib, ismingiz bilan salomlashadi.

> [!NOTE]
> `tunnel=True` uchun kompyuterda `cloudflared` yoki `ssh` bo'lishi kerak (`ssh` Windows 10+, macOS va Linux'da allaqachon bor). Batafsil: [HTTPS'siz ishlab chiqish](#miniapp-dev).

## HTTPS haqida

Telegram ilovalari Mini App'ni **faqat HTTPS** orqali ochadi — bu Telegram talabi va uni chetlab o'tib bo'lmaydi. Lekin buning uchun domen sotib olish yoki sertifikat sozlash shart emas:

| Holat | Yechim |
|---|---|
| Ishlab chiqish | `bot.start(tunnel=True)` — bepul HTTPS manzil |
| Brauzerda sinash | `Nicebot(debug=True)` → `http://localhost:8080` |
| Telegram test serveri | `Nicebot(test_server=True)` — HTTP ham ishlaydi |
| Production | o'z domeningiz + Caddy/Nginx → `Nicebot(public_url=...)` |

## Keyingi qadamlar

1. [Mini App'ni ochish usullari](#miniapp-open) — tugma, klaviatura, menyu, havola va BotFather
2. [Backend: @bot.api](#miniapp-backend) — ma'lumot olish, saqlash, fayl qabul qilish
3. [Frontend: nicebot.js](#miniapp-frontend) — JavaScript yordamchisi
4. [HTTPS'siz ishlab chiqish](#miniapp-dev) — tunnel, brauzer va test server
5. [Deploy va xavfsizlik](#miniapp-deploy) — domen, CORS, alohida hosting
6. [To'liq misol: do'kon](#miniapp-example)
""")

PAGES["miniapp-open"] = ("Mini App'ni ochish usullari", """
Mini App'ni 4 xil ochish mumkin. Qaysi birini tanlash — ilovangiz nima qilishiga bog'liq.

{code:miniapp_open}

| Usul | Qayerda ko'rinadi | Botga ma'lumot qaytarish |
|---|---|---|
| Inline tugma `Button(webapp=...)` | xabar ostida | `@bot.api` orqali (eng qulay) |
| Pastki klaviatura `ReplyButton(webapp=...)` | xabar maydoni ostida | `nicebot.sendData()` → `@bot.webapp_data()` |
| Menyu tugmasi `bot.menu_app(...)` | xabar maydoni yonida, doim | `@bot.api` orqali |
| Havola `bot.app_link(...)` | istalgan joyda (kanal, sayt, QR) | `@bot.api` orqali |

> [!TIP]
> Manzilni `"/shop"` kabi **nisbiy yo'l** bilan yozing. nicebot uni `public_url` (yoki tunnel manzili) bilan to'liq HTTPS manzilga o'zi aylantiradi. To'liq `https://...` manzil ham ishlaydi.

## Pastki klaviatura va sendData

Bu usulda Mini App ma'lumotni to'g'ridan-to'g'ri botga xabar qilib yuboradi va yopiladi. Server so'rovlari kerak emas — oddiy formalar uchun qulay. Ma'lumot hajmi 4 KB gacha.

{code:miniapp_senddata}

## BotFather'da sozlash

Inline tugma va menyu tugmasi uchun BotFather'da hech narsa sozlash shart emas. Qo'shimcha imkoniyatlar uchun:

1. **To'g'ridan-to'g'ri havola** (`t.me/your_bot/shop`): @BotFather → `/newapp` → botni tanlang → nom, tavsif, rasm va Mini App manzilini kiriting → qisqa nom (`shop`) bering. Havola: `bot.app_link("shop")`.
2. **Asosiy Mini App** (bot profilida "Open App" tugmasi): @BotFather → `/mybots` → botingiz → *Bot Settings* → *Configure Mini App* → manzilni kiriting. Havola: `bot.app_link()`.
3. **Menyu tugmasi** kodda: `bot.menu_app("🛍 Do'kon")` — bot ishga tushganda o'rnatiladi. Faqat bitta foydalanuvchi uchun: `await bot.set_menu_app("🎮 O'yin", "/game", chat_id=ctx.chat_id)`.

> [!WARNING]
> BotFather'ga tunnel manzilini kiritsangiz, u har ishga tushirishda o'zgaradi. BotFather uchun doimiy domen ishlating; ishlab chiqishda inline tugma va `bot.menu_app()` yetarli — ular joriy manzilni o'zi oladi.

## startapp parametri

Havola orqali parametr uzatish mumkin: `bot.app_link("shop", startapp="promo")`. Backend'da u `req.start_param`, frontend'da `nicebot.startParam` bo'lib keladi.
""")

PAGES["miniapp-backend"] = ("Backend: @bot.api", """
`@bot.api` — Mini App'ingiz chaqiradigan HTTP endpoint. U bot bilan bitta jarayonda ishlaydi, shuning uchun bazaga, `bot` ga va barcha nicebot imkoniyatlariga to'g'ridan-to'g'ri kirasiz.

{code:miniapp_api}

## Xavfsizlik avtomatik

Har bir so'rovdagi `initData` imzosi bot tokeningiz bilan **HMAC-SHA256** orqali tekshiriladi. Imzo noto'g'ri yoki eskirgan (24 soatdan oshgan) bo'lsa, so'rov handlerga yetib bormay `401` bilan rad etiladi. Shuning uchun `req.user` ga to'liq ishonish mumkin — uni soxtalashtirib bo'lmaydi.

`auth=False` — ochiq endpoint (masalan, mahsulotlar ro'yxati). Unda `req.user` bo'sh.

## WebAppRequest

{code:miniapp_req}

## Javob qaytarish

| Handler qaytaradi | Brauzer oladi |
|---|---|
| `dict` / `list` | JSON |
| `str` | matn |
| `None` | `{"ok": true}` |
| `aiohttp.web.Response` | o'zi |

Xatolarni oddiy Python istisnolari bilan bildiring — nicebot ularni to'g'ri HTTP javobga aylantiradi:

{code:miniapp_errors}

## Fayl qabul qilish

Mini App'dan rasm yoki hujjat yuklash: frontend'da `nicebot.upload(...)`, backend'da `await req.form()`.

{code:miniapp_upload_py}

## Foydalanuvchiga chatda javob

- `await req.send("...")` — botdan foydalanuvchiga xabar (tugmalar bilan ham)
- `await req.send_photo(...)`, `await req.send_document(...)` — fayl
- `await req.answer(title, text)` — Mini App inline tugmadan ochilgan bo'lsa, o'sha chatga foydalanuvchi nomidan xabar

> [!NOTE]
> `req.send` ishlashi uchun foydalanuvchi botni ishga tushirgan bo'lishi kerak (`/start`). Odatda Mini App bot ichidan ochiladi, shuning uchun bu shart bajarilgan bo'ladi.

## Testlash

{code:miniapp_test}
""")

PAGES["miniapp-frontend"] = ("Frontend: nicebot.js", """
`nicebot.js` — bot serveringiz `/nicebot.js` manzilida beradigan kichik JavaScript yordamchi. U Telegram'ning `telegram-web-app.js` kutubxonasi ustida ishlaydi va eng ko'p kerak bo'ladigan ishlarni bir qatorga keltiradi.

{code:miniapp_js_basic:html}

Ikkala skript ham `<head>` yoki `<body>` oxirida, **shu tartibda** ulanadi.

## So'rovlar

| Funksiya | Ma'nosi |
|---|---|
| `nicebot.get(path)` | GET so'rov |
| `nicebot.post(path, data)` | POST, JSON tana |
| `nicebot.put(path, data)`, `nicebot.del(path)` | PUT / DELETE |
| `nicebot.upload(path, files, fields)` | fayl yuklash (multipart) |

Hammasi `Promise` qaytaradi. `initData` har bir so'rovga o'zi qo'shiladi. Backend xato qaytarsa (`400`, `403`…), `Promise` rad etiladi va `e.message` da backend yozgan xato matni bo'ladi.

## Interfeys

{code:miniapp_js_ui}

| Funksiya | Ma'nosi |
|---|---|
| `nicebot.mainButton(text, onClick)` | pastdagi katta tugma |
| `nicebot.hideMainButton()` | yashirish |
| `nicebot.progress(true/false)` | tugmada yuklanish belgisi |
| `nicebot.backButton(onClick)` | yuqoridagi "orqaga" tugmasi |
| `nicebot.alert(text)` | xabar oynasi (`Promise`) |
| `nicebot.confirm(text)` | Ha/Yo'q oynasi (`Promise<boolean>`) |
| `nicebot.haptic(kind)` | tebranish: `"light"`, `"medium"`, `"heavy"`, `"success"`, `"error"`, `"warning"` |
| `nicebot.close()` | Mini App'ni yopish |

## Tema

`nicebot.theme()` Telegram ranglarini CSS o'zgaruvchilariga yozadi, shunda ilovangiz foydalanuvchining yorug' yoki qorong'i temasiga mos ko'rinadi:

{code:miniapp_js_theme:text}

## Boshqa imkoniyatlar

{code:miniapp_js_more}

To'liq Telegram API ham ochiq: `nicebot.tg` — bu `window.Telegram.WebApp` ning o'zi.

## Frontend boshqa joyda bo'lsa

Agar sahifangiz GitHub Pages yoki Vercel'da, bot esa boshqa serverda bo'lsa, `nicebot.js` ni **bot serveringizdan** ulang. U qaysi manzildan yuklanganini o'zi aniqlaydi va barcha so'rovlarni o'sha serverga yuboradi. Serverda CORS'ni yoqing — [Deploy va xavfsizlik](#miniapp-deploy).
""")

PAGES["miniapp-dev"] = ("HTTPS'siz ishlab chiqish", """
Telegram Mini App'ni faqat HTTPS orqali ochadi. Ishlab chiqish paytida buning uchun 3 ta yo'l bor — hech birida domen yoki sertifikat kerak emas.

## 1. Tunnel: bepul HTTPS manzil

{code:miniapp_dev_tunnel}

`tunnel=True` kompyuteringizdagi serverni internetga xavfsiz HTTPS manzil bilan chiqaradi va o'sha manzilni `bot.public_url` ga yozadi. Nisbiy Mini App manzillari (`webapp="/"`), `bot.menu_app()` va `webhook=True` shu manzildan foydalanadi.

| Provayder | Nima kerak | Manzil ko'rinishi |
|---|---|---|
| `cloudflared` | [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) dasturi | `https://...trycloudflare.com` |
| `localhost.run` | faqat `ssh` | `https://...lhr.life` |
| o'z buyrug'ingiz | masalan `ngrok` | buyruq chiqargan birinchi `https://` manzil |

> [!WARNING]
> Tunnel manzili har ishga tushirishda o'zgaradi. U faqat ishlab chiqish uchun; production'da o'z domeningizni ishlating.

Tunnel orqali webhook ham ishlaydi:

{code:miniapp_webhook}

## 2. Oddiy brauzerda sinash

Dizayn va mantiqni Telegram'siz, oddiy Chrome yoki Firefox'da tekshirish eng tez yo'l. `debug=True` bilan nicebot soxta, lekin to'g'ri imzolangan foydalanuvchi yaratadi va `nicebot.js` uni o'zi ishlatadi.

{code:miniapp_dev_browser}

`http://localhost:8080` ni oching — `@bot.api` so'rovlari `dev_user` nomidan ishlaydi. Brauzerdagi DevTools, hot reload va boshqa vositalar odatdagidek ishlaydi.

> [!NOTE]
> Xavfsizlik uchun soxta foydalanuvchi faqat `debug=True` bo'lganda va faqat shu kompyuterning o'zidan (`localhost`) kelgan so'rovlarga beriladi. Production'da `debug` ni o'chiring.

## 3. Telegram test serveri

Telegram'ning alohida test muhitida Mini App'lar oddiy `http://` havolalar bilan ham ochiladi — masalan, Wi-Fi tarmog'idagi telefoningizdan kompyuteringizga.

{code:miniapp_dev_test_server}

Test serveri uchun alohida akkaunt va bot kerak: Telegram ilovasida test akkaunti yarating va undagi @BotFather'dan token oling ([qo'llanma](https://core.telegram.org/bots/webapps#testing-mini-apps)).

## Qaysi birini tanlash

- Sahifa dizayni va JavaScript → **brauzer** (`debug=True`)
- Haqiqiy Telegram ichida tekshirish → **tunnel** (`tunnel=True`)
- Internetsiz lokal tarmoq → **test server**
""")

PAGES["miniapp-deploy"] = ("Deploy va xavfsizlik", """
## O'z domeningizda

Production'da botni serverda ishga tushiring va oldiga HTTPS beradigan veb-serverni (Caddy yoki Nginx) qo'ying.

{code:miniapp_deploy}

[Caddy](https://caddyserver.com) HTTPS sertifikatini o'zi oladi va yangilab turadi — butun sozlama 3 qator:

{code:miniapp_caddy:text}

`public_url` (yoki `PUBLIC_URL`) berilgandan keyin nisbiy manzillar, `bot.menu_app()` va `webhook=True` shu domen bilan ishlaydi.

## Frontend alohida hostingda

Frontend'ni GitHub Pages, Vercel yoki Netlify'da, backend'ni bot serverida saqlash mumkin. Buning uchun:

1. Bot serverida CORS'ni yoqing — qaysi saytlar so'rov yuborishi mumkinligini ayting.
2. Frontend'da `nicebot.js` ni bot serveridan ulang.
3. Mini App tugmasida frontend manzilini to'liq yozing: `Button("🛍", webapp="https://me.github.io/shop/")`.

{code:miniapp_cors}

## Xavfsizlik bo'yicha qoidalar

- **Hech qachon** `nicebot.user` yoki brauzerdan kelgan `user_id` ga ishonmang — faqat backend'dagi `req.user` ga ishoning, u imzo bilan tekshirilgan.
- Narx, chegirma va hisob-kitoblarni backend'da qiling; frontend faqat mahsulot `id` larini yuborsin.
- `auth=False` ni faqat haqiqatan ochiq ma'lumotlar uchun ishlating.
- `debug=True` ni production'da o'chiring.
- Bot tokeningizni frontend kodiga hech qachon yozmang.

Boshqa server (FastAPI, Django) ishlatsangiz, `initData` ni o'zingiz tekshiring:

{code:miniapp_security}

## Healthcheck

Server ishlayotganini tekshirish uchun: `GET /nicebot/health` → `{"ok": true, "bot": "...", "uptime": 123}`.
""")

PAGES["miniapp-example"] = ("To'liq misol: do'kon", """
Bu misol hamma qismlarni birlashtiradi: mahsulotlar ro'yxati, savat, Telegram'ning asosiy tugmasi, buyurtmani bazaga yozish, foydalanuvchiga va adminga xabar.

## bot.py

{code:miniapp_shop_py}

## webapp/index.html

{code:miniapp_shop_html:html}

## Ishga tushirish

1. `pip install nicebot`
2. Ikkala faylni yuqoridagi tuzilishda saqlang va `token=` ga @BotFather bergan tokenni yozing.
3. `python bot.py` — terminalda tunnel manzili chiqadi.
4. Telegram'da botga `/start` yozing, **🛍 Do'kon** ni bosing, mahsulot qo'shing va **Buyurtma berish** ni bosing.
5. Chatda buyurtma xabari keladi, admin esa bildirishnoma oladi.

> [!TIP]
> Avval `http://localhost:8080` ni brauzerda oching — `debug=True` tufayli hammasi Telegram'siz ham ishlaydi. Keyin Telegram ichida tekshiring.

## Keyingi qadamlar

- Mahsulotlarni `Product` modeliga o'tkazing ([Baza](#database))
- To'lovni Telegram Stars bilan qo'shing ([To'lovlar](#payments))
- Buyurtmalar uchun admin buyruqlarini yozing ([Admin panel](#admin))
""")
