"""Translations. Put ``locales/uz.json``, ``locales/ru.json``… next to your bot and call ``ctx.t("key")``.

Example::

    # locales/en.json → {"hello": "Hello, {name}!"}
    # locales/uz.json → {"hello": "Salom, {name}!"}
    await ctx.reply(ctx.t("hello", name=ctx.name))
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("nicebot.i18n")

# Texts the library itself shows. Override any of them in your own locale files.
BUILTIN: dict[str, dict[str, str]] = {
    "uz": {
        "nb.yes": "✅ Ha",
        "nb.no": "❌ Yo'q",
        "nb.done": "✔️ Tayyor",
        "nb.cancel": "🚫 Bekor qilish",
        "nb.cancelled": "Bekor qilindi.",
        "nb.back": "⬅️ Orqaga",
        "nb.prev": "◀️",
        "nb.next": "▶️",
        "nb.timeout": "⌛️ Javob kutish vaqti tugadi.",
        "nb.invalid": "❗️ Noto'g'ri qiymat, qaytadan kiriting.",
        "nb.too_many_tries": "Juda ko'p urinish. Keyinroq qayta boshlang.",
        "nb.expired": "⌛️ Bu tugmaning muddati tugagan.",
        "nb.not_yours": "🙅 Bu tugma siz uchun emas.",
        "nb.used": "Bu tugma allaqachon ishlatilgan.",
        "nb.throttled": "⏳ Biroz kuting...",
        "nb.maintenance": "🛠 Botda texnik ishlar olib borilmoqda. Birozdan so'ng qaytib keling.",
        "nb.subscribe": "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
        "nb.check": "✅ Tekshirish",
        "nb.not_subscribed": "❗️ Hali hamma kanallarga obuna bo'lmadingiz.",
        "nb.error": "😔 Xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.",
        "nb.send_phone": "📞 Raqamni yuborish",
        "nb.send_location": "📍 Joylashuvni yuborish",
        "nb.choose_hint": "Variantlarni tanlang va «Tayyor» tugmasini bosing.",
        "nb.page": "Sahifa {page}/{pages}",
        "nb.empty": "Hech narsa topilmadi.",
        "nb.captcha": "{mention}, guruhga xush kelibsiz! Robot emasligingizni tasdiqlang ({seconds} soniya).",
        "nb.captcha_button": "🤖 Men robot emasman",
        "nb.captcha_ok": "✅ Rahmat, endi yozishingiz mumkin.",
        "nb.warned": "⚠️ {mention} ogohlantirildi ({count}/{limit}). {reason}",
        "nb.banned_after_warns": "⛔️ {mention} {limit} ta ogohlantirishdan so'ng chetlatildi.",
        "nb.support_sent": "✅ Xabaringiz yuborildi. Tez orada javob beramiz.",
        "nb.v.int": "Butun son kiriting.",
        "nb.v.float": "Son kiriting (masalan, 12.5).",
        "nb.v.min": "Qiymat {min} dan kichik bo'lmasin.",
        "nb.v.max": "Qiymat {max} dan katta bo'lmasin.",
        "nb.v.len_min": "Kamida {min} ta belgi kiriting.",
        "nb.v.len_max": "Ko'pi bilan {max} ta belgi kiriting.",
        "nb.v.phone": "Telefon raqamini to'g'ri kiriting: +998 90 123 45 67",
        "nb.v.email": "Email manzilni to'g'ri kiriting: ism@misol.uz",
        "nb.v.date": "Sanani {format} ko'rinishida kiriting.",
        "nb.v.url": "To'g'ri havola kiriting (https://...).",
        "nb.v.choice": "Quyidagilardan birini tanlang: {choices}",
        "nb.v.photo": "Iltimos, rasm yuboring.",
        "nb.v.text": "Iltimos, matn yuboring.",
        "nb.v.regex": "Format noto'g'ri.",
        "nb.v.location": "Iltimos, joylashuvni yuboring.",
        "nb.v.file": "Iltimos, fayl yuboring.",
        "nb.v.video": "Iltimos, video yuboring.",
        "nb.v.document": "Iltimos, fayl (hujjat) yuboring.",
        "nb.v.audio": "Iltimos, audio yuboring.",
        "nb.v.voice": "Iltimos, ovozli xabar yuboring.",
        "nb.v.media": "Iltimos, rasm, video yoki fayl yuboring.",
        "nb.v.too_big": "Fayl juda katta (ko'pi bilan {max}).",
        "nb.v.mime": "Bu turdagi fayl qabul qilinmaydi.",
        "nb.admin.error_title": "Xatolik",
        "nb.admin.user": "Foydalanuvchi",
        "nb.admin.text": "Matn",
        "nb.admin.stats_title": "📊 <b>Statistika</b>",
        "nb.admin.stats_total": "👥 Jami: <b>{users}</b>",
        "nb.admin.stats_new": "🆕 Bugun: <b>{today}</b> · 7 kunda: <b>{week}</b>",
        "nb.admin.stats_active": "🔥 DAU: <b>{dau}</b> · WAU: <b>{wau}</b> · MAU: <b>{mau}</b>",
        "nb.admin.stats_blocked": "⛔️ Bloklagan: <b>{blocked}</b> · ⭐️ Premium: <b>{premium}</b>",
        "nb.admin.stats_referred": "🔗 Referal orqali: <b>{referred}</b>",
        "nb.admin.stats_retention": "📈 7 kunlik retention: <b>{retention}%</b>",
        "nb.admin.stats_top": "<b>Top buyruqlar (30 kun):</b>",
        "nb.admin.maintenance_on": "🛠 Texnik ishlar rejimi: <b>YOQILDI</b>",
        "nb.admin.maintenance_off": "✅ Texnik ishlar rejimi: <b>O'CHIRILDI</b>",
        "nb.admin.backup_unsupported": "💾 /backup faqat fayldagi SQLite uchun. PostgreSQL/MySQL/MongoDB uchun pg_dump / mysqldump / mongodump ishlating.",
        "nb.admin.backup_caption": "💾 Baza nusxasi",
        "nb.admin.broadcast_usage": "📣 Foydalanish: xabarga reply qilib <code>/broadcast</code> yozing yoki <code>/broadcast matn</code>.",
        "nb.admin.broadcast_confirm": "📣 {count} ta foydalanuvchiga yuborilsinmi?",
        "nb.admin.broadcast_sending": "⏳ Yuborilmoqda...",
        "nb.admin.broadcast_done": "✅ Tayyor!\nYuborildi: <b>{sent}</b>\nBloklagan: <b>{blocked}</b>\nXato: <b>{failed}</b>",
        "nb.admin.user_blocked": "⛔️ Foydalanuvchi botni bloklagan.",
        "nb.admin.channel": "📢 Kanal {n}",
        "nb.cmd.stats": "📊 Statistika",
        "nb.cmd.broadcast": "📣 Hammaga xabar",
        "nb.cmd.maintenance": "🛠 Texnik ishlar rejimi",
        "nb.cmd.backup": "💾 Bazaning nusxasi",
        "nb.date.d": "KK",
        "nb.date.m": "OO",
        "nb.date.y": "YYYY",
    },
    "ru": {
        "nb.yes": "✅ Да",
        "nb.no": "❌ Нет",
        "nb.done": "✔️ Готово",
        "nb.cancel": "🚫 Отмена",
        "nb.cancelled": "Отменено.",
        "nb.back": "⬅️ Назад",
        "nb.prev": "◀️",
        "nb.next": "▶️",
        "nb.timeout": "⌛️ Время ожидания ответа истекло.",
        "nb.invalid": "❗️ Неверное значение, попробуйте ещё раз.",
        "nb.too_many_tries": "Слишком много попыток. Начните заново позже.",
        "nb.expired": "⌛️ Срок действия кнопки истёк.",
        "nb.not_yours": "🙅 Эта кнопка не для вас.",
        "nb.used": "Эта кнопка уже использована.",
        "nb.throttled": "⏳ Подождите немного...",
        "nb.maintenance": "🛠 В боте ведутся технические работы. Загляните чуть позже.",
        "nb.subscribe": "Чтобы пользоваться ботом, подпишитесь на каналы:",
        "nb.check": "✅ Проверить",
        "nb.not_subscribed": "❗️ Вы ещё не подписались на все каналы.",
        "nb.error": "😔 Произошла ошибка. Попробуйте чуть позже.",
        "nb.send_phone": "📞 Отправить номер",
        "nb.send_location": "📍 Отправить геолокацию",
        "nb.choose_hint": "Выберите варианты и нажмите «Готово».",
        "nb.page": "Страница {page}/{pages}",
        "nb.empty": "Ничего не найдено.",
        "nb.captcha": "{mention}, добро пожаловать! Подтвердите, что вы не робот ({seconds} сек).",
        "nb.captcha_button": "🤖 Я не робот",
        "nb.captcha_ok": "✅ Спасибо, теперь вы можете писать.",
        "nb.warned": "⚠️ {mention} получил предупреждение ({count}/{limit}). {reason}",
        "nb.banned_after_warns": "⛔️ {mention} исключён после {limit} предупреждений.",
        "nb.support_sent": "✅ Сообщение отправлено. Скоро ответим.",
        "nb.v.int": "Введите целое число.",
        "nb.v.float": "Введите число (например, 12.5).",
        "nb.v.min": "Значение должно быть не меньше {min}.",
        "nb.v.max": "Значение должно быть не больше {max}.",
        "nb.v.len_min": "Введите не менее {min} символов.",
        "nb.v.len_max": "Введите не более {max} символов.",
        "nb.v.phone": "Введите номер правильно: +998 90 123 45 67",
        "nb.v.email": "Введите корректный email: name@example.com",
        "nb.v.date": "Введите дату в формате {format}.",
        "nb.v.url": "Введите корректную ссылку (https://...).",
        "nb.v.choice": "Выберите один из вариантов: {choices}",
        "nb.v.photo": "Пожалуйста, отправьте фото.",
        "nb.v.text": "Пожалуйста, отправьте текст.",
        "nb.v.regex": "Неверный формат.",
        "nb.v.location": "Пожалуйста, отправьте геолокацию.",
        "nb.v.file": "Пожалуйста, отправьте файл.",
        "nb.v.video": "Пожалуйста, отправьте видео.",
        "nb.v.document": "Пожалуйста, отправьте файл (документ).",
        "nb.v.audio": "Пожалуйста, отправьте аудио.",
        "nb.v.voice": "Пожалуйста, отправьте голосовое сообщение.",
        "nb.v.media": "Пожалуйста, отправьте фото, видео или файл.",
        "nb.v.too_big": "Файл слишком большой (максимум {max}).",
        "nb.v.mime": "Файлы такого типа не принимаются.",
        "nb.admin.error_title": "Ошибка",
        "nb.admin.user": "Пользователь",
        "nb.admin.text": "Текст",
        "nb.admin.stats_title": "📊 <b>Статистика</b>",
        "nb.admin.stats_total": "👥 Всего: <b>{users}</b>",
        "nb.admin.stats_new": "🆕 Сегодня: <b>{today}</b> · за 7 дней: <b>{week}</b>",
        "nb.admin.stats_active": "🔥 DAU: <b>{dau}</b> · WAU: <b>{wau}</b> · MAU: <b>{mau}</b>",
        "nb.admin.stats_blocked": "⛔️ Заблокировали: <b>{blocked}</b> · ⭐️ Premium: <b>{premium}</b>",
        "nb.admin.stats_referred": "🔗 По рефералке: <b>{referred}</b>",
        "nb.admin.stats_retention": "📈 Удержание за 7 дней: <b>{retention}%</b>",
        "nb.admin.stats_top": "<b>Топ команд (30 дней):</b>",
        "nb.admin.maintenance_on": "🛠 Режим техработ: <b>ВКЛЮЧЁН</b>",
        "nb.admin.maintenance_off": "✅ Режим техработ: <b>ВЫКЛЮЧЕН</b>",
        "nb.admin.backup_unsupported": "💾 /backup работает только с SQLite в файле. Для PostgreSQL/MySQL/MongoDB используйте pg_dump / mysqldump / mongodump.",
        "nb.admin.backup_caption": "💾 Копия базы",
        "nb.admin.broadcast_usage": "📣 Использование: ответьте на сообщение командой <code>/broadcast</code> или напишите <code>/broadcast текст</code>.",
        "nb.admin.broadcast_confirm": "📣 Отправить {count} пользователям?",
        "nb.admin.broadcast_sending": "⏳ Отправляю...",
        "nb.admin.broadcast_done": "✅ Готово!\nОтправлено: <b>{sent}</b>\nЗаблокировали: <b>{blocked}</b>\nОшибки: <b>{failed}</b>",
        "nb.admin.user_blocked": "⛔️ Пользователь заблокировал бота.",
        "nb.admin.channel": "📢 Канал {n}",
        "nb.cmd.stats": "📊 Статистика",
        "nb.cmd.broadcast": "📣 Рассылка",
        "nb.cmd.maintenance": "🛠 Режим техработ",
        "nb.cmd.backup": "💾 Копия базы",
        "nb.date.d": "ДД",
        "nb.date.m": "ММ",
        "nb.date.y": "ГГГГ",
    },
    "en": {
        "nb.yes": "✅ Yes",
        "nb.no": "❌ No",
        "nb.done": "✔️ Done",
        "nb.cancel": "🚫 Cancel",
        "nb.cancelled": "Cancelled.",
        "nb.back": "⬅️ Back",
        "nb.prev": "◀️",
        "nb.next": "▶️",
        "nb.timeout": "⌛️ Time is up.",
        "nb.invalid": "❗️ Invalid value, please try again.",
        "nb.too_many_tries": "Too many attempts. Please start over later.",
        "nb.expired": "⌛️ This button has expired.",
        "nb.not_yours": "🙅 This button is not for you.",
        "nb.used": "This button was already used.",
        "nb.throttled": "⏳ Please wait a moment...",
        "nb.maintenance": "🛠 The bot is under maintenance. Please come back soon.",
        "nb.subscribe": "To use the bot, please subscribe to these channels:",
        "nb.check": "✅ Check",
        "nb.not_subscribed": "❗️ You haven't joined all channels yet.",
        "nb.error": "😔 Something went wrong. Please try again later.",
        "nb.send_phone": "📞 Share phone number",
        "nb.send_location": "📍 Share location",
        "nb.choose_hint": "Pick the options and press “Done”.",
        "nb.page": "Page {page}/{pages}",
        "nb.empty": "Nothing found.",
        "nb.captcha": "{mention}, welcome! Please confirm you are human ({seconds} seconds).",
        "nb.captcha_button": "🤖 I'm not a robot",
        "nb.captcha_ok": "✅ Thanks, you can chat now.",
        "nb.warned": "⚠️ {mention} was warned ({count}/{limit}). {reason}",
        "nb.banned_after_warns": "⛔️ {mention} was removed after {limit} warnings.",
        "nb.support_sent": "✅ Message sent. We'll reply soon.",
        "nb.v.int": "Please enter a whole number.",
        "nb.v.float": "Please enter a number (e.g. 12.5).",
        "nb.v.min": "The value must be at least {min}.",
        "nb.v.max": "The value must be at most {max}.",
        "nb.v.len_min": "Enter at least {min} characters.",
        "nb.v.len_max": "Enter at most {max} characters.",
        "nb.v.phone": "Please enter a valid phone: +998 90 123 45 67",
        "nb.v.email": "Please enter a valid email: name@example.com",
        "nb.v.date": "Please enter the date as {format}.",
        "nb.v.url": "Please enter a valid link (https://...).",
        "nb.v.choice": "Please choose one of: {choices}",
        "nb.v.photo": "Please send a photo.",
        "nb.v.text": "Please send text.",
        "nb.v.regex": "Wrong format.",
        "nb.v.location": "Please send a location.",
        "nb.v.file": "Please send a file.",
        "nb.v.video": "Please send a video.",
        "nb.v.document": "Please send a file (document).",
        "nb.v.audio": "Please send an audio file.",
        "nb.v.voice": "Please send a voice message.",
        "nb.v.media": "Please send a photo, video or file.",
        "nb.v.too_big": "The file is too big (max {max}).",
        "nb.v.mime": "This file type is not accepted.",
        "nb.admin.error_title": "Error",
        "nb.admin.user": "User",
        "nb.admin.text": "Text",
        "nb.admin.stats_title": "📊 <b>Statistics</b>",
        "nb.admin.stats_total": "👥 Total: <b>{users}</b>",
        "nb.admin.stats_new": "🆕 Today: <b>{today}</b> · last 7 days: <b>{week}</b>",
        "nb.admin.stats_active": "🔥 DAU: <b>{dau}</b> · WAU: <b>{wau}</b> · MAU: <b>{mau}</b>",
        "nb.admin.stats_blocked": "⛔️ Blocked the bot: <b>{blocked}</b> · ⭐️ Premium: <b>{premium}</b>",
        "nb.admin.stats_referred": "🔗 Came via referral: <b>{referred}</b>",
        "nb.admin.stats_retention": "📈 7-day retention: <b>{retention}%</b>",
        "nb.admin.stats_top": "<b>Top commands (30 days):</b>",
        "nb.admin.maintenance_on": "🛠 Maintenance mode: <b>ON</b>",
        "nb.admin.maintenance_off": "✅ Maintenance mode: <b>OFF</b>",
        "nb.admin.backup_unsupported": "💾 /backup works only with a file-based SQLite database. Use pg_dump / mysqldump / mongodump for PostgreSQL/MySQL/MongoDB.",
        "nb.admin.backup_caption": "💾 Database backup",
        "nb.admin.broadcast_usage": "📣 Usage: reply to a message with <code>/broadcast</code> or send <code>/broadcast text</code>.",
        "nb.admin.broadcast_confirm": "📣 Send to {count} users?",
        "nb.admin.broadcast_sending": "⏳ Sending...",
        "nb.admin.broadcast_done": "✅ Done!\nSent: <b>{sent}</b>\nBlocked: <b>{blocked}</b>\nErrors: <b>{failed}</b>",
        "nb.admin.user_blocked": "⛔️ The user has blocked the bot.",
        "nb.admin.channel": "📢 Channel {n}",
        "nb.cmd.stats": "📊 Statistics",
        "nb.cmd.broadcast": "📣 Message everyone",
        "nb.cmd.maintenance": "🛠 Maintenance mode",
        "nb.cmd.backup": "💾 Database backup",
        "nb.date.d": "DD",
        "nb.date.m": "MM",
        "nb.date.y": "YYYY",
    },
}


class I18n:
    """Loads ``<folder>/<lang>.json`` (or ``.toml``) files. Missing keys fall back to the default language, then to the key itself."""

    def __init__(self, folder: str | Path | None = "locales", default: str = "uz", languages: tuple[str, ...] | None = None):
        self.default = default
        self.texts: dict[str, dict[str, str]] = {k: dict(v) for k, v in BUILTIN.items()}
        self.folder = Path(folder) if folder else None
        if self.folder and self.folder.is_dir():
            self.load(self.folder)
        self.languages = languages or tuple(sorted(self.texts))

    def load(self, folder: str | Path) -> None:
        for path in sorted(Path(folder).iterdir()):
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".toml":
                import tomllib

                data = tomllib.loads(path.read_text(encoding="utf-8"))
            else:
                continue
            self.add(path.stem, data)
        log.debug("Tarjimalar yuklandi: %s", sorted(self.texts))

    def add(self, lang: str, data: dict[str, Any], prefix: str = "") -> None:
        bucket = self.texts.setdefault(lang, {})
        for k, v in data.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict):
                self.add(lang, v, key + ".")
            else:
                bucket[key] = str(v)

    def resolve(self, code: str | None) -> str:
        """Map a Telegram ``language_code`` (``"ru-RU"``) to a loaded language."""
        if not code:
            return self.default
        code = code.lower().split("-")[0]
        if code in self.texts:
            return code
        return self.default

    def t(self, key: str, lang: str | None = None, /, **kwargs: Any) -> str:
        lang = lang or self.default
        text = self.texts.get(lang, {}).get(key)
        if text is None:
            text = self.texts.get(self.default, {}).get(key)
        if text is None:
            text = self.texts.get("en", {}).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text
