# Changelog

## 1.0.0 — 2026-11-04

Birinchi barqaror versiya. API endi semver bo'yicha: 1.x davomida eski kod buzilmaydi.

### Mini App
- `bot.start(tunnel=True)` — domen va sertifikatsiz bepul HTTPS manzil (cloudflared yoki ssh/localhost.run, yoki o'z buyrug'ingiz)
- `Nicebot(debug=True, dev_user=...)` — Mini App'ni oddiy brauzerda `http://localhost:8080` da sinash (faqat localhost'dan)
- `Nicebot(test_server=True)` — Telegram test serveri (HTTP havolalar ham ishlaydi)
- `Nicebot(public_url=...)`, `PUBLIC_URL` — nisbiy manzillar: `Button(webapp="/shop")`, `ReplyButton(webapp="/order")`
- `Nicebot(cors=[...])` — frontend boshqa hostingda bo'lsa; `nicebot.js` backend manzilini o'zi aniqlaydi
- `bot.menu_app()`, `bot.set_menu_app()`, `bot.app_link()`, `bot.webapp_url()`, `webhook=True`
- `WebAppRequest`: `req.user` endi `WebAppUser` (atributlar + dict), `req.form()`, `req.files()`, `req.send()`, `req.send_photo()`, `req.send_document()`, `req.answer()`, `req.start_param`, `req.query_id`, `req.ip`
- `nicebot.js`: `upload`, `put`, `del`, `mainButton`, `backButton`, `progress`, `alert`, `confirm`, `theme`, `storage` (CloudStorage), `share`, `openLink`, `startParam`, `isTelegram`; backend xato matni `e.message` da
- `ctx.web_app_data` — `sendData()` ma'lumoti (JSON avtomatik o'qiladi)

### Media
- `ctx.media` — kelgan har qanday fayl bitta `Media` obyektida: `kind`, `size`, `size_text`, `name`, `mime`, `extension`, `is_image`, `can_download`, `download()`, `save()`
- `ctx.save()` diskka bo'laklab yozadi, nomni o'zi qo'yadi (`downloads/<asl nom>`); `bot.download_file()`, `bot.save_file()`
- 20 MB dan katta fayl uchun aniq `FileTooBig` xatosi; lokal Bot API server (`--local`) qo'llab-quvvatlanadi
- `ctx.send_file()` (turini o'zi aniqlaydi), `ctx.edit_media()`, aralash rasm+video albomlar, `ctx.album_media`
- Validatorlar: `File(kinds=, max_size=, mime=)`, `Document`, `Video`, `Audio`, `Voice`
- Yuborish metodlarida `filename=`, `caption_above=`, `thumbnail=` va boshqa parametrlar

### Muharrir va hujjatlar
- Barcha metodlar to'liq turlangan: `ctx.reply(...)`, `ctx.photo(...)`, `@bot.command(...)` parametrlari VS Code/PyCharm'da ko'rinadi (`SendOptions`, `MediaOptions`, `HandlerOptions`)
- Kutubxonadagi har bir ochiq funksiya va klassda inglizcha tavsif va ishlatish misoli; Bot API'ning 185 metodi va 403 turida parametrlar ro'yxati va misol
- Kutubxona ichidagi barcha xato, log va CLI matnlari inglizcha; admin panel javoblari i18n orqali (uz/ru/en)
- Hujjatlar sayti GitHub uslubida qayta yasaldi: yangi Mini App (7 sahifa), Media (4 sahifa), VS Code va to'liq ma'lumotnoma (ctx, Nicebot, tugmalar, media, Mini App, testlar) bo'limlari

### Testlar
- `TestUser.send_video/send_voice/send_audio/send_web_app_data`, `send_photo/send_document(content=, size=, mime=)` — bot fayllarni haqiqatan yuklab oladi
- `await t.api(path, json, user=...)` — Mini App endpointlarini imzolangan initData bilan sinash

### Tuzatilgan xatolar
- `@bot.deep_link(...)` dekorator sifatida yiqilardi (havola yasovchi metod bilan nom to'qnashuvi)
- `ctx.answer_inline(generator)` `TypeError` berardi
- Mavjud bo'lmagan fayl yo'li file_id deb yuborilardi — endi `FileNotFoundError`
- `ctx.pin/unpin/react/forward/copy` xabarsiz update'larda `AttributeError` berardi — endi tushunarli `ValueError`
- `ctx.choose(selected=...)` qiymatlar dict bo'lsa yiqilardi
- Webhook rejimida `drop_pending=True` e'tiborga olinmasdi
- `Date` validatori xato matnida format har doim o'zbekcha edi

### Eski koddan o'tish
- Havola yasash: `bot.start_link(payload)` (eski `bot.deep_link(payload)` ham ishlaydi — u endi ham havola, ham dekorator)
- Botni yopish: `await bot.shutdown()` (`bot.close()` ham ishlaydi); Telegram'ning `close` metodi — `bot.close_bot_instance()`
- `File` validatori endi Telegram obyekti o'rniga `Media` qaytaradi (`.file_id` o'z joyida)
- Handlerlarga `ctx: Context` yozing — muharrir hamma metodlarni ko'rsatadi

## 0.1.2 — 2026-11-04

Kutubxona kodi o'zgarmagan.

- README boshidagi badge'lar olib tashlandi

## 0.1.1 — 2026-11-04

Kutubxona kodi o'zgarmagan.

- README qayta yozildi: natija ko'rinishi, aiogram bilan solishtirish, tez start va hujjatlarga havolali imkoniyatlar jadvali
- Hujjatlar sayti yangi dizaynda: landing sahifa, bo'lim sahifalari, kod yonida chat ko'rinishi va qidiruv

## 0.1.0 — 2026-11-03

Birinchi chiqarilish.

- Telegram Bot API 10.3: 403 ta tur va 185 ta metod (msgspec)
- Ichki ORM: SQLite, PostgreSQL, MySQL/MariaDB, MongoDB va avto-migratsiya
- `ctx.ask`, `confirm`, `choose`, `form` va validatorlar
- `Button(on_click=)`, callback shablonlari, Toggle, `ttl`/`once`/`only`, Menu, paginate
- Referal, broadcast, statistika, admin panel, majburiy obuna, support, Telegram Stars
- Guruh moderatsiyasi va captcha
- Mini App server: `@bot.api`, initData tekshiruvi, `nicebot.js`
- Scheduler, fon vazifalari, kesh, i18n (uz/ru/en), DI, middleware
- Hot reload, `bot.test()`, `nicebot` CLI
